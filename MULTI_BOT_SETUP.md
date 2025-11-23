# Multi-Bot Setup Guide

## Обзор

Эта версия бота поддерживает работу нескольких ботов в одном приложении. Каждый бот имеет:
- Свой токен Telegram
- Свою базу данных
- Свой Google Sheet
- Свои ключи оплаты (YooKassa, Prodamus)
- Своих администраторов
- Свой webhook путь

## Архитектура

### Структура конфигурации

Все настройки для каждого бота задаются через переменные окружения в `.env` файле с префиксом имени бота:

```
# Бот 1 (bot1)
TELEGRAM_BOT_TOKEN_bot1=123456:ABC-DEF...
PAYMENT_PROVIDER_TOKEN_bot1=...
GSHEET_ID_bot1=...
ADMIN_IDS_bot1=123,456
DATABASE_PATH_bot1=bot1.db
WEBHOOK_PATH_bot1=/webhook/bot1

# Бот 2 (bot2)
TELEGRAM_BOT_TOKEN_bot2=789012:GHI-JKL...
PAYMENT_PROVIDER_TOKEN_bot2=...
GSHEET_ID_bot2=...
ADMIN_IDS_bot2=789,012
DATABASE_PATH_bot2=bot2.db
WEBHOOK_PATH_bot2=/webhook/bot2
```

### Обратная совместимость

Если переменные с префиксом не найдены, используются переменные без префикса (для обратной совместимости):

```
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...  # Используется, если TELEGRAM_BOT_TOKEN_bot1 не найден
```

## Как добавить нового бота

### Шаг 1: Создайте бота в BotFather

1. Откройте [@BotFather](https://t.me/BotFather) в Telegram
2. Отправьте `/newbot`
3. Следуйте инструкциям и получите токен
4. Запомните имя бота (например, `my_new_bot`)

### Шаг 2: Настройте оплату (если нужно)

#### YooKassa:
1. В BotFather: `/mybots` → выберите бота → `Payments` → `YooKassa`
2. Подключите YooKassa и получите `PAYMENT_PROVIDER_TOKEN`

#### Prodamus:
1. Зарегистрируйтесь в Prodamus
2. Получите `PRODAMUS_SECRET_KEY`, `PRODAMUS_SYSTEM_ID`
3. Настройте `PRODAMUS_PAYFORM_URL`

### Шаг 3: Создайте Google Sheet

1. Создайте новую Google таблицу
2. Скопируйте ID из URL (между `/d/` и `/edit`)
3. Создайте листы: `Courses` и `Texts`
4. Заполните данные

### Шаг 4: Добавьте переменные в .env

Добавьте в `.env` файл переменные для нового бота (замените `newbot` на имя вашего бота):

```env
# === Новый бот: newbot ===
# Telegram
TELEGRAM_BOT_TOKEN_newbot=YOUR_BOT_TOKEN_HERE
ADMIN_IDS_newbot=YOUR_TELEGRAM_USER_ID

# База данных
DATABASE_PATH_newbot=newbot.db

# Google Sheets
GSHEET_ID_newbot=YOUR_GOOGLE_SHEET_ID
GSHEET_COURSES_NAME_newbot=Courses
GSHEET_TEXTS_NAME_newbot=Texts

# Оплата YooKassa
PAYMENT_PROVIDER_TOKEN_newbot=YOUR_YOOKASSA_TOKEN

# Оплата Prodamus (опционально)
ENABLE_PRODAMUS_newbot=True
PRODAMUS_TEST_MODE_newbot=True
PRODAMUS_PAYFORM_URL_newbot=testwork1.payform.ru
PRODAMUS_SECRET_KEY_newbot=YOUR_SECRET_KEY
PRODAMUS_SYSTEM_ID_newbot=YOUR_SYSTEM_ID

# Webhook (PythonAnywhere)
USE_WEBHOOK_newbot=True
WEBHOOK_HOST_newbot=yourusername.pythonanywhere.com
WEBHOOK_PATH_newbot=/webhook/newbot
WEBHOOK_SECRET_TOKEN_newbot=your_secret_token_here
```

### Шаг 5: Добавьте бота в список

Добавьте имя бота в переменную `BOTS_LIST` (опционально, для явного указания):

```env
BOTS_LIST=bot1,bot2,newbot
```

Или бот будет автоматически обнаружен по наличию `TELEGRAM_BOT_TOKEN_newbot`.

### Шаг 6: Настройте Prodamus webhooks (если используется)

В личном кабинете Prodamus укажите webhook URL'ы:

```
Result URL:  https://yourusername.pythonanywhere.com/prodamus/newbot/result
Success URL: https://yourusername.pythonanywhere.com/prodamus/newbot/success
Fail URL:    https://yourusername.pythonanywhere.com/prodamus/newbot/fail
```

### Шаг 7: Перезапустите приложение

На PythonAnywhere:
1. Перейдите в **Web** tab
2. Нажмите **Reload**
3. Проверьте **Error log** на наличие ошибок

## Структура файлов

```
makeup_courses_bot/
├── config.py              # Загрузка конфигурации (поддержка multi-bot)
├── bot_context.py         # Управление контекстом бота (thread-local)
├── bot_factory.py         # Создание экземпляров ботов
├── db.py                  # Работа с БД (поддержка разных БД)
├── google_sheets.py       # Работа с Google Sheets (поддержка разных Sheets)
├── main.py                # Основная логика бота
├── webhook_app.py         # Flask app для webhook (старая версия, для совместимости)
├── webhook_app_multi.py   # Flask app для multi-bot (новая версия)
├── bot1.db                # База данных для bot1
├── bot2.db                # База данных для bot2
├── newbot.db              # База данных для newbot
└── .env                   # Конфигурация всех ботов
```

## Webhook пути

Каждый бот имеет свой webhook путь:

- Bot1: `https://yourusername.pythonanywhere.com/webhook/bot1`
- Bot2: `https://yourusername.pythonanywhere.com/webhook/bot2`
- Newbot: `https://yourusername.pythonanywhere.com/webhook/newbot`

Webhook'и устанавливаются автоматически при запуске приложения.

## Базы данных

Каждый бот использует свою базу данных:
- `bot1.db` - для bot1
- `bot2.db` - для bot2
- `newbot.db` - для newbot

Базы данных создаются автоматически при первом использовании.

## Google Sheets

Каждый бот использует свой Google Sheet:
- Bot1: `GSHEET_ID_bot1`
- Bot2: `GSHEET_ID_bot2`
- Newbot: `GSHEET_ID_newbot`

## Проверка работы

### 1. Проверьте логи

На PythonAnywhere в **Error log** должны быть сообщения:
```
Initialized bot: bot1
Initialized bot: bot2
Initialized bot: newbot
Registered webhook route: /webhook/bot1 for bot: bot1
Registered webhook route: /webhook/bot2 for bot: bot2
Registered webhook route: /webhook/newbot for bot: newbot
Webhook set for bot1: https://...
Webhook set for bot2: https://...
Webhook set for newbot: https://...
```

### 2. Проверьте webhook статус

Отправьте команду боту `/start` и проверьте, что он отвечает.

### 3. Проверьте базу данных

Убедитесь, что создались файлы баз данных для каждого бота.

## Важные замечания

1. **Имена ботов**: Используйте простые имена без пробелов и специальных символов (например, `bot1`, `bot2`, `mybot`)

2. **Уникальность**: Каждый бот должен иметь уникальные:
   - Токен Telegram
   - Базу данных
   - Google Sheet
   - Webhook путь

3. **Администраторы**: Каждый бот может иметь разных администраторов

4. **Оплата**: Каждый бот может использовать разные ключи оплаты

5. **Обратная совместимость**: Старые переменные без префикса продолжают работать для бота по умолчанию

## Troubleshooting

### Бот не отвечает

1. Проверьте, что токен правильный
2. Проверьте, что webhook установлен: посмотрите в Error log
3. Проверьте, что путь webhook правильный в `.env`

### Ошибка "Bot not found"

1. Проверьте, что имя бота в `BOTS_LIST` или переменных окружения правильное
2. Проверьте, что все переменные с префиксом `_botname` заполнены

### Ошибка базы данных

1. Проверьте, что путь к БД правильный
2. Проверьте права доступа к файлу БД

### Ошибка Google Sheets

1. Проверьте, что `GSHEET_ID` правильный
2. Проверьте, что листы `Courses` и `Texts` существуют
3. Проверьте права доступа к таблице (если используете API)

