#!/usr/bin/env python3
"""
Полная диагностика всех компонентов на PythonAnywhere
"""
import sys
import os

print("=" * 70)
print("ПОЛНАЯ ДИАГНОСТИКА PYTHONANYWHERE")
print("=" * 70)

# 1. Проверка путей
print("\n1. ПРОВЕРКА PYTHON PATH")
print("-" * 70)
project_path = '/home/goshadvoryak/makeup_courses_bot'
venv_path = '/home/goshadvoryak/makeup_courses_bot/venv/lib/python3.10/site-packages'
user_site = None

try:
    import site
    user_site = site.getusersitepackages()
except:
    pass

print(f"Project path: {project_path}")
print(f"Venv path: {venv_path}")
print(f"User site-packages: {user_site}")

# Добавляем пути
if project_path not in sys.path:
    sys.path.insert(0, project_path)
if os.path.exists(venv_path) and venv_path not in sys.path:
    sys.path.insert(0, venv_path)
if user_site and user_site not in sys.path:
    sys.path.insert(0, user_site)

print(f"\nТекущий sys.path (первые 5):")
for p in sys.path[:5]:
    exists = "✅" if os.path.exists(p) else "❌"
    print(f"  {exists} {p}")

# 2. Проверка файлов проекта
print("\n2. ПРОВЕРКА ФАЙЛОВ ПРОЕКТА")
print("-" * 70)
required_files = [
    'main.py',
    'webhook_app.py',
    'config.py',
    'db.py',
    'google_sheets.py',
    '.env',
    'requirements.txt'
]

for file in required_files:
    filepath = os.path.join(project_path, file)
    exists = os.path.exists(filepath)
    status = "✅" if exists else "❌"
    size = os.path.getsize(filepath) if exists else 0
    print(f"  {status} {file} ({size} bytes)")

# 3. Проверка импортов
print("\n3. ПРОВЕРКА ИМПОРТОВ")
print("-" * 70)

try:
    import telebot
    print(f"✅ telebot: {telebot.__file__}")
except Exception as e:
    print(f"❌ telebot: {e}")

try:
    import flask
    print(f"✅ flask: {flask.__file__}")
except Exception as e:
    print(f"❌ flask: {e}")

try:
    import requests
    print(f"✅ requests: {requests.__file__}")
except Exception as e:
    print(f"❌ requests: {e}")

try:
    from config import (
        TELEGRAM_BOT_TOKEN, WEBHOOK_URL, WEBHOOK_PATH, 
        WEBHOOK_SECRET_TOKEN, DATABASE_PATH
    )
    print(f"✅ config импортирован")
    print(f"   TELEGRAM_BOT_TOKEN: {TELEGRAM_BOT_TOKEN[:10]}...")
    print(f"   WEBHOOK_URL: {WEBHOOK_URL}")
    print(f"   WEBHOOK_PATH: {WEBHOOK_PATH}")
    print(f"   DATABASE_PATH: {DATABASE_PATH}")
except Exception as e:
    print(f"❌ config: {e}")
    import traceback
    traceback.print_exc()

# 4. Проверка базы данных
print("\n4. ПРОВЕРКА БАЗЫ ДАННЫХ")
print("-" * 70)
try:
    db_path = DATABASE_PATH if 'DATABASE_PATH' in locals() else None
    if db_path:
        exists = os.path.exists(db_path)
        if exists:
            size = os.path.getsize(db_path)
            print(f"✅ База данных существует: {db_path} ({size} bytes)")
        else:
            print(f"⚠️ База данных не существует: {db_path}")
    else:
        print("⚠️ DATABASE_PATH не определён")
except Exception as e:
    print(f"❌ Ошибка проверки БД: {e}")

# 5. Проверка импорта main
print("\n5. ПРОВЕРКА ИМПОРТА MAIN")
print("-" * 70)
try:
    from main import bot
    print("✅ main импортирован")
    print(f"   Bot token: {TELEGRAM_BOT_TOKEN[:10]}...")
except Exception as e:
    print(f"❌ Ошибка импорта main: {e}")
    import traceback
    traceback.print_exc()

# 6. Проверка импорта webhook_app
print("\n6. ПРОВЕРКА ИМПОРТА WEBHOOK_APP")
print("-" * 70)
try:
    from webhook_app import app
    print("✅ webhook_app импортирован")
    print(f"   App type: {type(app)}")
    print(f"   App name: {app.name}")
except Exception as e:
    print(f"❌ Ошибка импорта webhook_app: {e}")
    import traceback
    traceback.print_exc()

# 7. Проверка маршрутов Flask
print("\n7. ПРОВЕРКА МАРШРУТОВ FLASK")
print("-" * 70)
try:
    routes = []
    for rule in app.url_map.iter_rules():
        routes.append(f"{rule.rule} [{', '.join(sorted(rule.methods))}]")
    
    if routes:
        print(f"✅ Найдено {len(routes)} маршрутов:")
        for route in routes:
            print(f"   {route}")
    else:
        print("❌ Маршруты не найдены!")
except Exception as e:
    print(f"❌ Ошибка проверки маршрутов: {e}")

# 8. Проверка WSGI файла
print("\n8. ПРОВЕРКА WSGI ФАЙЛА")
print("-" * 70)
wsgi_path = '/var/www/goshadvoryak_pythonanywhere_com_wsgi.py'
if os.path.exists(wsgi_path):
    print(f"✅ WSGI файл существует: {wsgi_path}")
    try:
        with open(wsgi_path, 'r') as f:
            wsgi_content = f.read()
        print(f"   Размер: {len(wsgi_content)} байт")
        
        # Проверяем содержимое
        checks = [
            ('sys.path.insert', 'Добавление путей'),
            ('webhook_app', 'Импорт webhook_app'),
            ('application', 'Переменная application'),
        ]
        
        for check, desc in checks:
            if check in wsgi_content:
                print(f"   ✅ {desc}")
            else:
                print(f"   ❌ {desc} - НЕ НАЙДЕНО!")
        
        # Показываем содержимое
        print("\n   Содержимое WSGI файла:")
        print("   " + "=" * 60)
        lines = wsgi_content.split('\n')
        for i, line in enumerate(lines[:30], 1):
            print(f"   {i:3d}: {line}")
        if len(lines) > 30:
            remaining = len(lines) - 30
            print(f"   ... (ещё {remaining} строк)")
        print("   " + "=" * 60)
        
    except Exception as e:
        print(f"❌ Ошибка чтения WSGI файла: {e}")
else:
    print(f"❌ WSGI файл НЕ существует: {wsgi_path}")
    print("   Создайте файл через Web → WSGI configuration file")

# 9. Проверка webhook в Telegram
print("\n9. ПРОВЕРКА WEBHOOK В TELEGRAM")
print("-" * 70)
try:
    import requests
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getWebhookInfo"
    response = requests.get(url, timeout=10)
    data = response.json()
    
    if data.get("ok"):
        webhook_info = data.get("result", {})
        current_url = webhook_info.get("url", "")
        pending = webhook_info.get("pending_update_count", 0)
        last_error = webhook_info.get("last_error_message")
        
        print(f"   Webhook URL: {current_url if current_url else 'НЕ УСТАНОВЛЕН'}")
        print(f"   Pending updates: {pending}")
        
        if current_url == WEBHOOK_URL:
            print("   ✅ Webhook URL совпадает с конфигурацией")
        elif current_url:
            print(f"   ⚠️ Webhook URL не совпадает!")
            print(f"      Текущий: {current_url}")
            print(f"      Ожидается: {WEBHOOK_URL}")
        else:
            print("   ❌ Webhook НЕ установлен!")
        
        if pending > 0:
            print(f"   ⚠️ Есть {pending} необработанных обновлений")
        
        if last_error:
            print(f"   ❌ Последняя ошибка: {last_error}")
        else:
            print("   ✅ Ошибок нет")
    else:
        print(f"❌ Ошибка получения статуса: {data.get('description')}")
except Exception as e:
    print(f"❌ Ошибка проверки webhook: {e}")

# 10. Тест endpoint
print("\n10. ТЕСТ ENDPOINT")
print("-" * 70)
try:
    import requests
    base_url = WEBHOOK_URL.replace(WEBHOOK_PATH, "")
    
    # Health check
    try:
        response = requests.get(base_url, timeout=10)
        if response.status_code == 200:
            print(f"✅ Health check работает: {base_url}")
        else:
            print(f"⚠️ Health check вернул {response.status_code}")
    except Exception as e:
        print(f"❌ Health check не работает: {e}")
    
    # Webhook GET
    try:
        response = requests.get(WEBHOOK_URL, timeout=10)
        if response.status_code == 200:
            print(f"✅ Webhook GET работает: {WEBHOOK_URL}")
            print(f"   Response: {response.text[:100]}")
        else:
            print(f"⚠️ Webhook GET вернул {response.status_code}")
    except Exception as e:
        print(f"❌ Webhook GET не работает: {e}")
        
except Exception as e:
    print(f"❌ Ошибка теста endpoint: {e}")

# 11. Проверка переменных окружения
print("\n11. ПРОВЕРКА ПЕРЕМЕННЫХ ОКРУЖЕНИЯ")
print("-" * 70)
env_vars = ['TELEGRAM_BOT_TOKEN', 'USE_WEBHOOK', 'WEBHOOK_URL', 'WEBHOOK_PATH']
for var in env_vars:
    value = os.environ.get(var)
    if value:
        if 'TOKEN' in var:
            print(f"   ✅ {var}: {value[:10]}...")
        else:
            print(f"   ✅ {var}: {value}")
    else:
        print(f"   ⚠️ {var}: не установлена")

print("\n" + "=" * 70)
print("ДИАГНОСТИКА ЗАВЕРШЕНА")
print("=" * 70)
print("\nВАЖНО:")
print("1. Проверьте WSGI файл - он должен импортировать webhook_app")
print("2. Проверьте, что webhook установлен в Telegram")
print("3. Перезагрузите веб-приложение после изменений")
print("4. Проверьте Error log после отправки сообщения боту")

