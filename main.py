# main.py
import datetime
import sqlite3
import json
import telebot
from telebot import types
import os
import time
import re
import hashlib
from urllib.parse import urlencode, quote
from flask import Flask, request, abort
import requests

from config import TELEGRAM_BOT_TOKEN, PAYMENT_PROVIDER_TOKEN, ADMIN_IDS, CURRENCY, USE_WEBHOOK, DATABASE_PATH, GSHEET_ID, ENABLE_PRODAMUS, PRODAMUS_PAYFORM_URL, PRODAMUS_SECRET_KEY, PRODAMUS_TEST_MODE, PRODAMUS_SYSTEM_ID, PRODAMUS_TEST_WEBHOOK_URL
from db import add_user, get_user, add_purchase, get_active_subscriptions, has_active_subscription, mark_subscription_expired, get_all_active_subscriptions
from google_sheets import get_courses_data, get_texts_data


bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN, parse_mode=None, threaded=False)

# In-memory state for Prodamus email collection
# Format: {user_id: {"course_id": course_id, "order_id": order_id, "price": price, "name": name}}
prodamus_pending_emails = {}

# --- Webhook / WSGI (PythonAnywhere) support ---
# Import webhook config from config.py (already processed and normalized)
try:
    from config import WEBHOOK_URL, WEBHOOK_PATH, WEBHOOK_SECRET_TOKEN, WEBHOOK_HOST
except ImportError:
    # Fallback to environment variables if config.py is not available
    WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")
    WEBHOOK_PATH = os.environ.get("WEBHOOK_PATH", "")
    WEBHOOK_SECRET_TOKEN = os.environ.get("WEBHOOK_SECRET_TOKEN", "")
    WEBHOOK_HOST = os.environ.get("WEBHOOK_HOST", "")
    # Normalize WEBHOOK_PATH (ensure it starts with "/")
    if WEBHOOK_PATH and not WEBHOOK_PATH.startswith("/"):
        WEBHOOK_PATH = "/" + WEBHOOK_PATH

# Flask app to be used by the WSGI server on PythonAnywhere
application = Flask(__name__)

@application.get("/")
def _health():
    return "OK", 200

# Webhook endpoint - use WEBHOOK_PATH if set, otherwise use default path
webhook_route = WEBHOOK_PATH if WEBHOOK_PATH else f"/{TELEGRAM_BOT_TOKEN}"

@application.post(webhook_route)
def _webhook():
    # Validate Telegram secret header if configured
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if WEBHOOK_SECRET_TOKEN and secret != WEBHOOK_SECRET_TOKEN:
        abort(403)
    # Forward the update to pyTelegramBotAPI
    try:
        update = telebot.types.Update.de_json(request.stream.read().decode("utf-8"))
        bot.process_new_updates([update])
    except Exception as e:
        print(f"Error processing webhook update: {e}")
    return "OK", 200

@application.get("/diag")
def _diag():
    # Light-weight diagnostics endpoint (admin-only command /diag_channels has more details)
    try:
        report = check_course_channels()
    except Exception as e:
        report = f"diag error: {e}"
    return report, 200

# Helper function to forward webhook data to test URL
def forward_to_test_webhook(endpoint_name: str, data: dict, method: str = "GET"):
    """Forward webhook data to test webhook URL (e.g., webhook.site) for debugging"""
    if not PRODAMUS_TEST_WEBHOOK_URL:
        return
    
    try:
        test_data = {
            "endpoint": endpoint_name,
            "method": method,
            "data": data,
            "timestamp": time.time()
        }
        requests.post(PRODAMUS_TEST_WEBHOOK_URL, json=test_data, timeout=5)
        print(f"[Prodamus Test] Forwarded {endpoint_name} data to test webhook")
    except Exception as e:
        print(f"[Prodamus Test] Failed to forward to test webhook: {e}")

# Prodamus webhook handlers (Success/Fail/Result URLs)
@application.route("/prodamus/result", methods=["GET", "POST"])
def prodamus_result():
    """
    Handle Prodamus Result URL notification (payment status update)
    This endpoint receives payment notifications from Prodamus
    Must return "OK" if payment is valid, or error code otherwise
    """
    try:
        # Get request data (can be GET or POST)
        if request.method == "GET":
            data = request.args.to_dict()
        else:
            data = request.form.to_dict() if request.form else request.get_json() or {}
        
        # For POST requests, check signature in header (Prodamus sends it as 'sign' header)
        if request.method == "POST" and "sign" in request.headers:
            data["signature"] = request.headers.get("sign", "")
        
        # Log the notification for debugging
        print(f"[Prodamus Result] Received notification: {data}")
        print(f"[Prodamus Result] Request headers: {dict(request.headers)}")
        
        # Forward to test webhook if configured
        forward_to_test_webhook("result", data, request.method)
        
        # Verify signature if secret key is configured
        if PRODAMUS_SECRET_KEY:
            if not verify_prodamus_signature(data, PRODAMUS_SECRET_KEY):
                print(f"[Prodamus Result] Invalid signature")
                return "ERROR: Invalid signature", 400
        
        # Extract required parameters
        # Prodamus may send order_id, order, or order_num parameter
        # order_num is used in Result URL POST requests
        order_number = data.get("order_num", "") or data.get("order_id", "") or data.get("order", "")
        amount = data.get("sum", "") or data.get("amount", "")
        # Prodamus may send status or payment_status
        payment_status = (data.get("payment_status", "") or data.get("status", "")).lower()
        
        if not order_number or not amount:
            print(f"[Prodamus Result] Missing required parameters. Received data: {data}")
            return "ERROR: Missing parameters", 400
        
        # Only process successful payments
        if payment_status not in ("success", "paid", "successful"):
            print(f"[Prodamus Result] Payment not successful, status: {payment_status}")
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
                # Column already exists, ignore
                pass
            try:
                cur.execute("ALTER TABLE pending_payments ADD COLUMN order_id TEXT")
            except sqlite3.OperationalError:
                # Column already exists, ignore
                pass
            # Try to find by order_id or invoice_id
            cur.execute("SELECT user_id, course_id, amount FROM pending_payments WHERE order_id = ? OR invoice_id = ?", (order_number, order_number))
            row = cur.fetchone()
            
            if not row:
                print(f"[Prodamus Result] Payment not found for order/invoice {order_number}")
                conn.close()
                return "ERROR: Payment not found", 404
            
            user_id, course_id, expected_amount = row[0], row[1], row[2]
            
            # Verify amount matches
            if abs(float(amount) - float(expected_amount)) > 0.01:  # Allow small floating point differences
                print(f"[Prodamus Result] Amount mismatch for order {order_number}: expected {expected_amount}, got {amount}")
                conn.close()
                return "ERROR: Amount mismatch", 400
            
            # Get course data
            try:
                courses = get_courses_data()
                course = next((x for x in courses if str(x.get("id")) == str(course_id)), None)
                if not course:
                    print(f"[Prodamus Result] Course {course_id} not found")
                    conn.close()
                    return "ERROR: Course not found", 404
                
                course_name = course.get("name", f"ID {course_id}")
                duration = int(course.get("duration_minutes", 0))
                channel = str(course.get("channel", ""))
                
                # Add purchase to database
                expiry_ts = add_purchase(user_id, str(course_id), course_name, channel, duration, payment_id=f"prodamus_{order_number}")
                
                # Remove from pending payments (use order_id to match storage pattern)
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
                        invite = bot.create_chat_invite_link(chat_id=channel, member_limit=1, expire_date=None)
                        invite_link = invite.invite_link
                    except Exception as e:
                        print(f"create_chat_invite_link failed for {channel}: {e}")
                
                if invite_link:
                    text += "\n\nНажмите кнопку ниже, чтобы перейти к материалам курса."
                    kb = types.InlineKeyboardMarkup()
                    kb.add(types.InlineKeyboardButton("Перейти в канал курса", url=invite_link))
                    bot.send_message(user_id, text, reply_markup=kb)
                else:
                    bot.send_message(user_id, text)
                
                # Notify admins
                admin_text = f"💰 Оплата Prodamus: пользователь {user_id} купил {clean_course_name} на сумму {amount} руб. (Order: {order_number})"
                for aid in ADMIN_IDS:
                    try:
                        bot.send_message(aid, admin_text)
                    except Exception:
                        pass
                
                print(f"[Prodamus Result] Successfully processed payment for order {order_number}")
                return "OK", 200
                
            except Exception as e:
                print(f"[Prodamus Result] Error processing payment: {e}")
                conn.close()
                return "ERROR: Processing error", 500
                
        except Exception as e:
            print(f"[Prodamus Result] Database error: {e}")
            return "ERROR: Database error", 500
        
    except Exception as e:
        print(f"[Prodamus Result] Error: {e}")
        return "ERROR", 500

@application.route("/prodamus/success", methods=["GET", "POST"])
def prodamus_success():
    """
    Handle Prodamus Success URL (user redirected after successful payment)
    """
    try:
        if request.method == "GET":
            data = request.args.to_dict()
        else:
            data = request.form.to_dict() if request.form else request.get_json() or {}
        
        print(f"[Prodamus Success] User redirected: {data}")
        
        # Forward to test webhook if configured
        forward_to_test_webhook("success", data, request.method)
        
        # Return a simple success page or redirect
        return "Payment successful! You can close this page.", 200
    except Exception as e:
        print(f"[Prodamus Success] Error: {e}")
        return "ERROR", 500

@application.route("/prodamus/fail", methods=["GET", "POST"])
def prodamus_fail():
    """
    Handle Prodamus Fail URL (user redirected after failed payment)
    """
    try:
        if request.method == "GET":
            data = request.args.to_dict()
        else:
            data = request.form.to_dict() if request.form else request.get_json() or {}
        
        print(f"[Prodamus Fail] User redirected: {data}")
        
        # Forward to test webhook if configured
        forward_to_test_webhook("fail", data, request.method)
        
        # Return a simple failure page or redirect
        return "Payment failed. Please try again.", 200
    except Exception as e:
        print(f"[Prodamus Fail] Error: {e}")
        return "ERROR", 500

# Configure Telegram webhook at import time when running under WSGI
if USE_WEBHOOK and WEBHOOK_URL and not WEBHOOK_URL.startswith("https://<"):
    try:
        bot.remove_webhook()
        time.sleep(0.5)
        bot.set_webhook(
            url=WEBHOOK_URL,
            secret_token=WEBHOOK_SECRET_TOKEN,
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query", "shipping_query", "pre_checkout_query"]
        )
        print(f"Webhook set to {WEBHOOK_URL}")
    except Exception as e:
        print("Failed to set webhook:", e)

# Price helpers
def rub_to_kopecks(rub: float) -> int:
    return int(round(float(rub) * 100))

def rub_str(rub: float) -> str:
    return f"{float(rub):.2f}"

def strip_html(text: str) -> str:
    """Remove HTML tags from text (for use in button labels, etc.)"""
    if not text:
        return ""
    return re.sub(r'<[^>]+>', '', str(text))

def clean_html_text(text: str) -> str:
    """Clean text that might have HTML - remove tags but keep content"""
    if not text:
        return ""
    # Remove HTML tags but keep the text content
    text = re.sub(r'<[^>]+>', '', str(text))
    # Decode common HTML entities if any
    text = text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    return text.strip()

# Prodamus payment integration
def generate_prodamus_signature(data: dict, secret_key: str) -> str:
    """
    Generate Prodamus webhook signature.
    Format: MD5 hash of sorted key-value pairs + secret key
    According to Prodamus docs: sort all parameters except 'sign'/'signature', join with &, add secret key, calculate MD5
    """
    # Sort keys alphabetically, exclude signature-related keys
    sorted_keys = sorted([k for k in data.keys() if k not in ('signature', 'sign')])
    # Build signature string
    signature_string = '&'.join([f"{k}={data[k]}" for k in sorted_keys])
    signature_string += f"&{secret_key}"
    # Calculate MD5 hash
    return hashlib.md5(signature_string.encode('utf-8')).hexdigest()

def verify_prodamus_signature(data: dict, secret_key: str) -> bool:
    """
    Verify Prodamus webhook signature.
    Prodamus may send signature as 'sign' (in header) or 'signature' (in body)
    """
    # Check for signature in data (can be 'sign' or 'signature')
    received_signature = data.get('signature', '') or data.get('sign', '')
    if not received_signature:
        print(f"[Prodamus] No signature found in data")
        return False
    
    received_signature = received_signature.lower()
    calculated_signature = generate_prodamus_signature(data, secret_key).lower()
    
    if PRODAMUS_TEST_MODE:
        print(f"[Prodamus] Signature verification: received={received_signature[:20]}..., calculated={calculated_signature[:20]}...")
    
    return received_signature == calculated_signature

def create_prodamus_invoice(order_id: str, amount: float, product_name: str = "", customer_email: str = "", customer_phone: str = "") -> str:
    """
    Create Prodamus invoice via API and get invoice_id.
    Returns invoice_id if successful, None otherwise.
    
    Documentation: 
    - https://help.prodamus.ru/payform/integracii/rest-api/instrukcii-dlya-samostoyatelnaya-integracii-servisov
    - https://help.prodamus.ru/payform/priyom-oplaty/kak-sozdat-personalnuyu-platyozhnuyu-ssylku
    """
    try:
        # Build API URL
        if PRODAMUS_TEST_MODE:
            api_url = f"https://{PRODAMUS_PAYFORM_URL}/"
        else:
            api_url = f"https://{PRODAMUS_PAYFORM_URL}/"
        
        # Prepare request data according to Prodamus API
        # For personal payment link, we need: products, order_id, customerEmail or customerPhone
        data = {
            "do": "link",  # Create invoice and get link
            "products[0][name]": product_name[:255] if product_name else "Доступ к курсу",
            "products[0][price]": str(float(amount)),
            "products[0][quantity]": "1",
            "order_id": order_id,
        }
        
        # Add system ID if configured
        if PRODAMUS_SYSTEM_ID:
            data["sys"] = PRODAMUS_SYSTEM_ID
        
        # For personal link, at least one contact is required
        if customer_email:
            data["customerEmail"] = customer_email
        
        if customer_phone:
            data["customerPhone"] = customer_phone
        
        # If no contact info, use a placeholder (some setups may require this)
        if not customer_email and not customer_phone:
            data["customerEmail"] = "customer@example.com"  # Placeholder
        
        if PRODAMUS_TEST_MODE:
            print(f"[Prodamus] Creating invoice with data: {data}")
            print(f"[Prodamus] Request URL: {api_url}")
        
        # Try GET request first (most common for payment forms)
        response = None
        try:
            response = requests.get(api_url, params=data, allow_redirects=True, timeout=15)
            if PRODAMUS_TEST_MODE:
                print(f"[Prodamus] GET request successful, status: {response.status_code}")
        except Exception as e:
            if PRODAMUS_TEST_MODE:
                print(f"[Prodamus] GET request failed: {e}, trying POST")
            # Fallback to POST
            try:
                response = requests.post(api_url, data=data, allow_redirects=True, timeout=15)
                if PRODAMUS_TEST_MODE:
                    print(f"[Prodamus] POST request successful, status: {response.status_code}")
            except Exception as e2:
                print(f"[Prodamus] Both GET and POST failed: {e2}")
                return None
        
        if not response:
            return None
        
        # Get final URL after redirects
        final_url = response.url
        
        # Try to extract from response text first (Prodamus returns short link in response text)
        response_text = response.text.strip()
        if PRODAMUS_TEST_MODE:
            print(f"[Prodamus] Final URL after redirects: {final_url}")
            print(f"[Prodamus] Response text (first 1000 chars): {response_text[:1000]}")
        
        # Prodamus may return short link like "https://payform.ru/5h9NArs/" in response text
        # Extract the short code (invoice_id) from this link
        if response_text.startswith("http"):
            # Response is a URL - extract invoice_id from it
            # Format: https://payform.ru/5h9NArs/ or https://testwork1.payform.ru/?invoice_id=xxx
            if "invoice_id=" in response_text:
                invoice_id = response_text.split("invoice_id=")[1].split("&")[0].split("?")[0].split("#")[0].split("/")[0]
                if invoice_id and len(invoice_id) > 10:
                    if PRODAMUS_TEST_MODE:
                        print(f"[Prodamus] Extracted invoice_id from response URL: {invoice_id}")
                    return invoice_id
            # Try to extract short code from URL path
            # Format: https://payform.ru/5h9NArs/ -> invoice_id = 5h9NArs
            import re
            match = re.search(r'payform\.ru/([a-zA-Z0-9]+)', response_text)
            if match:
                invoice_id = match.group(1)
                if len(invoice_id) >= 6:  # Short codes are usually 6+ characters
                    if PRODAMUS_TEST_MODE:
                        print(f"[Prodamus] Extracted invoice_id from short link: {invoice_id}")
                    return invoice_id
        
        # Extract invoice_id from final URL
        if "invoice_id=" in final_url:
            invoice_id = final_url.split("invoice_id=")[1].split("&")[0].split("?")[0].split("#")[0]
            if invoice_id and len(invoice_id) > 10:  # Basic validation
                if PRODAMUS_TEST_MODE:
                    print(f"[Prodamus] Extracted invoice_id from final URL: {invoice_id}")
                return invoice_id
        
        # Look for invoice_id in various formats
        import re
        patterns = [
            r'invoice_id[=:](\w{20,})',  # invoice_id=xxx or invoice_id:xxx
            r'invoice_id["\']?\s*[:=]\s*["\']?(\w{20,})',  # invoice_id: "xxx"
            r'<input[^>]*name=["\']invoice_id["\'][^>]*value=["\'](\w{20,})',  # HTML input
            r'data-invoice-id=["\'](\w{20,})',  # data attribute
        ]
        
        for pattern in patterns:
            match = re.search(pattern, response_text, re.IGNORECASE)
            if match:
                invoice_id = match.group(1)
                if len(invoice_id) > 10:
                    if PRODAMUS_TEST_MODE:
                        print(f"[Prodamus] Extracted invoice_id using pattern {pattern}: {invoice_id}")
                    return invoice_id
        
        # Try JSON response
        try:
            if response.headers.get("content-type", "").startswith("application/json"):
                response_data = response.json()
                if PRODAMUS_TEST_MODE:
                    print(f"[Prodamus] JSON response: {response_data}")
                if "invoice_id" in response_data:
                    return str(response_data["invoice_id"])
                if "link" in response_data:
                    link = str(response_data["link"])
                    if "invoice_id=" in link:
                        invoice_id = link.split("invoice_id=")[1].split("&")[0].split("?")[0]
                        return invoice_id
        except:
            pass
        
        if PRODAMUS_TEST_MODE:
            print(f"[Prodamus] Could not extract invoice_id. Final URL: {final_url}")
            print(f"[Prodamus] Response status: {response.status_code}")
        
        return None
        
    except Exception as e:
        print(f"[Prodamus] Error creating invoice: {e}")
        import traceback
        traceback.print_exc()
        return None

def generate_prodamus_payment_url(order_number: str, amount: float, product_name: str = "", customer_email: str = "", customer_phone: str = "") -> str:
    """
    Generate Prodamus payment URL with all parameters.
    
    Documentation: https://help.prodamus.ru/payform/integracii/rest-api/instrukcii-dlya-samostoyatelnaya-integracii-servisov
    
    Args:
        order_number: Unique order number (used in webhook)
        amount: Payment amount in rubles
        product_name: Product name (required)
        customer_email: Customer email (optional, but recommended for pre-filling form)
        customer_phone: Customer phone (optional)
    
    Returns:
        Payment URL string
    """
    # Build base URL
    if PRODAMUS_TEST_MODE:
        base_url = f"https://{PRODAMUS_PAYFORM_URL}/?old_auth=1"
    else:
        base_url = f"https://{PRODAMUS_PAYFORM_URL}/"
    
    params = {
        "do": "pay",
        "products[0][name]": product_name[:255] if product_name else "Доступ к курсу",
        "products[0][price]": str(float(amount)),
        "products[0][quantity]": "1",
        "order_id": order_number,
        "order": order_number,
    }
    
    if PRODAMUS_SYSTEM_ID:
        params["sys"] = PRODAMUS_SYSTEM_ID
    
    if customer_email:
        # Try multiple parameter names for email pre-filling
        # Prodamus may use different parameter names in different setups
        params["email"] = customer_email  # Simple parameter name
        params["customerEmail"] = customer_email  # CamelCase variant
        params["customer_email"] = customer_email  # Snake_case variant
    
    if customer_phone:
        params["customerPhone"] = customer_phone
        params["customer_phone"] = customer_phone  # Also try snake_case variant
    
    query_string = urlencode(params, doseq=True)
    full_url = f"{base_url}&{query_string}" if "?" in base_url else f"{base_url}?{query_string}"
    
    if PRODAMUS_TEST_MODE:
        print(f"[Prodamus] Generated payment URL (test mode): {full_url}")
    
    return full_url

# Load customizable texts
texts = {}
try:
    texts = get_texts_data()
except Exception as e:
    print("Warning: could not fetch texts from Google Sheets:", e)

WELCOME_MSG = texts.get("welcome_message", "Здравствуйте! Этот бот поможет вам купить курсы по макияжу.\nНиже находится меню.")
SUPPORT_MSG = texts.get("support_message", "Если у вас есть вопросы, напишите нам в поддержку.")
CATALOG_TITLE = texts.get("catalog_title", "Каталог курсов:")
ALREADY_PURCHASED_MSG = texts.get("already_purchased_message", "У вас уже есть доступ к этому курсу.")
COURSE_NOT_AVAILABLE_MSG = texts.get("course_not_available_message", "Извините, курс сейчас недоступен.")
PURCHASE_SUCCESS_MSG = texts.get("purchase_success_message", "Оплата успешно выполнена! Вам предоставлен доступ к курсу {course_name}.")
PURCHASE_RECEIPT_MSG = texts.get("purchase_receipt_message", "Чек об оплате будет отправлен на ваш email в системе YooKassa/Мой Налог.")
SUBSCRIPTION_EXPIRED_MSG = texts.get("subscription_expired_message", "Ваш доступ к курсу {course_name} закончился.")


# Main menu keyboard generator (with admin buttons conditionally)
def get_main_menu_keyboard(user_id: int) -> types.ReplyKeyboardMarkup:
    """Generate main menu keyboard, adding admin buttons if user is admin"""
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn_catalog = types.KeyboardButton("Каталог")
    btn_subs = types.KeyboardButton("Активные подписки")
    btn_support = types.KeyboardButton("Поддержка")
    btn_oferta = types.KeyboardButton("Оферта")
    keyboard.add(btn_catalog)
    keyboard.add(btn_subs, btn_support)
    keyboard.add(btn_oferta)
    
    # Add admin buttons if user is admin
    if user_id in ADMIN_IDS:
        btn_admin_subs = types.KeyboardButton("📊 Все подписки")
        btn_admin_sheets = types.KeyboardButton("📋 Google Sheets")
        keyboard.add(btn_admin_subs, btn_admin_sheets)
    
    return keyboard

# Legacy main menu keyboard for backward compatibility (used in some places)
main_menu_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
btn_catalog = types.KeyboardButton("Каталог")
btn_subs = types.KeyboardButton("Активные подписки")
btn_support = types.KeyboardButton("Поддержка")
btn_oferta = types.KeyboardButton("Оферта")
main_menu_keyboard.add(btn_catalog)
main_menu_keyboard.add(btn_subs, btn_support)
main_menu_keyboard.add(btn_oferta)

@bot.message_handler(commands=['start'])
def handle_start(message: telebot.types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or ""
    add_user(user_id, username)

    # Use dynamic keyboard that includes admin buttons if user is admin
    keyboard = get_main_menu_keyboard(user_id)
    welcome_image_url = texts.get("welcome_image_url")
    try:
        if welcome_image_url:
            bot.send_photo(user_id, welcome_image_url, caption=WELCOME_MSG, reply_markup=keyboard)
        else:
            bot.send_message(user_id, WELCOME_MSG, reply_markup=keyboard)
    except Exception:
        bot.send_message(user_id, WELCOME_MSG, reply_markup=keyboard)

def send_catalog_message(user_id, edit_message=None, edit_message_id=None, edit_chat_id=None):
    """Helper function to send/update catalog message"""
    try:
        courses = get_courses_data()
    except Exception as e:
        error_msg = "Не удалось загрузить каталог курсов. Попробуйте позже."
        if edit_message:
            try:
                bot.edit_message_text(error_msg, chat_id=edit_chat_id, message_id=edit_message_id)
            except Exception:
                bot.send_message(user_id, error_msg)
        else:
            bot.send_message(user_id, error_msg)
        print("Error fetching courses:", e)
        return
    
    if not courses:
        empty_msg = "Каталог пока пуст."
        if edit_message:
            try:
                bot.edit_message_text(empty_msg, chat_id=edit_chat_id, message_id=edit_message_id)
            except Exception:
                bot.send_message(user_id, empty_msg)
        else:
            bot.send_message(user_id, empty_msg)
        return

    kb = types.InlineKeyboardMarkup()
    for c in courses:
        cid = str(c.get("id"))
        name = c.get("name", "Курс")
        # Strip HTML from button labels (buttons don't support HTML formatting)
        button_label = strip_html(name)
        kb.add(types.InlineKeyboardButton(button_label, callback_data=f"course_{cid}"))
    banner = texts.get("catalog_image_url")
    caption = texts.get("catalog_text", CATALOG_TITLE)
    
    if edit_message:
        # When going back to catalog, always delete old message and send new one
        # This ensures the image updates correctly (can't change photo in existing message)
        try:
            bot.delete_message(chat_id=edit_chat_id, message_id=edit_message_id)
        except Exception:
            pass  # If deletion fails (e.g., message too old), continue anyway
        # Send new catalog message
        try:
            if banner:
                bot.send_photo(user_id, banner, caption=caption, reply_markup=kb)
            else:
                bot.send_message(user_id, caption, reply_markup=kb)
        except Exception:
            bot.send_message(user_id, caption, reply_markup=kb)
    else:
        # Send new message
        try:
            if banner:
                bot.send_photo(user_id, banner, caption=caption, reply_markup=kb)
            else:
                bot.send_message(user_id, caption, reply_markup=kb)
        except Exception:
            bot.send_message(user_id, caption, reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "Каталог")
def handle_catalog(message: telebot.types.Message):
    user_id = message.from_user.id
    send_catalog_message(user_id)

@bot.message_handler(func=lambda m: m.text == "Активные подписки")
def handle_active(message: telebot.types.Message):
    user_id = message.from_user.id
    subs = get_active_subscriptions(user_id)
    subs = list(subs) if subs else []
    if not subs:
        bot.send_message(user_id, "У вас нет активных подписок.")
        return
    text = "Ваши активные подписки:\n"
    for s in subs:
        course_name = s["course_name"]
        clean_course_name = strip_html(course_name) if course_name else "Курс"
        channel_id = s["channel_id"]
        expiry_ts = s["expiry"]
        dt = datetime.datetime.fromtimestamp(expiry_ts)
        dstr = dt.strftime("%Y-%m-%d")
        text += f"• {clean_course_name} (доступ до {dstr}) – "
        if str(channel_id).startswith("@"):
            text += f"{channel_id}\n"
        else:
            text += "ссылка недоступна\n"
    bot.send_message(user_id, text, disable_web_page_preview=True)

@bot.message_handler(func=lambda m: m.text == "Поддержка")
def handle_support(message: telebot.types.Message):
    bot.send_message(message.from_user.id, SUPPORT_MSG)

# Handler for email input for Prodamus payments
@bot.message_handler(func=lambda m: m.from_user.id in prodamus_pending_emails)
def handle_prodamus_email(message: telebot.types.Message):
    user_id = message.from_user.id
    email_text = message.text.strip()
    
    # Validate email format
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email_text):
        bot.send_message(user_id, "❌ Неверный формат email адреса. Пожалуйста, отправьте корректный email (например: example@mail.ru)")
        return
    
    # Get pending payment info
    if user_id not in prodamus_pending_emails:
        bot.send_message(user_id, "❌ Сессия истекла. Пожалуйста, начните оплату заново.")
        return
    
    payment_info = prodamus_pending_emails.pop(user_id)
    course_id = payment_info["course_id"]
    order_id = payment_info["order_id"]
    price = payment_info["price"]
    clean_name = payment_info["name"]
    
    # Save email to user profile
    try:
        user = get_user(user_id)
        if user:
            # Update user email in database (if you have email field)
            conn = sqlite3.connect(DATABASE_PATH)
            cur = conn.cursor()
            # Try to add email column if it doesn't exist
            try:
                cur.execute("ALTER TABLE users ADD COLUMN email TEXT")
            except sqlite3.OperationalError:
                pass
            cur.execute("UPDATE users SET email = ? WHERE user_id = ?", (email_text, user_id))
            conn.commit()
            conn.close()
    except Exception as e:
        print(f"Error saving email to user profile: {e}")
    
    # Generate payment URL with real email
    customer_email = email_text
    customer_phone = ""
    
    try:
        payment_url = generate_prodamus_payment_url(
            order_number=order_id,
            amount=price,
            product_name=clean_name,
            customer_email=customer_email,
            customer_phone=customer_phone
        )
        
        # Store payment info in database
        try:
            conn = sqlite3.connect(DATABASE_PATH)
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
            try:
                cur.execute("ALTER TABLE pending_payments ADD COLUMN payment_system TEXT")
            except sqlite3.OperationalError:
                pass
            try:
                cur.execute("ALTER TABLE pending_payments ADD COLUMN order_id TEXT")
            except sqlite3.OperationalError:
                pass
            
            # Use order_id as primary key
            cur.execute(
                "INSERT OR REPLACE INTO pending_payments (invoice_id, user_id, course_id, amount, created_at, payment_system, order_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (order_id, user_id, course_id, price, int(time.time()), "prodamus", order_id)
            )
            conn.commit()
            conn.close()
            
            if PRODAMUS_TEST_MODE:
                print(f"[Prodamus] Stored pending payment with email: order_id={order_id}, email={customer_email}")
        except Exception as e:
            print(f"Error storing pending payment: {e}")
        
        # Send payment link to user
        text = f"✅ Email сохранен!\n\n"
        text += f"💳 Оплата курса: {clean_name}\n\n"
        text += f"Сумма: {price:.2f} руб.\n\n"
        text += "Нажмите на кнопку ниже, чтобы перейти к оплате:"
        
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("💳 Оплатить через Prodamus", url=payment_url))
        kb.add(types.InlineKeyboardButton("⬅️ Назад", callback_data=f"course_{course_id}"))
        
        bot.send_message(user_id, text, reply_markup=kb)
        
        if PRODAMUS_TEST_MODE:
            print(f"[Prodamus TEST MODE] Generated payment URL with email for order_id {order_id}: {payment_url}")
            
    except Exception as e:
        error_msg = str(e)
        print(f"Error generating Prodamus payment URL: {error_msg}")
        bot.send_message(user_id, "❌ Ошибка при создании ссылки на оплату. Пожалуйста, попробуйте позже или обратитесь в поддержку.")


# Handler for "Оферта" button
@bot.message_handler(func=lambda m: m.text == "Оферта")
def handle_oferta(message: telebot.types.Message):
    user_id = message.from_user.id
    oferta_url = "https://github.com/george-dvoryak/cdn/blob/main/oferta.pdf?raw=true"
    try:
        bot.send_document(user_id, oferta_url, caption="Договор оферты (PDF)")
    except Exception:
        # Fallback: просто отправим ссылку, если по какой-то причине Telegram не скачал файл по URL
        bot.send_message(user_id, f"Договор оферты: {oferta_url}", disable_web_page_preview=False)

# Admin handlers
@bot.message_handler(func=lambda m: m.text == "📊 Все подписки")
def handle_admin_all_subscriptions(message: telebot.types.Message):
    """Admin handler: show all active subscriptions for all users"""
    user_id = message.from_user.id
    if user_id not in ADMIN_IDS:
        bot.send_message(user_id, "У вас нет доступа к этой функции.")
        return
    
    try:
        all_subs = get_all_active_subscriptions()
        all_subs = list(all_subs) if all_subs else []
        
        if not all_subs:
            bot.send_message(user_id, "Нет активных подписок.")
            return
        
        # Group by user for better readability
        user_subs = {}
        for s in all_subs:
            uid = s["user_id"]
            if uid not in user_subs:
                user_subs[uid] = []
            user_subs[uid].append(s)
        
        text = f"📊 Все активные подписки ({len(all_subs)} всего):\n\n"
        
        for uid, subs in sorted(user_subs.items()):
            # Try to get username
            user_info = get_user(uid)
            username = user_info["username"] if user_info and user_info["username"] else f"ID {uid}"
            text += f"👤 {username} (ID: {uid}):\n"
            
            for s in subs:
                course_name = s["course_name"]
                clean_course_name = strip_html(course_name) if course_name else "Курс"
                expiry_ts = s["expiry"]
                dt = datetime.datetime.fromtimestamp(expiry_ts)
                dstr = dt.strftime("%Y-%m-%d %H:%M")
                text += f"  • {clean_course_name} (до {dstr})\n"
            text += "\n"
        
        # Split message if too long (Telegram limit is 4096 chars)
        if len(text) > 4000:
            parts = text.split("\n\n")
            current_msg = ""
            for part in parts:
                if len(current_msg) + len(part) + 2 > 4000:
                    bot.send_message(user_id, current_msg, disable_web_page_preview=True)
                    current_msg = part + "\n\n"
                else:
                    current_msg += part + "\n\n"
            if current_msg.strip():
                bot.send_message(user_id, current_msg, disable_web_page_preview=True)
        else:
            bot.send_message(user_id, text, disable_web_page_preview=True)
            
    except Exception as e:
        print(f"Error in handle_admin_all_subscriptions: {e}")
        bot.send_message(user_id, f"Ошибка при получении подписок: {e}")

@bot.message_handler(func=lambda m: m.text == "📋 Google Sheets")
def handle_admin_google_sheets(message: telebot.types.Message):
    """Admin handler: open Google Sheets link"""
    user_id = message.from_user.id
    if user_id not in ADMIN_IDS:
        bot.send_message(user_id, "У вас нет доступа к этой функции.")
        return
    
    if not GSHEET_ID:
        bot.send_message(user_id, "Google Sheets ID не настроен.")
        return
    
    sheets_url = f"https://docs.google.com/spreadsheets/d/{GSHEET_ID}/edit"
    
    # Create inline keyboard with URL button
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("📋 Открыть Google Sheets", url=sheets_url))
    
    bot.send_message(
        user_id,
        "Нажмите на кнопку ниже, чтобы открыть Google Sheets:",
        reply_markup=keyboard
    )

@bot.callback_query_handler(func=lambda c: c.data.startswith("course_"))
def cb_course(c: telebot.types.CallbackQuery):
    user_id = c.from_user.id
    course_id = c.data.split("_", 1)[1]
    try:
        courses = get_courses_data()
    except Exception:
        bot.answer_callback_query(c.id, "Ошибка загрузки курса.", show_alert=True)
        return
    course = next((x for x in courses if str(x.get("id")) == str(course_id)), None)
    if not course:
        bot.answer_callback_query(c.id, "Курс не найден.", show_alert=True)
        return

    name = course.get("name", "")
    desc = course.get("description", "")
    price = course.get("price", 0)
    duration = course.get("duration_minutes", 0)
    image_url = course.get("image_url", "")
    channel_id = course.get("channel", "")

    # Strip all HTML from course name - display as plain text only
    formatted_name = strip_html(name) if name else "Курс"

    if has_active_subscription(user_id, str(course_id)):
        clean_desc = strip_html(desc) if desc else ""
        text = f"{formatted_name}\n{clean_desc}\n\n✅ {ALREADY_PURCHASED_MSG}"
        ikb = types.InlineKeyboardMarkup()
        if channel_id:
            if str(channel_id).startswith("@"):
                url = f"https://t.me/{channel_id[1:]}"
                ikb.add(types.InlineKeyboardButton("Открыть канал курса", url=url))
            else:
                invite_link = None
                try:
                    invite = bot.create_chat_invite_link(chat_id=channel_id, member_limit=1, expire_date=None)
                    invite_link = invite.invite_link
                except Exception as e:
                    print("Invite link error:", e)
                if invite_link:
                    ikb.add(types.InlineKeyboardButton("Перейти в канал курса", url=invite_link))
        ikb.add(types.InlineKeyboardButton("⬅️ Назад к каталогу", callback_data="back_to_catalog"))
        try:
            if c.message.content_type == "photo":
                bot.edit_message_caption(chat_id=c.message.chat.id, message_id=c.message.message_id, caption=text, reply_markup=ikb)
            else:
                bot.edit_message_text(text, chat_id=c.message.chat.id, message_id=c.message.message_id, reply_markup=ikb)
        except Exception:
            bot.send_message(user_id, text, reply_markup=ikb)
        bot.answer_callback_query(c.id)
        return

    # Strip HTML from description too
    clean_desc = strip_html(desc) if desc else ""
    text = f"{formatted_name}\n{clean_desc}\n\nЦена: {price} руб.\nДоступ: {duration} мин."
    ikb = types.InlineKeyboardMarkup()
    # Add payment buttons
    if ENABLE_PRODAMUS and PRODAMUS_SECRET_KEY:
        ikb.row(
            types.InlineKeyboardButton("Купить (ЮKassa)", callback_data=f"pay_yk_{course_id}"),
            types.InlineKeyboardButton("Купить (Prodamus)", callback_data=f"pay_prodamus_{course_id}")
        )
    else:
        ikb.add(types.InlineKeyboardButton("Купить (ЮKassa)", callback_data=f"pay_yk_{course_id}"))
    ikb.add(types.InlineKeyboardButton("⬅️ Назад к каталогу", callback_data="back_to_catalog"))
    
    # Try to edit existing message first, then fallback to sending new message
    message_sent = False
    try:
        if image_url:
            # If course has image, try to edit message media (if original was photo) or send new photo
            if c.message.content_type == "photo":
                # Try to edit photo
                try:
                    bot.edit_message_media(
                        chat_id=c.message.chat.id,
                        message_id=c.message.message_id,
                        media=types.InputMediaPhoto(image_url, caption=text),
                        reply_markup=ikb
                    )
                    bot.answer_callback_query(c.id)
                    return
                except Exception as e:
                    # If edit fails, delete old message and send new one
                    print(f"Failed to edit message media: {e}")
                    try:
                        bot.delete_message(chat_id=c.message.chat.id, message_id=c.message.message_id)
                    except Exception:
                        pass
            # Send new photo (either because original wasn't photo, or edit/delete failed)
            bot.send_photo(user_id, image_url, caption=text, reply_markup=ikb)
            message_sent = True
        else:
            # No course image - edit text or send new message
            if c.message.content_type == "photo":
                # Original was photo, but course has no image - send text message
                bot.send_message(user_id, text, reply_markup=ikb)
                message_sent = True
            else:
                # Original was text - can edit
                try:
                    bot.edit_message_text(text, chat_id=c.message.chat.id, message_id=c.message.message_id, reply_markup=ikb)
                    message_sent = True
                except Exception as e:
                    print(f"Failed to edit message text: {e}")
                    # If edit fails, send new message
                    bot.send_message(user_id, text, reply_markup=ikb)
                    message_sent = True
        bot.answer_callback_query(c.id)
    except Exception as e:
        # Fallback: send text message if everything else fails (only if we haven't sent anything yet)
        print(f"Error in course handler: {e}")
        if not message_sent:
            bot.send_message(user_id, text, reply_markup=ikb)
        bot.answer_callback_query(c.id)

@bot.callback_query_handler(func=lambda c: c.data == "back_to_catalog")
def cb_back_to_catalog(c: telebot.types.CallbackQuery):
    user_id = c.from_user.id
    send_catalog_message(
        user_id,
        edit_message=c.message,
        edit_message_id=c.message.message_id,
        edit_chat_id=c.message.chat.id
    )
    bot.answer_callback_query(c.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("buy_"))
def cb_buy(c: telebot.types.CallbackQuery):
    user_id = c.from_user.id
    course_id = c.data.split("_", 1)[1]
    try:
        courses = get_courses_data()
    except Exception:
        bot.answer_callback_query(c.id, "Не удалось получить данные курса.", show_alert=True)
        return
    course = next((x for x in courses if str(x.get("id")) == str(course_id)), None)
    if not course:
        bot.answer_callback_query(c.id, COURSE_NOT_AVAILABLE_MSG, show_alert=True)
        return
    if has_active_subscription(user_id, str(course_id)):
        bot.answer_callback_query(c.id, "У вас уже есть этот курс.", show_alert=True)
        return
    name = course.get("name", "Курс")
    price = float(course.get("price", 0))
    clean_name = strip_html(name) if name else "Курс"
    text = f"{clean_name}\nВыберите способ оплаты:"
    kb = types.InlineKeyboardMarkup()
    # Add payment buttons
    if ENABLE_PRODAMUS and PRODAMUS_SECRET_KEY:
        kb.row(
            types.InlineKeyboardButton("ЮKassa", callback_data=f"pay_yk_{course_id}"),
            types.InlineKeyboardButton("Prodamus", callback_data=f"pay_prodamus_{course_id}")
        )
    else:
        kb.add(types.InlineKeyboardButton("ЮKassa", callback_data=f"pay_yk_{course_id}"))
    try:
        bot.send_message(user_id, text, reply_markup=kb)
        bot.answer_callback_query(c.id)
    except Exception:
        bot.answer_callback_query(c.id, "Ошибка при подготовке оплаты.", show_alert=True)

# Handler for ЮKassa payments
@bot.callback_query_handler(func=lambda c: c.data.startswith("pay_yk_"))
def cb_pay_yk(c: telebot.types.CallbackQuery):
    user_id = c.from_user.id
    course_id = c.data.split("_", 2)[2]
    try:
        courses = get_courses_data()
    except Exception:
        bot.answer_callback_query(c.id, "Не удалось получить данные курса.", show_alert=True)
        return
    course = next((x for x in courses if str(x.get("id")) == str(course_id)), None)
    if not course:
        bot.answer_callback_query(c.id, COURSE_NOT_AVAILABLE_MSG, show_alert=True)
        return
    if has_active_subscription(user_id, str(course_id)):
        bot.answer_callback_query(c.id, "У вас уже есть этот курс.", show_alert=True)
        return

    name = course.get("name", "Курс")
    price = float(course.get("price", 0))
    # Strip HTML from payment label (payment systems don't support HTML in labels)
    payment_label = strip_html(name)
    prices = [types.LabeledPrice(label=payment_label, amount=rub_to_kopecks(price))]
    payload = f"{user_id}:{course_id}"

    # Add Telegram username to payment description if available (for YooKassa)
    username = getattr(c.from_user, "username", None)
    desc_suffix = f" (tg:@{username})" if username else ""
    # Strip HTML from name for invoice description
    clean_name = strip_html(name)
    invoice_description = f'Оплата доступа к курсу "{clean_name}"{desc_suffix}'
    invoice_description = invoice_description[:255]

    # Description for YooKassa payment object
    yk_description = invoice_description[:128]
    yk_metadata = {
        "telegram_user_id": str(user_id),
        "course_id": str(course_id),
    }
    if username:
        yk_metadata["telegram_username"] = f"@{username}"

    # Strip HTML from item description for receipt
    item_description = strip_html(name)
    item_description = item_description[:128] if item_description else "Курс"
    provider_data = {
        "description": yk_description,
        "metadata": yk_metadata,
        "receipt": {
            "items": [
                {
                    "description": item_description,
                    "quantity": 1,
                    "amount": {"value": rub_str(price), "currency": CURRENCY},
                    "vat_code": 1
                }
            ]
        }
    }
    provider_data_json = json.dumps(provider_data, ensure_ascii=False)

    # Strip HTML from invoice title
    clean_title_name = strip_html(name) if name else "Курс"
    try:
        bot.send_invoice(
            user_id,
            title=f"Курс: {clean_title_name}",
            description=invoice_description,
            provider_token=PAYMENT_PROVIDER_TOKEN,
            currency=CURRENCY,
            prices=prices,
            start_parameter="purchase-course",
            invoice_payload=payload,
            need_email=True,
            send_email_to_provider=True,
            provider_data=provider_data_json
        )
        bot.answer_callback_query(c.id)
    except Exception as e:
        print("send_invoice (YK) error:", e)
        bot.answer_callback_query(c.id, "Ошибка при выставлении счета (ЮKassa).", show_alert=True)

# Handler for Prodamus direct payments (via payment link)
@bot.callback_query_handler(func=lambda c: c.data.startswith("pay_prodamus_"))
def cb_pay_prodamus(c: telebot.types.CallbackQuery):
    user_id = c.from_user.id
    course_id = c.data.split("_", 2)[2]
    
    # Validate Prodamus configuration
    if not PRODAMUS_SECRET_KEY:
        bot.answer_callback_query(c.id, "Prodamus не настроена. Обратитесь к администратору.", show_alert=True)
        return
    
    # Log test mode status
    if PRODAMUS_TEST_MODE:
        print(f"[Prodamus TEST MODE] Payment request from user {user_id} for course {course_id}")
    
    try:
        courses = get_courses_data()
    except Exception as e:
        print(f"Error fetching courses for Prodamus payment: {e}")
        bot.answer_callback_query(c.id, "Не удалось получить данные курса.", show_alert=True)
        return
    
    course = next((x for x in courses if str(x.get("id")) == str(course_id)), None)
    if not course:
        bot.answer_callback_query(c.id, COURSE_NOT_AVAILABLE_MSG, show_alert=True)
        return
    
    if has_active_subscription(user_id, str(course_id)):
        bot.answer_callback_query(c.id, "У вас уже есть этот курс.", show_alert=True)
        return

    name = course.get("name", "Курс")
    price = float(course.get("price", 0))
    
    # Validate price
    if price <= 0:
        bot.answer_callback_query(c.id, "Неверная цена курса.", show_alert=True)
        return

    # Generate unique order ID for Prodamus
    # Format: PROD-{timestamp}-{user_id}-{course_id} (ensures uniqueness and readability)
    now_ts = datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")
    # Add microseconds for better uniqueness
    now_us = datetime.datetime.utcnow().strftime("%f")[:3]  # milliseconds
    order_id = f"PROD-{now_ts}{now_us}-{user_id}-{course_id}"

    # Clean course name for description
    clean_name = strip_html(name)
    
    # Check if we have user email saved in database
    customer_email = ""
    try:
        user = get_user(user_id)
        if user:
            # Try to get email from user record (if email column exists)
            # user is a Row object, so we can access by column name or index
            if hasattr(user, 'keys') and 'email' in user.keys():
                customer_email = user['email']
            elif len(user) > 2:  # If email column exists (after user_id and username)
                try:
                    customer_email = user[2]  # Assuming email is 3rd column
                except:
                    pass
    except Exception as e:
        if PRODAMUS_TEST_MODE:
            print(f"[Prodamus] Error getting user email: {e}")
        pass
    
    # If no email, request it from user
    if not customer_email:
        # Store payment info in memory to continue after email is received
        prodamus_pending_emails[user_id] = {
            "course_id": course_id,
            "order_id": order_id,
            "price": price,
            "name": clean_name
        }
        
        # Request email from user
        text = "📧 Для создания счета на оплату через Prodamus нужен ваш email адрес.\n\n"
        text += "Пожалуйста, отправьте ваш email адрес:"
        
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("⬅️ Отмена", callback_data=f"course_{course_id}"))
        
        bot.send_message(user_id, text, reply_markup=kb)
        bot.answer_callback_query(c.id)
        return
    
    # We have email, proceed with payment URL generation
    customer_phone = ""
    
    # Generate payment URL with all parameters (including email)
    try:
        payment_url = generate_prodamus_payment_url(
            order_number=order_id,
            amount=price,
            product_name=clean_name,  # Use clean course name as product name
            customer_email=customer_email,
            customer_phone=customer_phone
        )
        
        # Store payment info in database for later verification
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
            
            # Store payment info in database
            # Use order_id as primary key (since we're not using invoice_id anymore)
            cur.execute(
                "INSERT OR REPLACE INTO pending_payments (invoice_id, user_id, course_id, amount, created_at, payment_system, order_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (order_id, user_id, course_id, price, int(time.time()), "prodamus", order_id)
            )
            conn.commit()
            conn.close()
            
            if PRODAMUS_TEST_MODE:
                print(f"[Prodamus] Stored pending payment: order_id={order_id}, user_id={user_id}, course_id={course_id}, amount={price}, email={customer_email}")
        except Exception as e:
            print(f"Error storing pending payment: {e}")
            import traceback
            traceback.print_exc()
        
        # Send payment link to user
        clean_title_name = strip_html(name) if name else "Курс"
        text = f"💳 Оплата курса: {clean_title_name}\n\n"
        text += f"Сумма: {price:.2f} руб.\n\n"
        text += "Нажмите на кнопку ниже, чтобы перейти к оплате:"
        
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("💳 Оплатить через Prodamus", url=payment_url))
        kb.add(types.InlineKeyboardButton("⬅️ Назад", callback_data=f"course_{course_id}"))
        
        bot.send_message(user_id, text, reply_markup=kb)
        bot.answer_callback_query(c.id)
        
        if PRODAMUS_TEST_MODE:
            print(f"[Prodamus TEST MODE] Generated payment URL for order_id {order_id}: {payment_url}")
            
    except Exception as e:
        error_msg = str(e)
        print(f"Error generating Prodamus payment URL: {error_msg}")
        if PRODAMUS_TEST_MODE:
            print(f"[Prodamus TEST MODE] Full error details: {repr(e)}")
        bot.answer_callback_query(c.id, "Ошибка при создании ссылки на оплату.", show_alert=True)

@bot.pre_checkout_query_handler(func=lambda q: True)
def handle_pre_checkout(q: telebot.types.PreCheckoutQuery):
    try:
        user_id = q.from_user.id
        payload = q.invoice_payload
        # Payload format: "user_id:course_id"
        parts = payload.split(":", 1)
        if len(parts) < 2:
            bot.answer_pre_checkout_query(q.id, ok=False, error_message="Неверный формат заказа.")
            return
        # Extract course_id (second part), user_id validation not needed here
        cid = parts[1]
        courses = get_courses_data()
        course = next((x for x in courses if str(x.get("id")) == str(cid)), None)
        if course is None:
            bot.answer_pre_checkout_query(q.id, ok=False, error_message=COURSE_NOT_AVAILABLE_MSG)
            return
        if has_active_subscription(user_id, str(cid)):
            bot.answer_pre_checkout_query(q.id, ok=False, error_message="Этот курс уже активен у вас.")
            return
        bot.answer_pre_checkout_query(q.id, ok=True)
    except Exception as e:
        print("pre_checkout error:", e)
        bot.answer_pre_checkout_query(q.id, ok=False, error_message="Ошибка проверки заказа.")

@bot.message_handler(content_types=['successful_payment'])
def handle_successful_payment(message: telebot.types.Message):
    payment = message.successful_payment
    user_id = message.from_user.id
    payload = payment.invoice_payload
    # Payload format: "user_id:course_id"
    parts = payload.split(":", 1)
    if len(parts) < 2:
        bot.send_message(user_id, "Ошибка: неверный формат заказа. Обратитесь в поддержку.")
        return
    # Extract course_id (second part)
    course_id = parts[1]

    try:
        courses = get_courses_data()
    except Exception:
        courses = []
    course = next((x for x in courses if str(x.get("id")) == str(course_id)), None)
    course_name = course.get("name", f"ID {course_id}") if course else f"ID {course_id}"
    duration = int(course.get("duration_minutes", 0)) if course else 0
    channel = str(course.get("channel", "")) if course else ""

    expiry_ts = add_purchase(user_id, str(course_id), course_name, channel, duration, payment_id=payment.telegram_payment_charge_id)

    invite_link = None
    if channel:
        try:
            invite = bot.create_chat_invite_link(chat_id=channel, member_limit=1, expire_date=None)
            invite_link = invite.invite_link
        except Exception as e:
            print(f"create_chat_invite_link failed for {channel}:", e)

    clean_course_name = strip_html(course_name) if course_name else f"ID {course_id}"
    text = PURCHASE_SUCCESS_MSG.format(course_name=clean_course_name)
    if invite_link:
        text += "\nНажмите кнопку ниже, чтобы перейти к материалам курса."
    text += f"\n\n{PURCHASE_RECEIPT_MSG}"

    if invite_link:
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("Перейти в канал курса", url=invite_link))
        bot.send_message(user_id, text, reply_markup=kb)
    else:
        bot.send_message(user_id, text)

    # Notify admins
    try:
        amount = payment.total_amount / 100.0
        cur = payment.currency
    except Exception:
        amount, cur = 0, CURRENCY
    buyer_email = None
    try:
        if payment.order_info and payment.order_info.email:
            buyer_email = payment.order_info.email
    except Exception:
        pass
    clean_course_name = strip_html(course_name) if course_name else f"ID {course_id}"
    admin_text = f"💰 Оплата: пользователь {user_id} купил {clean_course_name} на сумму {amount:.2f} {cur}."
    if buyer_email:
        admin_text += f"\nEmail: {buyer_email}"
    for aid in ADMIN_IDS:
        try:
            bot.send_message(aid, admin_text)
        except Exception:
            pass

    # Placeholder for sending fiscal receipt (YooKassa auto-fiscalization recommended)
    try:
        # Strip HTML from course name for receipt
        clean_receipt_name = strip_html(course_name) if course_name else f"ID {course_id}"
        send_receipt_to_tax(user_id, clean_receipt_name, amount, buyer_email)
    except Exception as e:
        print("send_receipt_to_tax error:", e)

def send_receipt_to_tax(user_id: int, course_name: str, amount: float, buyer_email: str = None):
    # Placeholder for 'Мой Налог' integration (YooKassa auto-fiscalization can be enabled in account settings).
    print(f"[Receipt] user={user_id}, product='{course_name}', amount={amount}, email={buyer_email}")

# Admin broadcasts
@bot.message_handler(commands=['cleanup_expired'])
def handle_cleanup_expired(message: telebot.types.Message):
    """Admin command to manually trigger expired subscriptions cleanup"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    bot.reply_to(message, "🔄 Запуск очистки просроченных подписок...")
    
    try:
        from db import get_expired_subscriptions, mark_subscription_expired, get_connection
        import time as time_module
        
        # Run diagnostics
        conn = get_connection()
        cur = conn.cursor()
        now = int(time_module.time())
        
        cur.execute("SELECT COUNT(*) FROM purchases WHERE expiry > 0 AND expiry <= ?", (now,))
        expired_count = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM purchases WHERE expiry > ?", (now,))
        active_count = cur.fetchone()[0]
        
        report = f"📊 Статистика:\n"
        report += f"• Просроченных (необработанных): {expired_count}\n"
        report += f"• Активных: {active_count}\n\n"
        
        if expired_count == 0:
            bot.reply_to(message, report + "✅ Просроченных подписок не найдено.")
            return
        
        # Process expired subscriptions
        expired = get_expired_subscriptions()
        processed = 0
        failed = 0
        
        for rec in expired:
            try:
                user_id = rec["user_id"]
                course_id = rec["course_id"]
                course_name = rec["course_name"]
                channel_id = rec["channel_id"]
                
                if channel_id:
                    ok = remove_user_from_channel(user_id, channel_id)
                    if not ok:
                        # Double check
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
                except:
                    pass
                
                processed += 1
            except Exception as e:
                failed += 1
                print(f"Error processing expired subscription: {e}")
        
        report += f"✅ Обработано: {processed}\n"
        if failed > 0:
            report += f"⚠️ Ошибок: {failed}"
        
        bot.reply_to(message, report)
        
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка при очистке: {e}")
        import traceback
        print(f"Cleanup error: {traceback.format_exc()}")

@bot.message_handler(commands=['broadcast_all', 'broadcast_buyers', 'broadcast_nonbuyers'])
def handle_broadcast(message: telebot.types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "После команды укажите текст сообщения.")
        return
    cmd = parts[0]
    text = parts[1]

    recipients = []
    try:
        # Use separate connection for broadcast to avoid conflicts
        conn = sqlite3.connect(DATABASE_PATH)
        cur = conn.cursor()
        if cmd == "/broadcast_all":
            cur.execute("SELECT user_id FROM users;")
        elif cmd == "/broadcast_buyers":
            cur.execute("SELECT DISTINCT user_id FROM purchases;")
        elif cmd == "/broadcast_nonbuyers":
            cur.execute("SELECT user_id FROM users WHERE user_id NOT IN (SELECT DISTINCT user_id FROM purchases);")
        rows = cur.fetchall()
        recipients = [r[0] for r in rows]
        conn.close()
    except Exception as e:
        print(f"Broadcast database error: {e}")
        bot.reply_to(message, f"Ошибка при получении списка получателей: {e}")
        return

    sent = 0
    failed = 0
    for uid in recipients:
        try:
            bot.send_message(uid, text, disable_web_page_preview=True)
            sent += 1
        except Exception as e:
            failed += 1
            # Log first few failures for debugging
            if failed <= 3:
                print(f"Failed to send broadcast to user {uid}: {e}")
    total = len(recipients)
    reply_msg = f"Отправлено {sent} из {total} пользователям."
    if failed > 0:
        reply_msg += f" Не удалось отправить: {failed}."
    bot.reply_to(message, reply_msg)


def remove_user_from_channel(user_id: int, channel_id: str):
    """
    Remove user from channel by banning and immediately unbanning.
    This effectively removes the user from the channel.
    """
    import datetime
    timestamp = datetime.datetime.now().isoformat()
    
    if not channel_id:
        print(f"[{timestamp}] [remove_user_from_channel] ERROR: No channel_id provided for user {user_id}")
        return False
    
    print(f"[{timestamp}] [remove_user_from_channel] Starting removal process: user_id={user_id}, channel_id={channel_id}")
    
    # First, check if user is actually a member before attempting removal
    try:
        print(f"[{timestamp}] [remove_user_from_channel] Checking user membership status...")
        member = bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        member_status = getattr(member, "status", "unknown")
        print(f"[{timestamp}] [remove_user_from_channel] User {user_id} current status in channel {channel_id}: {member_status}")
        
        if member_status in ("left", "kicked"):
            print(f"[{timestamp}] [remove_user_from_channel] User {user_id} already not a member (status: {member_status}), skipping removal")
            return True
    except Exception as e:
        error_msg = str(e).lower()
        print(f"[{timestamp}] [remove_user_from_channel] Warning: Could not check membership status: {e}")
        # Continue with removal attempt anyway
    
    try:
        print(f"[{timestamp}] [remove_user_from_channel] Attempting to ban user {user_id} from channel {channel_id}...")
        # First, try to ban the user (removes them from channel)
        bot.ban_chat_member(chat_id=channel_id, user_id=user_id, until_date=None)
        print(f"[{timestamp}] [remove_user_from_channel] Successfully banned user {user_id}")
        
        # Then immediately unban (allows them to rejoin if needed, but they're already removed)
        print(f"[{timestamp}] [remove_user_from_channel] Unbanning user {user_id}...")
        bot.unban_chat_member(chat_id=channel_id, user_id=user_id, only_if_banned=True)
        print(f"[{timestamp}] [remove_user_from_channel] Successfully unbanned user {user_id}")
        
        # Verify removal by checking status again
        try:
            member = bot.get_chat_member(chat_id=channel_id, user_id=user_id)
            final_status = getattr(member, "status", "unknown")
            print(f"[{timestamp}] [remove_user_from_channel] Verification: User {user_id} final status: {final_status}")
            if final_status in ("left", "kicked"):
                print(f"[{timestamp}] [remove_user_from_channel] ✅ SUCCESS: User {user_id} successfully removed from channel {channel_id}")
                return True
            else:
                print(f"[{timestamp}] [remove_user_from_channel] ⚠️ WARNING: User {user_id} still has status '{final_status}' after ban/unban")
                return True  # Still return True as ban/unban succeeded
        except Exception as verify_e:
            print(f"[{timestamp}] [remove_user_from_channel] Could not verify removal status: {verify_e}")
            # If we can't verify but ban/unban succeeded, assume success
            print(f"[{timestamp}] [remove_user_from_channel] ✅ SUCCESS: Ban/unban completed, assuming removal successful")
            return True
            
    except Exception as e:
        error_msg = str(e).lower()
        print(f"[{timestamp}] [remove_user_from_channel] ERROR during ban/unban: {e}")
        print(f"[{timestamp}] [remove_user_from_channel] Error type: {type(e).__name__}")
        
        # Check if user is already not a member
        if any(s in error_msg for s in ("user not found", "user is not a member", "chat not found")):
            print(f"[{timestamp}] [remove_user_from_channel] User {user_id} already not a member of {channel_id} (error indicates this)")
            return True
        
        # Check if bot doesn't have admin rights
        if any(s in error_msg for s in ("not enough rights", "not an admin", "can't ban", "can't restrict")):
            print(f"[{timestamp}] [remove_user_from_channel] ❌ FAILED: Bot doesn't have admin rights in {channel_id}: {e}")
            return False
        
        print(f"[{timestamp}] [remove_user_from_channel] ❌ FAILED: Unknown error removing {user_id} from {channel_id}: {e}")
        return False


# Диагностика каналов / админ-команда
def check_course_channels() -> str:
    """
    Проверяем корректность поля 'channel' у курсов и права бота.
    Возвращает человекочитаемый отчёт.
    """
    lines = []
    # Кто мы
    try:
        me = bot.get_me()
        bot_id = me.id
        bot_name = f"@{me.username}" if getattr(me, "username", None) else str(me.id)
    except Exception as e:
        bot_id = None
        bot_name = "<unknown>"
        lines.append(f"⚠️ Не удалось получить информацию о боте: {e}")

    # Курсы
    try:
        courses = get_courses_data()
    except Exception as e:
        return f"❌ Не удалось получить список курсов: {e}"

    if not courses:
        return "Список курсов пуст."

    for course in courses:
        name = course.get("name", "Курс")
        channel = str(course.get("channel", "") or "")
        if not channel:
            clean_name = strip_html(name) if name else "Курс"
            lines.append(f"• {clean_name}: канал не указан.")
            continue

        # Проверяем доступность чата
        try:
            chat = bot.get_chat(channel)
        except Exception as e:
            clean_name = strip_html(name) if name else "Курс"
            lines.append(f"• {clean_name} — {channel}: ❌ чат недоступен для бота (возможно, бот не добавлен/не админ, или неверный ID). Ошибка: {e}")
            continue

        if channel.startswith("@"):
            # Публичный канал — используем прямую ссылку
            public_url = f"https://t.me/{channel[1:]}"
            clean_name = strip_html(name) if name else "Курс"
            lines.append(f"• {clean_name} — {channel}: ✅ публичный канал, ссылка ок: {public_url}")
        else:
            # Приватный/числовой ID — проверяем, что бот админ и может приглашать
            try:
                admins = bot.get_chat_administrators(chat.id)
            except Exception as e:
                clean_name = strip_html(name) if name else "Курс"
                lines.append(f"• {clean_name} — {channel}: ⚠️ не удалось получить админов. Ошибка: {e}")
                continue

            bot_admin = None
            for a in admins:
                try:
                    if a.user.id == bot_id:
                        bot_admin = a
                        break
                except Exception:
                    pass

            if not bot_admin:
                clean_name = strip_html(name) if name else "Курс"
                lines.append(f"• {clean_name} — {channel}: ❌ бот {bot_name} не является админом. Добавьте бота админом канала.")
            else:
                can_invite = getattr(bot_admin, "can_invite_users", False)
                can_manage = getattr(bot_admin, "can_manage_chat", False)
                if can_invite or can_manage:
                    clean_name = strip_html(name) if name else "Курс"
                    lines.append(f"• {clean_name} — {channel}: ✅ бот админ, права на приглашения есть.")
                else:
                    clean_name = strip_html(name) if name else "Курс"
                    lines.append(f"• {clean_name} — {channel}: ⚠️ бот админ, но нет права приглашать пользователей. Включите право «Добавлять пользователей».")

    return "\n".join(lines)


@bot.message_handler(commands=["diag_channels"])
def handle_diag_channels(message: telebot.types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    report = check_course_channels()
    # Делим длинные ответы на части
    parts = []
    current = ""
    for line in report.split("\n"):
        if len(current) + len(line) + 1 > 3900:
            parts.append(current)
            current = ""
        current += (("\n" if current else "") + line)
    if current:
        parts.append(current)
    for p in parts:
        try:
            bot.send_message(message.chat.id, "🔎 Диагностика каналов:\n" + p, disable_web_page_preview=True)
        except Exception:
            pass

if __name__ == "__main__":
    if USE_WEBHOOK:
        print("Webhook mode enabled. Run webhook_app.py (WSGI) on your server.")
    else:
        # Однократная проверка каналов при старте
        try:
            startup_report = check_course_channels()
            for aid in ADMIN_IDS:
                try:
                    bot.send_message(aid, "🔎 Диагностика каналов при старте:\n" + startup_report, disable_web_page_preview=True)
                except Exception:
                    pass
        except Exception as e:
            print("Channel diagnostics failed on startup:", e)
        print("Bot started in polling mode...")
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
