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
import sqlite3
from datetime import datetime

from config import get_available_bots, get_bot_config
from bot_factory import initialize_all_bots, get_bot_instance
from bot_context import set_bot_context, get_bot_context, clear_bot_context

app = Flask(__name__)

# Store raw POST body for Prodamus webhook signature verification
# Flask parses form data automatically, but we need raw body for signature verification
_raw_body_storage = {}

@app.before_request
def save_raw_body():
    """Save raw POST body before Flask parses it (for Prodamus signature verification)"""
    if request.method == 'POST' and request.path.startswith('/prodamus/'):
        # Only for Prodamus endpoints
        try:
            # Try to read from WSGI input stream directly (before Flask parses it)
            if 'wsgi.input' in request.environ:
                wsgi_input = request.environ['wsgi.input']
                # Check if stream is seekable
                if hasattr(wsgi_input, 'tell') and hasattr(wsgi_input, 'seek'):
                    # Save current position
                    pos = wsgi_input.tell()
                    # Read from beginning
                    wsgi_input.seek(0)
                    content_length = request.environ.get('CONTENT_LENGTH', 0)
                    if content_length:
                        raw_data = wsgi_input.read(int(content_length))
                        _raw_body_storage[id(request)] = raw_data.decode('utf-8', errors='ignore')
                    # Restore position
                    wsgi_input.seek(pos)
                else:
                    # Fallback: use request.get_data (may be empty if already parsed)
                    raw_data = request.get_data(cache=False)
                    if raw_data:
                        _raw_body_storage[id(request)] = raw_data.decode('utf-8', errors='ignore')
        except Exception as e:
            print(f"[{datetime.now()}] [RawBody] Failed to save raw body: {e}", file=sys.stderr)

@app.after_request
def cleanup_raw_body(response):
    """Clean up stored raw body after request"""
    if id(request) in _raw_body_storage:
        del _raw_body_storage[id(request)]
    return response

# Initialize all bots at startup
bots = initialize_all_bots()
print(f"[{datetime.now()}] Initialized {len(bots)} bot(s): {', '.join(bots.keys())}")

# Preload texts for all bots at startup
print(f"[{datetime.now()}] Preloading texts for all bots...")
try:
    from google_sheets import get_texts_data
    for bot_name in bots.keys():
        try:
            set_bot_context(bot_name)
            texts = get_texts_data(bot_name)
            print(f"[{datetime.now()}] Preloaded {len(texts)} texts for {bot_name}")
            clear_bot_context()
        except Exception as e:
            print(f"[{datetime.now()}] Failed to preload texts for {bot_name}: {e}")
            clear_bot_context()
except Exception as e:
    print(f"[{datetime.now()}] Error during texts preload: {e}")

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
        
        from main import remove_user_from_channel, strip_html, cleanup_old_images
        
        # Clean up old cached images
        try:
            cleanup_old_images()
        except Exception as e:
            print(f"[{datetime.now()}] [Auto-Cleanup-{bot_name}] Error cleaning up images: {e}")
        
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

# Import the global bot from main.py which has all handlers registered
# This is critical: handlers are registered on this global bot instance,
# so we must use IT for process_new_updates, while get_current_bot() 
# returns the correct instance for sending messages (with correct token)
from main import bot as main_bot

# Webhook routing for each bot
# Pattern: /webhook/{bot_name}
def create_webhook_handler(bot_name, webhook_secret):
    """Create webhook handler for a specific bot"""
    def telegram_webhook():
        import sys
        
        # Set bot context for this request BEFORE processing
        # This is critical: get_current_bot() in handlers will return
        # the correct bot instance for this bot_name
        set_bot_context(bot_name)
        
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
                
                # Process update using GLOBAL bot from main.py
                # This bot has all handlers registered!
                # The handlers use get_current_bot() to get the correct instance for sending
                try:
                    main_bot.process_new_updates([update])
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

for bot_name in bots.keys():
    config = get_bot_config(bot_name)
    webhook_path = config.get('WEBHOOK_PATH', f'/webhook/{bot_name}')
    webhook_secret = config.get('WEBHOOK_SECRET_TOKEN', '')
    
    # Ensure path starts with /
    if not webhook_path.startswith('/'):
        webhook_path = '/' + webhook_path
    
    # Register route for this bot with unique endpoint name
    app.route(webhook_path, methods=['POST', 'GET'], endpoint=f'telegram_webhook_{bot_name}')(create_webhook_handler(bot_name, webhook_secret))
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

        def remove_pending_payment(db_path: str, order_number: str):
            """Delete pending payment entry for non-successful payments."""
            if not order_number:
                return False
            try:
                conn = sqlite3.connect(db_path)
                cur = conn.cursor()
                cur.execute("DELETE FROM pending_payments WHERE order_id = ? OR invoice_id = ?", (order_number, order_number))
                deleted = cur.rowcount
                conn.commit()
                conn.close()
                if deleted:
                    print(f"[{datetime.now()}] [Prodamus-{bot_name} Result] 🧹 Cleared pending payment for {order_number}", file=sys.stderr)
                return deleted > 0
            except sqlite3.OperationalError as e:
                if "no such table" in str(e).lower():
                    return False
                print(f"[{datetime.now()}] [Prodamus-{bot_name} Result] ⚠️ Failed to clear pending payment: {e}", file=sys.stderr)
                return False
            except Exception as e:
                print(f"[{datetime.now()}] [Prodamus-{bot_name} Result] ⚠️ Error clearing pending payment: {e}", file=sys.stderr)
                return False
        
        @app.route(f"/prodamus/{bot_name}/result", methods=["GET", "POST"], endpoint=f'prodamus_result_{bot_name}')
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

            set_bot_context(bot_name)
            bot = get_bot_instance(bot_name)
            config = get_bot_config(bot_name)

            try:
                secret_key = config.get('PRODAMUS_SECRET_KEY', '')
                signature = request.headers.get("Sign") or request.headers.get("sign") or ""
                
                # According to Prodamus PHP documentation: Hmac::verify($_POST, $secret_key, $headers['Sign'])
                # $_POST in PHP contains parsed form data from application/x-www-form-urlencoded
                # Flask's request.form is equivalent to $_POST - it's already parsed
                
                if not request.form:
                    print(f"[{datetime.now()}] [Prodamus-{bot_name} Result] ❌ Empty POST data (request.form is empty)", file=sys.stderr)
                    return "ERROR: Empty payload", 400
                
                # Get raw POST body (saved by before_request middleware)
                raw_body = _raw_body_storage.get(id(request))
                
                # Fallback: try Flask's get_data
                if not raw_body:
                    raw_body = request.get_data(as_text=True, cache=False)
                
                from main import get_prodamus_client
                client = get_prodamus_client(secret_key)
                
                # Try to parse raw body first (handles PHP-style arrays correctly)
                if raw_body:
                    try:
                        data = client.parse(raw_body)
                        if data:
                            print(f"[{datetime.now()}] [Prodamus-{bot_name} Result] 📝 Parsed from raw body", file=sys.stderr)
                    except Exception as e:
                        print(f"[{datetime.now()}] [Prodamus-{bot_name} Result] ⚠️ Failed to parse raw body: {e}, trying request.form", file=sys.stderr)
                        data = None
                else:
                    data = None
                
                # Fallback: reconstruct query string from request.form and parse it
                if not data:
                    # Reconstruct query string from form data for parsing
                    from urllib.parse import quote
                    query_parts = []
                    for key, value in request.form.items():
                        # URL-encode the value
                        encoded_value = quote(str(value), safe='')
                        query_parts.append(f"{key}={encoded_value}")
                    query_string = "&".join(query_parts)
                    
                    try:
                        data = client.parse(query_string)
                        if data:
                            print(f"[{datetime.now()}] [Prodamus-{bot_name} Result] 📝 Parsed from reconstructed query string", file=sys.stderr)
                    except Exception as e:
                        print(f"[{datetime.now()}] [Prodamus-{bot_name} Result] ⚠️ Failed to parse reconstructed query: {e}", file=sys.stderr)
                        # Last resort: use form dict directly (may not work for arrays)
                        data = request.form.to_dict(flat=True)
                        print(f"[{datetime.now()}] [Prodamus-{bot_name} Result] ⚠️ Using request.form directly (arrays may not work)", file=sys.stderr)

                if not data:
                    print(f"[{datetime.now()}] [Prodamus-{bot_name} Result] ❌ Empty payload after parsing", file=sys.stderr)
                    return "ERROR: Empty payload", 400

                print(f"[{datetime.now()}] [Prodamus-{bot_name} Result] 📨 Payload: {data}", file=sys.stderr)
                print(f"[{datetime.now()}] [Prodamus-{bot_name} Result] 🔑 Signature header: {signature}", file=sys.stderr)
                print(f"[{datetime.now()}] [Prodamus-{bot_name} Result] 🔐 Secret key present: {bool(secret_key)}", file=sys.stderr)
                if secret_key:
                    # Log first and last 10 chars of secret key for verification (without exposing full key)
                    print(f"[{datetime.now()}] [Prodamus-{bot_name} Result] 🔐 Secret key: {secret_key[:10]}...{secret_key[-10:] if len(secret_key) > 20 else ''} (length: {len(secret_key)})", file=sys.stderr)
                
                # Debug: log raw body for troubleshooting
                if raw_body:
                    print(f"[{datetime.now()}] [Prodamus-{bot_name} Result] 🔍 Raw body length: {len(raw_body)}, preview: {raw_body[:200]}", file=sys.stderr)
                
                forward_to_test_webhook("result", data, request.method)

                # Verify signature using parsed payload dict (as per Prodamus PHP documentation)
                # Equivalent to: Hmac::verify($_POST, $secret_key, $headers['Sign'])
                if not signature:
                    print(f"[{datetime.now()}] [Prodamus-{bot_name} Result] ❌ Signature header missing", file=sys.stderr)
                    return "ERROR: Signature header missing", 400
                
                if not secret_key:
                    print(f"[{datetime.now()}] [Prodamus-{bot_name} Result] ❌ Secret key missing", file=sys.stderr)
                    return "ERROR: Secret key missing", 400
                
                # Use verify_prodamus_signature (implements exact PHP algorithm)
                from main import verify_prodamus_signature
                if not verify_prodamus_signature(data, secret_key, signature):
                    print(f"[{datetime.now()}] [Prodamus-{bot_name} Result] ❌ Invalid signature", file=sys.stderr)
                    return "ERROR: Invalid signature", 400
                else:
                    print(f"[{datetime.now()}] [Prodamus-{bot_name} Result] ✅ Signature verified", file=sys.stderr)

                order_number = data.get("order_num") or data.get("order_id") or data.get("order")
                amount = data.get("sum") or data.get("amount")
                payment_status_raw = (data.get("payment_status") or data.get("payment_status_description") or data.get("status") or "")
                payment_status = payment_status_raw.strip().lower()

                if not order_number or not amount:
                    print(f"[{datetime.now()}] [Prodamus-{bot_name} Result] ❌ Missing parameters", file=sys.stderr)
                    return "ERROR: Missing parameters", 400

                success_statuses = ("success", "paid", "successful", "succeeded")
                failure_statuses = ("fail", "failed", "error", "cancel", "canceled", "cancelled", "rejected", "refunded", "chargeback", "expired")

                db_path = config.get('DATABASE_PATH', f'{bot_name}.db')

                if payment_status in failure_statuses:
                    remove_pending_payment(db_path, order_number)
                    print(f"[{datetime.now()}] [Prodamus-{bot_name} Result] ❌ Payment failed/cancelled (status={payment_status})", file=sys.stderr)
                    return "OK", 200

                if payment_status not in success_statuses:
                    print(f"[{datetime.now()}] [Prodamus-{bot_name} Result] ⚠️ Ignored interim status: {payment_status_raw}", file=sys.stderr)
                    return "OK", 200

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
                    channel_id = course.get("channel") or course.get("channel_id")

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

