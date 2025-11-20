#!/usr/bin/env python3
"""
Проверка pending payments и диагностика Prodamus webhook
"""
import sqlite3
import sys
from datetime import datetime
from config import DATABASE_PATH

def check_pending_payments():
    """Проверить pending payments в базе данных"""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cur = conn.cursor()
        
        # Проверить существование таблицы
        cur.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='pending_payments'
        """)
        table_exists = cur.fetchone()
        
        if not table_exists:
            print("❌ Таблица pending_payments не существует!")
            conn.close()
            return
        
        # Получить все pending payments
        cur.execute("""
            SELECT invoice_id, user_id, course_id, amount, created_at, payment_system, order_id
            FROM pending_payments
            ORDER BY created_at DESC
            LIMIT 10
        """)
        rows = cur.fetchall()
        
        if not rows:
            print("✅ Нет pending payments в базе данных")
        else:
            print(f"📋 Найдено {len(rows)} pending payment(s):\n")
            for row in rows:
                invoice_id, user_id, course_id, amount, created_at, payment_system, order_id = row
                created_dt = datetime.fromtimestamp(created_at) if created_at else "N/A"
                print(f"  Order ID: {order_id}")
                print(f"  Invoice ID: {invoice_id}")
                print(f"  User ID: {user_id}")
                print(f"  Course ID: {course_id}")
                print(f"  Amount: {amount} руб.")
                print(f"  Payment System: {payment_system}")
                print(f"  Created: {created_dt}")
                print("-" * 50)
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Ошибка при проверке базы данных: {e}")
        import traceback
        traceback.print_exc()

def check_recent_order(order_id_pattern=None):
    """Проверить конкретный заказ"""
    if not order_id_pattern:
        print("⚠️ Укажите order_id для поиска")
        return
    
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cur = conn.cursor()
        
        # Поиск по order_id или invoice_id
        cur.execute("""
            SELECT invoice_id, user_id, course_id, amount, created_at, payment_system, order_id
            FROM pending_payments
            WHERE order_id LIKE ? OR invoice_id LIKE ?
        """, (f"%{order_id_pattern}%", f"%{order_id_pattern}%"))
        
        rows = cur.fetchall()
        
        if not rows:
            print(f"❌ Заказ с order_id содержащим '{order_id_pattern}' не найден в pending_payments")
            print("\n💡 Возможные причины:")
            print("  1. Заказ не был создан (ошибка при нажатии кнопки оплаты)")
            print("  2. Заказ был обработан и удален из pending_payments")
            print("  3. order_id не совпадает")
        else:
            print(f"✅ Найдено {len(rows)} заказ(ов):\n")
            for row in rows:
                invoice_id, user_id, course_id, amount, created_at, payment_system, order_id = row
                created_dt = datetime.fromtimestamp(created_at) if created_at else "N/A"
                print(f"  Order ID: {order_id}")
                print(f"  Invoice ID: {invoice_id}")
                print(f"  User ID: {user_id}")
                print(f"  Course ID: {course_id}")
                print(f"  Amount: {amount} руб.")
                print(f"  Payment System: {payment_system}")
                print(f"  Created: {created_dt}")
                
                # Проверить, есть ли покупка в purchases
                cur.execute("""
                    SELECT course_name, channel_id, expiry, payment_id
                    FROM purchases
                    WHERE user_id = ? AND course_id = ?
                    ORDER BY purchase_date DESC
                    LIMIT 1
                """, (user_id, course_id))
                
                purchase = cur.fetchone()
                if purchase:
                    print(f"\n  ✅ Покупка найдена в purchases:")
                    print(f"     Course: {purchase[0]}")
                    print(f"     Channel: {purchase[1]}")
                    print(f"     Expiry: {purchase[2]}")
                    print(f"     Payment ID: {purchase[3]}")
                else:
                    print(f"\n  ❌ Покупка НЕ найдена в purchases")
                    print(f"     Это означает, что webhook не обработал платеж!")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("=" * 60)
    print("ПРОВЕРКА PRODAMUS PAYMENTS")
    print("=" * 60)
    print()
    
    if len(sys.argv) > 1:
        # Проверить конкретный заказ
        order_id = sys.argv[1]
        print(f"🔍 Поиск заказа: {order_id}\n")
        check_recent_order(order_id)
    else:
        # Показать все pending payments
        check_pending_payments()
        print("\n💡 Для проверки конкретного заказа:")
        print("   python3 check_prodamus_payment.py PROD-20251119181623747-314112021-3")

