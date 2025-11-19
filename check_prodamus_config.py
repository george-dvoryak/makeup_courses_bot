#!/usr/bin/env python3
"""
Проверка конфигурации Prodamus
"""
import sys
import os

# Добавляем пути
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 70)
print("ПРОВЕРКА КОНФИГУРАЦИИ PRODAMUS")
print("=" * 70)

try:
    from config import (
        ENABLE_PRODAMUS, PRODAMUS_TEST_MODE, PRODAMUS_PAYFORM_URL,
        PRODAMUS_SECRET_KEY, PRODAMUS_SYSTEM_ID, PRODAMUS_TEST_WEBHOOK_URL,
        WEBHOOK_HOST, WEBHOOK_URL
    )
    
    print("\n1. ОСНОВНЫЕ НАСТРОЙКИ")
    print("-" * 70)
    print(f"ENABLE_PRODAMUS: {ENABLE_PRODAMUS}")
    print(f"PRODAMUS_TEST_MODE: {PRODAMUS_TEST_MODE}")
    print(f"PRODAMUS_PAYFORM_URL: {PRODAMUS_PAYFORM_URL}")
    print(f"PRODAMUS_SECRET_KEY: {'***SET***' if PRODAMUS_SECRET_KEY else '❌ НЕ УСТАНОВЛЕН'}")
    print(f"PRODAMUS_SYSTEM_ID: {PRODAMUS_SYSTEM_ID if PRODAMUS_SYSTEM_ID else 'Не установлен'}")
    print(f"PRODAMUS_TEST_WEBHOOK_URL: {PRODAMUS_TEST_WEBHOOK_URL if PRODAMUS_TEST_WEBHOOK_URL else 'Не установлен'}")
    
    print("\n2. WEBHOOK URLS")
    print("-" * 70)
    base_url = WEBHOOK_URL if WEBHOOK_URL else f"https://{WEBHOOK_HOST}" if WEBHOOK_HOST else "НЕ НАСТРОЕН"
    print(f"Base URL: {base_url}")
    print(f"\nResult URL (для уведомлений о платежах):")
    print(f"  {base_url}/prodamus/result")
    print(f"\nSuccess URL (редирект после успешной оплаты):")
    print(f"  {base_url}/prodamus/success")
    print(f"\nFail URL (редирект после неуспешной оплаты):")
    print(f"  {base_url}/prodamus/fail")
    
    print("\n3. ПРОВЕРКА КОНФИГУРАЦИИ")
    print("-" * 70)
    
    issues = []
    if not PRODAMUS_SECRET_KEY:
        issues.append("❌ PRODAMUS_SECRET_KEY не установлен (нужен для проверки подписи webhooks)")
    
    if not WEBHOOK_URL and not WEBHOOK_HOST:
        issues.append("❌ WEBHOOK_URL или WEBHOOK_HOST не установлены (нужны для webhook URLs)")
    
    if PRODAMUS_TEST_MODE:
        if PRODAMUS_PAYFORM_URL != "testwork1.payform.ru":
            issues.append(f"⚠️ В тестовом режиме рекомендуется использовать testwork1.payform.ru, сейчас: {PRODAMUS_PAYFORM_URL}")
    else:
        if PRODAMUS_PAYFORM_URL == "testwork1.payform.ru":
            issues.append("⚠️ В продакшн режиме не используйте тестовый URL testwork1.payform.ru")
    
    if issues:
        print("Найдены проблемы:")
        for issue in issues:
            print(f"  {issue}")
    else:
        print("✅ Конфигурация выглядит корректно")
    
    print("\n4. ЧТО НУЖНО НАСТРОИТЬ В PRODAMUS")
    print("-" * 70)
    print("В личном кабинете Prodamus нужно настроить следующие URL:")
    print(f"\n1. Result URL (обязательно):")
    print(f"   {base_url}/prodamus/result")
    print("   Это URL для получения уведомлений о статусе платежей")
    print("   Метод: POST")
    print("   Prodamus будет отправлять сюда уведомления о платежах")
    
    print(f"\n2. Success URL (опционально, для редиректа пользователя):")
    print(f"   {base_url}/prodamus/success")
    print("   Метод: GET")
    print("   Пользователь будет перенаправлен сюда после успешной оплаты")
    
    print(f"\n3. Fail URL (опционально, для редиректа пользователя):")
    print(f"   {base_url}/prodamus/fail")
    print("   Метод: GET")
    print("   Пользователь будет перенаправлен сюда после неуспешной оплаты")
    
    print("\n5. SECRET KEY")
    print("-" * 70)
    if PRODAMUS_SECRET_KEY:
        print("✅ Secret key установлен")
        print("   Используется для проверки подписи webhook запросов")
        print(f"   Первые 10 символов: {PRODAMUS_SECRET_KEY[:10]}...")
    else:
        print("❌ Secret key НЕ установлен")
        print("   Получите его в личном кабинете Prodamus:")
        print("   Настройки → Безопасность → Secret Key")
        print("   Добавьте в .env: PRODAMUS_SECRET_KEY=ваш_ключ")
    
    print("\n" + "=" * 70)
    print("ПРОВЕРКА ЗАВЕРШЕНА")
    print("=" * 70)
    
except Exception as e:
    print(f"❌ Ошибка при проверке конфигурации: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

