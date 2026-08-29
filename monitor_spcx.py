import os
import logging
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
import yfinance as yf
from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import load_dotenv

from log_setup import setup_logging

# Use o diretório do programa, não o diretório em que o systemd iniciou o
# processo. Sem isso, um restart pode deixar o bot sem credenciais mesmo com o
# .env correto ao lado do código.
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(dotenv_path=BASE_DIR / ".env")

# ---------------------------------------------------------------------------
# Configuração — defina as variáveis no arquivo .env
# ---------------------------------------------------------------------------
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

SPCX34_UPPER = 57.74
SPCX34_LOWER = 54.50
SPCX_BAND_PCT = 0.05   # ±5%

POLL_INTERVAL_SECONDS = 60
COOLDOWN_MINUTES = 20

B3_TZ = ZoneInfo("America/Sao_Paulo")
NYSE_TZ = ZoneInfo("America/New_York")

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
_last_alert: dict[str, datetime] = {}   # ticker -> last alert timestamp
_spcx_ref_price: float | None = None    # previous close used as SPCX reference

setup_logging(level=logging.INFO)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------
def send_telegram(message: str) -> bool:
    """Envia uma mensagem e informa se o Telegram a aceitou."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        log.warning("Telegram not configured — would have sent: %s", message)
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        resp = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message}, timeout=10)
        resp.raise_for_status()
        payload = resp.json()
        if not payload.get("ok", False):
            log.error("Telegram rejected the message: %s", payload.get("description", "unknown error"))
            return False
        log.info("Telegram alert sent.")
        return True
    except requests.RequestException as exc:
        # O texto de HTTPError pode incluir a URL — e, portanto, o token do bot.
        log.error("Failed to send Telegram alert (%s).", type(exc).__name__)
        return False
    except ValueError:
        log.error("Telegram returned an invalid JSON response.")
        return False


def _b3_pregao_aberto() -> bool:
    """SPCX34.SA (BDR) só negocia em pregão B3 — seg-sex 10h-18h BRT.
    Fora disso o preço fica parado no fechamento anterior; sem esse filtro
    o monitor re-alertava o mesmo preço estático a cada cooldown, à noite
    inteira (bug real observado em produção)."""
    now = datetime.now(B3_TZ)
    return now.weekday() < 5 and 10 <= now.hour < 18


def _nyse_pregao_aberto() -> bool:
    """SPCX (ação EUA) só negocia em pregão NYSE — seg-sex ~9h30-16h horário de NY."""
    now = datetime.now(NYSE_TZ)
    if now.weekday() >= 5:
        return False
    minutes = now.hour * 60 + now.minute
    return 9 * 60 + 30 <= minutes < 16 * 60


def _in_cooldown(ticker: str) -> bool:
    last = _last_alert.get(ticker)
    if last is None:
        return False
    return datetime.now() - last < timedelta(minutes=COOLDOWN_MINUTES)


def _mark_alert(ticker: str) -> None:
    _last_alert[ticker] = datetime.now()


# ---------------------------------------------------------------------------
# Fetchers
# ---------------------------------------------------------------------------
def _scalar(value) -> float:
    """Coerce yfinance cell (may be Series in newer versions) to float."""
    import numpy as np
    if hasattr(value, "item"):       # numpy scalar or 1-element array
        return float(value.item())
    if hasattr(value, "iloc"):       # pandas Series
        return float(value.iloc[0])
    return float(value)


def fetch_price(ticker: str) -> float | None:
    try:
        data = yf.download(ticker, period="1d", interval="1m", progress=False,
                           auto_adjust=True, multi_level_index=False)
        if data.empty:
            log.warning("%s: no data returned.", ticker)
            return None
        price = _scalar(data["Close"].iloc[-1])
        log.info("%s: last price = %.4f", ticker, price)
        return price
    except Exception as exc:
        log.error("%s: error fetching price — %s", ticker, exc)
        return None


def fetch_prev_close(ticker: str) -> float | None:
    try:
        data = yf.download(ticker, period="5d", interval="1d", progress=False,
                           auto_adjust=True, multi_level_index=False)
        if len(data) < 2:
            return None
        # second-to-last row is the most recent completed session
        price = _scalar(data["Close"].iloc[-2])
        log.info("%s: previous close = %.4f", ticker, price)
        return price
    except Exception as exc:
        log.error("%s: error fetching previous close — %s", ticker, exc)
        return None


# ---------------------------------------------------------------------------
# Check logic
# ---------------------------------------------------------------------------
def check_spcx34() -> None:
    if not _b3_pregao_aberto():
        return
    ticker = "SPCX34.SA"
    price = fetch_price(ticker)
    if price is None:
        return

    breached = False
    if price > SPCX34_UPPER:
        direction = f"acima da banda superior ({SPCX34_UPPER})"
        breached = True
    elif price < SPCX34_LOWER:
        direction = f"abaixo da banda inferior ({SPCX34_LOWER})"
        breached = True

    if breached and not _in_cooldown(ticker):
        msg = (
            f"🚨 ALERTA SPCX34.SA\n"
            f"Preço: R$ {price:.2f} — {direction}\n"
            f"Hora: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
        )
        log.info("ALERT: %s", msg)
        if send_telegram(msg):
            _mark_alert(ticker)


def check_spcx() -> None:
    if not _nyse_pregao_aberto():
        return
    global _spcx_ref_price
    ticker = "SPCX"

    # Lazy-load the reference price (previous close)
    if _spcx_ref_price is None:
        _spcx_ref_price = fetch_prev_close(ticker)
        if _spcx_ref_price is None:
            log.warning("SPCX: could not load reference price, skipping check.")
            return

    price = fetch_price(ticker)
    if price is None:
        return

    ref = _spcx_ref_price
    upper = ref * (1 + SPCX_BAND_PCT)
    lower = ref * (1 - SPCX_BAND_PCT)

    breached = False
    if price > upper:
        direction = f"acima de +5% (ref {ref:.4f}, limite {upper:.4f})"
        breached = True
    elif price < lower:
        direction = f"abaixo de -5% (ref {ref:.4f}, limite {lower:.4f})"
        breached = True

    if breached and not _in_cooldown(ticker):
        msg = (
            f"🚨 ALERTA SPCX\n"
            f"Preço: ${price:.4f} — {direction}\n"
            f"Hora: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
        )
        log.info("ALERT: %s", msg)
        if send_telegram(msg):
            _mark_alert(ticker)


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------
def poll() -> None:
    log.info("--- poll ---")
    check_spcx34()
    check_spcx()


def main() -> None:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        log.warning(
            "TELEGRAM_TOKEN or TELEGRAM_CHAT_ID not set — alerts will only be logged."
        )
    else:
        send_telegram(
            "✅ Monitor SPCX iniciado. Alertas serão enviados durante o pregão."
        )

    scheduler = BlockingScheduler()
    scheduler.add_job(poll, "interval", seconds=POLL_INTERVAL_SECONDS, next_run_time=datetime.now())
    log.info(
        "Monitor iniciado. Polling a cada %ds. Cooldown: %dmin.",
        POLL_INTERVAL_SECONDS,
        COOLDOWN_MINUTES,
    )
    try:
        scheduler.start()
    except KeyboardInterrupt:
        log.info("Monitor encerrado.")


if __name__ == "__main__":
    main()
