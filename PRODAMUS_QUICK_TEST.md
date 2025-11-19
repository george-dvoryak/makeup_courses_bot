# Быстрое тестирование Prodamus

## Шаг 1: Проверка конфигурации

```bash
python3 check_prodamus_config.py
```

Это покажет:
- ✅ Текущие настройки
- ✅ Правильные URL для настройки в Prodamus
- ❌ Проблемы в конфигурации

## Шаг 2: Настройка webhooks в Prodamus

Войдите в личный кабинет Prodamus и настройте:

### Result URL (обязательно!)
```
https://goshadvoryak.pythonanywhere.com/prodamus/result
```
- Метод: **POST**
- Это URL для получения уведомлений о платежах

### Success URL (опционально)
```
https://goshadvoryak.pythonanywhere.com/prodamus/success
```
- Метод: **GET**
- Для редиректа пользователя

### Fail URL (опционально)
```
https://goshadvoryak.pythonanywhere.com/prodamus/fail
```
- Метод: **GET**
- Для редиректа пользователя

## Шаг 3: Тестирование endpoints

```bash
python3 test_prodamus_webhook.py
```

Этот скрипт отправит тестовые запросы и проверит доступность endpoints.

## Шаг 4: Тестовая оплата

1. Откройте бота в Telegram
2. Выберите курс
3. Нажмите "Prodamus"
4. Введите email (если запросит)
5. Перейдите на страницу оплаты
6. Используйте тестовую карту: `4111 1111 1111 1111`
7. Заполните любые данные (CVV: 123, срок: любая будущая дата)
8. Оплатите

## Шаг 5: Проверка логов

На PythonAnywhere проверьте **Error log**:

Должны появиться строки:
```
[Prodamus Result] Received notification: {...}
[Prodamus Result] Successfully processed payment for order PROD-...
```

## Что проверить

1. ✅ Webhook URL доступен из интернета
2. ✅ Secret Key правильный
3. ✅ Result URL настроен в Prodamus
4. ✅ Платеж обрабатывается (проверить логи)
5. ✅ Пользователь получает доступ к курсу

## Проблемы?

### Webhook не приходит
- Проверьте, что Result URL правильно настроен в Prodamus
- Убедитесь, что веб-приложение запущено
- Проверьте доступность URL: `curl https://goshadvoryak.pythonanywhere.com/prodamus/result`

### Invalid signature
- Проверьте, что `PRODAMUS_SECRET_KEY` правильный
- Убедитесь, что ключ соответствует тестовому/продакшн аккаунту

### Платеж не обрабатывается
- Проверьте логи - там будет указана причина
- Убедитесь, что order_id совпадает
- Проверьте сумму платежа

