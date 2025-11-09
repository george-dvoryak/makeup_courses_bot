# webhook_app.py
from flask import Flask, request
import telebot

from config import TELEGRAM_BOT_TOKEN, WEBHOOK_URL
from main import bot  # handlers are already registered on import

app = Flask(__name__)

# Reset and set webhook
try:
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    print(f"Webhook set to: {WEBHOOK_URL}")
except Exception as e:
    print("Webhook setup error:", e)

@app.route(f'/{TELEGRAM_BOT_TOKEN}', methods=['POST'])
def telegram_webhook():
    try:
        json_str = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_str)
        bot.process_new_updates([update])
    except Exception as e:
        print("Webhook handling error:", e)
    return "OK", 200

# For PythonAnywhere WSGI:
# In your WSGI file, import: from webhook_app import app as application
