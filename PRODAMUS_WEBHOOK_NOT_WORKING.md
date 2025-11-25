# Проблема: Prodamus webhook не работает

> ℹ️ Начиная с актуальной версии бота мы используем только `Result URL` для обработки платежей. `Success`/`Fail` нужны лишь для редиректа пользователя и не влияют на выдачу доступа.

## Симптомы

- ✅ Success URL вызывается (пользователь перенаправляется после оплаты)
- ❌ Result URL (webhook) НЕ вызывается (нет логов `[Prodamus Result]`)
- ❌ Доступ не выдается пользователю

## Причина

**Prodamus не отправляет уведомление на `/prodamus/result`**, потому что URL для уведомлений не настроен или настроен неправильно в личном кабинете Prodamus.

## Решение

### Шаг 1: Проверьте настройки в Prodamus

1. Войдите в личный кабинет Prodamus
2. Перейдите в раздел **"Настройка уведомлений"** (НЕ "Настройка адресов"!)
3. Найдите поле **"URL адреса для уведомлений"**
4. Убедитесь, что указан правильный URL:
   ```
   https://goshadvoryak.pythonanywhere.com/prodamus/result
   ```
5. **Сохраните настройки**

### Шаг 2: Проверьте, что URL доступен

На PythonAnywhere выполните:

```bash
curl https://goshadvoryak.pythonanywhere.com/prodamus/result
```

Должен вернуться ответ (даже если это ошибка, главное - что endpoint доступен).

### Шаг 3: Проверьте pending payments

На PythonAnywhere выполните:

```bash
cd ~/makeup_courses_bot
python3.10 check_prodamus_payment.py PROD-20251119181623747-314112021-3
```

Это покажет:
- Есть ли заказ в `pending_payments`
- Был ли он обработан (есть ли в `purchases`)

### Шаг 4: Проверьте логи

После тестовой оплаты проверьте **Error log** на PythonAnywhere:

Ищите записи:
- `[Prodamus Result] Received notification` - если webhook пришел
- `[Prodamus Result] ❌` - если была ошибка обработки

## Важные моменты

### Success URL vs Result URL

- **Success URL** (`/prodamus/success`) - это редирект пользователя после оплаты. Он вызывается браузером пользователя.
- **Result URL** (`/prodamus/result`) - это webhook уведомление от Prodamus сервера. Он вызывается автоматически Prodamus для уведомления о статусе платежа.

**Result URL критичен для работы бота!** Без него бот не узнает о платеже.

### Настройка в Prodamus

В личном кабинете Prodamus есть **два разных раздела**:

1. **"Настройка адресов"** - для Success/Fail URL (редирект пользователя)
   - Success URL: `https://goshadvoryak.pythonanywhere.com/prodamus/success`
   - Fail URL: `https://goshadvoryak.pythonanywhere.com/prodamus/fail`

2. **"Настройка уведомлений"** - для Result URL (webhook уведомления) ⭐
   - URL адреса для уведомлений: `https://goshadvoryak.pythonanywhere.com/prodamus/result`

**Оба раздела нужно настроить!**

### Тестовый режим

Если `PRODAMUS_TEST_MODE=True`, убедитесь, что:
- В настройках Prodamus указан правильный URL для тестового режима
- Проверьте, не отключена ли отправка уведомлений для демо-платежей в настройках Prodamus

## Диагностика

### 1. Проверка pending payments

```bash
python3.10 check_prodamus_payment.py
```

Покажет все необработанные платежи.

### 2. Проверка конкретного заказа

```bash
python3.10 check_prodamus_payment.py PROD-20251119181623747-314112021-3
```

Покажет статус конкретного заказа.

### 3. Проверка доступности endpoint

```bash
curl -X POST https://goshadvoryak.pythonanywhere.com/prodamus/result \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "order_num=TEST&sum=100&payment_status=success"
```

Должен вернуть ответ (даже если это ошибка валидации).

## Если все еще не работает

1. **Проверьте настройки Prodamus еще раз** - возможно, настройки не сохранились
2. **Проверьте, что `ENABLE_PRODAMUS=True`** в `.env`
3. **Проверьте Error log** - там должны быть логи всех запросов
4. **Свяжитесь с поддержкой Prodamus** - возможно, есть проблемы с отправкой уведомлений в тестовом режиме

## Временное решение (ручная обработка)

Если webhook не работает, можно временно обработать платеж вручную:

1. Найдите заказ в `pending_payments`:
   ```bash
   python3.10 check_prodamus_payment.py PROD-20251119181623747-314112021-3
   ```

2. Используйте админ-команду для выдачи доступа (если есть такая команда)

3. Или обработайте платеж через SQL (не рекомендуется, только для экстренных случаев)

