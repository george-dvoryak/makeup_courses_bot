# webhook_app_multi.py
"""
Multi-bot webhook application for PythonAnywhere.
Supports multiple bots in a single Flask application.
"""
from flask import Flask, request, abort
import telebot
import threading
import time
import sys
from datetime import datetime

from config import get_available_bots, get_bot_config
from bot_factory import initialize_all_bots, get_bot_instance
from bot_context import set_bot_context, get_bot_context, clear_bot_context

app = Flask(__name__)

# Initialize all bots at startup
bots = initialize_all_bots()
print(f"[{datetime.now()}] Initialized {len(bots)} bot(s): {', '.join(bots.keys())}")

# Background cleanup scheduler (one per bot)
_cleanup_threads = {}
_cleanup_running = {}

def run_cleanup(bot_name: str):
    """Run expired subscriptions cleanup for a specific bot"""
    try:
        from db import get_expired_subscriptions, mark_subscription_expired, get_connection
        from bot_factory import get_bot_instance
        from bot_context import set_bot_context
        
        # Set bot context for this cleanup
        set_bot_context(bot_name)
        bot = get_bot_instance(bot_name)
        
        from main import remove_user_from_channel, strip_html
        
        expired = get_expired_subscriptions()
        if not expired:
            print(f"[{datetime.now()}] [Auto-Cleanup-{bot_name}] No expired subscriptions found.")
            return
        
        print(f"[{datetime.now()}] [Auto-Cleanup-{bot_name}] Found {len(expired)} expired subscription(s) to process.")
        
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
                        try:
                            member = bot.get_chat_member(channel_id, user_id)
                            status = getattr(member, "status", "unknown")
                            if status in ("left", "kicked"):
                                ok = True
                        except:
                            ok = True
                
                mark_subscription_expired(user_id, course_id)
                
                try:
                    clean_course_name = strip_html(course_name) if course_name else "курсу"
                    bot.send_message(user_id, f"Доступ к курсу {clean_course_name} завершен. Спасибо, что были с нами!")
                except Exception as e:
                    error_msg = str(e).lower()
                    if "chat not found" in error_msg or "bot was blocked" in error_msg:
                        print(f"[{datetime.now()}] [Auto-Cleanup-{bot_name}] User {user_id} blocked bot, skipping notification")
                    else:
                        print(f"[{datetime.now()}] [Auto-Cleanup-{bot_name}] Failed to notify user {user_id}: {e}")
                
                processed += 1
            except Exception as e:
                print(f"[{datetime.now()}] [Auto-Cleanup-{bot_name}] Error processing subscription: {e}")
        
        print(f"[{datetime.now()}] [Auto-Cleanup-{bot_name}] Processed {processed} expired subscription(s).")
        
    except Exception as e:
        print(f"[{datetime.now()}] [Auto-Cleanup-{bot_name}] Error during cleanup: {e}")
        import traceback
        traceback.print_exc()

def cleanup_scheduler(bot_name: str):
    """Background thread that runs cleanup periodically for a specific bot"""
    global _cleanup_running
    
    # Run cleanup immediately on startup
    print(f"[{datetime.now()}] [Auto-Cleanup-{bot_name}] Running initial cleanup on startup...")
    run_cleanup(bot_name)
    
    # Then run every hour (3600 seconds)
    _cleanup_running[bot_name] = True
    while _cleanup_running.get(bot_name, False):
        time.sleep(3600)  # Wait 1 hour
        if _cleanup_running.get(bot_name, False):
            print(f"[{datetime.now()}] [Auto-Cleanup-{bot_name}] Running scheduled cleanup...")
            run_cleanup(bot_name)

def start_cleanup_scheduler(bot_name: str):
    """Start the background cleanup scheduler for a specific bot"""
    global _cleanup_threads
    
    if bot_name in _cleanup_threads:
        return  # Already started
    
    try:
        thread = threading.Thread(target=cleanup_scheduler, args=(bot_name,), daemon=True)
        thread.start()
        _cleanup_threads[bot_name] = thread
        print(f"[{datetime.now()}] [Auto-Cleanup-{bot_name}] Scheduler started")
    except Exception as e:
        print(f"[{datetime.now()}] [Auto-Cleanup-{bot_name}] Failed to start scheduler: {e}")
        import traceback
        traceback.print_exc()

# Start cleanup schedulers for all bots
for bot_name in bots.keys():
    try:
        start_cleanup_scheduler(bot_name)
    except Exception as e:
        print(f"[{datetime.now()}] Failed to start cleanup scheduler for {bot_name}: {e}")

# Health check endpoint
@app.route('/', methods=['GET'])
def health_check():
    """Health check endpoint to verify app is running"""
    return "OK", 200

# Webhook routing for each bot
# Pattern: /webhook/{bot_name}
for bot_name in bots.keys():
    config = get_bot_config(bot_name)
    webhook_path = config.get('WEBHOOK_PATH', f'/webhook/{bot_name}')
    webhook_secret = config.get('WEBHOOK_SECRET_TOKEN', '')
    
    # Ensure path starts with /
    if not webhook_path.startswith('/'):
        webhook_path = '/' + webhook_path
    
    # Create webhook handler for this bot
    def create_webhook_handler(bot_name, webhook_secret):
        def telegram_webhook():
            import sys
            
            # Set bot context for this request
            set_bot_context(bot_name)
            bot = get_bot_instance(bot_name)
            
            try:
                # GET request - return status for testing
                if request.method == 'GET':
                    return f"Webhook endpoint active for bot: {bot_name}. Path: {request.path}", 200
                
                # POST request - handle Telegram webhook
                print(f"[{datetime.now()}] [Webhook-{bot_name}] Received POST request", file=sys.stderr)
                
                try:
                    # Validate Telegram secret header if configured
                    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
                    if webhook_secret:
                        if secret != webhook_secret:
                            print(f"[{datetime.now()}] [Webhook-{bot_name}] ❌ Invalid secret token", file=sys.stderr)
                            abort(403)
                        else:
                            print(f"[{datetime.now()}] [Webhook-{bot_name}] ✅ Secret token validated", file=sys.stderr)
                    
                    # Get update data
                    json_str = request.get_data().decode('utf-8')
                    print(f"[{datetime.now()}] [Webhook-{bot_name}] Received data: {len(json_str)} bytes", file=sys.stderr)
                    
                    # Parse update
                    update = telebot.types.Update.de_json(json_str)
                    
                    # Log update type
                    if update.message:
                        user_id = update.message.from_user.id
                        text = update.message.text or ""
                        print(f"[{datetime.now()}] [Webhook-{bot_name}] Processing message from user {user_id}: {text[:50]}", file=sys.stderr)
                    elif update.callback_query:
                        user_id = update.callback_query.from_user.id
                        data = update.callback_query.data or ""
                        print(f"[{datetime.now()}] [Webhook-{bot_name}] Processing callback_query from user {user_id}: {data[:50]}", file=sys.stderr)
                    
                    # Process update
                    try:
                        bot.process_new_updates([update])
                        print(f"[{datetime.now()}] [Webhook-{bot_name}] ✅ Update processed successfully", file=sys.stderr)
                    except Exception as e:
                        error_msg = str(e).lower()
                        if "chat not found" in error_msg or "bot was blocked" in error_msg or "user is deactivated" in error_msg:
                            print(f"[{datetime.now()}] [Webhook-{bot_name}] ⚠️ User blocked bot or chat not found", file=sys.stderr)
                        else:
                            print(f"[{datetime.now()}] [Webhook-{bot_name}] ❌ Error in bot.process_new_updates: {e}", file=sys.stderr)
                            import traceback
                            traceback.print_exc(file=sys.stderr)
                    
                except Exception as e:
                    print(f"[{datetime.now()}] [Webhook-{bot_name}] ❌ Error processing update: {e}", file=sys.stderr)
                    import traceback
                    traceback.print_exc(file=sys.stderr)
                
                return "OK", 200
            finally:
                # Clear bot context after processing
                clear_bot_context()
        
        return telegram_webhook
    
    # Register route for this bot
    app.route(webhook_path, methods=['POST', 'GET'])(create_webhook_handler(bot_name, webhook_secret))
    print(f"[{datetime.now()}] Registered webhook route: {webhook_path} for bot: {bot_name}")

# Set webhooks for all bots
for bot_name in bots.keys():
    try:
        config = get_bot_config(bot_name)
        webhook_url = config.get('WEBHOOK_URL', '')
        webhook_secret = config.get('WEBHOOK_SECRET_TOKEN', '')
        
        if webhook_url and not webhook_url.startswith("https://<"):
            bot = get_bot_instance(bot_name)
            try:
                current_webhook = bot.get_webhook_info()
                if current_webhook.url != webhook_url:
                    bot.remove_webhook()
                    time.sleep(0.5)
                    bot.set_webhook(
                        url=webhook_url,
                        secret_token=webhook_secret,
                        drop_pending_updates=True,
                        allowed_updates=["message", "callback_query", "shipping_query", "pre_checkout_query"]
                    )
                    print(f"[{datetime.now()}] Webhook set for {bot_name}: {webhook_url}")
                else:
                    print(f"[{datetime.now()}] Webhook already set for {bot_name}: {webhook_url}")
            except Exception as e:
                error_msg = str(e).lower()
                if "429" in error_msg or "too many requests" in error_msg:
                    print(f"[{datetime.now()}] Webhook setup skipped for {bot_name} (rate limit): {e}")
                else:
                    print(f"[{datetime.now()}] Webhook setup error for {bot_name}: {e}")
    except Exception as e:
        print(f"[{datetime.now()}] Failed to set webhook for {bot_name}: {e}")

# Prodamus webhook endpoints (with bot routing)
# Pattern: /prodamus/{bot_name}/result
for bot_name in bots.keys():
    config = get_bot_config(bot_name)
    enable_prodamus = config.get('ENABLE_PRODAMUS', False)
    
    if not enable_prodamus:
        continue
    
    # Create Prodamus handlers for this bot
    def create_prodamus_handlers(bot_name):
        """Create Prodamus webhook handlers for a specific bot"""
        
        @app.route(f"/prodamus/{bot_name}/result", methods=["GET", "POST"])
        def prodamus_result():
            """Handle Prodamus Result URL notification"""
            import sys
            from main import (
                verify_prodamus_signature,
                forward_to_test_webhook,
                get_courses_data,
                get_texts_data,
                add_purchase,
                strip_html,
                add_user,
                extract_prodamus_payload,
            )
            from bot_context import set_bot_context, clear_bot_context
            from bot_factory import get_bot_instance
            import sqlite3

            set_bot_context(bot_name)
            bot = get_bot_instance(bot_name)
            config = get_bot_config(bot_name)

            try:
                secret_key = config.get('PRODAMUS_SECRET_KEY', '')
                signature = request.headers.get("Sign") or request.headers.get("sign") or ""
                data = extract_prodamus_payload(request, secret_key)

                if not data:
                    print(f"[{datetime.now()}] [Prodamus-{bot_name} Result] ❌ Empty payload", file=sys.stderr)
                    return "ERROR: Empty payload", 400

                print(f"[{datetime.now()}] [Prodamus-{bot_name} Result] 📨 Payload: {data}", file=sys.stderr)
                forward_to_test_webhook("result", data, request.method)

                if secret_key:
                    if not verify_prodamus_signature(data, secret_key, signature):
                        print(f"[{datetime.now()}] [Prodamus-{bot_name} Result] ❌ Invalid signature", file=sys.stderr)
                        return "ERROR: Invalid signature", 400

                order_number = data.get("order_num") or data.get("order_id") or data.get("order")
                amount = data.get("sum") or data.get("amount")
                payment_status = (data.get("payment_status") or data.get("payment_status_description") or data.get("status") or "").lower()

                if not order_number or not amount:
                    print(f"[{datetime.now()}] [Prodamus-{bot_name} Result] ❌ Missing parameters", file=sys.stderr)
                    return "ERROR: Missing parameters", 400

                if payment_status not in ("success", "paid", "successful"):
                    print(f"[{datetime.now()}] [Prodamus-{bot_name} Result] ⚠️ Ignored status: {payment_status}", file=sys.stderr)
                    return "OK", 200

                db_path = config.get('DATABASE_PATH', f'{bot_name}.db')
                try:
                    conn = sqlite3.connect(db_path)
                    cur = conn.cursor()
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS pending_payments (
                            invoice_id TEXT PRIMARY KEY,
                            user_id INTEGER,
                            course_id TEXT,
                            amount REAL,
                            created_at INTEGER,
                            payment_system TEXT,
                            order_id TEXT
                        )
                    """)
                    cur.execute("SELECT user_id, course_id, amount FROM pending_payments WHERE order_id = ? OR invoice_id = ?", (order_number, order_number))
                    row = cur.fetchone()

                    if not row:
                        print(f"[{datetime.now()}] [Prodamus-{bot_name} Result] ⚠️ Pending payment not found: {order_number}", file=sys.stderr)
                        conn.close()
                        return "OK", 200

                    user_id, course_id, expected_amount = row
                    amount_float = float(amount)

                    if abs(amount_float - expected_amount) > 0.01:
                        print(f"[{datetime.now()}] [Prodamus-{bot_name} Result] ⚠️ Amount mismatch: expected {expected_amount}, got {amount_float}", file=sys.stderr)
                        conn.close()
                        return "OK", 200

                    courses = get_courses_data(bot_name)
                    course = next((c for c in courses if str(c.get("id")) == str(course_id)), None)

                    if not course:
                        print(f"[{datetime.now()}] [Prodamus-{bot_name} Result] ❌ Course not found: {course_id}", file=sys.stderr)
                        conn.close()
                        return "ERROR: Course not found", 400

                    course_name = course.get("name", "Курс")
                    duration_days = course.get("duration_days")
                    channel_id = course.get("channel_id")

                    add_user(user_id, "")

                    payment_id = f"prodamus_{order_number}"
                    add_purchase(
                        user_id,
                        course_id,
                        course_name,
                        channel_id,
                        duration_days,
                        payment_id=payment_id
                    )

                    cur.execute("DELETE FROM pending_payments WHERE order_id = ? OR invoice_id = ?", (order_number, order_number))
                    conn.commit()
                    conn.close()

                    print(f"[{datetime.now()}] [Prodamus-{bot_name} Result] ✅ Payment processed: user {user_id}, course {course_id}", file=sys.stderr)

                    clean_course_name = strip_html(course_name)
                    texts = get_texts_data(bot_name)
                    success_msg = texts.get(
                        "purchase_success_message",
                        f"Оплата успешно выполнена! Вам предоставлен доступ к курсу {clean_course_name}."
                    )
                    success_msg = success_msg.format(course_name=clean_course_name)

                    try:
                        bot.send_message(user_id, success_msg)
                    except Exception as e:
                        print(f"[{datetime.now()}] [Prodamus-{bot_name} Result] Failed to send success message: {e}", file=sys.stderr)

                    admin_ids = config.get('ADMIN_IDS', [])
                    admin_text = f"💰 Оплата Prodamus: пользователь {user_id} купил {clean_course_name} на сумму {amount_float} руб. (Order: {order_number})"
                    for aid in admin_ids:
                        try:
                            bot.send_message(aid, admin_text)
                        except Exception:
                            pass

                    return "OK", 200
                except Exception as e:
                    print(f"[{datetime.now()}] [Prodamus-{bot_name} Result] ❌ Error: {e}", file=sys.stderr)
                    import traceback
                    traceback.print_exc(file=sys.stderr)
                    return "ERROR", 500
            finally:
                clear_bot_context()

    create_prodamus_handlers(bot_name)

# For now, export app for WSGI
# In production, rename this file to webhook_app.py or update WSGI file

