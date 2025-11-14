# Быстрое исправление ошибки 404 для webhook

## Проблема
`Wrong response from the webhook: 404 NOT FOUND`

## Решение (3 шага)

### Шаг 1: Проверьте WSGI файл

1. PythonAnywhere → **Web** → **WSGI configuration file**
2. Убедитесь, что файл содержит:

```python
import sys

path = '/home/goshadvoryak/makeup_courses_bot'  # Замените на ваш username!
if path not in sys.path:
    sys.path.insert(0, path)

from webhook_app import app as application
```

**КРИТИЧНО:** Должно быть `from webhook_app import app as application`, НЕ `from main import application`!

### Шаг 2: Перезагрузите веб-приложение

1. **Web** → зелёная кнопка **Reload**
2. Подождите 10 секунд

### Шаг 3: Проверьте работу

**Вариант A: Через браузер**
Откройте в браузере:
```
https://goshadvoryak.pythonanywhere.com/webhook
```
Должно показать: `Webhook endpoint active. Path: /webhook`

**Вариант B: Через curl (на PythonAnywhere)**
```bash
curl https://goshadvoryak.pythonanywhere.com/webhook
```
Должно вернуть: `Webhook endpoint active. Path: /webhook`

**Вариант C: Через скрипт**
```bash
cd ~/makeup_courses_bot
python3.10 test_webhook_routes.py
```

## Если всё ещё не работает

1. **Проверьте Error log** (Web → Error log)
   - Должны быть сообщения: `Webhook set to: ...`
   - Не должно быть ошибок импорта

2. **Проверьте маршруты:**
   ```bash
   cd ~/makeup_courses_bot
   python3.10 test_webhook_routes.py
   ```
   Должен показать маршрут `/webhook`

3. **Проверьте .env файл:**
   ```bash
   grep WEBHOOK_PATH ~/makeup_courses_bot/.env
   ```
   Должно быть: `WEBHOOK_PATH=/webhook`

## После исправления

1. Отправьте `/start` боту - должен ответить
2. Проверьте статус webhook:
   ```bash
   python3.10 check_webhook.py
   ```
   Не должно быть ошибки 404

## Частая ошибка

❌ **НЕПРАВИЛЬНО:**
```python
from main import application  # Это неправильно!
```

✅ **ПРАВИЛЬНО:**
```python
from webhook_app import app as application  # Это правильно!
```

