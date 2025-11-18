#!/usr/bin/env python3
"""
Диагностика webhook на PythonAnywhere
Проверяет все компоненты системы
"""
import sys
import os

print("=" * 60)
print("ДИАГНОСТИКА WEBHOOK")
print("=" * 60)

# 1. Проверка импортов
print("\n1. Проверка импортов...")
try:
    import telebot
    print("✅ telebot импортирован")
except Exception as e:
    print(f"❌ Ошибка импорта telebot: {e}")
    sys.exit(1)

try:
    from flask import Flask
    print("✅ flask импортирован")
except Exception as e:
    print(f"❌ Ошибка импорта flask: {e}")
    sys.exit(1)

try:
    from config import TELEGRAM_BOT_TOKEN, WEBHOOK_URL, WEBHOOK_PATH, WEBHOOK_SECRET_TOKEN
    print("✅ config импортирован")
    print(f"   USE_WEBHOOK: {os.environ.get('USE_WEBHOOK', 'не установлен')}")
    print(f"   WEBHOOK_URL: {WEBHOOK_URL}")
    print(f"   WEBHOOK_PATH: {WEBHOOK_PATH}")
except Exception as e:
    print(f"❌ Ошибка импорта config: {e}")
    sys.exit(1)

# 2. Проверка импорта main
print("\n2. Проверка импорта main...")
try:
    from main import bot
    print("✅ main импортирован")
    print(f"   Bot token: {TELEGRAM_BOT_TOKEN[:10]}...")
except Exception as e:
    print(f"❌ Ошибка импорта main: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 3. Проверка импорта webhook_app
print("\n3. Проверка импорта webhook_app...")
try:
    from webhook_app import app
    print("✅ webhook_app импортирован")
    print(f"   App type: {type(app)}")
except Exception as e:
    print(f"❌ Ошибка импорта webhook_app: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 4. Проверка маршрутов
print("\n4. Проверка маршрутов Flask...")
try:
    routes = []
    for rule in app.url_map.iter_rules():
        routes.append(f"{rule.rule} [{', '.join(rule.methods)}]")
    
    if routes:
        print("✅ Маршруты зарегистрированы:")
        for route in routes:
            print(f"   {route}")
    else:
        print("⚠️ Маршруты не найдены")
except Exception as e:
    print(f"❌ Ошибка проверки маршрутов: {e}")

# 5. Проверка статуса webhook в Telegram
print("\n5. Проверка статуса webhook в Telegram...")
try:
    import requests
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getWebhookInfo"
    response = requests.get(url, timeout=10)
    data = response.json()
    
    if data.get("ok"):
        webhook_info = data.get("result", {})
        webhook_url = webhook_info.get("url", "НЕ УСТАНОВЛЕН")
        pending = webhook_info.get("pending_update_count", 0)
        last_error = webhook_info.get("last_error_message")
        
        print(f"   Webhook URL: {webhook_url}")
        print(f"   Pending updates: {pending}")
        
        if webhook_url == WEBHOOK_URL:
            print("✅ Webhook URL совпадает с конфигурацией")
        else:
            print(f"⚠️ Webhook URL не совпадает! Ожидается: {WEBHOOK_URL}")
        
        if pending > 0:
            print(f"⚠️ Есть {pending} необработанных обновлений")
        
        if last_error:
            print(f"❌ Последняя ошибка: {last_error}")
        else:
            print("✅ Ошибок нет")
    else:
        print(f"❌ Ошибка получения статуса: {data.get('description')}")
except Exception as e:
    print(f"❌ Ошибка проверки webhook: {e}")

# 6. Тест обработки сообщения
print("\n6. Тест обработки сообщения...")
try:
    # Создаем тестовый update
    test_update = {
        "update_id": 999999999,
        "message": {
            "message_id": 1,
            "from": {
                "id": 123456789,
                "is_bot": False,
                "first_name": "Test",
                "username": "test_user"
            },
            "chat": {
                "id": 123456789,
                "type": "private"
            },
            "date": 1234567890,
            "text": "/start"
        }
    }
    
    import json
    update_obj = telebot.types.Update.de_json(json.dumps(test_update))
    
    if update_obj:
        print("✅ Тестовый update создан")
        print(f"   Message text: {update_obj.message.text if update_obj.message else 'N/A'}")
        
        # НЕ обрабатываем реально, только проверяем структуру
        print("✅ Структура update корректна")
    else:
        print("❌ Не удалось создать update")
except Exception as e:
    print(f"❌ Ошибка теста обработки: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("ДИАГНОСТИКА ЗАВЕРШЕНА")
print("=" * 60)
print("\nЕсли все проверки пройдены, но бот не отвечает:")
print("1. Проверьте Error log в PythonAnywhere")
print("2. Проверьте Server log в PythonAnywhere")
print("3. Убедитесь, что webhook установлен правильно")
print("4. Попробуйте отправить /start боту снова")

