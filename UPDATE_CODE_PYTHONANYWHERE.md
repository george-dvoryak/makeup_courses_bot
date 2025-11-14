# Как обновить код на PythonAnywhere

## Быстрый способ (если используете Git)

### Шаг 1: Откройте Bash консоль на PythonAnywhere

1. Зайдите на PythonAnywhere
2. Откройте вкладку **Consoles**
3. Создайте или откройте **Bash console**

### Шаг 2: Обновите код из репозитория

```bash
cd ~/makeup_courses_bot
git pull
```

Если вы работаете с конкретной веткой (например, `feature/remove-robocasa`):

```bash
cd ~/makeup_courses_bot
git fetch origin
git pull origin feature/remove-robocasa
```

### Шаг 3: Установите новые зависимости (если есть)

Если в `requirements.txt` появились новые пакеты:

```bash
pip install --user -r requirements.txt
```

Или если используете виртуальное окружение:

```bash
source venv/bin/activate
pip install -r requirements.txt
```

### Шаг 4: Перезагрузите веб-приложение

1. Перейдите на вкладку **Web**
2. Нажмите зеленую кнопку **Reload**
3. Подождите несколько секунд

### Шаг 5: Проверьте логи

1. На вкладке **Web** откройте **Error log**
2. Убедитесь, что нет ошибок
3. Должны быть сообщения:
   ```
   Webhook set to: https://goshadvoryak.pythonanywhere.com/webhook
   [Auto-Cleanup] Background cleanup scheduler started
   ```

### Шаг 6: Протестируйте бота

Отправьте команду `/start` боту в Telegram, чтобы убедиться, что всё работает.

## Если возникли конфликты при git pull

Если Git сообщает о конфликтах:

```bash
cd ~/makeup_courses_bot
git status  # Посмотреть статус
git stash   # Сохранить локальные изменения
git pull    # Обновить код
git stash pop  # Вернуть локальные изменения (если нужно)
```

Или если нужно принудительно обновить (⚠️ потеряете локальные изменения):

```bash
cd ~/makeup_courses_bot
git fetch origin
git reset --hard origin/feature/remove-robocasa  # или main/master
```

## Если не используете Git

### Вариант 1: Загрузка файлов через веб-интерфейс

1. Перейдите на вкладку **Files**
2. Откройте `/home/<ваш-username>/makeup_courses_bot/`
3. Загрузите обновленные файлы через кнопку **Upload**
4. Перезагрузите веб-приложение (Web → Reload)

### Вариант 2: Использование Git (рекомендуется)

Если код еще не под Git на PythonAnywhere:

```bash
cd ~
git clone https://github.com/george-dvoryak/makeup_courses_bot.git makeup_courses_bot
cd makeup_courses_bot
git checkout feature/remove-robocasa  # если нужна конкретная ветка
```

Затем настройте `.env` файл и перезагрузите веб-приложение.

## Обновление зависимостей

Если обновились зависимости в `requirements.txt`:

```bash
cd ~/makeup_courses_bot
pip install --user --upgrade -r requirements.txt
```

Или для конкретного пакета:

```bash
pip install --user --upgrade telebot flask
```

## Проверка обновления

После обновления кода проверьте:

1. **Версия кода:**
   ```bash
   cd ~/makeup_courses_bot
   git log -1  # Последний коммит
   ```

2. **Работа бота:**
   - Отправьте `/start` боту
   - Проверьте ответ

3. **Логи:**
   - Web → Error log (должны быть сообщения о запуске)
   - Web → Server log (общие сообщения сервера)

## Автоматическое обновление (опционально)

Можно создать scheduled task для автоматического обновления:

1. Перейдите на вкладку **Tasks**
2. Создайте новую задачу:
   - **Command**: `cd ~/makeup_courses_bot && git pull && touch /var/www/goshadvoryak_pythonanywhere_com_wsgi.py`
   - **Hour**: `*` (каждый час) или конкретное время
   - **Minute**: `0`
3. Сохраните

**Примечание:** `touch` команда перезагружает веб-приложение. Используйте осторожно!

## Частые проблемы

### Проблема: "Permission denied" при git pull

**Решение:**
```bash
cd ~/makeup_courses_bot
git config --global --add safe.directory ~/makeup_courses_bot
git pull
```

### Проблема: "Could not resolve hostname"

**Решение:** Проверьте интернет-соединение на PythonAnywhere. На free tier могут быть ограничения.

### Проблема: Бот не работает после обновления

**Решение:**
1. Проверьте Error log
2. Убедитесь, что `.env` файл не был перезаписан
3. Проверьте, что все зависимости установлены
4. Перезагрузите веб-приложение еще раз

### Проблема: Конфликты в .env файле

**Решение:** `.env` файл обычно не должен быть в Git. Если он был изменен локально:

```bash
cd ~/makeup_courses_bot
git checkout -- .env  # Вернуть оригинальный .env из репозитория
# Затем вручную обновите нужные переменные
```

## Чеклист обновления

- [ ] Открыл Bash консоль на PythonAnywhere
- [ ] Перешел в директорию проекта: `cd ~/makeup_courses_bot`
- [ ] Обновил код: `git pull`
- [ ] Установил новые зависимости (если есть): `pip install --user -r requirements.txt`
- [ ] Перезагрузил веб-приложение: Web → Reload
- [ ] Проверил Error log на наличие ошибок
- [ ] Протестировал бота командой `/start`

## Рекомендации

1. **Делайте бэкап перед обновлением:**
   ```bash
   cp bot.db bot.db.backup
   ```

2. **Обновляйте в нерабочее время** (если возможно)

3. **Проверяйте изменения:**
   ```bash
   git log --oneline -10  # Последние 10 коммитов
   git diff HEAD~1  # Изменения в последнем коммите
   ```

4. **Тестируйте локально** перед обновлением на продакшене

5. **Следите за логами** после обновления

