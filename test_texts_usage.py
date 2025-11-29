#!/usr/bin/env python3
"""
Тестирование использования текстов в сообщениях бота
"""
import sys
import os
import time

# Добавляем пути
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 80)
print("ТЕСТИРОВАНИЕ ИСПОЛЬЗОВАНИЯ ТЕКСТОВ В СООБЩЕНИЯХ БОТА")
print("=" * 80)

try:
    # Проверяем наличие необходимых модулей
    try:
        from dotenv import load_dotenv
    except ImportError:
        print("❌ Не установлен python-dotenv. Установите командой:")
        print("   pip install python-dotenv")
        sys.exit(1)

    from config import get_available_bots, get_bot_config
    from google_sheets import get_texts_data
    from bot_context import set_bot_context, clear_bot_context, get_bot_context
    from main import get_text_value, _get_texts_for_bot, _texts_cache

    bots = get_available_bots()
    if not bots:
        print("❌ Не найдено ни одного бота в конфигурации.")
        sys.exit(1)

    print(f"Найдено ботов: {', '.join(bots)}\n")

    # Очищаем кэш для чистого теста
    _texts_cache.clear()
    print("✅ Кэш текстов очищен\n")

    for bot_name in bots:
        print("=" * 80)
        print(f"ТЕСТ ДЛЯ БОТА: {bot_name}")
        print("=" * 80)

        config = get_bot_config(bot_name)
        gsheet_id = config.get('GSHEET_ID', '')
        texts_name = config.get('GSHEET_TEXTS_NAME', 'Texts')

        if not gsheet_id:
            print(f"  ❌ GSHEET_ID не задан для бота {bot_name}. Пропускаем.")
            continue

        print(f"  GSHEET_ID: {gsheet_id}")
        print(f"  GSHEET_TEXTS_NAME: {texts_name}")
        print()

        # Устанавливаем контекст бота
        set_bot_context(bot_name)
        print(f"  Контекст установлен: {get_bot_context()}")

        try:
            # 1. Тестируем прямую загрузку текстов
            print("  1. ➜ Тестируем прямую загрузку текстов...")
            texts = get_texts_data(bot_name)
            print(f"     ✅ Загружено {len(texts)} текстов")

            if texts:
                print("     Примеры текстов:")
                for idx, (key, value) in enumerate(list(texts.items())[:5], 1):
                    value_preview = value[:40] + "..." if len(value) > 40 else value
                    print(f"       {idx}. {key:25s} = {value_preview}")
                if len(texts) > 5:
                    print(f"       ... и еще {len(texts) - 5} записей")
            print()

            # 2. Тестируем функцию get_text_value (без логирования)
            print("  2. ➜ Тестируем get_text_value для стандартных ключей...")
            standard_keys = [
                "greeting_text",
                "catalog_intro",
                "catalog_empty",
                "catalog_error",
                "support_text",
                "no_active_subscriptions",
                "active_subscriptions_header",
                "purchase_success_message"
            ]

            for key in standard_keys:
                try:
                    # Временно отключаем логирование для чистоты вывода
                    import main
                    original_print = print

                    def silent_print(*args, **kwargs):
                        pass

                    # Заменяем print на silent_print временно
                    main.print = silent_print

                    value = get_text_value(key, f"[DEFAULT_FOR_{key.upper()}]")

                    # Возвращаем нормальный print
                    main.print = original_print

                    if value.startswith("[DEFAULT_FOR_"):
                        print(f"     ❌ {key:25s} = {value}")
                    else:
                        value_preview = value[:40] + "..." if len(value) > 40 else value
                        print(f"     ✅ {key:25s} = {value_preview}")

                except Exception as e:
                    print(f"     ⚠️  {key:25s} = ОШИБКА: {e}")

            print()

            # 3. Тестируем кэширование
            print("  3. ➜ Тестируем кэширование...")
            cached_data = _texts_cache.get(bot_name)
            if cached_data:
                cache_age = time.time() - cached_data["ts"]
                print(f"     ✅ Данные в кэше, возраст: {cache_age:.1f} сек")
                print(f"     Количество текстов в кэше: {len(cached_data['data'])}")
            else:
                print("     ❌ Данные не найдены в кэше")

        except Exception as e:
            print(f"  ❌ Ошибка при тестировании: {e}")
            import traceback
            traceback.print_exc()
        finally:
            clear_bot_context()
            print(f"  Контекст очищен: {get_bot_context()}")
            print()

    # 4. Тестируем симуляцию обработки сообщения
    print("  4. ➜ Тестируем симуляцию обработки сообщения...")
    print("     Имитируем обработку /start для проверки контекста")

    # Имитируем установку контекста как в webhook
    set_bot_context(bot_name)
    try:
        # Имитируем вызовы из handle_start
        from main import get_current_bot, build_main_menu, format_text_for_telegram

        current_bot = get_current_bot()
        print(f"     ✅ get_current_bot() вернул: {type(current_bot).__name__}")

        greeting = format_text_for_telegram(get_text_value("greeting_text", "Привет!"))
        print(f"     ✅ greeting_text получен: {len(greeting)} символов")

        # Проверяем build_main_menu
        menu = build_main_menu(123456789)
        print(f"     ✅ build_main_menu() создал меню с {len(menu.keyboard)} строками")

        print("     ✅ Контекст работает корректно в рамках обработки")

    except Exception as e:
        print(f"     ❌ Ошибка в симуляции: {e}")
        import traceback
        traceback.print_exc()
    finally:
        clear_bot_context()

    print()

    print("=" * 80)
    print("ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
    print("=" * 80)
    print("\nРЕЗУЛЬТАТЫ:")
    print("• Если тексты загружаются, но get_text_value возвращает дефолты,")
    print("  значит проблема в установке контекста бота")
    print("• Если тексты не загружаются вообще, проверьте:")
    print("  - GSHEET_ID для каждого бота")
    print("  - Название вкладки GSHEET_TEXTS_NAME")
    print("  - Доступность Google Sheets")
    print("• Логи в Server log покажут, какой бот используется при обработке сообщений")
    print("• Если проблема только в runtime, проверьте что контекст очищается правильно")

except Exception as e:
    print(f"❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
