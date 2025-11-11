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
- Courses: `id, name, description, price, duration_days, image_url, channel`
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
- `OFFER_INN` — ИНН для подписи оферты (по умолчанию 771618630441).
- `OFFER_FULL_NAME` — ФИО для подписи оферты (по умолчанию "Дворяк Георгий Алексеевич").

## Права бота в каналах
Бот должен быть администратором каждого канала-курса с правами:
- Добавлять пользователя (создавать инвайт-ссылки).
- Удалять/банить/разбанивать участников.

## Локальный запуск (polling)
1. `pip install -r requirements.txt`
2. Создайте `.env` файл из `.env.example` и заполните обязательные переменные.
3. `python main.py` (по умолчанию polling, если `USE_WEBHOOK` не включен).

## PythonAnywhere (webhook)
1. Загрузите проект (например, в `/home/<username>/makeup_courses_bot`).
2. В **Web** → **Add a new web app** → Flask → укажите Python 3.X.
3. В WSGI-файле добавьте:
   ```python
   import sys
   path = '/home/<username>/makeup_courses_bot'
   if path not in sys.path:
       sys.path.append(path)
   from webhook_app import app as application
   ```
4. В `config.py` установите `USE_WEBHOOK=True`, `WEBHOOK_HOST='<username>.pythonanywhere.com'`.
5. Перезапустите web app — webhook установится автоматически (см. логи).

## Удаление просроченных подписок (cron)
На PythonAnywhere → **Tasks**:
- Команда: `python /home/<username>/makeup_courses_bot/remove_expired.py`
- Периодичность: ежедневно (или чаще на платном тарифе).

## YooKassa и фискализация
- Подключите YooKassa к боту (BotFather → Payments → YooKassa).
- Включите автоотправку чеков для самозанятого (в кабинете YooKassa/Мой Налог).
- В `main.py` функция `send_receipt_to_tax` — заглушка для кастомной интеграции.

## Robokassa (Telegram Payments)
### Настройка тестовой среды
1. Зарегистрируйтесь в [Robokassa](https://www.robokassa.ru/) и создайте тестовый магазин.
2. В личном кабинете Robokassa настройте магазин для Telegram Payments.
3. В BotFather подключите Robokassa как провайдера платежей:
   - BotFather → ваш бот → Payments → Add Provider → Robokassa
   - Введите данные магазина (MerchantLogin, пароли)
   - Получите provider token (формат: `MerchantLogin:TEST:Password` для теста)
4. В `config.py` установите:
   ```python
   ENABLE_ROBOKASSA = True
   ROBOKASSA_PROVIDER_TOKEN = "ваш_тестовый_токен_от_BotFather"
   RBK_TEST_MODE = True  # Для тестовой среды
   ```
5. Настройте параметры чека (для самозанятого/НПД):
   - `RBK_SNO = "usn_income"` (система налогообложения)
   - `RBK_TAX = "none"` (без НДС для НПД)
   - `RBK_PAYMENT_OBJECT = "service"` (тип товара/услуги)
   - `RBK_PAYMENT_METHOD = "full_payment"` (способ расчета)

### Переход в production
1. Создайте production магазин в Robokassa.
2. Получите production provider token от BotFather (формат: `MerchantLogin:LIVE:Password`).
3. В `config.py` установите:
   ```python
   ROBOKASSA_PROVIDER_TOKEN = "ваш_продакшн_токен"
   RBK_TEST_MODE = False  # Для production
   ```

### Формат provider_data
Бот автоматически формирует `provider_data` с:
- `InvoiceId`: уникальный номер заказа (user_id + timestamp)
- `Receipt`: фискальный чек с параметрами налогообложения

Подробная документация: https://docs.robokassa.ru/

## Команды админа
- `/broadcast_all <текст>`
- `/broadcast_buyers <текст>`
- `/broadcast_nonbuyers <текст>`

## Замечания
- Проверка повторной покупки реализована.
- Валидация наличия курса на этапе pre-checkout.
- При успешной оплате создается одноразовая инвайт-ссылка на канал.
- Для приватных каналов используйте numeric ID (`-100...`) и выдайте боту права админа.
