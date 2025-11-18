#!/usr/bin/env python3
"""
Тест логирования в webhook_app
"""
import sys
import os

# Добавляем пути
sys.path.insert(0, '/home/goshadvoryak/makeup_courses_bot')
venv_path = '/home/goshadvoryak/makeup_courses_bot/venv/lib/python3.10/site-packages'
if os.path.exists(venv_path) and venv_path not in sys.path:
    sys.path.insert(0, venv_path)

print("=" * 60)
print("ТЕСТ ЛОГИРОВАНИЯ")
print("=" * 60)

# Тест 1: Проверка sys.stderr
print("\n1. Тест sys.stderr...")
try:
    print("Тест обычного print", file=sys.stderr)
    print("✅ sys.stderr работает")
except Exception as e:
    print(f"❌ Ошибка: {e}")

# Тест 2: Импорт webhook_app
print("\n2. Импорт webhook_app...")
try:
    from webhook_app import app
    print("✅ webhook_app импортирован")
except Exception as e:
    print(f"❌ Ошибка импорта: {e}")
    import traceback
    traceback.print_exc()

# Тест 3: Проверка маршрутов
print("\n3. Проверка маршрутов...")
try:
    routes = []
    for rule in app.url_map.iter_rules():
        routes.append(f"{rule.rule} [{', '.join(rule.methods)}]")
    
    print(f"✅ Найдено {len(routes)} маршрутов:")
    for route in routes:
        print(f"   {route}")
except Exception as e:
    print(f"❌ Ошибка: {e}")

# Тест 4: Симуляция запроса
print("\n4. Симуляция POST запроса к webhook...")
try:
    from webhook_app import app
    from config import WEBHOOK_PATH
    from datetime import datetime
    
    with app.test_client() as client:
        # Тестовый update
        test_data = {
            "update_id": 999999999,
            "message": {
                "message_id": 1,
                "from": {"id": 123456789, "is_bot": False, "first_name": "Test"},
                "chat": {"id": 123456789, "type": "private"},
                "date": 1234567890,
                "text": "/start"
            }
        }
        
        headers = {}
        from config import WEBHOOK_SECRET_TOKEN
        if WEBHOOK_SECRET_TOKEN:
            headers["X-Telegram-Bot-Api-Secret-Token"] = WEBHOOK_SECRET_TOKEN
        
        print(f"   Отправка POST на {WEBHOOK_PATH}...")
        print(f"   [Это должно появиться в Error log]", file=sys.stderr)
        
        response = client.post(
            WEBHOOK_PATH,
            json=test_data,
            headers=headers
        )
        
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.data.decode()[:100]}")
        
        if response.status_code == 200:
            print("   ✅ Endpoint обработал запрос")
        else:
            print(f"   ⚠️ Неожиданный статус: {response.status_code}")
            
except Exception as e:
    print(f"❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("ТЕСТ ЗАВЕРШЁН")
print("=" * 60)
print("\nВАЖНО:")
print("1. Проверьте Error log - там должны быть строки с '[Webhook]'")
print("2. Если строк нет, возможно проблема с перенаправлением sys.stderr")
print("3. Попробуйте отправить реальное сообщение боту и сразу проверьте Error log")

