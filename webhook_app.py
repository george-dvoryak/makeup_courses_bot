# webhook_app.py
from flask import Flask, request, abort
import telebot

from config import TELEGRAM_BOT_TOKEN, WEBHOOK_URL, WEBHOOK_PATH, WEBHOOK_SECRET_TOKEN
from main import bot  # handlers are already registered on import

app = Flask(__name__)

# Reset and set webhook
if WEBHOOK_URL:
    try:
        bot.remove_webhook()
        bot.set_webhook(
            url=WEBHOOK_URL,
            secret_token=WEBHOOK_SECRET_TOKEN,
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query", "shipping_query", "pre_checkout_query"]
        )
        print(f"Webhook set to: {WEBHOOK_URL}")
    except Exception as e:
        print("Webhook setup error:", e)

# Webhook endpoint - use WEBHOOK_PATH if available, otherwise fallback to token-based path
if WEBHOOK_PATH:
    @app.route(WEBHOOK_PATH, methods=['POST'])
    def telegram_webhook():
        # Validate Telegram secret header if configured
        secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if WEBHOOK_SECRET_TOKEN and secret != WEBHOOK_SECRET_TOKEN:
            abort(403)
        try:
            json_str = request.get_data().decode('utf-8')
            update = telebot.types.Update.de_json(json_str)
            bot.process_new_updates([update])
        except Exception as e:
            print("Webhook handling error:", e)
        return "OK", 200
else:
    # Fallback to old token-based path for backward compatibility
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
