# Как разрешить конфликт слияния в webhook_app.py

## Если вы получили сообщение о конфликте

```
CONFLICT (content): Merge conflict in webhook_app.py
Automatic merge failed; fix conflicts and then commit the result.
```

## Шаг 1: Проверьте конфликт

Откройте файл `webhook_app.py` и найдите маркеры конфликта:

```
<<<<<<< HEAD
(ваш локальный код)
=======
(код из удалённой ветки)
>>>>>>> origin/feature/remove-robocasa
```

## Шаг 2: Разрешите конфликт

У вас есть 3 варианта:

### Вариант A: Оставить локальную версию (ваши изменения)

Удалите маркеры конфликта и оставьте только ваш код:

```python
# Оставить только код между <<<<<<< HEAD и =======
# Удалить всё от ======= до >>>>>>> origin/feature/remove-robocasa
```

### Вариант B: Взять удалённую версию

Удалите маркеры конфликта и оставьте только код из удалённой ветки:

```python
# Удалить всё от <<<<<<< HEAD до =======
# Оставить только код между ======= и >>>>>>> origin/feature/remove-robocasa
```

### Вариант C: Объединить оба варианта (рекомендуется)

Оставьте нужные части из обеих версий, удалив маркеры конфликта.

## Шаг 3: Сохраните файл

После разрешения конфликта сохраните файл без маркеров конфликта.

## Шаг 4: Добавьте файл в staging

```bash
git add webhook_app.py
```

## Шаг 5: Завершите merge

```bash
git commit -m "Merge: разрешён конфликт в webhook_app.py"
```

Или просто:

```bash
git commit
```

Git автоматически создаст сообщение коммита для merge.

## Шаг 6: Отправьте изменения

```bash
git push origin feature/remove-robocasa
```

## Если хотите отменить merge

Если вы передумали и хотите отменить merge:

```bash
git merge --abort
```

Это вернёт вас к состоянию до начала merge.

## Пример разрешения конфликта

**До (с конфликтом):**
```python
# Health check endpoint
<<<<<<< HEAD
@app.route('/', methods=['GET'])
def health_check():
    """Health check endpoint to verify app is running"""
    return "OK", 200
=======
# No health check in remote version
>>>>>>> origin/feature/remove-robocasa

# Reset and set webhook
```

**После (разрешённый конфликт):**
```python
# Health check endpoint
@app.route('/', methods=['GET'])
def health_check():
    """Health check endpoint to verify app is running"""
    return "OK", 200

# Reset and set webhook
```

## Проверка после разрешения

1. Убедитесь, что файл компилируется:
   ```bash
   python3 -m py_compile webhook_app.py
   ```

2. Проверьте синтаксис:
   ```bash
   python3 -c "import webhook_app"
   ```

3. Убедитесь, что нет маркеров конфликта:
   ```bash
   grep -n "<<<<<<< HEAD\|=======\|>>>>>>>" webhook_app.py
   ```
   Должно быть пусто.

## Текущее состояние

Если вы видите это сообщение, но конфликт уже разрешён:

1. Проверьте статус:
   ```bash
   git status
   ```

2. Если файл в состоянии "both modified", добавьте его:
   ```bash
   git add webhook_app.py
   git commit -m "Merge: разрешён конфликт"
   ```

3. Если всё чисто, просто продолжайте работу.

## Автоматическое разрешение (если возможно)

Если конфликт простой, можно использовать стратегию:

**Взять локальную версию:**
```bash
git checkout --ours webhook_app.py
git add webhook_app.py
git commit
```

**Взять удалённую версию:**
```bash
git checkout --theirs webhook_app.py
git add webhook_app.py
git commit
```

⚠️ **Внимание:** Это перезапишет файл полностью одной из версий!



