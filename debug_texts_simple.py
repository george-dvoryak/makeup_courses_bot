#!/usr/bin/env python3
"""
Простая диагностика текстов из Google Sheets
"""
import sys
import os

# Добавляем пути
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 60)
print("ПРОСТАЯ ДИАГНОСТИКА ТЕКСТОВ")
print("=" * 60)

try:
    from dotenv import load_dotenv
    load_dotenv()

    from config import get_available_bots, get_bot_config
    from google_sheets import get_texts_data
    from bot_context import set_bot_context, clear_bot_context

    bots = get_available_bots()
    if not bots:
        print("❌ Не найдено ни одного бота")
        sys.exit(1)

    print(f"Найдено ботов: {', '.join(bots)}\n")

    for bot_name in bots:
        print(f"БОТ: {bot_name}")
        print("-" * 40)

        config = get_bot_config(bot_name)
        gsheet_id = config.get('GSHEET_ID', '')
        texts_name = config.get('GSHEET_TEXTS_NAME', 'Texts')

        print(f"GSHEET_ID: {gsheet_id}")
        print(f"GSHEET_TEXTS_NAME: {texts_name}")

        if not gsheet_id:
            print("❌ GSHEET_ID не задан\n")
            continue

        set_bot_context(bot_name)
        try:
            texts = get_texts_data(bot_name)

            if not texts:
                print("❌ Тексты не загружены!\n")
                continue

            print(f"✅ Загружено {len(texts)} текстов")

            # Проверяем основные ключи
            required_keys = ['greeting_text', 'catalog_intro', 'catalog_empty', 'catalog_error']
            optional_keys = ['welcome_image_url', 'catalog_image_url']

            print("\nПРОВЕРКА ОСНОВНЫХ КЛЮЧЕЙ:")
            for key in required_keys:
                if key in texts:
                    value = texts[key][:60] + "..." if len(texts[key]) > 60 else texts[key]
                    print(f"✅ {key}: {value}")
                else:
                    print(f"❌ {key}: НЕ НАЙДЕН")

            print("\nПРОВЕРКА ОПЦИОНАЛЬНЫХ КЛЮЧЕЙ (для картинок):")
            for key in optional_keys:
                if key in texts and texts[key].strip():
                    value = texts[key][:60] + "..." if len(texts[key]) > 60 else texts[key]
                    print(f"✅ {key}: {value}")
                else:
                    print(f"⚠️  {key}: НЕ ЗАДАН (картинка не будет отправляться)")

            print(f"\nВСЕ ДОСТУПНЫЕ КЛЮЧИ ({len(texts)}):")
            for key in sorted(texts.keys()):
                value = texts[key][:40] + "..." if len(texts[key]) > 40 else texts[key]
                print(f"  {key}: {value}")

        except Exception as e:
            print(f"❌ Ошибка: {e}")
        finally:
            clear_bot_context()

        print("\n" + "=" * 60)

    print("КАК ДОБАВИТЬ ТЕКСТЫ В GOOGLE SHEETS:")
    print("1. Откройте таблицу по ссылке из GSHEET_ID")
    print("2. Создайте/откройте вкладку 'Texts' (или укажите имя в GSHEET_TEXTS_NAME)")
    print("3. В первой колонке - ключи, во второй - значения:")
    print("   | greeting_text | Привет! Добро пожаловать в наш бот! |")
    print("   | catalog_intro | 📚 Наши курсы:\nВыберите курс |")
    print("4. Сохраните и перезапустите бота")

except Exception as e:
    print(f"❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()
