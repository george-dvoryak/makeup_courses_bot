# Полная проверка настроек на PythonAnywhere

## Шаг 1: Запустите полную диагностику

В Bash консоли на PythonAnywhere выполните:

```bash
cd ~/makeup_courses_bot
python3.10 full_diagnostic.py
```

Этот скрипт проверит:
- ✅ Все пути Python
- ✅ Существование всех файлов
- ✅ Импорты всех модулей
- ✅ Базу данных
- ✅ WSGI файл
- ✅ Webhook в Telegram
- ✅ Доступность endpoints

**Пришлите полный вывод этого скрипта!**

## Шаг 2: Проверьте WSGI файл

### 2.1. Откройте WSGI файл

1. Зайдите в PythonAnywhere → **Web**
2. Найдите раздел **"WSGI configuration file"**
3. Нажмите на ссылку с именем файла (обычно `goshadvoryak_pythonanywhere_com_wsgi.py`)

### 2.2. Проверьте содержимое

WSGI файл должен содержать:

```python
import sys

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
```

### 2.3. Если файл отличается

1. Замените содержимое на шаблон выше
2. Сохраните файл
3. Перезагрузите веб-приложение (Web → **Reload**)

## Шаг 3: Проверьте настройки веб-приложения

В PythonAnywhere → **Web** проверьте:

### 3.1. Source code
- **Working directory**: `/home/goshadvoryak/makeup_courses_bot`
- **WSGI configuration file**: `/var/www/goshadvoryak_pythonanywhere_com_wsgi.py`

### 3.2. Static files (если есть)
- Обычно не нужны для этого проекта

## Шаг 4: Проверьте webhook

```bash
cd ~/makeup_courses_bot
python3.10 check_webhook_status.py
```

Если webhook не установлен:

```bash
python3.10 set_webhook.py
```

## Шаг 5: Проверьте зависимости

```bash
cd ~/makeup_courses_bot
pip3.10 install --user -r requirements.txt
```

## Шаг 6: Перезагрузите веб-приложение

1. PythonAnywhere → **Web**
2. Нажмите зелёную кнопку **Reload**
3. Подождите 10-15 секунд

## Шаг 7: Проверьте логи

### 7.1. Server log

PythonAnywhere → **Web** → **Server log**

Должны быть строки:
```
Webhook set to: https://goshadvoryak.pythonanywhere.com/webhook
[Auto-Cleanup] Background cleanup scheduler started
WSGI app 0 (mountpoint='') ready
```

### 7.2. Error log

PythonAnywhere → **Web** → **Error log**

1. Откройте Error log в отдельной вкладке
2. Отправьте `/start` боту
3. **Сразу** обновите Error log (F5)

Должны появиться строки:
```
[Webhook] Received POST request
[Webhook] Processing message from user XXXXX: /start
[Webhook] ✅ Update processed successfully
```

## Шаг 8: Тест endpoint

```bash
cd ~/makeup_courses_bot
python3.10 test_endpoint.py
```

## Что проверить, если ничего не работает

1. **WSGI файл правильный?** → Проверьте шаг 2
2. **Зависимости установлены?** → Проверьте шаг 5
3. **Webhook установлен?** → Проверьте шаг 4
4. **Веб-приложение перезагружено?** → Проверьте шаг 6
5. **Логи показывают ошибки?** → Проверьте шаг 7

## Важно

- **Error log** показывает обработку запросов (там вывод через `sys.stderr`)
- **Server log** показывает только запуск uWSGI
- Если в Error log ничего нет после отправки сообщения — Telegram не отправляет запросы или они не доходят до обработчика

## После всех проверок

Пришлите:
1. Полный вывод `full_diagnostic.py`
2. Содержимое WSGI файла (первые 20 строк)
3. Содержимое Error log после отправки `/start` боту
4. Результат `test_endpoint.py`

