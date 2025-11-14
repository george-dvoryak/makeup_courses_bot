#!/usr/bin/env python3
"""
Скрипт для тестирования импорта webhook_app через WSGI на PythonAnywhere.
Запустите на PythonAnywhere для диагностики проблем.
"""
import sys

# Симулируем WSGI окружение
path = '/home/goshadvoryak/makeup_courses_bot'
if path not in sys.path:
    sys.path.insert(0, path)

# Add virtual environment to path
venv_path = '/home/goshadvoryak/makeup_courses_bot/venv/lib/python3.10/site-packages'
if venv_path not in sys.path:
    sys.path.insert(0, venv_path)

print("=" * 60)
print("ТЕСТ ИМПОРТА WEBHOOK_APP")
print("=" * 60)
print()

print("1. Проверка sys.path:")
for p in sys.path[:5]:
    print(f"   {p}")
print()

print("2. Проверка импорта модулей...")
try:
    import telebot
    print("   ✅ telebot импортирован")
except Exception as e:
    print(f"   ❌ telebot: {e}")
    sys.exit(1)

try:
    import flask
    print("   ✅ flask импортирован")
except Exception as e:
    print(f"   ❌ flask: {e}")
    sys.exit(1)

try:
    from config import TELEGRAM_BOT_TOKEN, USE_WEBHOOK, WEBHOOK_URL, WEBHOOK_PATH
    print("   ✅ config импортирован")
    print(f"   USE_WEBHOOK: {USE_WEBHOOK}")
    print(f"   WEBHOOK_URL: {WEBHOOK_URL}")
    print(f"   WEBHOOK_PATH: {WEBHOOK_PATH}")
except Exception as e:
    print(f"   ❌ config: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()
print("3. Проверка импорта main...")
try:
    from main import bot
    print("   ✅ main импортирован")
    print(f"   Bot token: {TELEGRAM_BOT_TOKEN[:10]}...")
except Exception as e:
    print(f"   ❌ main: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()
print("4. Проверка импорта webhook_app...")
try:
    from webhook_app import app
    print("   ✅ webhook_app импортирован")
    print(f"   App type: {type(app)}")
    print(f"   App name: {app.name}")
except Exception as e:
    print(f"   ❌ webhook_app: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()
print("5. Проверка маршрутов...")
try:
    routes = []
    for rule in app.url_map.iter_rules():
        routes.append(f"{rule.rule} [{', '.join(rule.methods - {'HEAD', 'OPTIONS'})}]")
    
    if routes:
        print("   Зарегистрированные маршруты:")
        for route in routes:
            print(f"     {route}")
    else:
        print("   ⚠️  Маршруты не найдены")
except Exception as e:
    print(f"   ❌ Ошибка при проверке маршрутов: {e}")

print()
print("=" * 60)
print("✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ!")
print("=" * 60)
print()
print("Если этот скрипт выполнился без ошибок, но веб-приложение")
print("не работает, проверьте:")
print("1. Web → Reload (перезагрузите веб-приложение)")
print("2. Web → Error log (проверьте логи)")
print("3. Web → Server log (проверьте серверные логи)")

