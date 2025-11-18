#!/usr/bin/env python3
"""
Тест доступности webhook endpoint
"""
import sys
import requests
import json

sys.path.insert(0, '/home/goshadvoryak/makeup_courses_bot')
venv_path = '/home/goshadvoryak/makeup_courses_bot/venv/lib/python3.10/site-packages'
if venv_path not in sys.path:
    sys.path.insert(0, venv_path)

from config import WEBHOOK_URL, WEBHOOK_PATH, WEBHOOK_SECRET_TOKEN

print("=" * 60)
print("ТЕСТ ДОСТУПНОСТИ ENDPOINT")
print("=" * 60)

# 1. Тест health check endpoint
print("\n1. Тест health check endpoint (GET /)...")
try:
    base_url = WEBHOOK_URL.replace(WEBHOOK_PATH, "")
    response = requests.get(base_url, timeout=10)
    print(f"   URL: {base_url}")
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.text[:100]}")
    if response.status_code == 200:
        print("   ✅ Health check работает")
    else:
        print(f"   ⚠️ Неожиданный статус: {response.status_code}")
except Exception as e:
    print(f"   ❌ Ошибка: {e}")

# 2. Тест webhook endpoint (GET)
print(f"\n2. Тест webhook endpoint (GET {WEBHOOK_PATH})...")
try:
    response = requests.get(WEBHOOK_URL, timeout=10)
    print(f"   URL: {WEBHOOK_URL}")
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.text[:200]}")
    if response.status_code == 200:
        print("   ✅ Webhook endpoint доступен (GET)")
    else:
        print(f"   ⚠️ Неожиданный статус: {response.status_code}")
except Exception as e:
    print(f"   ❌ Ошибка: {e}")

# 3. Тест webhook endpoint (POST) - симуляция запроса от Telegram
print(f"\n3. Тест webhook endpoint (POST {WEBHOOK_PATH}) - симуляция Telegram...")
try:
    # Создаём тестовый update от Telegram
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
    
    headers = {
        "Content-Type": "application/json"
    }
    
    # Добавляем secret token, если он настроен
    if WEBHOOK_SECRET_TOKEN:
        headers["X-Telegram-Bot-Api-Secret-Token"] = WEBHOOK_SECRET_TOKEN
        print(f"   Используется secret token: {WEBHOOK_SECRET_TOKEN[:10]}...")
    
    response = requests.post(
        WEBHOOK_URL,
        json=test_update,
        headers=headers,
        timeout=10
    )
    
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.text[:200]}")
    
    if response.status_code == 200:
        print("   ✅ Webhook endpoint обработал запрос (POST)")
    else:
        print(f"   ⚠️ Неожиданный статус: {response.status_code}")
        
except Exception as e:
    print(f"   ❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()

# 4. Проверка реальных pending updates
print("\n4. Проверка pending updates в Telegram...")
try:
    from config import TELEGRAM_BOT_TOKEN
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getWebhookInfo"
    response = requests.get(url, timeout=10)
    data = response.json()
    
    if data.get("ok"):
        webhook_info = data.get("result", {})
        pending = webhook_info.get("pending_update_count", 0)
        print(f"   Pending updates: {pending}")
        
        if pending > 0:
            print(f"   ⚠️ Есть {pending} необработанных обновлений!")
            print("   Telegram пытается отправить их, но они не обрабатываются.")
            print("   Это может означать проблему с endpoint или обработкой.")
        else:
            print("   ✅ Нет pending updates")
    else:
        print(f"   ❌ Ошибка получения статуса: {data.get('description')}")
except Exception as e:
    print(f"   ❌ Ошибка: {e}")

print("\n" + "=" * 60)
print("ТЕСТ ЗАВЕРШЁН")
print("=" * 60)
print("\nЕсли POST запрос вернул 200, но в Error log ничего нет:")
print("1. Проверьте, что Error log обновляется (обновите страницу)")
print("2. Проверьте, что sys.stderr правильно перенаправляется")
print("3. Попробуйте отправить реальное сообщение боту и сразу проверьте Error log")

