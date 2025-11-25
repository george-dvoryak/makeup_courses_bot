# Multi-Bot Quick Start Guide

## Быстрый старт

### 1. Добавьте переменные в .env

Для каждого бота добавьте переменные с префиксом имени бота:

```env
# Бот 1
TELEGRAM_BOT_TOKEN_bot1=ваш_токен_бота_1
ADMIN_IDS_bot1=ваш_telegram_id
GSHEET_ID_bot1=id_google_sheet_1
PAYMENT_PROVIDER_TOKEN_bot1=токен_юкассы_1
DATABASE_PATH_bot1=bot1.db
WEBHOOK_PATH_bot1=/webhook/bot1

# Бот 2
TELEGRAM_BOT_TOKEN_bot2=ваш_токен_бота_2
ADMIN_IDS_bot2=ваш_telegram_id
GSHEET_ID_bot2=id_google_sheet_2
PAYMENT_PROVIDER_TOKEN_bot2=токен_юкассы_2
DATABASE_PATH_bot2=bot2.db
WEBHOOK_PATH_bot2=/webhook/bot2
```

### 2. Проверьте конфигурацию

```bash
python test_multi_bot_config.py
```

### 3. Используйте webhook_app_multi.py

На PythonAnywhere в WSGI файле укажите:

```python
import sys
path = '/home/yourusername/makeup_courses_bot'
if path not in sys.path:
    sys.path.insert(0, path)
from webhook_app_multi import app as application
```

### 4. Перезапустите приложение

На PythonAnywhere: **Web** tab → **Reload**

## Важные моменты

1. **Имена ботов**: Используйте простые имена (bot1, bot2, mybot)
2. **Уникальность**: Каждый бот должен иметь уникальные токены, БД, Google Sheets
3. **Webhook пути**: Автоматически формируются как `/webhook/{bot_name}`
4. **Prodamus**: Настраивайте только Result URL (`/prodamus/{bot_name}/result`). Success/Fail можно не указывать — они больше не используются логикой бота.
5. **Базы данных**: Автоматически создаются как `{bot_name}.db`

## Полная документация

См. [MULTI_BOT_SETUP.md](MULTI_BOT_SETUP.md) для детальной информации.

