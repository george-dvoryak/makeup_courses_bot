# Как запустить бота из Cursor IDE

## Быстрый старт (Polling режим - для разработки)

### 1. Убедитесь, что у вас установлен Python 3.8+

В терминале Cursor IDE (View → Terminal или `` Ctrl+` ``):
```bash
python3 --version
# или
python --version
```

### 2. Создайте виртуальное окружение (рекомендуется)

```bash
cd /Users/g.dvoryak/Desktop/makeup_courses_bot
python3 -m venv .venv
```

### 3. Активируйте виртуальное окружение

**На macOS/Linux:**
```bash
source .venv/bin/activate
```

**На Windows:**
```bash
.venv\Scripts\activate
```

После активации в терминале появится `(.venv)` в начале строки.

### 4. Установите зависимости

```bash
pip install -r requirements.txt
```

### 5. Проверьте файл .env

Убедитесь, что файл `.env` существует и содержит все необходимые переменные:
- `TELEGRAM_BOT_TOKEN`
- `PAYMENT_PROVIDER_TOKEN`
- `GSHEET_ID`
- `ADMIN_IDS`

Если файла нет, скопируйте из примера:
```bash
cp .env.example .env
# Затем отредактируйте .env и заполните значения
```

### 6. Запустите бота в режиме polling

```bash
python main.py
```

Или если используете `python3`:
```bash
python3 main.py
```

Бот запустится и начнет получать обновления через polling. Вы увидите в консоли:
```
Bot started in polling mode...
```

---

## Запуск через Cursor IDE (Run Configuration)

### Способ 1: Использование встроенного терминала

1. Откройте терминал в Cursor: `View → Terminal` или `` Ctrl+` ``
2. Выполните команды выше (активация venv, запуск)

### Способ 2: Создание задачи (Task)

1. Создайте файл `.vscode/tasks.json` (Cursor использует конфигурацию VS Code):
```json
{
    "version": "2.0.0",
    "tasks": [
        {
            "label": "Run Bot (Polling)",
            "type": "shell",
            "command": "${workspaceFolder}/.venv/bin/python",
            "args": ["main.py"],
            "options": {
                "cwd": "${workspaceFolder}"
            },
            "problemMatcher": [],
            "presentation": {
                "reveal": "always",
                "panel": "new"
            }
        }
    ]
}
```

2. Запустите задачу: `Terminal → Run Task → Run Bot (Polling)`

### Способ 3: Прямой запуск через Python

1. Откройте `main.py`
2. Нажмите `F5` или `Run → Start Debugging`
3. Выберите "Python File" или создайте конфигурацию запуска

---

## Запуск в режиме Webhook (для production)

Если вы хотите использовать webhook (например, на PythonAnywhere):

1. В `.env` установите:
```
USE_WEBHOOK=True
WEBHOOK_HOST=your-domain.com
WEBHOOK_PATH=/your-webhook-path
WEBHOOK_SECRET_TOKEN=your-secret-token
```

2. Запустите Flask приложение:
```bash
python webhook_app.py
```

Или используйте WSGI сервер (gunicorn, uwsgi):
```bash
gunicorn -w 1 -b 0.0.0.0:5000 webhook_app:app
```

---

## Проверка работы бота

1. Откройте Telegram и найдите вашего бота
2. Отправьте команду `/start`
3. Проверьте, что бот отвечает и показывает меню

---

## Отладка

### Просмотр логов

Все ошибки и информационные сообщения выводятся в консоль. Следите за:
- Ошибками подключения к Telegram API
- Ошибками загрузки данных из Google Sheets
- Ошибками работы с базой данных

### Проверка конфигурации

Запустите Python в интерактивном режиме:
```bash
python
>>> from config import *
>>> print(TELEGRAM_BOT_TOKEN[:10] + "...")  # Проверка загрузки токена
```

### Тестирование Google Sheets

```bash
python
>>> from google_sheets import get_courses_data
>>> courses = get_courses_data()
>>> print(courses)
```

---

## Остановка бота

В терминале нажмите `Ctrl+C` для остановки бота.

---

## Частые проблемы

### "ModuleNotFoundError: No module named 'telebot'"
**Решение:** Убедитесь, что виртуальное окружение активировано и зависимости установлены:
```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### "ValueError: TELEGRAM_BOT_TOKEN is required"
**Решение:** Проверьте, что файл `.env` существует и содержит `TELEGRAM_BOT_TOKEN`

### "python: command not found"
**Решение:** Используйте `python3` вместо `python`:
```bash
python3 main.py
```

### Бот не отвечает
**Решение:** 
1. Проверьте правильность токена в `.env`
2. Убедитесь, что бот запущен (нет ошибок в консоли)
3. Проверьте интернет-соединение

---

## Автоматический запуск при старте системы (опционально)

Для macOS можно создать LaunchAgent:

1. Создайте файл `~/Library/LaunchAgents/com.makeupbot.plist`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.makeupbot</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/g.dvoryak/Desktop/makeup_courses_bot/.venv/bin/python</string>
        <string>/Users/g.dvoryak/Desktop/makeup_courses_bot/main.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/g.dvoryak/Desktop/makeup_courses_bot</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
```

2. Загрузите:
```bash
launchctl load ~/Library/LaunchAgents/com.makeupbot.plist
```

