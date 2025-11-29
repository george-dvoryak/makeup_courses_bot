#!/usr/bin/env python3
"""
Тестирование загрузки текстов из Google Sheets
"""
import sys
import os

# Добавляем пути
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 70)
print("ТЕСТИРОВАНИЕ ЗАГРУЗКИ ТЕКСТОВ ИЗ GOOGLE SHEETS")
print("=" * 70)

try:
    from config import get_available_bots, get_bot_config
    from google_sheets import get_texts_data
    from bot_context import set_bot_context, clear_bot_context

    bots = get_available_bots()
    if not bots:
        print("❌ Не найдено ни одного бота в конфигурации.")
        sys.exit(1)

    print(f"Найдено ботов: {', '.join(bots)}\n")

    for bot_name in bots:
        print("=" * 70)
        print(f"ТЕСТ ДЛЯ БОТА: {bot_name}")
        print("=" * 70)

        config = get_bot_config(bot_name)
        gsheet_id = config.get('GSHEET_ID', '')
        texts_name = config.get('GSHEET_TEXTS_NAME', 'Texts')
        use_api = config.get('GOOGLE_SHEETS_USE_API', False)

        if not gsheet_id:
            print(f"  ❌ GSHEET_ID не задан для бота {bot_name}. Пропускаем.")
            continue

        print(f"  GSHEET_ID: {gsheet_id}")
        print(f"  GSHEET_TEXTS_NAME: {texts_name}")
        print(f"  GOOGLE_SHEETS_USE_API: {use_api}")
        print()

        # Устанавливаем контекст бота
        set_bot_context(bot_name)

        try:
            print("  ➜ Загружаем тексты...")
            texts = get_texts_data(bot_name)

            if not texts:
                print("  ⚠️ Тексты не загружены или таблица пуста!")
                print("     Проверьте:")
                print(f"     - Существует ли вкладка '{texts_name}' в таблице")
                print(f"     - Есть ли данные в таблице (минимум 2 колонки: ключ и значение)")
                print(f"     - Правильно ли указан GSHEET_ID")
            else:
                print(f"  ✅ Загружено {len(texts)} текстовых записей")
                print()
                print("  Примеры загруженных текстов:")
                print("  " + "-" * 66)
                for idx, (key, value) in enumerate(list(texts.items())[:10], 1):
                    value_preview = value[:50] + "..." if len(value) > 50 else value
                    print(f"  {idx:2d}. {key:30s} = {value_preview}")
                if len(texts) > 10:
                    print(f"  ... и еще {len(texts) - 10} записей")
                print("  " + "-" * 66)
                print()

                # Проверяем наличие стандартных ключей
                standard_keys = [
                    "catalog_intro",
                    "catalog_empty",
                    "catalog_error",
                    "greeting_text",
                    "support_text",
                    "no_active_subscriptions",
                    "active_subscriptions_header",
                    "purchase_success_message"
                ]
                print("  Проверка стандартных ключей:")
                for key in standard_keys:
                    if key in texts:
                        print(f"    ✅ {key}")
                    else:
                        print(f"    ⚠️  {key} - отсутствует (будет использовано значение по умолчанию)")

        except Exception as e:
            print(f"  ❌ Ошибка при загрузке текстов: {e}")
            import traceback
            traceback.print_exc()
        finally:
            clear_bot_context()

        print()

    print("=" * 70)
    print("ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
    print("=" * 70)
    print("\nВАЖНО:")
    print("1. Убедитесь, что таблица Google Sheets доступна для чтения")
    print("2. Проверьте формат таблицы: первая колонка - ключ, вторая - значение")
    print("3. Если используется CSV (GOOGLE_SHEETS_USE_API=False), таблица должна быть публичной")
    print("4. Проверьте логи выше для детальной информации о загрузке")

except Exception as e:
    print(f"❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

