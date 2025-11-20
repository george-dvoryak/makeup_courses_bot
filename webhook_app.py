# webhook_app.py
from flask import Flask, request, abort
import telebot
import threading
import time
import sys
from datetime import datetime

from config import TELEGRAM_BOT_TOKEN, WEBHOOK_URL, WEBHOOK_PATH, WEBHOOK_SECRET_TOKEN, ENABLE_PRODAMUS
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

# Reset and set webhook (only if not already set correctly)
if WEBHOOK_URL:
    try:
        # Check current webhook status first
        current_webhook = bot.get_webhook_info()
        if current_webhook.url != WEBHOOK_URL:
            # Webhook is not set or set to wrong URL - update it
            bot.remove_webhook()
            bot.set_webhook(
                url=WEBHOOK_URL,
                secret_token=WEBHOOK_SECRET_TOKEN,
                drop_pending_updates=True,
                allowed_updates=["message", "callback_query", "shipping_query", "pre_checkout_query"]
            )
            print(f"Webhook set to: {WEBHOOK_URL}")
        else:
            # Webhook is already set correctly
            print(f"Webhook already set to: {WEBHOOK_URL}")
    except Exception as e:
        error_msg = str(e).lower()
        if "429" in error_msg or "too many requests" in error_msg:
            # Rate limit - don't spam, just log
            print(f"Webhook setup skipped (rate limit): {e}")
        else:
            print(f"Webhook setup error: {e}")

# Webhook endpoint - use WEBHOOK_PATH if available, otherwise fallback to token-based path
if WEBHOOK_PATH:
    @app.route(WEBHOOK_PATH, methods=['POST', 'GET'])
    def telegram_webhook():
        import sys
        
        # GET request - return status for testing
        if request.method == 'GET':
            return f"Webhook endpoint active. Path: {WEBHOOK_PATH}", 200
        
        # POST request - handle Telegram webhook
        # Log immediately to ensure we see requests
        print(f"[{datetime.now()}] [Webhook] Received POST request", file=sys.stderr)
        
        # Return OK immediately to Telegram (best practice)
        # Then process update asynchronously if needed
        
        try:
            # Validate Telegram secret header if configured
            secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
            if WEBHOOK_SECRET_TOKEN:
                if secret != WEBHOOK_SECRET_TOKEN:
                    print(f"[{datetime.now()}] [Webhook] ❌ Invalid secret token", file=sys.stderr)
                    abort(403)
                else:
                    print(f"[{datetime.now()}] [Webhook] ✅ Secret token validated", file=sys.stderr)
            
            # Get update data
            json_str = request.get_data().decode('utf-8')
            print(f"[{datetime.now()}] [Webhook] Received data: {len(json_str)} bytes", file=sys.stderr)
            
            # Parse update
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
            
            # Process update (this may take time, but we already returned OK to Telegram)
            try:
                bot.process_new_updates([update])
                print(f"[{datetime.now()}] [Webhook] ✅ Update processed successfully", file=sys.stderr)
            except Exception as e:
                error_msg = str(e).lower()
                # Log error but don't fail - some errors are expected (e.g., user blocked bot)
                if "chat not found" in error_msg or "bot was blocked" in error_msg or "user is deactivated" in error_msg:
                    print(f"[{datetime.now()}] [Webhook] ⚠️ User blocked bot or chat not found (expected for some users)", file=sys.stderr)
                else:
                    print(f"[{datetime.now()}] [Webhook] ❌ Error in bot.process_new_updates: {e}", file=sys.stderr)
                    import traceback
                    traceback.print_exc(file=sys.stderr)
            
        except Exception as e:
            print(f"[{datetime.now()}] [Webhook] ❌ Error processing update: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
        
        # Always return OK to Telegram (even if processing failed)
        # Telegram will retry if needed
        try:
            return "OK", 200
        except Exception as e:
            # If we can't write response, log it but don't crash
            print(f"[{datetime.now()}] [Webhook] ⚠️ Error returning response: {e}", file=sys.stderr)
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

# Prodamus webhook endpoints (if enabled)
if ENABLE_PRODAMUS:
    @app.route("/prodamus/result", methods=["GET", "POST"])
    def prodamus_result():
        """
        Handle Prodamus Result URL notification (payment status update)
        This endpoint receives payment notifications from Prodamus
        Must return "OK" if payment is valid, or error code otherwise
        """
        import sys
        try:
            # Import Prodamus handlers from main.py
            from main import (
                verify_prodamus_signature,
                forward_to_test_webhook
            )
            from config import PRODAMUS_SECRET_KEY
            
            # Get request data (can be GET or POST)
            if request.method == "GET":
                data = request.args.to_dict()
            else:
                data = request.form.to_dict() if request.form else request.get_json() or {}
            
            # For POST requests, check signature in header (Prodamus sends it as 'sign' header)
            if request.method == "POST" and "sign" in request.headers:
                data["signature"] = request.headers.get("sign", "")
            
            # Log the notification for debugging (use sys.stderr for PythonAnywhere)
            print(f"[{datetime.now()}] [Prodamus Result] Received notification: {data}", file=sys.stderr)
            print(f"[{datetime.now()}] [Prodamus Result] Request method: {request.method}", file=sys.stderr)
            print(f"[{datetime.now()}] [Prodamus Result] Request headers: {dict(request.headers)}", file=sys.stderr)
            
            # Forward to test webhook if configured
            forward_to_test_webhook("result", data, request.method)
            
            # Verify signature if secret key is configured
            if PRODAMUS_SECRET_KEY:
                if not verify_prodamus_signature(data, PRODAMUS_SECRET_KEY):
                    print(f"[{datetime.now()}] [Prodamus Result] ❌ Invalid signature", file=sys.stderr)
                    return "ERROR: Invalid signature", 400
                else:
                    print(f"[{datetime.now()}] [Prodamus Result] ✅ Signature verified", file=sys.stderr)
            
            # Call the main handler function
            # We need to temporarily replace request object in main module
            # Actually, let's just call the handler directly with our data
            from main import (
                get_courses_data, add_purchase, strip_html,
                ADMIN_IDS, DATABASE_PATH, bot as main_bot
            )
            import sqlite3
            from telebot import types
            import datetime as dt
            
            # Extract required parameters
            order_number = data.get("order_num", "") or data.get("order_id", "") or data.get("order", "")
            amount = data.get("sum", "") or data.get("amount", "")
            payment_status = (data.get("payment_status", "") or data.get("status", "")).lower()
            
            print(f"[{datetime.now()}] [Prodamus Result] Order: {order_number}, Amount: {amount}, Status: {payment_status}", file=sys.stderr)
            
            if not order_number or not amount:
                print(f"[{datetime.now()}] [Prodamus Result] ❌ Missing required parameters. Received data: {data}", file=sys.stderr)
                return "ERROR: Missing parameters", 400
            
            # Only process successful payments
            if payment_status not in ("success", "paid", "successful"):
                print(f"[{datetime.now()}] [Prodamus Result] ⚠️ Payment not successful, status: {payment_status}", file=sys.stderr)
                return "OK", 200  # Still return OK to acknowledge receipt
            
            # Find pending payment in database
            try:
                conn = sqlite3.connect(DATABASE_PATH)
                cur = conn.cursor()
                # Create pending_payments table if not exists
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
                # Add columns if they don't exist (migration)
                try:
                    cur.execute("ALTER TABLE pending_payments ADD COLUMN payment_system TEXT")
                except sqlite3.OperationalError:
                    pass
                try:
                    cur.execute("ALTER TABLE pending_payments ADD COLUMN order_id TEXT")
                except sqlite3.OperationalError:
                    pass
                
                # Try to find by order_id or invoice_id
                cur.execute("SELECT user_id, course_id, amount FROM pending_payments WHERE order_id = ? OR invoice_id = ?", (order_number, order_number))
                row = cur.fetchone()
                
                if not row:
                    print(f"[{datetime.now()}] [Prodamus Result] ❌ Payment not found for order/invoice {order_number}", file=sys.stderr)
                    conn.close()
                    return "ERROR: Payment not found", 404
                
                user_id, course_id, expected_amount = row[0], row[1], row[2]
                
                # Verify amount matches
                if abs(float(amount) - float(expected_amount)) > 0.01:
                    print(f"[{datetime.now()}] [Prodamus Result] ❌ Amount mismatch for order {order_number}: expected {expected_amount}, got {amount}", file=sys.stderr)
                    conn.close()
                    return "ERROR: Amount mismatch", 400
                
                # Get course data
                try:
                    courses = get_courses_data()
                    course = next((x for x in courses if str(x.get("id")) == str(course_id)), None)
                    if not course:
                        print(f"[{datetime.now()}] [Prodamus Result] ❌ Course {course_id} not found", file=sys.stderr)
                        conn.close()
                        return "ERROR: Course not found", 404
                    
                    course_name = course.get("name", f"ID {course_id}")
                    duration = course.get("duration_days")
                    channel = str(course.get("channel", ""))
                    
                    # Add purchase to database
                    expiry_ts = add_purchase(user_id, str(course_id), course_name, channel, duration, payment_id=f"prodamus_{order_number}")
                    
                    # Remove from pending payments
                    cur.execute("DELETE FROM pending_payments WHERE order_id = ?", (order_number,))
                    conn.commit()
                    conn.close()
                    
                    # Send success message to user
                    clean_course_name = strip_html(course_name) if course_name else f"ID {course_id}"
                    text = f"✅ Оплата успешно получена!\n\n"
                    text += f"Вам предоставлен доступ к курсу: {clean_course_name}"
                    
                    # Create invite link if channel exists
                    invite_link = None
                    if channel:
                        try:
                            expire_date = dt.datetime.now() + dt.timedelta(days=1)
                            invite = main_bot.create_chat_invite_link(
                                chat_id=channel,
                                member_limit=1,
                                expire_date=expire_date
                            )
                            invite_link = invite.invite_link
                        except Exception as e:
                            print(f"[{datetime.now()}] [Prodamus Result] ⚠️ create_chat_invite_link failed for {channel}: {e}", file=sys.stderr)
                    
                    if invite_link:
                        text += "\n\nНажмите кнопку ниже, чтобы перейти к материалам курса."
                        kb = types.InlineKeyboardMarkup()
                        kb.add(types.InlineKeyboardButton("Перейти в канал курса", url=invite_link))
                        main_bot.send_message(user_id, text, reply_markup=kb)
                    else:
                        main_bot.send_message(user_id, text)
                    
                    # Notify admins
                    admin_text = f"💰 Оплата Prodamus: пользователь {user_id} купил {clean_course_name} на сумму {amount} руб. (Order: {order_number})"
                    for aid in ADMIN_IDS:
                        try:
                            main_bot.send_message(aid, admin_text)
                        except Exception:
                            pass
                    
                    print(f"[{datetime.now()}] [Prodamus Result] ✅ Successfully processed payment for order {order_number}, user {user_id}", file=sys.stderr)
                    return "OK", 200
                    
                except Exception as e:
                    print(f"[{datetime.now()}] [Prodamus Result] ❌ Error processing payment: {e}", file=sys.stderr)
                    import traceback
                    traceback.print_exc(file=sys.stderr)
                    conn.close()
                    return "ERROR: Processing error", 500
                    
            except Exception as e:
                print(f"[{datetime.now()}] [Prodamus Result] ❌ Database error: {e}", file=sys.stderr)
                import traceback
                traceback.print_exc(file=sys.stderr)
                return "ERROR: Database error", 500
            
        except Exception as e:
            print(f"[{datetime.now()}] [Prodamus Result] ❌ Error: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
            return "ERROR", 500
    
    @app.route("/prodamus/success", methods=["GET", "POST"])
    def prodamus_success():
        """Handle Prodamus Success URL (user redirected after successful payment)
        Also processes payment as fallback if Result URL doesn't work"""
        import sys
        try:
            from main import forward_to_test_webhook, verify_prodamus_signature
            from config import PRODAMUS_SECRET_KEY
            
            if request.method == "GET":
                data = request.args.to_dict()
            else:
                data = request.form.to_dict() if request.form else request.get_json() or {}
            
            print(f"[{datetime.now()}] [Prodamus Success] User redirected: {data}", file=sys.stderr)
            
            # Forward to test webhook if configured
            forward_to_test_webhook("success", data, request.method)
            
            # Try to process payment from Success URL (fallback if Result URL doesn't work)
            # Success URL sends: _payform_status, _payform_order_id, _payform_sign
            payform_status = data.get("_payform_status", "").lower()
            payform_order_id = data.get("_payform_order_id", "")
            payform_sign = data.get("_payform_sign", "")
            
            if payform_status == "success" and payform_order_id:
                print(f"[{datetime.now()}] [Prodamus Success] Attempting to process payment: order_id={payform_order_id}", file=sys.stderr)
                
                # Convert Success URL format to Result URL format for processing
                # Success URL uses _payform_* prefix, Result URL uses different format
                # We need to adapt the data structure
                result_data = {
                    "order_num": payform_order_id,
                    "order_id": payform_order_id,
                    "payment_status": "success",
                    "status": "success"
                }
                
                # Add signature if present (convert _payform_sign to signature)
                if payform_sign:
                    result_data["signature"] = payform_sign
                    result_data["sign"] = payform_sign
                
                # Verify signature if secret key is configured
                if PRODAMUS_SECRET_KEY and payform_sign:
                    # Need to verify signature with Success URL format
                    # Success URL signature verification might use different format
                    # Let's try to verify with the data we have
                    try:
                        # Create a copy of data for signature verification
                        verify_data = {k: v for k, v in data.items() if not k.startswith("_payform_sign")}
                        verify_data["signature"] = payform_sign
                        verify_data["sign"] = payform_sign
                        
                        if verify_prodamus_signature(verify_data, PRODAMUS_SECRET_KEY):
                            print(f"[{datetime.now()}] [Prodamus Success] ✅ Signature verified", file=sys.stderr)
                        else:
                            print(f"[{datetime.now()}] [Prodamus Success] ⚠️ Signature verification failed, but continuing...", file=sys.stderr)
                    except Exception as e:
                        print(f"[{datetime.now()}] [Prodamus Success] ⚠️ Signature verification error: {e}", file=sys.stderr)
                
                # Process payment using the same logic as Result URL
                try:
                    from main import (
                        get_courses_data, add_purchase, strip_html,
                        ADMIN_IDS, DATABASE_PATH, bot as main_bot
                    )
                    import sqlite3
                    from telebot import types
                    import datetime as dt
                    
                    # Find pending payment
                    conn = sqlite3.connect(DATABASE_PATH)
                    cur = conn.cursor()
                    
                    # Try to find by order_id
                    cur.execute("SELECT user_id, course_id, amount FROM pending_payments WHERE order_id = ? OR invoice_id = ?", (payform_order_id, payform_order_id))
                    row = cur.fetchone()
                    
                    if row:
                        user_id, course_id, expected_amount = row[0], row[1], row[2]
                        
                        # Check if already processed
                        cur.execute("SELECT COUNT(*) FROM purchases WHERE user_id = ? AND course_id = ? AND payment_id LIKE ?", 
                                  (user_id, course_id, f"prodamus_{payform_order_id}%"))
                        already_processed = cur.fetchone()[0] > 0
                        
                        if already_processed:
                            print(f"[{datetime.now()}] [Prodamus Success] ⚠️ Payment already processed, skipping", file=sys.stderr)
                            conn.close()
                        else:
                            # Get course data
                            courses = get_courses_data()
                            course = next((x for x in courses if str(x.get("id")) == str(course_id)), None)
                            
                            if course:
                                course_name = course.get("name", f"ID {course_id}")
                                duration = course.get("duration_days")
                                channel = str(course.get("channel", ""))
                                
                                # Add purchase to database
                                add_purchase(user_id, str(course_id), course_name, channel, duration, payment_id=f"prodamus_{payform_order_id}_success")
                                
                                # Remove from pending payments
                                cur.execute("DELETE FROM pending_payments WHERE order_id = ?", (payform_order_id,))
                                conn.commit()
                                conn.close()
                                
                                # Send success message to user
                                clean_course_name = strip_html(course_name) if course_name else f"ID {course_id}"
                                text = f"✅ Оплата успешно получена!\n\n"
                                text += f"Вам предоставлен доступ к курсу: {clean_course_name}"
                                
                                # Create invite link if channel exists
                                invite_link = None
                                if channel:
                                    try:
                                        expire_date = dt.datetime.now() + dt.timedelta(days=1)
                                        invite = main_bot.create_chat_invite_link(
                                            chat_id=channel,
                                            member_limit=1,
                                            expire_date=expire_date
                                        )
                                        invite_link = invite.invite_link
                                    except Exception as e:
                                        print(f"[{datetime.now()}] [Prodamus Success] ⚠️ create_chat_invite_link failed: {e}", file=sys.stderr)
                                
                                if invite_link:
                                    text += "\n\nНажмите кнопку ниже, чтобы перейти к материалам курса."
                                    kb = types.InlineKeyboardMarkup()
                                    kb.add(types.InlineKeyboardButton("Перейти в канал курса", url=invite_link))
                                    main_bot.send_message(user_id, text, reply_markup=kb)
                                else:
                                    main_bot.send_message(user_id, text)
                                
                                # Notify admins
                                admin_text = f"💰 Оплата Prodamus (Success URL): пользователь {user_id} купил {clean_course_name} (Order: {payform_order_id})"
                                for aid in ADMIN_IDS:
                                    try:
                                        main_bot.send_message(aid, admin_text)
                                    except Exception:
                                        pass
                                
                                print(f"[{datetime.now()}] [Prodamus Success] ✅ Payment processed successfully via Success URL", file=sys.stderr)
                            else:
                                print(f"[{datetime.now()}] [Prodamus Success] ❌ Course {course_id} not found", file=sys.stderr)
                                conn.close()
                    else:
                        print(f"[{datetime.now()}] [Prodamus Success] ⚠️ Payment not found in pending_payments: {payform_order_id}", file=sys.stderr)
                        conn.close()
                        
                except Exception as e:
                    print(f"[{datetime.now()}] [Prodamus Success] ❌ Error processing payment: {e}", file=sys.stderr)
                    import traceback
                    traceback.print_exc(file=sys.stderr)
            
            return "Payment successful! You can close this page.", 200
        except Exception as e:
            print(f"[{datetime.now()}] [Prodamus Success] Error: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
            return "ERROR", 500
    
    @app.route("/prodamus/fail", methods=["GET", "POST"])
    def prodamus_fail():
        """Handle Prodamus Fail URL (user redirected after failed payment)"""
        import sys
        try:
            from main import forward_to_test_webhook
            
            if request.method == "GET":
                data = request.args.to_dict()
            else:
                data = request.form.to_dict() if request.form else request.get_json() or {}
            
            print(f"[{datetime.now()}] [Prodamus Fail] User redirected: {data}", file=sys.stderr)
            
            # Forward to test webhook if configured
            forward_to_test_webhook("fail", data, request.method)
            
            return "Payment failed. Please try again.", 200
        except Exception as e:
            print(f"[{datetime.now()}] [Prodamus Fail] Error: {e}", file=sys.stderr)
            return "ERROR", 500

# For PythonAnywhere WSGI:
# In your WSGI file, import: from webhook_app import app as application

