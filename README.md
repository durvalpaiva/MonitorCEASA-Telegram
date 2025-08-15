# MonitorCEASA-Telegram

Automação para monitoramento diário dos boletins de preços da CEASA, com envio automático de resumo para o Telegram.

## Funcionalidades
- Baixa o PDF de cotações do site da CEASA.
- Extrai e normaliza os dados dos produtos.
- Filtra e envia os preços para o Telegram via bot.
- Executa automaticamente todos os dias via GitHub Actions.

## Como usar
1. Configure o arquivo `.env` com seu `TELEGRAM_TOKEN` e `TELEGRAM_CHAT_ID`.
2. Execute localmente com `python main.py` para visualizar os dados.
3. O envio automático é feito pelo workflow do GitHub Actions (`cotacao.py`).

## Requisitos
- Python 3.12+
- streamlit, pdfplumber, pandas, requests, beautifulsoup4, python-telegram-bot

## Licença
MIT
