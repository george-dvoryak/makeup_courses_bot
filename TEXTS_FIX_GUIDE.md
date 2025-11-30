# Исправление проблемы с загрузкой текстов из Google Sheets

## Проблема
Тексты загружаются из Google Sheets, но не используются в сообщениях бота.

## Возможные причины

### 1. Проблема с парсером Google Sheets
- Неправильное определение заголовка
- Пустые строки или неправильный формат
- Неправильное название вкладки

### 2. Проблема с контекстом бота
- Контекст не устанавливается перед вызовом `get_text_value`
- Контекст очищается слишком рано
- Кэш текстов не обновляется для разных ботов

### 3. Проблема с ключами
- Ключи в таблице не совпадают с ожидаемыми
- Регистр или пробелы в ключах

## Шаги по исправлению

### Шаг 1: Проверьте формат таблицы Texts

Вкладка `Texts` должна иметь формат:

| Ключ | Значение |
|------|----------|
| greeting_text | Привет! Я помогу выбрать и оплатить курс. |
| welcome_image_url | https://example.com/welcome.jpg | (опционально)
| catalog_intro | 📚 Каталог курсов\nВыберите интересующий курс: |
| catalog_image_url | https://example.com/catalog.jpg | (опционально)
| ... | ... |

**Важно:**
- Первая колонка - ключи (без пробелов в начале/конце)
- Вторая колонка - значения
- Первая строка может быть заголовком (пропускается автоматически)

### Шаг 2: Проверьте конфигурацию

Убедитесь, что в `.env` файле правильно заданы:
```
GSHEET_TEXTS_NAME_bot1=Texts
GSHEET_TEXTS_NAME_bot2=Texts
```

### Шаг 3: Запустите диагностику

1. **На локальной машине:**
   ```bash
   python3 test_texts_usage.py
   ```

2. **На PythonAnywhere:**
   Загрузите `test_texts_usage.py` и запустите:
   ```bash
   python3 test_texts_usage.py
   ```

### Шаг 4: Проверьте логи

При запуске бота в Server log должны быть строки:
```
[Texts] Loading texts for bot: bot1
[Texts] Loaded X text entries for bot1
[Texts] Sample keys: ['greeting_text', 'catalog_intro', ...]
```

При получении сообщения `/start`:
```
[Texts] get_text_value called: key='greeting_text', bot='bot1'
[Texts] Found value for 'greeting_text': Привет!...
```

### Шаг 5: Если проблема остается

Если тексты загружаются, но не используются в сообщениях:

1. **Проверьте логи** - какие ключи ищутся и какие доступны
2. **Сравните регистр** - `greeting_text` vs `Greeting_Text`
3. **Проверьте пробелы** - убедитесь, что ключи без лишних пробелов
4. **Проверьте кэширование** - возможно, загружены старые данные

### Шаг 6: Очистка кэша

Если нужно сбросить кэш текстов:
```python
from main import _texts_cache
_texts_cache.clear()
```

## Важно: правильные названия ключей

**ВНИМАНИЕ!** Названия ключей в Google Sheets должны **ТОЧНО** совпадать с названиями в коде. Регистр важен!

❌ Неправильно:
- `support_message` (не существует в коде)
- `Support Text` (неверный регистр)
- `support-text` (дефис вместо подчеркивания)

✅ Правильно:
- `support_text` (как в коде)

## Стандартные ключи, используемые в коде

| Ключ | Использование | Дефолтное значение |
|------|---------------|-------------------|
| `greeting_text` | Приветствие при /start | "Привет! Я помогу выбрать и оплатить курс." |
| `catalog_intro` | Заголовок каталога | "📚 Каталог курсов\nВыберите интересующий курс:" |
| `catalog_empty` | Каталог пуст | "Каталог пока пуст. Загляните позже." |
| `catalog_error` | Ошибка загрузки каталога | "Не удалось загрузить каталог. Попробуйте позже." |
| `support_text` | Текст поддержки (кнопка "Поддержка") | "Напишите нам в поддержку: @your_support или info@example.com" |
| `no_active_subscriptions` | Нет активных подписок | "У вас пока нет активных подписок." |
| `active_subscriptions_header` | Заголовок активных подписок | "📘 Ваши активные курсы:" |
| `purchase_success_message` | Успешная оплата | Сообщение об успешной оплате |

## Отладочные команды

```bash
# Проверить загрузку текстов
python3 -c "
from config import get_bot_config
from google_sheets import get_texts_data
from bot_context import set_bot_context, clear_bot_context

set_bot_context('bot1')
texts = get_texts_data('bot1')
print(f'Loaded {len(texts)} texts')
for k, v in list(texts.items())[:5]:
    print(f'{k}: {v[:50]}...')
clear_bot_context()
"

# Проверить get_text_value
python3 -c "
from main import get_text_value
from bot_context import set_bot_context, clear_bot_context

set_bot_context('bot1')
value = get_text_value('greeting_text', 'DEFAULT')
print(f'greeting_text: {value}')
clear_bot_context()
"
```
