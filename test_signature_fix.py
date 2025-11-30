#!/usr/bin/env python3
"""
Тест проверки подписи Prodamus с реальными данными из вебхука
"""
import sys
import os

# Добавляем пути
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from prodamuspy import ProdamusPy

# Данные из вашего вебхука
raw_body = "date=2025-12-01T02%3A12%3A22%2B03%3A00&order_id=38639115&order_num=PROD-20251130231106381-466513805-2&domain=testwork1.payform.ru&sum=102.00&currency=rub&customer_phone=&customer_email=Shah%40ya.ru&customer_extra=%D0%9E%D0%BF%D0%BB%D0%B0%D1%82%D0%B0+%D0%BA%D1%83%D1%80%D1%81%D0%B0%3A+Soft+Matte&payment_type=%D0%9E%D0%BF%D0%BB%D0%B0%D1%82%D0%B0+%D0%BA%D0%B0%D1%80%D1%82%D0%BE%D0%B9%2C+%D0%B2%D1%8B%D0%BF%D1%83%D1%89%D0%B5%D0%BD%D0%BD%D0%BE%D0%B9+%D0%B2+%D0%A0%D0%A4&commission=100&commission_sum=102.00&attempt=1&products%5B0%5D%5Bname%5D=Soft+Matte&products%5B0%5D%5Bprice%5D=102.00&products%5B0%5D%5Bquantity%5D=1&products%5B0%5D%5Bsum%5D=102.00&payment_status=success&payment_status_description=%D0%A3%D1%81%D0%BF%D0%B5%D1%88%D0%BD%D0%B0%D1%8F+%D0%BE%D0%BF%D0%BB%D0%B0%D1%82%D0%B0&payment_init=manual"

# Подпись из заголовка
signature_from_header = "4a83fc181996918c54b8e58b52586cbf4e163a84fe6b3003ca8e08029c8219ea"

# Ваш секретный ключ
secret_key = "1af49e71d4e9842984e29e0488ba71705486054a8aa2a56b782e73667e2d14c7"

print("=" * 70)
print("ТЕСТ ПРОВЕРКИ ПОДПИСИ PRODAMUS")
print("=" * 70)

# Создаем клиент
client = ProdamusPy(secret_key)

# Парсим данные
print("\n1. Парсинг raw body...")
try:
    parsed_data = client.parse(raw_body)
    print(f"✅ Данные распарсены: {len(parsed_data)} полей")
    print(f"   Примеры полей: order_id={parsed_data.get('order_id')}, sum={parsed_data.get('sum')}")
except Exception as e:
    print(f"❌ Ошибка парсинга: {e}")
    sys.exit(1)

# Генерируем подпись
print("\n2. Генерация подписи из распарсенных данных...")
try:
    calculated_signature = client.sign(parsed_data)
    print(f"✅ Рассчитанная подпись: {calculated_signature}")
except Exception as e:
    print(f"❌ Ошибка генерации подписи: {e}")
    sys.exit(1)

# Проверяем подпись
print("\n3. Проверка подписи...")
print(f"   Подпись из заголовка: {signature_from_header}")
print(f"   Рассчитанная подпись: {calculated_signature}")

try:
    is_valid = client.verify(parsed_data, signature_from_header)
    if is_valid:
        print("✅ ПОДПИСЬ ВАЛИДНА!")
    else:
        print("❌ ПОДПИСЬ НЕВАЛИДНА!")
        print("\nВозможные причины:")
        print("1. Неправильный секретный ключ")
        print("2. Данные были изменены после создания подписи")
        print("3. Подпись из другого запроса")
except Exception as e:
    print(f"❌ Ошибка проверки: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
