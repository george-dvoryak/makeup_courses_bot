# Решение проблемы "divergent branches" при git pull

## Проблема

При выполнении `git pull` возникает ошибка:
```
hint: You have divergent branches and need to specify how to reconcile them.
fatal: Need to specify how to reconcile divergent branches.
```

## Быстрое решение

### Вариант 1: Использовать merge (рекомендуется)

```bash
git pull --no-rebase origin feature/remove-robocasa
```

### Вариант 2: Настроить по умолчанию

```bash
git config pull.rebase false
```

После этого обычный `git pull` будет работать без проблем.

## Объяснение стратегий

### 1. Merge (объединение)
```bash
git pull --no-rebase
# или
git config pull.rebase false
```
- **Что делает:** Создаёт merge commit, объединяя локальные и удалённые изменения
- **Когда использовать:** Когда работаете в команде или хотите сохранить полную историю
- **Плюсы:** Сохраняет всю историю коммитов
- **Минусы:** Создаёт дополнительные merge коммиты

### 2. Rebase (перемещение)
```bash
git pull --rebase
# или
git config pull.rebase true
```
- **Что делает:** Перемещает ваши локальные коммиты поверх удалённых
- **Когда использовать:** Когда хотите линейную историю без merge коммитов
- **Плюсы:** Чистая линейная история
- **Минусы:** Может быть сложнее при конфликтах

### 3. Fast-forward only (только быстрая перемотка)
```bash
git pull --ff-only
# или
git config pull.ff only
```
- **Что делает:** Обновляет только если можно сделать fast-forward (без merge)
- **Когда использовать:** Когда хотите избежать merge коммитов, но только если нет расхождений
- **Плюсы:** Самый безопасный вариант
- **Минусы:** Может не работать при расхождениях

## Рекомендация для этого проекта

Используйте **merge** стратегию (по умолчанию):

```bash
git config pull.rebase false
```

Это безопаснее и проще для работы в команде.

## Если ветки действительно разошлись

Если локальная и удалённая ветки действительно имеют разные коммиты:

### 1. Посмотреть различия:
```bash
git log --oneline --graph --all -10
git log --oneline HEAD..origin/feature/remove-robocasa  # Что есть на удалённой
git log --oneline origin/feature/remove-robocasa..HEAD   # Что есть локально
```

### 2. Выбрать стратегию:

**Если хотите сохранить оба набора изменений:**
```bash
git pull --no-rebase
# Разрешите конфликты если есть
git push
```

**Если хотите взять только удалённые изменения (потеряете локальные):**
```bash
git fetch origin
git reset --hard origin/feature/remove-robocasa
```

**Если хотите отправить только локальные изменения:**
```bash
git push --force-with-lease origin feature/remove-robocasa
```

⚠️ **Внимание:** `--force` может перезаписать удалённые изменения!

## Проверка текущей конфигурации

```bash
git config pull.rebase
# Покажет: false, true, или (пусто) - значит не настроено
```

## Глобальная настройка (для всех репозиториев)

```bash
git config --global pull.rebase false
```

## Частые проблемы

### Проблема: "Already up to date" но всё равно ошибка

**Решение:** Ветки синхронизированы, просто настройте стратегию:
```bash
git config pull.rebase false
```

### Проблема: Конфликты при merge

**Решение:**
1. Разрешите конфликты в файлах
2. Добавьте файлы: `git add .`
3. Завершите merge: `git commit`
4. Отправьте: `git push`

### Проблема: Хочу отменить merge

**Решение:**
```bash
git merge --abort  # Если merge ещё не завершён
# или
git reset --hard HEAD~1  # Если merge уже сделан (потеряете изменения!)
```

## Быстрая команда для обновления

После настройки стратегии, просто используйте:

```bash
git pull
```

Или с указанием ветки:

```bash
git pull origin feature/remove-robocasa
```

