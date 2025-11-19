# PRODAMUS_TEST_WEBHOOK_URL - Что это и как использовать

## Что это?

`PRODAMUS_TEST_WEBHOOK_URL` — это **опциональная** переменная для отладки webhook запросов от Prodamus.

Когда она установлена, все webhook данные **дублируются** на этот URL для удобного просмотра и отладки.

## Зачем это нужно?

1. **Просмотр всех запросов** от Prodamus в реальном времени
2. **Отладка** структуры данных
3. **Проверка подписей** и параметров
4. **Тестирование** без необходимости проверять логи на сервере

## Как получить URL?

### Вариант 1: webhook.site (рекомендуется)

1. Откройте https://webhook.site
2. Скопируйте уникальный URL (например: `https://webhook.site/abc123-def456-ghi789`)
3. Добавьте в `.env`:
   ```env
   PRODAMUS_TEST_WEBHOOK_URL=https://webhook.site/abc123-def456-ghi789
   ```

**Преимущества:**
- ✅ Бесплатно
- ✅ Не требует регистрации
- ✅ Удобный интерфейс
- ✅ История запросов
- ✅ Можно просматривать headers, body, query params

### Вариант 2: requestbin.com

1. Откройте https://requestbin.com
2. Создайте новый bin
3. Скопируйте URL
4. Добавьте в `.env`

### Вариант 3: ngrok (для локальной разработки)

Если тестируете локально:

1. Установите ngrok: https://ngrok.com
2. Запустите: `ngrok http 5000` (или ваш порт)
3. Скопируйте URL (например: `https://abc123.ngrok.io`)
4. Добавьте в `.env`

## Как это работает?

Когда `PRODAMUS_TEST_WEBHOOK_URL` установлен, код автоматически отправляет копию всех webhook данных на этот URL:

```python
# В main.py есть функция forward_to_test_webhook
# Она вызывается для каждого webhook запроса:
# - /prodamus/result
# - /prodamus/success  
# - /prodamus/fail
```

## Пример использования

### 1. Получите URL от webhook.site

1. Откройте https://webhook.site
2. Скопируйте URL (например: `https://webhook.site/abc123-def456`)

### 2. Добавьте в .env

```env
PRODAMUS_TEST_WEBHOOK_URL=https://webhook.site/abc123-def456
```

### 3. Перезапустите приложение

На PythonAnywhere:
- Web → Reload

### 4. Проведите тестовую оплату

1. Откройте бота
2. Выберите курс → Prodamus
3. Оплатите тестовой картой

### 5. Проверьте webhook.site

На странице webhook.site вы увидите:
- Все запросы от Prodamus
- Headers
- Body/Form data
- Query parameters
- Время запроса

## Что вы увидите на webhook.site?

### Result URL запрос (POST):
```
order_num=PROD-20251112180945692-314112021-3
order_id=37934589
sum=100.00
currency=rub
customer_email=user@example.com
payment_status=success
payment_status_description=Успешная оплата
signature=abc123...
```

### Success URL запрос (GET):
```
_payform_status=success
_payform_id=37934589
_payform_order_id=PROD-20251112180945692-314112021-3
_payform_sign=abc123...
```

## Важно!

- ⚠️ Это **только для отладки** - не используйте в продакшне
- ⚠️ URL от webhook.site **временный** - создается новый при каждом открытии
- ⚠️ Данные на webhook.site **публичные** - не используйте для реальных платежей
- ✅ Для тестирования это отличный инструмент!

## Когда использовать?

✅ **Используйте когда:**
- Тестируете интеграцию
- Отлаживаете проблемы с webhooks
- Хотите увидеть структуру данных
- Проверяете подписи

❌ **Не используйте когда:**
- Работаете в продакшне с реальными платежами
- Нужна безопасность данных

## Пример .env

```env
# Для тестирования (с webhook.site)
PRODAMUS_TEST_WEBHOOK_URL=https://webhook.site/abc123-def456-ghi789

# Для продакшна (оставьте пустым или удалите)
# PRODAMUS_TEST_WEBHOOK_URL=
```

## Альтернатива: проверка логов

Если не хотите использовать внешний сервис, можно просто проверять логи на PythonAnywhere:

- **Error log** - там будут все логи с префиксом `[Prodamus]`
- Все webhook запросы логируются автоматически

Но webhook.site удобнее для визуального просмотра!

