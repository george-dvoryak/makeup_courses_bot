# Синхронизация кода с PythonAnywhere

## Быстрый способ (через Git)

### Шаг 1: На PythonAnywhere

```bash
cd ~/makeup_courses_bot

# Проверьте статус
git status

# Если есть изменения, закоммитьте их
git add .
git commit -m "Working version from PythonAnywhere"
git push origin feature/remove-robocasa
```

### Шаг 2: На локальной машине

```bash
cd ~/Desktop/makeup_courses_bot

# Получите изменения
git pull origin feature/remove-robocasa
```

Теперь у вас локально та же версия, что и на PythonAnywhere.

## Если Git не используется на PythonAnywhere

### Вариант A: Создать архив на PythonAnywhere

1. **На PythonAnywhere:**
   ```bash
   cd ~/makeup_courses_bot
   tar -czf code_backup.tar.gz *.py *.txt *.md .env.example
   ```

2. **Скачайте архив:**
   - PythonAnywhere → Files → `code_backup.tar.gz` → Download

3. **Локально распакуйте:**
   ```bash
   cd ~/Desktop/makeup_courses_bot
   tar -xzf code_backup.tar.gz
   ```

### Вариант B: Скопировать файлы вручную

1. **На PythonAnywhere** откройте файлы через Files tab
2. **Скопируйте содержимое** каждого файла
3. **Локально** вставьте содержимое в соответствующие файлы

### Вариант C: Инициализировать Git на PythonAnywhere

Если Git ещё не используется:

```bash
cd ~/makeup_courses_bot

# Инициализируйте репозиторий (если ещё не инициализирован)
git init

# Добавьте удалённый репозиторий
git remote add origin https://github.com/george-dvoryak/makeup_courses_bot.git

# Проверьте текущую ветку
git branch

# Если нужно, переключитесь на нужную ветку
git checkout feature/remove-robocasa

# Закоммитьте текущее состояние
git add .
git commit -m "Working version from PythonAnywhere"

# Отправьте на GitHub
git push origin feature/remove-robocasa
```

## После синхронизации

1. **Отредактируйте код локально**
2. **Протестируйте** (если возможно)
3. **Закоммитьте изменения:**
   ```bash
   git add .
   git commit -m "Описание изменений"
   git push origin feature/remove-robocasa
   ```

4. **На PythonAnywhere обновите код:**
   ```bash
   cd ~/makeup_courses_bot
   git pull origin feature/remove-robocasa
   ```

5. **Перезагрузите веб-приложение:**
   - Web → Reload

## Важные файлы для синхронизации

Основные файлы, которые нужно синхронизировать:
- `main.py` - основной код бота
- `webhook_app.py` - WSGI приложение
- `config.py` - конфигурация
- `db.py` - работа с базой данных
- `google_sheets.py` - интеграция с Google Sheets
- `requirements.txt` - зависимости

**НЕ синхронизируйте:**
- `.env` - содержит секретные данные (токены, пароли)
- `bot.db` - база данных (может быть большой)
- `venv/` - виртуальное окружение
- `__pycache__/` - кэш Python

## Рекомендация

**Используйте Git** - это самый надёжный способ синхронизации:
- ✅ История изменений
- ✅ Легко откатить изменения
- ✅ Работа в команде
- ✅ Резервная копия на GitHub

Если Git не настроен на PythonAnywhere, настройте его один раз, и дальше будет проще.

