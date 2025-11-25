#!/usr/bin/env python3
"""
Полная диагностика мульти-ботовой установки на PythonAnywhere.
Скрипт проверяет:
  • Пути и виртуальное окружение
  • Наличие ключевых файлов
  • Установку зависимостей
  • Конфигурацию всех ботов
  • Подключение баз данных
  • Flask-приложение webhook_app_multi
  • WSGI конфигурацию
  • Webhook статусы Telegram для каждого бота
  • Доступность HTTP endpoint'ов
"""
import os
import sys
import json
import traceback
from pathlib import Path

try:
    import requests
except ImportError:
    requests = None

SEPARATOR = "=" * 80
project_path = Path(__file__).resolve().parent
default_project_root = project_path
default_venv = (project_path / "venv")
python_version = f"python{sys.version_info.major}.{sys.version_info.minor}"


def mask(value: str, visible: int = 6) -> str:
    if not value:
        return "<empty>"
    if len(value) <= visible:
        return value
    return value[:visible] + "..."


def print_header(title: str):
    print(f"\n{title}")
    print("-" * len(title))


def add_sys_paths():
    added = []
    user_site = None
    try:
        import site

        user_site = site.getusersitepackages()
    except Exception:
        pass

    venv_path = Path(os.environ.get("VIRTUAL_ENV", default_venv))
    site_packages = venv_path / "lib" / python_version / "site-packages"

    for path in [str(project_path), str(site_packages), user_site]:
        if path and path not in sys.path:
            sys.path.insert(0, path)
            added.append(path)

    print_header("1. PYTHON PATH / ВИРТУАЛЬНОЕ ОКРУЖЕНИЕ")
    print(f"Project root: {project_path}")
    print(f"Virtualenv : {venv_path}")
    print(f"Site-packages added: {site_packages}")
    if user_site:
        print(f"User site-packages: {user_site}")
    print("\nПути добавлены в sys.path:")
    for path in added:
        exists = "✅" if os.path.exists(path) else "❌"
        print(f"  {exists} {path}")
    print("\nПервые 5 записей sys.path:")
    for p in sys.path[:5]:
        exists = "✅" if os.path.exists(p) else "❌"
        print(f"  {exists} {p}")


def check_files():
    print_header("2. ПРОВЕРКА КЛЮЧЕВЫХ ФАЙЛОВ")
    required_files = [
        "main.py",
        "webhook_app_multi.py",
        "bot_factory.py",
        "bot_context.py",
        "config.py",
        "db.py",
        "google_sheets.py",
        ".env",
        "requirements.txt",
        "MULTI_BOT_SETUP.md",
    ]
    for rel_path in required_files:
        path = project_path / rel_path
        exists = path.exists()
        size = path.stat().st_size if exists else 0
        status = "✅" if exists else "❌"
        print(f"  {status} {rel_path} ({size} bytes)")


def check_dependencies():
    print_header("3. ПРОВЕРКА ЗАВИСИМОСТЕЙ")
    to_check = ["telebot", "flask", "requests", "prodamuspy", "dotenv"]
    for module in to_check:
        try:
            mod = __import__(module)
            location = getattr(mod, "__file__", "built-in")
            print(f"✅ {module}: {location}")
        except Exception as e:
            print(f"❌ {module}: {e}")


def summarize_config():
    print_header("4. КОНФИГУРАЦИЯ БОТОВ")
    try:
        from config import (
            CURRENT_BOT_NAME,
            get_available_bots,
            get_bot_config,
        )

        bots = get_available_bots()
        if not bots:
            bots = [CURRENT_BOT_NAME]

        print(f"Найдено ботов: {len(bots)} (current default: {CURRENT_BOT_NAME})")
        env_bots_list = os.environ.get("BOTS_LIST")
        if env_bots_list:
            print(f"BOTS_LIST (env): {env_bots_list}")

        for bot_name in bots:
            cfg = get_bot_config(bot_name)
            print(f"\n--- Бот: {bot_name} ---")
            print(f"  Token             : {mask(cfg.get('TELEGRAM_BOT_TOKEN'))}")
            print(f"  Admin IDs         : {cfg.get('ADMIN_IDS', [])}")
            print(f"  DB Path           : {cfg.get('DATABASE_PATH')}")
            print(f"  Sheets ID         : {cfg.get('GSHEET_ID')}")
            print(f"  Courses sheet     : {cfg.get('GSHEET_COURSES_NAME')}")
            print(f"  Texts sheet       : {cfg.get('GSHEET_TEXTS_NAME')}")
            print(f"  YooKassa token    : {mask(cfg.get('PAYMENT_PROVIDER_TOKEN'))}")
            print(f"  Currency          : {cfg.get('CURRENCY')}")
            print(f"  Prodamus enabled  : {cfg.get('ENABLE_PRODAMUS')}")
            if cfg.get("ENABLE_PRODAMUS"):
                print(f"    Payform URL     : {cfg.get('PRODAMUS_PAYFORM_URL')}")
                print(f"    Secret key      : {mask(cfg.get('PRODAMUS_SECRET_KEY'))}")
                print(f"    System ID       : {cfg.get('PRODAMUS_SYSTEM_ID') or '<not set>'}")
            webhook_host = cfg.get("WEBHOOK_HOST")
            webhook_path = cfg.get("WEBHOOK_PATH") or f"/webhook/{bot_name}"
            webhook_url = cfg.get("WEBHOOK_URL") or (f"https://{webhook_host}{webhook_path}" if webhook_host else "")
            print(f"  Webhook host      : {webhook_host}")
            print(f"  Webhook path      : {webhook_path}")
            print(f"  Webhook URL       : {webhook_url or '<not set>'}")
            print(f"  Webhook secret    : {mask(cfg.get('WEBHOOK_SECRET_TOKEN')) if cfg.get('WEBHOOK_SECRET_TOKEN') else '<empty>'}")

        return bots
    except Exception as e:
        print(f"❌ Не удалось прочитать конфигурацию: {e}")
        traceback.print_exc()
        return []


def check_databases(bots):
    print_header("5. ПРОВЕРКА БАЗ ДАННЫХ")
    if not bots:
        print("⚠️ Боты не обнаружены, пропускаем проверку БД")
        return
    from config import get_bot_config

    for bot_name in bots:
        cfg = get_bot_config(bot_name)
        db_path = Path(cfg.get("DATABASE_PATH", f"{bot_name}.db"))
        exists = db_path.exists()
        size = db_path.stat().st_size if exists else 0
        status = "✅" if exists else "⚠️"
        print(f"{status} {bot_name}: {db_path} ({size} bytes)")


def check_main_import():
    print_header("6. ПРОВЕРКА ИМПОРТА main.py")
    try:
        import main  # noqa

        print("✅ main.py импортирован успешно")
    except Exception as e:
        print(f"❌ Ошибка импорта main: {e}")
        traceback.print_exc()


def check_webhook_app():
    print_header("7. ПРОВЕРКА webhook_app_multi.py")
    try:
        from webhook_app_multi import app

        print(f"✅ webhook_app_multi импортирован (Flask app: {app.name})")
        print("\nМаршруты Flask:")
        for rule in sorted(app.url_map.iter_rules(), key=lambda r: r.rule):
            methods = ", ".join(sorted(rule.methods))
            print(f"  • {rule.rule} [{methods}] (endpoint: {rule.endpoint})")
    except Exception as e:
        print(f"❌ Ошибка импорта webhook_app_multi: {e}")
        traceback.print_exc()


def find_wsgi_candidates():
    candidates = []
    domain_env = os.environ.get("PYTHONANYWHERE_DOMAIN")
    if domain_env:
        slug = domain_env.replace(".", "_").replace("-", "_")
        candidates.append(Path(f"/var/www/{slug}_wsgi.py"))

    # Try to derive from configured webhook hosts
    try:
        from config import get_available_bots, get_bot_config

        for bot_name in get_available_bots():
            host = get_bot_config(bot_name).get("WEBHOOK_HOST")
            if host:
                slug = host.replace(".", "_").replace("-", "_")
                candidates.append(Path(f"/var/www/{slug}_wsgi.py"))
    except Exception:
        pass

    # Add generic glob matches
    candidates.extend(sorted(Path("/var/www").glob("*pythonanywhere_com_wsgi.py")))

    # Remove duplicates while preserving order
    unique = []
    seen = set()
    for path in candidates:
        if path and path not in seen:
            unique.append(path)
            seen.add(path)
    return unique


def check_wsgi():
    print_header("8. ПРОВЕРКА WSGI ФАЙЛА")
    candidates = find_wsgi_candidates()
    existing = [p for p in candidates if p.exists()]

    if not existing:
        print("❌ Ни одного WSGI файла не найдено в /var/www/*pythonanywhere_com_wsgi.py")
        print("   Проверьте правильность домена в настройках Web → WSGI configuration file.")
        if candidates:
            print("   Проверены пути:")
            for cand in candidates[:5]:
                print(f"     - {cand}")
        return

    wsgi_path = existing[0]
    print(f"✅ Используем WSGI файл: {wsgi_path}")
    try:
        content = wsgi_path.read_text()
        print(f"   Размер: {len(content)} байт")
        required_snippets = {
            "webhook_app_multi": "Импорт webhook_app_multi",
            "application": "Переменная application",
            "sys.path.insert": "Добавление project_path",
        }
        for snippet, desc in required_snippets.items():
            status = "✅" if snippet in content else "❌"
            print(f"   {status} {desc}")
    except Exception as e:
        print(f"❌ Ошибка чтения WSGI файла: {e}")


def check_webhooks(bots):
    print_header("9. ПРОВЕРКА TELEGRAM WEBHOOK ДЛЯ КАЖДОГО БОТА")
    if not requests:
        print("❌ Модуль requests недоступен, пропускаем проверку")
        return
    from config import get_bot_config

    for bot_name in bots:
        cfg = get_bot_config(bot_name)
        token = cfg.get("TELEGRAM_BOT_TOKEN")
        webhook_url_expected = cfg.get("WEBHOOK_URL") or (f"https://{cfg.get('WEBHOOK_HOST')}{cfg.get('WEBHOOK_PATH')}" if cfg.get("WEBHOOK_HOST") else "")
        print(f"\nБот {bot_name}:")
        if not token:
            print("  ❌ Token не задан")
            continue
        try:
            resp = requests.get(f"https://api.telegram.org/bot{token}/getWebhookInfo", timeout=10)
            data = resp.json()
            if not data.get("ok"):
                print(f"  ❌ Telegram API error: {data.get('description')}")
                continue
            info = data.get("result", {})
            current_url = info.get("url") or "<не установлен>"
            pending = info.get("pending_update_count", 0)
            last_error = info.get("last_error_message")
            print(f"  Текущий webhook URL: {current_url}")
            if webhook_url_expected:
                if current_url == webhook_url_expected:
                    print("  ✅ Совпадает с ожидаемым URL")
                else:
                    print(f"  ⚠️ Ожидается: {webhook_url_expected}")
            print(f"  Pending updates: {pending}")
            if last_error:
                print(f"  ❌ Последняя ошибка: {last_error}")
            else:
                print("  ✅ Telegram ошибок не сообщает")
        except Exception as e:
            print(f"  ❌ Ошибка запроса getWebhookInfo: {e}")


def test_http_endpoints(bots):
    print_header("10. ТЕСТ HTTP ENDPOINT-ОВ")
    if not requests:
        print("❌ Модуль requests недоступен, пропускаем тест")
        return
    from config import get_bot_config

    checked_hosts = set()
    for bot_name in bots:
        cfg = get_bot_config(bot_name)
        webhook_host = cfg.get("WEBHOOK_HOST")
        webhook_path = cfg.get("WEBHOOK_PATH") or f"/webhook/{bot_name}"
        if not webhook_host:
            print(f"\nБот {bot_name}: ⚠️ WEBHOOK_HOST не задан, пропускаем HTTP тесты")
            continue
        base_url = f"https://{webhook_host}"
        if base_url not in checked_hosts:
            print(f"\nОбщий health-check: {base_url}")
            try:
                resp = requests.get(base_url, timeout=10)
                print(f"  Статус: {resp.status_code}")
                if resp.status_code == 200:
                    print(f"  ✅ Health endpoint OK (ответ: {resp.text[:80]})")
                else:
                    print(f"  ⚠️ Ответ: {resp.text[:80]}")
            except Exception as e:
                print(f"  ❌ Health-check не доступен: {e}")
            checked_hosts.add(base_url)

        webhook_url = cfg.get("WEBHOOK_URL") or f"{base_url}{webhook_path}"
        print(f"\nБот {bot_name}: проверяем {webhook_url}")
        try:
            resp = requests.get(webhook_url, timeout=10)
            print(f"  Статус: {resp.status_code}")
            preview = resp.text[:120].replace("\n", " ")
            print(f"  Ответ: {preview}")
            if resp.status_code == 200:
                print("  ✅ Webhook GET доступен")
            else:
                print("  ⚠️ Webhook GET ответил не 200")
        except Exception as e:
            print(f"  ❌ Ошибка обращения к webhook: {e}")


def check_environment(bots):
    print_header("11. ПРОВЕРКА КЛЮЧЕВЫХ ENV ПЕРЕМЕННЫХ")
    keys = [
        "BOTS_LIST",
        "USE_WEBHOOK",
        "WEBHOOK_HOST",
        "WEBHOOK_PATH",
        "WEBHOOK_SECRET_TOKEN",
    ]
    for key in keys:
        value = os.environ.get(key)
        if not value:
            print(f"  ⚠️ {key}: не установлена")
        elif "TOKEN" in key or "SECRET" in key:
            print(f"  ✅ {key}: {mask(value)}")
        else:
            print(f"  ✅ {key}: {value}")

    if not bots:
        return

    print("\nПеременные из конфигурации ботов:")
    from config import get_bot_config

    for bot_name in bots:
        cfg = get_bot_config(bot_name)
        print(f"  Бот {bot_name}:")
        host = cfg.get("WEBHOOK_HOST") or "<не задан>"
        path = cfg.get("WEBHOOK_PATH") or f"/webhook/{bot_name}"
        secret = cfg.get("WEBHOOK_SECRET_TOKEN")
        print(f"    WEBHOOK_HOST        : {host}")
        print(f"    WEBHOOK_PATH        : {path}")
        print(f"    WEBHOOK_SECRET_TOKEN: {mask(secret) if secret else '<empty>'}")


def main():
    print(SEPARATOR)
    print("ПОЛНЫЙ ДИАГНОСТИЧЕСКИЙ ОТЧЕТ (мульти-бот)")
    print(SEPARATOR)
    add_sys_paths()
    check_files()
    check_dependencies()
    bots = summarize_config()
    check_databases(bots)
    check_main_import()
    check_webhook_app()
    check_wsgi()
    if bots:
        check_webhooks(bots)
        test_http_endpoints(bots)
    else:
        print("\n⚠️ Боты не обнаружены, пропускаем проверки webhook/HTTP")
    check_environment(bots)
    print("\n" + SEPARATOR)
    print("Диагностика завершена. Проверьте вывод выше на наличие ❌/⚠️.")
    print("Если обнаружены ошибки:")
    print("  1) Убедитесь, что виртуальное окружение активировано в Web settings")
    print("  2) Перезапустите веб-приложение после исправлений")
    print("  3) Перепроверьте токены и webhook URLs в конфигурации")


if __name__ == "__main__":
    main()

