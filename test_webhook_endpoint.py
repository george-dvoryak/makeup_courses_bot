#!/usr/bin/env python3
"""
Тест webhook endpoint - проверка, что он отвечает на запросы
"""
import requests
import json
from config import WEBHOOK_URL, WEBHOOK_SECRET_TOKEN

print("=" * 60)
print("ТЕСТ WEBHOOK ENDPOINT")
print("=" * 60)
print()

# Тест 1: GET запрос
print("1. Тест GET запроса...")
try:
    response = requests.get(WEBHOOK_URL, timeout=5)
    print(f"   Статус: {response.status_code}")
    print(f"   Ответ: {response.text[:100]}")
    if response.status_code == 200:
        print("   ✅ GET запрос работает")
    else:
        print(f"   ❌ Неожиданный статус: {response.status_code}")
except Exception as e:
    print(f"   ❌ Ошибка: {e}")

print()

# Тест 2: POST запрос без секретного токена
print("2. Тест POST запроса без секретного токена...")
test_data = {
    "update_id": 123456789,
    "message": {
        "message_id": 1,
        "from": {
            "id": 123456789,
            "is_bot": False,
            "first_name": "Test"
        },
        "chat": {
            "id": 123456789,
            "type": "private"
        },
        "date": 1234567890,
        "text": "/start"
    }
}

try:
    headers = {"Content-Type": "application/json"}
    response = requests.post(WEBHOOK_URL, json=test_data, headers=headers, timeout=5)
    print(f"   Статус: {response.status_code}")
    print(f"   Ответ: {response.text[:100]}")
    if response.status_code == 200:
        print("   ✅ POST запрос работает")
    elif response.status_code == 403:
        print("   ⚠️  403 Forbidden - секретный токен требуется (это нормально)")
    else:
        print(f"   ❌ Неожиданный статус: {response.status_code}")
except Exception as e:
    print(f"   ❌ Ошибка: {e}")

print()

# Тест 3: POST запрос с секретным токеном
if WEBHOOK_SECRET_TOKEN:
    print("3. Тест POST запроса с секретным токеном...")
    try:
        headers = {
            "Content-Type": "application/json",
            "X-Telegram-Bot-Api-Secret-Token": WEBHOOK_SECRET_TOKEN
        }
        response = requests.post(WEBHOOK_URL, json=test_data, headers=headers, timeout=5)
        print(f"   Статус: {response.status_code}")
        print(f"   Ответ: {response.text[:100]}")
        if response.status_code == 200:
            print("   ✅ POST запрос с токеном работает")
        else:
            print(f"   ❌ Неожиданный статус: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
else:
    print("3. Секретный токен не настроен, пропускаем тест")

print()
print("=" * 60)
print("РЕКОМЕНДАЦИИ:")
print("=" * 60)
print()
print("Если все тесты прошли успешно, но бот не отвечает:")
print("1. Проверьте статус webhook: python3.10 check_webhook_status.py")
print("2. Убедитесь, что webhook установлен правильно")
print("3. Проверьте, что Telegram отправляет запросы (может быть задержка)")
print("4. Проверьте Server log после отправки сообщения боту")

