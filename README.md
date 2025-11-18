# Telegram бот для продажи курсов по макияжу

Функционал:
- Каталог курсов из Google Sheets (админ-панель).
- Покупка доступа через Telegram Payments (YooKassa).
- Автовыдача приглашения в приватный канал курса, запрет повторной покупки активного курса.
- Список активных подписок, кнопка поддержки.
- Автоматическое удаление из каналов по истечении срока (cron-скрипт).
- Админ-рассылки: всем / покупателям / непокупателям.

## Структура
- `.env` — файл с переменными окружения (токены, ID, URL-ы). **НЕ коммитить в git!**
- `.env.example` — пример файла с переменными окружения (можно коммитить).
- `config.py` — загрузка переменных из `.env` файла.
- `db.py` — SQLite (пользователи, покупки).
- `google_sheets.py` — загрузка курсов/текстов из Google Sheets (CSV по умолчанию).
- `main.py` — логика бота (меню, каталог, покупка, выдача доступа, рассылки).
- `webhook_app.py` — Flask-приложение для вебхука (PythonAnywhere).
- `remove_expired.py` — удаление пользователей из каналов по истечении срока.
- `requirements.txt` — зависимости.

## Google Sheets
Два листа: **Courses** и **Texts**.
- Courses: `id, name, description, price, duration_days, image_url, channel` (если `duration_days` пустое или 0, доступ бессрочный)
- Texts: `key, value` (например: `welcome_message`, `support_message`, `catalog_title`, `welcome_image_url`, `catalog_image_url`, `catalog_text`)

Для простоты используйте публикацию листов как CSV:     File → Publish to the web → выбрать лист → получить CSV. Установите `GSHEET_ID` и имена листов в `.env` файле.

## Настройка окружения

### 1. Установка зависимостей
```bash
pip install -r requirements.txt
```

### 2. Создание .env файла
Скопируйте `.env.example` в `.env` и заполните значения:
```bash
cp .env.example .env
```

Затем отредактируйте `.env` файл и укажите ваши значения:
- `TELEGRAM_BOT_TOKEN` — токен бота (BotFather).
- `PAYMENT_PROVIDER_TOKEN` — токен YooKassa для Telegram Payments (в BotFather → Payments).
- `GSHEET_ID` — ID вашей Google таблицы.
- `ADMIN_IDS` — список Telegram user_id через запятую (например: `123456789,987654321`).

**Важно:** Файл `.env` содержит секретные данные и **НЕ должен** попадать в git! Он уже добавлен в `.gitignore`.

### 3. Переменные окружения (.env файл)

**Обязательные:**
- `TELEGRAM_BOT_TOKEN` — токен бота (BotFather).
- `PAYMENT_PROVIDER_TOKEN` — токен YooKassa для Telegram Payments.
- `GSHEET_ID` — ID Google таблицы.
- `ADMIN_IDS` — список Telegram user_id через запятую.

**Опциональные:**
- `DATABASE_PATH` — путь к SQLite (по умолчанию `bot.db`).
- `GSHEET_COURSES_NAME` — имя листа с курсами (по умолчанию `Courses`).
- `GSHEET_TEXTS_NAME` — имя листа с текстами (по умолчанию `Texts`).
- `GOOGLE_SHEETS_USE_API` — `True` для gspread, иначе CSV.
- `GOOGLE_CREDENTIALS_FILE` — JSON сервисного аккаунта (если используете gspread).
- `USE_WEBHOOK`, `WEBHOOK_HOST`, `WEBHOOK_PATH` — для PythonAnywhere вебхука.

## Права бота в каналах
Бот должен быть администратором каждого канала-курса с правами:
- Добавлять пользователя (создавать инвайт-ссылки).
- Удалять/банить/разбанивать участников.

## Локальный запуск (polling)
1. `pip install -r requirements.txt`
2. Создайте `.env` файл из `.env.example` и заполните обязательные переменные.
3. `python main.py` (по умолчанию polling, если `USE_WEBHOOK` не включен).

## PythonAnywhere (webhook)

**📖 Полная инструкция по развертыванию**: См. [PYTHONANYWHERE_DEPLOYMENT.md](PYTHONANYWHERE_DEPLOYMENT.md)

### Краткая инструкция:

1. Загрузите проект (через Git или Files tab)
2. Установите зависимости: `pip install --user -r requirements.txt`
3. Создайте `.env` файл с необходимыми переменными
4. Создайте Web app (Flask, Python 3.10+)
5. В WSGI-файле:
   ```python
   import sys
   path = '/home/<username>/makeup_courses_bot'
   if path not in sys.path:
       sys.path.insert(0, path)
   from webhook_app import app as application
   ```
6. Перезагрузите web app

**Автоматическая очистка**: Встроена в код! Очистка запускается:
- При старте web app
- Каждый час автоматически в фоновом режиме

Логи можно увидеть в Error log в разделе Web.

## Удаление просроченных подписок (автоматическое)

### Автоматическая очистка встроена в код!

При использовании `webhook_app.py` (PythonAnywhere), очистка запускается автоматически:
- ✅ **При старте web app** - сразу после запуска
- ✅ **Каждый час** - автоматически в фоновом режиме

Логи можно увидеть в Error log в разделе Web PythonAnywhere.

### Дополнительные варианты (опционально)

Если вы хотите более частую очистку или используете локальный запуск:

#### Вариант 1: Локальный Linux/Mac (cron)

1. Откройте crontab для редактирования:
   ```bash
   crontab -e
   ```

2. Добавьте строку для запуска каждые 5 минут:
   ```bash
   */5 * * * * cd /path/to/makeup_courses_bot && /usr/bin/python3 remove_expired.py >> /path/to/makeup_courses_bot/cleanup.log 2>&1
   ```

   Или используйте helper script:
   ```bash
   */5 * * * * /path/to/makeup_courses_bot/run_cleanup.sh >> /path/to/makeup_courses_bot/cleanup.log 2>&1
   ```

3. Сохраните и выйдите (в nano: Ctrl+X, затем Y, затем Enter)

4. Проверьте, что cron работает:
   ```bash
   crontab -l
   ```

#### Вариант 2: Windows (Task Scheduler)

1. Откройте **Task Scheduler** (Планировщик заданий)
2. Создайте новую задачу:
   - **Trigger**: По расписанию, каждые 5 минут
   - **Action**: Запустить программу
   - **Program**: `python.exe` (или полный путь к python)
   - **Arguments**: `remove_expired.py`
   - **Start in**: Путь к папке проекта

#### Вариант 3: Ручной запуск через бота (для тестирования)

Админы могут запустить очистку вручную через команду:
```
/cleanup_expired
```

### Проверка работы

1. Проверьте логи скрипта (если настроены)
2. Используйте команду `/cleanup_expired` в боте для проверки статистики
3. Проверьте, что пользователи действительно удаляются из каналов после истечения времени

### Рекомендации по частоте запуска

- **Каждые 5 минут**: для точного удаления (рекомендуется)
- **Каждые 15 минут**: компромисс между точностью и нагрузкой
- **Каждый час**: минимальная частота, но возможна задержка до часа

## YooKassa и фискализация
- Подключите YooKassa к боту (BotFather → Payments → YooKassa).
- Включите автоотправку чеков для самозанятого (в кабинете YooKassa/Мой Налог).
- В `main.py` функция `send_receipt_to_tax` — заглушка для кастомной интеграции.

## Команды админа
- `/broadcast_all <текст>` - рассылка всем пользователям
- `/broadcast_buyers <текст>` - рассылка только покупателям
- `/broadcast_nonbuyers <текст>` - рассылка только непокупателям
- `/cleanup_expired` - вручную запустить очистку просроченных подписок (показывает статистику и обрабатывает)
- `/diag_channels` - диагностика каналов курсов (проверка прав бота)

## Замечания
- Проверка повторной покупки реализована.
- Валидация наличия курса на этапе pre-checkout.
- При успешной оплате создается одноразовая инвайт-ссылка на канал.
- Для приватных каналов используйте numeric ID (`-100...`) и выдайте боту права админа.
