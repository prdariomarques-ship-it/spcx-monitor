# spcx-monitor

Monitor de preço dos ativos da SpaceX com alerta via Telegram.

## O que faz

- Acompanha **SPCX34.SA** (BDR na B3) e **SPCX** (ação na Nasdaq) via yfinance.
- Dispara alerta no Telegram quando o preço rompe uma banda configurável.
- Poll a cada 60s (APScheduler), com cooldown de 20min por tipo de alerta para não floodar.

## Bandas atuais

| Ativo | Condição de alerta |
|-------|--------------------|
| SPCX34.SA | preço > R$ 57,74 (máx. da estreia) ou < R$ 54,50 (mín. da estreia) |
| SPCX | preço > fechamento anterior ×1,05 ou < ×0,95 |

> Nota: na estreia (12/06/2026), a referência do SPCX era o preço de IPO (US$ 135), o que deixava o "+5%" sempre disparado. Com fechamentos reais no histórico isso se normaliza. Revisar as bandas para níveis-alvo de preço quando fizer sentido.

## Execução

- Credenciais via `.env` (NÃO usar `export` com token na linha de comando):
  - `TELEGRAM_TOKEN` — token do BotFather
  - `TELEGRAM_CHAT_ID` — `883232211`
- `.env` está no `.gitignore` e nunca deve ser versionado.
- Sem token configurado, os alertas vão só para o log (não quebra) — útil para teste.
- Em produção: rodar como **systemd user service** com restart automático.

## Dependências

`yfinance`, `apscheduler`, `requests`, `python-dotenv`.

## Gotchas

- `B3` só negocia o BDR em pregão (seg–sex, ~10h–18h BRT); fora disso o SPCX34 pode vir sem cotação — comportamento esperado, não é erro.
- yfinance pode retornar `Series` em vez de escalar — normalizar para `float` antes de comparar.
