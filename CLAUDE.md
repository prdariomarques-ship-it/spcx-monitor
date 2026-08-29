# spcx-monitor

Monitor de preço dos ativos da SpaceX com alerta via Telegram.

## O que faz

- Acompanha **SPCX34.SA** (BDR na B3) e **SPCX** (ação na Nasdaq) via yfinance.
- Dispara alerta no Telegram quando o preço rompe uma banda configurável.
- Poll a cada 60s (APScheduler), com cooldown de 20min por tipo de alerta para não floodar.
- Ao iniciar, envia confirmação "✅ Monitor SPCX iniciado" no Telegram.

## Bandas atuais

| Ativo | Condição de alerta |
|-------|--------------------|
| SPCX34.SA | preço > R$ 57,74 (máx. da estreia) ou < R$ 54,50 (mín. da estreia) |
| SPCX | preço > fechamento anterior ×1,05 ou < ×0,95 |

> Nota: na estreia (12/06/2026), a referência do SPCX era o preço de IPO (US$ 135), o que deixava o "+5%" sempre disparado. Com fechamentos reais no histórico isso se normaliza. Revisar as bandas para níveis-alvo de preço quando fizer sentido.

## Configuração do ambiente

```bash
# 1. Clone o repositório
git clone https://github.com/prdariomarques-ship-it/spcx-monitor ~/spcx-monitor
cd ~/spcx-monitor

# 2. Instale as dependências
pip install -r requirements.txt

# 3. Crie o .env com as credenciais (nunca versionar)
cp .env.example .env
nano .env  # preencha TELEGRAM_TOKEN e TELEGRAM_CHAT_ID

# 4. Crie a pasta de logs
mkdir -p logs
```

## Variáveis de ambiente (`.env`)

| Variável | Descrição |
|----------|-----------|
| `TELEGRAM_TOKEN` | Token do BotFather (formato: `123456789:ABC-DEF...`) |
| `TELEGRAM_CHAT_ID` | Seu chat ID numérico (obtenha via @userinfobot) |

O `.env` está no `.gitignore` e **nunca deve ser versionado**.

## Execução

```bash
# Iniciar em background (Termux)
cd ~/spcx-monitor
nohup python monitor_spcx.py >> logs/termux.out 2>&1 &

# Ver logs
tail -f ~/spcx-monitor/logs/termux.out

# Parar
pkill -f monitor_spcx.py
```

## Auto-start no Termux (Android)

1. Instale o app **Termux:Boot** da Play Store / F-Droid.
2. Copie o script de boot:
   ```bash
   mkdir -p ~/.termux/boot
   cp ~/spcx-monitor/termux/boot.sh ~/.termux/boot/start-spcx-monitor.sh
   chmod +x ~/.termux/boot/start-spcx-monitor.sh
   ```
3. Reinicie o celular — o monitor sobe automaticamente.

## Testar credenciais Telegram

```bash
source ~/spcx-monitor/.env
# Verificar token
curl -s "https://api.telegram.org/bot${TELEGRAM_TOKEN}/getMe" | python3 -m json.tool
# Enviar mensagem de teste
curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendMessage" \
  -d "chat_id=${TELEGRAM_CHAT_ID}&text=teste+monitor+spcx" | python3 -m json.tool
```

## Dependências

`yfinance`, `apscheduler`, `requests`, `python-dotenv`, `tzdata`.

## Gotchas

- `B3` só negocia o BDR em pregão (seg–sex, ~10h–18h BRT); fora disso o SPCX34 não dispara alertas.
- `NYSE` só opera seg–sex 9h30–16h ET; fora disso SPCX não dispara alertas.
- yfinance pode retornar `Series` em vez de escalar — normalizado via `_scalar()`.
- O cooldown (20min) só conta quando o Telegram aceita a mensagem — sem token configurado, alertas vão só para o log e cooldown não é marcado.
