#!/usr/bin/env python3
"""
Тестирование Prodamus webhook endpoints
"""
import sys
import os
import requests
import hashlib
from urllib.parse import urlencode

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
    
    # Функция для генерации подписи (как в main.py)
    def generate_prodamus_signature(data: dict, secret_key: str) -> str:
        """Generate Prodamus webhook signature"""
        # Sort all parameters except 'sign'/'signature', join with &, add secret key, calculate MD5
        sorted_params = sorted([(k, v) for k, v in data.items() if k not in ('sign', 'signature')])
        param_string = '&'.join([f"{k}={v}" for k, v in sorted_params])
        sign_string = param_string + secret_key
        return hashlib.md5(sign_string.encode('utf-8')).hexdigest()
    
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
    
    # Генерируем подпись
    signature = generate_prodamus_signature(test_data, PRODAMUS_SECRET_KEY)
    test_data["signature"] = signature
    
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
            "sign": signature  # Prodamus также может отправлять подпись в заголовке
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
    
    # Тест Success URL
    print("\n" + "=" * 70)
    print("ТЕСТ 2: Success URL (GET) - редирект после оплаты")
    print("=" * 70)
    
    success_data = {
        "_payform_status": "success",
        "_payform_id": "12345678",
        "_payform_order_id": test_order_id,
        "_payform_sign": signature
    }
    
    success_url = f"{base_url}/prodamus/success?{urlencode(success_data)}"
    print(f"\nОтправка GET запроса на: {success_url}")
    
    try:
        response = requests.get(success_url, timeout=10)
        print(f"\nСтатус ответа: {response.status_code}")
        print(f"Ответ: {response.text[:200]}")
        
        if response.status_code == 200:
            print("✅ Success URL работает корректно!")
        else:
            print(f"⚠️ Success URL вернул статус {response.status_code}")
            
    except Exception as e:
        print(f"❌ Ошибка при тестировании Success URL: {e}")
    
    # Тест Fail URL
    print("\n" + "=" * 70)
    print("ТЕСТ 3: Fail URL (GET) - редирект после неуспешной оплаты")
    print("=" * 70)
    
    fail_data = {
        "_payform_status": "fail",
        "_payform_id": "12345678",
        "_payform_order_id": test_order_id
    }
    
    fail_url = f"{base_url}/prodamus/fail?{urlencode(fail_data)}"
    print(f"\nОтправка GET запроса на: {fail_url}")
    
    try:
        response = requests.get(fail_url, timeout=10)
        print(f"\nСтатус ответа: {response.status_code}")
        print(f"Ответ: {response.text[:200]}")
        
        if response.status_code == 200:
            print("✅ Fail URL работает корректно!")
        else:
            print(f"⚠️ Fail URL вернул статус {response.status_code}")
            
    except Exception as e:
        print(f"❌ Ошибка при тестировании Fail URL: {e}")
    
    print("\n" + "=" * 70)
    print("ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
    print("=" * 70)
    print("\nВАЖНО:")
    print("1. Эти тесты проверяют только доступность endpoints")
    print("2. Для реального тестирования нужно провести тестовую оплату в Prodamus")
    print("3. Проверьте логи на сервере после отправки запросов")
    print("4. Убедитесь, что webhook URLs настроены в личном кабинете Prodamus")
    
except Exception as e:
    print(f"❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

