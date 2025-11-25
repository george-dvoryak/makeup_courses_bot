# Настройка Webhook URL в Prodamus

## Проблема

> ℹ️ Бот обрабатывает только `Result URL`. Поля `Success` и `Fail` в Prodamus теперь используются исключительно для редиректа пользователя и не влияют на выдачу доступа.

После успешной оплаты бот не получает уведомление и не выдает доступ. Это происходит потому, что **URL для уведомлений не настроен в Prodamus**.

## Решение

### Шаг 1: Откройте настройки Prodamus

1. Войдите в личный кабинет Prodamus
2. Перейдите в раздел **"Настройка уведомлений"** (не "Настройка адресов"!)
3. Найдите поле **"URL адреса для уведомлений"**

### Шаг 2: Укажите Result URL

В поле **"URL адреса для уведомлений"** укажите:

```
https://goshadvoryak.pythonanywhere.com/prodamus/result
```

**Важно:**
- Это **НЕ** Success URL и **НЕ** Fail URL
- Это отдельное поле для **webhook уведомлений**
- Prodamus будет отправлять POST запросы на этот URL при изменении статуса платежа

### Шаг 3: Настройте Success и Fail URL (опционально)

В разделе **"Настройка адресов"** (отдельный раздел):

- **Success URL:** `https://goshadvoryak.pythonanywhere.com/prodamus/success`
- **Fail URL:** `https://goshadvoryak.pythonanywhere.com/prodamus/fail`

Эти URL используются для редиректа пользователя после оплаты, но **не критичны** для работы бота.

### Шаг 4: Сохраните настройки

Нажмите кнопку **"Сохранить"** в разделе "Настройка уведомлений".

### Шаг 5: Проверьте настройки

После сохранения:

1. Проведите тестовую оплату
2. Проверьте логи на PythonAnywhere:
   - Web → Error log
   - Ищите записи с префиксом `[Prodamus Result]`

## Что происходит после настройки?

1. Пользователь оплачивает курс через Prodamus
2. Prodamus отправляет **POST запрос** на `/prodamus/result` с данными о платеже
3. Бот проверяет подпись и обрабатывает платеж
4. Бот выдает доступ пользователю и отправляет сообщение с ссылкой на канал

## Проверка работы

### Вариант 1: Проверка логов

После тестовой оплаты проверьте Error log на PythonAnywhere:

```
[2025-11-14 XX:XX:XX] [Prodamus Result] Received notification: {...}
[2025-11-14 XX:XX:XX] [Prodamus Result] ✅ Signature verified
[2025-11-14 XX:XX:XX] [Prodamus Result] ✅ Successfully processed payment...
```

### Вариант 2: Использование webhook.site

1. Откройте https://webhook.site
2. Скопируйте уникальный URL
3. Добавьте в `.env`:
   ```env
   PRODAMUS_TEST_WEBHOOK_URL=https://webhook.site/ваш-id
   ```
4. Проведите тестовую оплату
5. Проверьте webhook.site - там будут все запросы от Prodamus

## Важные моменты

1. **Result URL обязателен** - без него бот не получит уведомление о платеже
2. **Success/Fail URL опциональны** - используются только для редиректа пользователя
3. **Подпись проверяется автоматически** - если `PRODAMUS_SECRET_KEY` настроен в `.env`
4. **Логи пишутся в Error log** - используйте `sys.stderr` для видимости на PythonAnywhere

## Документация Prodamus

Согласно документации Prodamus:
- https://help.prodamus.ru/payform/integracii/rest-api/url-dlya-uvedomlenii-i-sekretnyi-klyuch

**URL для уведомлений** - это отдельный URL, на который Prodamus отправляет уведомления о статусе платежа.

## Если не работает

1. Проверьте, что URL указан правильно (без лишних пробелов, с `https://`)
2. Проверьте, что настройки сохранены в Prodamus
3. Проверьте Error log на PythonAnywhere
4. Проверьте, что `ENABLE_PRODAMUS=True` в `.env`
5. Проверьте, что `PRODAMUS_SECRET_KEY` указан правильно в `.env`

