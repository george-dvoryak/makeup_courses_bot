# webhook_app.py
from flask import Flask, request, abort
import telebot
import threading
import time
from datetime import datetime

from config import TELEGRAM_BOT_TOKEN, WEBHOOK_URL, WEBHOOK_PATH, WEBHOOK_SECRET_TOKEN
from main import bot  # handlers are already registered on import

app = Flask(__name__)

# Background cleanup scheduler
# Initialize variables at module level to ensure they exist
_cleanup_thread = None
_cleanup_running = False

# Ensure variables are in module globals
if '_cleanup_thread' not in globals():
    _cleanup_thread = None
if '_cleanup_running' not in globals():
    _cleanup_running = False

def run_cleanup():
    """Run expired subscriptions cleanup"""
    try:
        from db import get_expired_subscriptions, mark_subscription_expired, get_connection
        from main import remove_user_from_channel, strip_html
        
        expired = get_expired_subscriptions()
        if not expired:
            print(f"[{datetime.now()}] [Auto-Cleanup] No expired subscriptions found.")
            return
        
        print(f"[{datetime.now()}] [Auto-Cleanup] Found {len(expired)} expired subscription(s) to process.")
        
        processed = 0
        for rec in expired:
            try:
                user_id = rec["user_id"]
                course_id = rec["course_id"]
                course_name = rec["course_name"]
                channel_id = rec["channel_id"]
                
                if channel_id:
                    ok = remove_user_from_channel(user_id, channel_id)
                    if not ok:
                        # Double check user status
                        try:
                            member = bot.get_chat_member(channel_id, user_id)
                            status = getattr(member, "status", "unknown")
                            if status in ("left", "kicked"):
                                ok = True
                        except:
                            ok = True  # Assume removed if can't check
                
                mark_subscription_expired(user_id, course_id)
                
                # Try to notify user
                try:
                    clean_course_name = strip_html(course_name) if course_name else "курсу"
                    bot.send_message(user_id, f"Доступ к курсу {clean_course_name} завершен. Спасибо, что были с нами!")
                except Exception as e:
                    error_msg = str(e).lower()
                    # Ignore "chat not found" errors (user blocked bot or deleted chat)
                    if "chat not found" in error_msg or "bot was blocked" in error_msg:
                        print(f"[{datetime.now()}] [Auto-Cleanup] User {user_id} blocked bot or chat not found, skipping notification")
                    else:
                        print(f"[{datetime.now()}] [Auto-Cleanup] Failed to notify user {user_id}: {e}")
                
                processed += 1
            except Exception as e:
                print(f"[{datetime.now()}] [Auto-Cleanup] Error processing subscription: {e}")
        
        print(f"[{datetime.now()}] [Auto-Cleanup] Processed {processed} expired subscription(s).")
        
    except Exception as e:
        print(f"[{datetime.now()}] [Auto-Cleanup] Error during cleanup: {e}")
        import traceback
        traceback.print_exc()

def cleanup_scheduler():
    """Background thread that runs cleanup periodically"""
    global _cleanup_running
    
    # Run cleanup immediately on startup
    print(f"[{datetime.now()}] [Auto-Cleanup] Running initial cleanup on startup...")
    run_cleanup()
    
    # Then run every hour (3600 seconds)
    _cleanup_running = True
    while _cleanup_running:
        time.sleep(3600)  # Wait 1 hour
        if _cleanup_running:
            print(f"[{datetime.now()}] [Auto-Cleanup] Running scheduled cleanup...")
            run_cleanup()

def start_cleanup_scheduler():
    """Start the background cleanup scheduler"""
    global _cleanup_thread, _cleanup_running
    try:
        # Try to access _cleanup_thread - if it doesn't exist, NameError will be raised
        thread = _cleanup_thread
        if thread is None or not thread.is_alive():
            _cleanup_thread = threading.Thread(target=cleanup_scheduler, daemon=True)
            _cleanup_thread.start()
            print(f"[{datetime.now()}] [Auto-Cleanup] Background cleanup scheduler started (runs every hour + on startup)")
        else:
            print(f"[{datetime.now()}] [Auto-Cleanup] Cleanup scheduler already running")
    except NameError:
        # Variable doesn't exist - initialize it
        _cleanup_thread = threading.Thread(target=cleanup_scheduler, daemon=True)
        _cleanup_thread.start()
        print(f"[{datetime.now()}] [Auto-Cleanup] Background cleanup scheduler started (after NameError fix)")
    except Exception as e:
        print(f"[{datetime.now()}] [Auto-Cleanup] Error starting scheduler: {e}")
        import traceback
        traceback.print_exc()

# Start cleanup scheduler when module is imported
# Wrap in try-except to prevent import errors
try:
    start_cleanup_scheduler()
except Exception as e:
    print(f"[{datetime.now()}] [Auto-Cleanup] Failed to start scheduler on import: {e}")
    import traceback
    traceback.print_exc()

# Health check endpoint
@app.route('/', methods=['GET'])
def health_check():
    """Health check endpoint to verify app is running"""
    return "OK", 200

# Reset and set webhook
if WEBHOOK_URL:
    try:
        bot.remove_webhook()
        bot.set_webhook(
            url=WEBHOOK_URL,
            secret_token=WEBHOOK_SECRET_TOKEN,
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query", "shipping_query", "pre_checkout_query"]
        )
        print(f"Webhook set to: {WEBHOOK_URL}")
    except Exception as e:
        print("Webhook setup error:", e)

# Webhook endpoint - use WEBHOOK_PATH if available, otherwise fallback to token-based path
if WEBHOOK_PATH:
    @app.route(WEBHOOK_PATH, methods=['POST', 'GET'])
    def telegram_webhook():
        # GET request - return status for testing
        if request.method == 'GET':
            return f"Webhook endpoint active. Path: {WEBHOOK_PATH}", 200
        
        # POST request - handle Telegram webhook
        # Use sys.stderr for Error log visibility
        import sys
        print(f"[{datetime.now()}] [Webhook] Received POST request", file=sys.stderr)
        print(f"[{datetime.now()}] [Webhook] Received POST request")
        
        # Validate Telegram secret header if configured
        secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if WEBHOOK_SECRET_TOKEN:
            if secret != WEBHOOK_SECRET_TOKEN:
                print(f"[{datetime.now()}] [Webhook] ❌ Invalid secret token", file=sys.stderr)
                abort(403)
            else:
                print(f"[{datetime.now()}] [Webhook] ✅ Secret token validated", file=sys.stderr)
        
        try:
            json_str = request.get_data().decode('utf-8')
            print(f"[{datetime.now()}] [Webhook] Received data: {len(json_str)} bytes", file=sys.stderr)
            
            update = telebot.types.Update.de_json(json_str)
            
            # Log update type
            if update.message:
                user_id = update.message.from_user.id
                text = update.message.text or ""
                print(f"[{datetime.now()}] [Webhook] Processing message from user {user_id}: {text[:50]}", file=sys.stderr)
            elif update.callback_query:
                user_id = update.callback_query.from_user.id
                data = update.callback_query.data or ""
                print(f"[{datetime.now()}] [Webhook] Processing callback_query from user {user_id}: {data[:50]}", file=sys.stderr)
            
            bot.process_new_updates([update])
            print(f"[{datetime.now()}] [Webhook] ✅ Update processed successfully", file=sys.stderr)
        except Exception as e:
            print(f"[{datetime.now()}] [Webhook] ❌ Error processing update: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
        
        return "OK", 200
else:
    # Fallback to old token-based path for backward compatibility
    @app.route(f'/{TELEGRAM_BOT_TOKEN}', methods=['POST'])
    def telegram_webhook():
        try:
            json_str = request.get_data().decode('utf-8')
            update = telebot.types.Update.de_json(json_str)
            bot.process_new_updates([update])
        except Exception as e:
            print("Webhook handling error:", e)
        return "OK", 200

# For PythonAnywhere WSGI:
# In your WSGI file, import: from webhook_app import app as application

