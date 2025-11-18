#!/usr/bin/env python3
"""
Шаблон правильного WSGI файла для PythonAnywhere
"""
wsgi_template = '''import sys

# Add your project directory to the path
path = '/home/goshadvoryak/makeup_courses_bot'
if path not in sys.path:
    sys.path.insert(0, path)

# Add virtual environment to path (ВАЖНО!)
venv_path = '/home/goshadvoryak/makeup_courses_bot/venv/lib/python3.10/site-packages'
if venv_path not in sys.path:
    sys.path.insert(0, venv_path)

# Also add user site-packages (for --user installations)
import site
user_site = site.getusersitepackages()
if user_site and user_site not in sys.path:
    sys.path.insert(0, user_site)

# Import the Flask app
from webhook_app import app as application

# The app will automatically:
# - Set up webhook on startup
# - Start background cleanup scheduler (runs every hour + on startup)
'''

print("=" * 70)
print("ШАБЛОН WSGI ФАЙЛА")
print("=" * 70)
print("\nСодержимое правильного WSGI файла:")
print("-" * 70)
print(wsgi_template)
print("-" * 70)
print("\nПуть к WSGI файлу:")
print("/var/www/goshadvoryak_pythonanywhere_com_wsgi.py")
print("\nКак обновить WSGI файл:")
print("1. Зайдите в PythonAnywhere → Web")
print("2. Найдите 'WSGI configuration file'")
print("3. Откройте файл и замените содержимое на шаблон выше")
print("4. Сохраните и перезагрузите веб-приложение")

