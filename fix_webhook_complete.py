#!/usr/bin/env python3
"""
Полная проверка и исправление webhook на PythonAnywhere
"""
import sys
import os

print("=" * 60)
print("ПОЛНАЯ ПРОВЕРКА И ИСПРАВЛЕНИЕ WEBHOOK")
print("=" * 60)

# Добавляем пути
sys.path.insert(0, '/home/goshadvoryak/makeup_courses_bot')
venv_path = '/home/goshadvoryak/makeup_courses_bot/venv/lib/python3.10/site-packages'
if os.path.exists(venv_path) and venv_path not in sys.path:
    sys.path.insert(0, venv_path)

# Также добавляем user site-packages
import site
user_site = site.getusersitepackages()
if user_site and user_site not in sys.path:
    sys.path.insert(0, user_site)

print(f"\n1. Python path:")
for p in sys.path[:5]:
    print(f"   {p}")

print("\n2. Проверка импортов...")
try:
    import telebot
    print("✅ telebot импортирован")
except Exception as e:
    print(f"❌ Ошибка импорта telebot: {e}")
    print("\nУстановите зависимости:")
    print("pip3.10 install --user -r requirements.txt")
    sys.exit(1)

try:
    from config import TELEGRAM_BOT_TOKEN, WEBHOOK_URL, WEBHOOK_PATH, WEBHOOK_SECRET_TOKEN
    print("✅ config импортирован")
    print(f"   WEBHOOK_URL: {WEBHOOK_URL}")
    print(f"   WEBHOOK_PATH: {WEBHOOK_PATH}")
except Exception as e:
    print(f"❌ Ошибка импорта config: {e}")
    sys.exit(1)

print("\n3. Проверка статуса webhook в Telegram...")
try:
    import requests
    
    # Получаем текущий статус
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getWebhookInfo"
    response = requests.get(url, timeout=10)
    data = response.json()
    
    if data.get("ok"):
        webhook_info = data.get("result", {})
        current_url = webhook_info.get("url", "")
        pending = webhook_info.get("pending_update_count", 0)
        last_error = webhook_info.get("last_error_message")
        last_error_date = webhook_info.get("last_error_date")
        
        print(f"   Текущий webhook URL: {current_url if current_url else 'НЕ УСТАНОВЛЕН'}")
        print(f"   Pending updates: {pending}")
        
        if last_error:
            print(f"   ⚠️ Последняя ошибка: {last_error}")
            if last_error_date:
                from datetime import datetime
                error_time = datetime.fromtimestamp(last_error_date)
                print(f"   Дата ошибки: {error_time}")
        
        # Проверяем, нужно ли установить webhook
        if not current_url or current_url != WEBHOOK_URL:
            print(f"\n4. Установка webhook...")
            print(f"   URL: {WEBHOOK_URL}")
            
            # Удаляем старый webhook
            try:
                delete_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/deleteWebhook"
                delete_response = requests.post(delete_url, json={"drop_pending_updates": True}, timeout=10)
                if delete_response.json().get("ok"):
                    print("   ✅ Старый webhook удалён")
            except Exception as e:
                print(f"   ⚠️ Ошибка удаления старого webhook: {e}")
            
            # Устанавливаем новый webhook
            try:
                set_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook"
                payload = {
                    "url": WEBHOOK_URL,
                    "drop_pending_updates": True,
                    "allowed_updates": ["message", "callback_query", "shipping_query", "pre_checkout_query"]
                }
                
                if WEBHOOK_SECRET_TOKEN:
                    payload["secret_token"] = WEBHOOK_SECRET_TOKEN
                    print(f"   Используется secret token: {WEBHOOK_SECRET_TOKEN[:10]}...")
                
                set_response = requests.post(set_url, json=payload, timeout=10)
                set_data = set_response.json()
                
                if set_data.get("ok"):
                    print("   ✅ Webhook успешно установлен!")
                    print(f"   URL: {set_data.get('result', {}).get('url', WEBHOOK_URL)}")
                else:
                    print(f"   ❌ Ошибка установки webhook: {set_data.get('description')}")
                    if set_data.get("error_code") == 429:
                        retry_after = set_data.get("parameters", {}).get("retry_after", 0)
                        print(f"   ⚠️ Слишком много запросов. Подождите {retry_after} секунд")
            except Exception as e:
                print(f"   ❌ Ошибка установки webhook: {e}")
        else:
            print(f"\n4. ✅ Webhook уже установлен правильно")
    else:
        print(f"❌ Ошибка получения статуса: {data.get('description')}")
        
except Exception as e:
    print(f"❌ Ошибка проверки webhook: {e}")
    import traceback
    traceback.print_exc()

print("\n5. Тест доступности endpoint...")
try:
    import requests
    test_url = WEBHOOK_URL.replace("/webhook", "")  # Health check endpoint
    response = requests.get(test_url, timeout=10)
    if response.status_code == 200:
        print(f"   ✅ Endpoint доступен: {response.text}")
    else:
        print(f"   ⚠️ Endpoint вернул код {response.status_code}")
except Exception as e:
    print(f"   ⚠️ Не удалось проверить endpoint: {e}")

print("\n" + "=" * 60)
print("ПРОВЕРКА ЗАВЕРШЕНА")
print("=" * 60)
print("\nСледующие шаги:")
print("1. Убедитесь, что зависимости установлены:")
print("   pip3.10 install --user -r requirements.txt")
print("2. Перезагрузите веб-приложение (Web → Reload)")
print("3. Отправьте /start боту")
print("4. Проверьте Error log в PythonAnywhere")

