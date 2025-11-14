#!/usr/bin/env python3
"""
Проверка статуса webhook в Telegram
"""
import sys
sys.path.insert(0, '/home/goshadvoryak/makeup_courses_bot')
sys.path.insert(0, '/home/goshadvoryak/makeup_courses_bot/venv/lib/python3.10/site-packages')

from config import TELEGRAM_BOT_TOKEN
import telebot

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

print("=" * 60)
print("ПРОВЕРКА WEBHOOK СТАТУСА")
print("=" * 60)
print()

try:
    webhook_info = bot.get_webhook_info()
    print(f"Webhook URL: {webhook_info.url or 'НЕ УСТАНОВЛЕН'}")
    print(f"Pending updates: {webhook_info.pending_update_count}")
    print(f"Last error date: {webhook_info.last_error_date or 'Нет ошибок'}")
    print(f"Last error message: {webhook_info.last_error_message or 'Нет ошибок'}")
    print(f"Max connections: {webhook_info.max_connections or 'Не указано'}")
    print()
    
    if webhook_info.url:
        print("✅ Webhook установлен")
        if webhook_info.pending_update_count > 0:
            print(f"⚠️  Есть {webhook_info.pending_update_count} необработанных обновлений")
        if webhook_info.last_error_message:
            print(f"❌ Последняя ошибка: {webhook_info.last_error_message}")
    else:
        print("❌ Webhook НЕ установлен!")
        
except Exception as e:
    print(f"❌ Ошибка при проверке: {e}")
    import traceback
    traceback.print_exc()

