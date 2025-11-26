#!/usr/bin/env python3
"""
Тестирование Prodamus webhook endpoints
"""
import sys
import os
import requests
from prodamuspy import ProdamusPy

# Добавляем пути
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 70)
print("ТЕСТИРОВАНИЕ PRODAMUS WEBHOOK")
print("=" * 70)

try:
    from config import get_available_bots, get_bot_config

    bots = get_available_bots()
    if not bots:
        print("❌ Не найдено ни одного бота в конфигурации.")
        sys.exit(1)

    print(f"Найдено ботов: {', '.join(bots)}")

    for bot_name in bots:
        print("\n" + "=" * 70)
        print(f"ТЕСТ ДЛЯ БОТА: {bot_name}")
        print("=" * 70)

        config = get_bot_config(bot_name)
        if not config.get("ENABLE_PRODAMUS", False):
            print("  ⚠️ Prodamus отключен для этого бота. Пропускаем.")
            continue

        secret_key = config.get("PRODAMUS_SECRET_KEY", "")
        if not secret_key:
            print("  ❌ PRODAMUS_SECRET_KEY не задан. Пропускаем.")
            continue

        prodamus_domain = config.get("PRODAMUS_PAYFORM_URL", "")
        webhook_host = config.get("WEBHOOK_HOST", "")
        if not webhook_host:
            print("  ❌ WEBHOOK_HOST не указан. Невозможно построить URL.")
            continue

        base_url = webhook_host if webhook_host.startswith("http") else f"https://{webhook_host}"
        result_url = f"{base_url.rstrip('/')}/prodamus/{bot_name}/result"

        print(f"  Webhook host: {base_url}")
        print(f"  Payform URL: {prodamus_domain}")
        print(f"  Result URL: {result_url}")

        prodamus_client = ProdamusPy(secret_key)

        test_order_id = f"TEST-{bot_name}-{int.from_bytes(os.urandom(3), 'little')}"
        test_payload = {
            "date": "2025-11-25T00:00:00+03:00",
            "order_id": test_order_id,
            "order_num": test_order_id,
            "domain": prodamus_domain,
            "sum": "1000.00",
            "customer_phone": "+79999999999",
            "customer_email": "email@example.com",
            "customer_extra": "тест",
            "payment_type": "Пластиковая карта",
            "commission": "3.5",
            "commission_sum": "35.00",
            "attempt": "1",
            "sys": "test",
            "products[0][name]": "Доступ к обучающим материалам",
            "products[0][price]": "1000.00",
            "products[0][quantity]": "1",
            "products[0][sum]": "1000.00",
            "payment_status": "success",
            "payment_status_description": "Успешная оплата",
        }

        signature = prodamus_client.sign(test_payload)

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Sign": signature,
        }

        print("  ➜ Отправляем тестовый успешный платеж...")
        try:
            response = requests.post(result_url, data=test_payload, headers=headers, timeout=15)
            print(f"    Статус: {response.status_code}")
            print(f"    Ответ: {response.text[:200]}")
        except Exception as e:
            print(f"    ❌ Ошибка запроса: {e}")
            continue

        # Дополнительно тестируем неуспешный платеж, чтобы убедиться, что он не подвисает
        fail_payload = test_payload.copy()
        fail_payload["order_id"] = f"{test_order_id}-FAIL"
        fail_payload["order_num"] = f"{test_order_id}-FAIL"
        fail_payload["payment_status"] = "failed"
        fail_payload["payment_status_description"] = "Ошибка оплаты"
        fail_signature = prodamus_client.sign(fail_payload)

        fail_headers = headers.copy()
        fail_headers["Sign"] = fail_signature

        print("  ➜ Отправляем тестовый НЕуспешный платеж (failed)...")
        try:
            fail_response = requests.post(result_url, data=fail_payload, headers=fail_headers, timeout=15)
            print(f"    Статус: {fail_response.status_code}")
            print(f"    Ответ: {fail_response.text[:200]}")
        except Exception as e:
            print(f"    ❌ Ошибка запроса: {e}")

    print("\n" + "=" * 70)
    print("ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
    print("=" * 70)
    print("\nВАЖНО:")
    print("1. Эти тесты проверяют только доступность endpoints")
    print("2. Для реального теста необходимо провести оплату в Prodamus")
    print("3. Проверьте server log после тестов")
    print("4. URL должен совпадать с настройками в личном кабинете Prodamus")

except Exception as e:
    print(f"❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

