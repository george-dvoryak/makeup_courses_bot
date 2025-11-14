# Исправление ошибки 404 NOT FOUND для webhook

## Проблема
Telegram получает ошибку `404 NOT FOUND` при попытке отправить webhook на `/webhook`.

## Причины
1. WSGI файл не настроен правильно
2. Веб-приложение не перезагружено
3. Неправильный импорт Flask приложения

## Решение

### Шаг 1: Проверьте WSGI файл

1. На PythonAnywhere перейдите на вкладку **Web**
2. Найдите ссылку **WSGI configuration file** и кликните на неё
3. Убедитесь, что файл содержит:

```python
import sys

# Add your project directory to the path
path = '/home/goshadvoryak/makeup_courses_bot'
if path not in sys.path:
    sys.path.insert(0, path)

# Import the Flask app from webhook_app.py
from webhook_app import app as application

# The app will automatically:
# - Set up webhook on startup
# - Start background cleanup scheduler (runs every hour + on startup)
```

**ВАЖНО:** 
- Замените `goshadvoryak` на ваш реальный username
- Должно быть `from webhook_app import app as application` (НЕ `from main import application`)

### Шаг 2: Перезагрузите веб-приложение

1. На вкладке **Web** нажмите зелёную кнопку **Reload**
2. Подождите 10-15 секунд

### Шаг 3: Проверьте Error log

1. На вкладке **Web** откройте **Error log**
2. Должны быть сообщения:
   ```
   Webhook set to: https://goshadvoryak.pythonanywhere.com/webhook
   [Auto-Cleanup] Background cleanup scheduler started
   ```

Если видите ошибки импорта - переходите к Шагу 4.

### Шаг 4: Проверьте маршруты (если всё ещё не работает)

Создайте тестовый скрипт на PythonAnywhere:

```bash
cd ~/makeup_courses_bot
python3.10 -c "
import sys
sys.path.insert(0, '/home/goshadvoryak/makeup_courses_bot')
from webhook_app import app
print('Registered routes:')
for rule in app.url_map.iter_rules():
    print(f'  {rule.rule} -> {rule.endpoint} [{", ".join(rule.methods)}]')
"
```

Должен показать маршрут `/webhook` с методом `POST`.

### Шаг 5: Проверьте доступность эндпоинта

На PythonAnywhere в Bash консоли:

```bash
curl -X POST https://goshadvoryak.pythonanywhere.com/webhook -H "Content-Type: application/json" -d '{"test": "data"}'
```

Должен вернуть `OK` (или ошибку валидации, но не 404).

## Альтернативное решение: Использовать main.py

Если `webhook_app.py` не работает, можно использовать Flask приложение из `main.py`:

В WSGI файле замените:
```python
from webhook_app import app as application
```

На:
```python
from main import application
```

**НО:** Это менее предпочтительно, так как `webhook_app.py` специально создан для PythonAnywhere и включает автоматическую очистку.

## Проверка после исправления

1. Запустите диагностику:
   ```bash
   cd ~/makeup_courses_bot
   python3.10 check_webhook.py
   ```

2. Проверьте статус webhook в Telegram:
   ```bash
   curl https://api.telegram.org/bot<YOUR_TOKEN>/getWebhookInfo
   ```

3. Отправьте `/start` боту - должен ответить

4. Проверьте Error log - не должно быть ошибок 404

## Частые ошибки

### Ошибка: "No module named 'webhook_app'"
**Решение:** Проверьте путь в WSGI файле - должен быть правильный username

### Ошибка: "No module named 'config'"
**Решение:** Установите зависимости:
```bash
pip install --user -r requirements.txt
```

### Ошибка: Маршрут не найден
**Решение:** Убедитесь, что используете `from webhook_app import app`, а не `from main import application`

## Если ничего не помогает

1. Удалите веб-приложение и создайте заново
2. Следуйте инструкциям из `PYTHONANYWHERE_WSGI_SETUP.md`
3. Убедитесь, что все файлы загружены правильно

