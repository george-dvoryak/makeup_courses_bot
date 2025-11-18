#!/usr/bin/env python3
"""
Установка webhook в Telegram
"""
import sys
import time
sys.path.insert(0, '/home/goshadvoryak/makeup_courses_bot')
sys.path.insert(0, '/home/goshadvoryak/makeup_courses_bot/venv/lib/python3.10/site-packages')

from config import TELEGRAM_BOT_TOKEN, WEBHOOK_URL, WEBHOOK_SECRET_TOKEN
import telebot

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

print("=" * 60)
print("УСТАНОВКА WEBHOOK")
print("=" * 60)
print()

print(f"Webhook URL: {WEBHOOK_URL}")
print(f"Secret Token: {'***SET***' if WEBHOOK_SECRET_TOKEN else 'NOT SET'}")
print()

try:
    # Сначала удалим старый webhook
    print("1. Удаление старого webhook...")
    result = bot.delete_webhook()
    print(f"   Результат: {result}")
    print()
    
    # Подождём немного
    print("2. Ожидание 2 секунды...")
    time.sleep(2)
    print()
    
    # Установим новый webhook
    print("3. Установка нового webhook...")
    result = bot.set_webhook(
        url=WEBHOOK_URL,
        secret_token=WEBHOOK_SECRET_TOKEN if WEBHOOK_SECRET_TOKEN else None,
        drop_pending_updates=True,
        allowed_updates=["message", "callback_query", "shipping_query", "pre_checkout_query"]
    )
    print(f"   Результат: {result}")
    print()
    
    # Проверим статус
    print("4. Проверка статуса webhook...")
    webhook_info = bot.get_webhook_info()
    print(f"   Webhook URL: {webhook_info.url or 'НЕ УСТАНОВЛЕН'}")
    print(f"   Pending updates: {webhook_info.pending_update_count}")
    
    if webhook_info.url == WEBHOOK_URL:
        print()
        print("=" * 60)
        print("✅ WEBHOOK УСПЕШНО УСТАНОВЛЕН!")
        print("=" * 60)
    else:
        print()
        print("=" * 60)
        print("❌ ОШИБКА: Webhook не установлен!")
        print("=" * 60)
        if webhook_info.last_error_message:
            print(f"Ошибка: {webhook_info.last_error_message}")
        
except Exception as e:
    print(f"❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()

