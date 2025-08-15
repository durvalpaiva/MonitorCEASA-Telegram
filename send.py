def send_telegram_message(token, chat_id, message):
    url = f'https://api.telegram.org/bot{token}/sendMessage'
    payload = {
        'chat_id': chat_id,
        'text': message
    }
    response = requests.post(url, data=payload)
    return response.json()
import requests
from dotenv import load_dotenv
import os

load_dotenv()

def send_telegram_message(token, chat_id, message):
    url = f'https://api.telegram.org/bot{token}/sendMessage'
    payload = {
        'chat_id': chat_id,
        'text': message
    }
    response = requests.post(url, data=payload)
    return response.json()

if __name__ == '__main__':
    token = os.getenv('TELEGRAM_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    message = 'Teste de envio via bot MonitorRSTBot!'
    if not token or not chat_id:
        print('Configure TELEGRAM_TOKEN e TELEGRAM_CHAT_ID no arquivo .env')
    else:
        result = send_telegram_message(token, chat_id, message)
        print(result)
