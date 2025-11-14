#!/usr/bin/env python3
"""
Diagnostic script to check webhook configuration and status.
Run this on PythonAnywhere to verify your webhook setup.
"""
import os
import sys
from pathlib import Path

# Add project directory to path
project_dir = Path(__file__).parent
sys.path.insert(0, str(project_dir))

try:
    from config import (
        USE_WEBHOOK, WEBHOOK_URL, WEBHOOK_PATH, WEBHOOK_HOST, 
        WEBHOOK_SECRET_TOKEN, TELEGRAM_BOT_TOKEN
    )
    import telebot
    
    print("=" * 60)
    print("WEBHOOK CONFIGURATION CHECK")
    print("=" * 60)
    print()
    
    print("1. Configuration:")
    print(f"   USE_WEBHOOK: {USE_WEBHOOK}")
    print(f"   WEBHOOK_HOST: {WEBHOOK_HOST}")
    print(f"   WEBHOOK_PATH: {WEBHOOK_PATH}")
    print(f"   WEBHOOK_URL: {WEBHOOK_URL}")
    print(f"   WEBHOOK_SECRET_TOKEN: {'***SET***' if WEBHOOK_SECRET_TOKEN else 'NOT SET'}")
    print()
    
    if not USE_WEBHOOK:
        print("❌ ERROR: USE_WEBHOOK is False!")
        print("   Set USE_WEBHOOK=True in your .env file")
        sys.exit(1)
    
    if not WEBHOOK_URL:
        print("❌ ERROR: WEBHOOK_URL is not set!")
        print("   Set WEBHOOK_HOST and WEBHOOK_PATH in your .env file")
        sys.exit(1)
    
    print("2. Checking Telegram webhook status...")
    bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
    
    try:
        webhook_info = bot.get_webhook_info()
        print(f"   Webhook URL: {webhook_info.url or 'NOT SET'}")
        print(f"   Pending updates: {webhook_info.pending_update_count}")
        print(f"   Last error date: {webhook_info.last_error_date or 'None'}")
        print(f"   Last error message: {webhook_info.last_error_message or 'None'}")
        print()
        
        if webhook_info.url != WEBHOOK_URL:
            print("⚠️  WARNING: Telegram webhook URL doesn't match config!")
            print(f"   Expected: {WEBHOOK_URL}")
            print(f"   Actual: {webhook_info.url}")
            print("   The webhook will be set when webhook_app.py loads")
        else:
            print("✅ Webhook URL matches configuration")
        
        if webhook_info.pending_update_count > 0:
            print(f"⚠️  WARNING: {webhook_info.pending_update_count} pending updates")
        
        if webhook_info.last_error_message:
            print(f"❌ ERROR: Last webhook error: {webhook_info.last_error_message}")
        
    except Exception as e:
        print(f"❌ ERROR checking webhook: {e}")
        sys.exit(1)
    
    print()
    print("3. Testing webhook endpoint...")
    print(f"   Expected endpoint: {WEBHOOK_PATH or f'/{TELEGRAM_BOT_TOKEN}'}")
    print(f"   Full URL: {WEBHOOK_URL}")
    print()
    
    print("4. WSGI Configuration:")
    wsgi_path = os.environ.get('PYTHONANYWHERE_SITE', '')
    if wsgi_path:
        print(f"   PythonAnywhere site: {wsgi_path}")
    else:
        print("   (Not running on PythonAnywhere or WSGI not detected)")
    print()
    
    print("=" * 60)
    print("RECOMMENDATIONS:")
    print("=" * 60)
    print()
    print("1. Make sure your .env file on PythonAnywhere has:")
    print("   USE_WEBHOOK=True")
    print(f"   WEBHOOK_HOST=goshadvoryak.pythonanywhere.com")
    print(f"   WEBHOOK_PATH=/webhook")
    print("   WEBHOOK_SECRET_TOKEN=<your-secret-token>")
    print()
    print("2. Verify WSGI file imports from webhook_app:")
    print("   from webhook_app import app as application")
    print()
    print("3. Reload your web app in PythonAnywhere Web tab")
    print()
    print("4. Check Error log for:")
    print("   'Webhook set to: https://...'")
    print("   '[Auto-Cleanup] Background cleanup scheduler started'")
    print()
    
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure all dependencies are installed:")
    print("  pip install --user -r requirements.txt")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

