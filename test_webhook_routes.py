#!/usr/bin/env python3
"""
Скрипт для проверки зарегистрированных маршрутов в Flask приложении.
Запустите на PythonAnywhere для диагностики проблемы 404.
"""
import sys
from pathlib import Path

# Add project directory to path
project_dir = Path(__file__).parent
sys.path.insert(0, str(project_dir))

print("=" * 60)
print("ПРОВЕРКА МАРШРУТОВ FLASK ПРИЛОЖЕНИЯ")
print("=" * 60)
print()

try:
    print("1. Импорт webhook_app...")
    from webhook_app import app
    print("   ✅ webhook_app успешно импортирован")
    print()
    
    print("2. Зарегистрированные маршруты:")
    print()
    routes_found = False
    webhook_route_found = False
    
    for rule in app.url_map.iter_rules():
        routes_found = True
        methods = ', '.join(sorted(rule.methods - {'HEAD', 'OPTIONS'}))
        print(f"   {rule.rule:30} -> {rule.endpoint:20} [{methods}]")
        
        if '/webhook' in rule.rule and 'POST' in rule.methods:
            webhook_route_found = True
    
    print()
    
    if not routes_found:
        print("   ❌ ОШИБКА: Маршруты не найдены!")
        print("   Возможно, Flask приложение не инициализировано правильно")
    elif not webhook_route_found:
        print("   ❌ ОШИБКА: Маршрут /webhook не найден!")
        print("   Проверьте, что WEBHOOK_PATH установлен в .env файле")
    else:
        print("   ✅ Маршрут /webhook найден!")
    
    print()
    print("3. Проверка конфигурации:")
    try:
        from config import WEBHOOK_PATH, WEBHOOK_URL
        print(f"   WEBHOOK_PATH: {WEBHOOK_PATH}")
        print(f"   WEBHOOK_URL: {WEBHOOK_URL}")
        
        if WEBHOOK_PATH and WEBHOOK_PATH != '/webhook':
            print(f"   ⚠️  ВНИМАНИЕ: WEBHOOK_PATH = {WEBHOOK_PATH}, но ожидается /webhook")
    except Exception as e:
        print(f"   ⚠️  Не удалось импортировать конфигурацию: {e}")
    
    print()
    print("=" * 60)
    print("РЕКОМЕНДАЦИИ:")
    print("=" * 60)
    print()
    
    if not webhook_route_found:
        print("1. Проверьте .env файл - должен быть установлен WEBHOOK_PATH=/webhook")
        print("2. Перезагрузите веб-приложение (Web → Reload)")
        print("3. Проверьте Error log на наличие ошибок импорта")
    else:
        print("✅ Маршрут /webhook зарегистрирован правильно!")
        print("Если всё ещё получаете 404:")
        print("1. Убедитесь, что веб-приложение перезагружено")
        print("2. Проверьте, что WSGI файл импортирует: from webhook_app import app as application")
        print("3. Проверьте Error log на наличие ошибок")
    
except ImportError as e:
    print(f"❌ ОШИБКА ИМПОРТА: {e}")
    print()
    print("Возможные решения:")
    print("1. Установите зависимости: pip install --user -r requirements.txt")
    print("2. Проверьте путь в WSGI файле")
    print("3. Убедитесь, что все файлы загружены на PythonAnywhere")
    sys.exit(1)
except Exception as e:
    print(f"❌ ОШИБКА: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

