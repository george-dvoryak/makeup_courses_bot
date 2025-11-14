# Исправление конфликта merge на PythonAnywhere

## Проблема

При выполнении `git pull` на PythonAnywhere:
```
error: Pulling is not possible because you have unmerged files.
hint: Fix them up in the work tree, and then use 'git add/rm <file>'
hint: as appropriate to mark resolution and make a commit.
```

## Решение

### Шаг 1: Проверьте какие файлы в конфликте

На PythonAnywhere в Bash консоли выполните:

```bash
cd ~/makeup_courses_bot
git status
```

Вы увидите список файлов с конфликтами (обычно помечены как "both modified").

### Шаг 2: Посмотрите конфликт в файле

```bash
git diff webhook_app.py
```

Или откройте файл в редакторе и найдите маркеры:
- `<<<<<<< HEAD` - начало вашей версии
- `=======` - разделитель
- `>>>>>>> origin/feature/remove-robocasa` - конец удалённой версии

### Шаг 3: Разрешите конфликт

У вас есть 3 варианта:

#### Вариант A: Взять удалённую версию (рекомендуется, если локально всё работает)

```bash
cd ~/makeup_courses_bot
git checkout --theirs webhook_app.py
git add webhook_app.py
git commit -m "Merge: разрешён конфликт, использована удалённая версия"
```

#### Вариант B: Взять локальную версию (если на PythonAnywhere были важные изменения)

```bash
cd ~/makeup_courses_bot
git checkout --ours webhook_app.py
git add webhook_app.py
git commit -m "Merge: разрешён конфликт, использована локальная версия"
```

#### Вариант C: Разрешить вручную (если нужно объединить изменения)

1. Откройте файл в редакторе:
   ```bash
   nano webhook_app.py
   # или используйте встроенный редактор PythonAnywhere
   ```

2. Найдите маркеры конфликта и разрешите их вручную

3. Сохраните файл

4. Добавьте и закоммитьте:
   ```bash
   git add webhook_app.py
   git commit -m "Merge: разрешён конфликт вручную"
   ```

### Шаг 4: Проверьте что конфликт разрешён

```bash
git status
```

Должно показать "nothing to commit, working tree clean" или список изменений без конфликтов.

### Шаг 5: Завершите merge (если нужно)

Если всё ещё есть активный merge:

```bash
git commit -m "Merge: завершено слияние"
```

### Шаг 6: Отправьте изменения (если нужно)

```bash
git push origin feature/remove-robocasa
```

## Быстрое решение (если не важны локальные изменения на PythonAnywhere)

Если на PythonAnywhere не было важных локальных изменений, самый простой способ:

```bash
cd ~/makeup_courses_bot

# Отменить текущий merge
git merge --abort

# Взять последнюю версию из удалённого репозитория
git fetch origin
git reset --hard origin/feature/remove-robocasa

# Теперь можно делать pull
git pull
```

⚠️ **Внимание:** `git reset --hard` удалит все локальные изменения на PythonAnywhere!

## Альтернатива: Пересоздать клон

Если ничего не помогает, можно пересоздать клон:

```bash
cd ~
mv makeup_courses_bot makeup_courses_bot.backup
git clone -b feature/remove-robocasa https://github.com/george-dvoryak/makeup_courses_bot.git makeup_courses_bot
cd makeup_courses_bot

# Скопировать .env файл из backup
cp ../makeup_courses_bot.backup/.env .

# Перезагрузить веб-приложение
# Web → Reload
```

## Проверка после исправления

1. Убедитесь, что нет конфликтов:
   ```bash
   git status
   ```

2. Проверьте, что файлы корректны:
   ```bash
   python3.10 -m py_compile webhook_app.py
   ```

3. Перезагрузите веб-приложение:
   - Web → Reload

4. Проверьте логи:
   - Web → Error log
   - Должны быть сообщения о запуске

## Частые проблемы

### Проблема: "fatal: You have not concluded your merge"

**Решение:**
```bash
git merge --abort  # Отменить merge
# или
git commit -m "Merge: завершено"  # Завершить merge
```

### Проблема: Конфликт в нескольких файлах

**Решение:** Разрешите каждый файл отдельно:
```bash
git checkout --theirs <файл1>
git checkout --theirs <файл2>
git add .
git commit -m "Merge: разрешены все конфликты"
```

### Проблема: Забыл что изменял локально

**Решение:** Посмотрите изменения:
```bash
git diff HEAD
git log --oneline -5
```

