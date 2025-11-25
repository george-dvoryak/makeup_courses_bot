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
    from config import (
        PRODAMUS_SECRET_KEY, PRODAMUS_TEST_MODE, PRODAMUS_PAYFORM_URL,
        WEBHOOK_URL, WEBHOOK_HOST
    )
    
    if not PRODAMUS_SECRET_KEY:
        print("❌ PRODAMUS_SECRET_KEY не установлен!")
        print("   Установите его в .env файле")
        sys.exit(1)
    
    base_url = WEBHOOK_URL if WEBHOOK_URL else f"https://{WEBHOOK_HOST}" if WEBHOOK_HOST else None
    if not base_url:
        print("❌ WEBHOOK_URL или WEBHOOK_HOST не установлены!")
        print("   Установите их в .env файле")
        sys.exit(1)
    
    print(f"\nBase URL: {base_url}")
    print(f"Test Mode: {PRODAMUS_TEST_MODE}")
    print(f"Payform URL: {PRODAMUS_PAYFORM_URL}")
    
    prodamus_client = ProdamusPy(PRODAMUS_SECRET_KEY)
    
    # Тестовые данные (симуляция успешного платежа)
    print("\n" + "=" * 70)
    print("ТЕСТ 1: Result URL (POST) - успешный платеж")
    print("=" * 70)
    
    test_order_id = f"TEST-{int(os.urandom(4).hex(), 16)}"
    test_data = {
        "order_num": test_order_id,
        "order_id": "12345678",  # Внутренний ID Prodamus
        "sum": "100.00",
        "currency": "rub",
        "customer_email": "test@example.com",
        "payment_status": "success",
        "payment_status_description": "Успешная оплата"
    }
    
    # Генерируем подпись для заголовка Sign
    signature = prodamus_client.sign(test_data)
    
    print(f"\nТестовые данные:")
    for key, value in test_data.items():
        if key == "signature":
            print(f"  {key}: {value[:20]}...")
        else:
            print(f"  {key}: {value}")
    
    result_url = f"{base_url}/prodamus/result"
    print(f"\nОтправка POST запроса на: {result_url}")
    
    try:
        # Отправляем POST запрос с form-data
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Sign": signature  # Prodamus отправляет подпись в заголовке
        }
        
        response = requests.post(
            result_url,
            data=test_data,
            headers=headers,
            timeout=10
        )
        
        print(f"\nСтатус ответа: {response.status_code}")
        print(f"Ответ: {response.text[:200]}")
        
        if response.status_code == 200:
            print("✅ Result URL работает корректно!")
        else:
            print(f"⚠️ Result URL вернул статус {response.status_code}")
            
    except Exception as e:
        print(f"❌ Ошибка при тестировании Result URL: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 70)
    print("ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
    print("=" * 70)
    print("\nВАЖНО:")
    print("1. Эти тесты проверяют только доступность endpoints")
    print("2. Для реального тестирования нужно провести тестовую оплату в Prodamus")
    print("3. Проверьте логи на сервере после отправки запросов")
    print("4. Убедитесь, что Result URL настроен в личном кабинете Prodamus (Success/Fail необязательны)")
    
except Exception as e:
    print(f"❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

