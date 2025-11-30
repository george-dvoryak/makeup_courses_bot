# main.py
import datetime
import sqlite3
import json
import telebot
from telebot import types
import os
import time
import re
import tempfile
import hashlib
import threading
from urllib.parse import urlencode, quote
from flask import Flask, request, abort
import requests
from PIL import Image
from io import BytesIO

from config import TELEGRAM_BOT_TOKEN, PAYMENT_PROVIDER_TOKEN, ADMIN_IDS, CURRENCY, USE_WEBHOOK, DATABASE_PATH, GSHEET_ID, ENABLE_PRODAMUS, PRODAMUS_PAYFORM_URL, PRODAMUS_SECRET_KEY, PRODAMUS_TEST_MODE, PRODAMUS_SYSTEM_ID, PRODAMUS_TEST_WEBHOOK_URL, get_bot_config, CURRENT_BOT_NAME
from db import add_user, get_user, add_purchase, get_active_subscriptions, has_active_subscription, mark_subscription_expired, get_all_active_subscriptions, clear_all_data, get_connection
from google_sheets import get_courses_data, get_texts_data
from bot_context import get_bot_context, set_bot_context
from bot_factory import get_bot_instance
import hmac
from prodamuspy import ProdamusPy  # type: ignore

# Create default bot instance (for backward compatibility)
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN, parse_mode=None, threaded=False)

# Helper function to get the current bot instance
def get_current_bot():
    """
    Get the current bot instance based on context.
    Falls back to default bot if no context is set.
    """
    bot_name = get_bot_context()
    if bot_name:
        try:
            return get_bot_instance(bot_name)
        except Exception:
            pass
    return bot

# Helper function to get current bot config
def get_current_config():
    """Get current bot configuration based on context"""
    context_bot = get_bot_context()
    bot_name = context_bot or CURRENT_BOT_NAME
    # Debug logging
    print(f"[Config] get_current_config called: context={context_bot}, using={bot_name}")
    return get_bot_config(bot_name)

# Helper function to get current admin IDs
def get_current_admin_ids():
    """Get current bot's admin IDs"""
    config = get_current_config()
    return config.get('ADMIN_IDS', ADMIN_IDS)

# Helper function to get current payment config
def get_current_payment_config():
    """Get current bot's payment configuration"""
    config = get_current_config()
    return {
        'PAYMENT_PROVIDER_TOKEN': config.get('PAYMENT_PROVIDER_TOKEN', PAYMENT_PROVIDER_TOKEN),
        'CURRENCY': config.get('CURRENCY', CURRENCY),
        'ENABLE_PRODAMUS': config.get('ENABLE_PRODAMUS', ENABLE_PRODAMUS),
        'PRODAMUS_PAYFORM_URL': config.get('PRODAMUS_PAYFORM_URL', PRODAMUS_PAYFORM_URL),
        'PRODAMUS_SECRET_KEY': config.get('PRODAMUS_SECRET_KEY', PRODAMUS_SECRET_KEY),
        'PRODAMUS_TEST_MODE': config.get('PRODAMUS_TEST_MODE', PRODAMUS_TEST_MODE),
        'PRODAMUS_SYSTEM_ID': config.get('PRODAMUS_SYSTEM_ID', PRODAMUS_SYSTEM_ID),
        'PRODAMUS_TEST_WEBHOOK_URL': config.get('PRODAMUS_TEST_WEBHOOK_URL', PRODAMUS_TEST_WEBHOOK_URL)
    }

# Image caching and optimization
_IMAGE_CACHE_DIR = os.path.join(os.path.dirname(__file__), '.image_cache')
_MAX_IMAGE_SIZE = 2 * 1024 * 1024  # 2MB max file size
_MAX_IMAGE_DIMENSION = 1920  # Max width or height
_IMAGE_CACHE_TTL = 7 * 24 * 60 * 60  # 7 days

# Create cache directory if it doesn't exist
os.makedirs(_IMAGE_CACHE_DIR, exist_ok=True)

def _get_image_cache_key(image_url: str) -> str:
    """Generate cache key for image URL"""
    return hashlib.md5(image_url.encode()).hexdigest()

def _get_cached_image_info(image_url: str):
    """Get cached image info from database"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT file_id, local_path, cached_at FROM image_cache WHERE image_url = ?",
        (image_url,)
    )
    row = cur.fetchone()
    if row:
        # Check if cache is still valid
        cached_at = row[2]
        if time.time() - cached_at < _IMAGE_CACHE_TTL:
            # Check if local file still exists
            if row[1] and os.path.exists(row[1]):
                return {'file_id': row[0], 'local_path': row[1]}
            else:
                # Local file missing, remove from cache
                cur.execute("DELETE FROM image_cache WHERE image_url = ?", (image_url,))
                conn.commit()
    return None

def _save_image_cache(image_url: str, file_id: str = None, local_path: str = None):
    """Save image cache info to database"""
    conn = get_connection()
    cur = conn.cursor()
    file_size = os.path.getsize(local_path) if local_path and os.path.exists(local_path) else 0
    cur.execute(
        """
        INSERT OR REPLACE INTO image_cache (image_url, file_id, local_path, cached_at, file_size)
        VALUES (?, ?, ?, ?, ?)
        """,
        (image_url, file_id, local_path, int(time.time()), file_size)
    )
    conn.commit()

def _download_and_optimize_image(image_url: str) -> str:
    """
    Download and optimize image. Returns path to optimized image file.
    Raises exception if download or optimization fails.
    """
    try:
        print(f"[Image] Downloading: {image_url}")
        response = requests.get(image_url, timeout=15, stream=True)
        response.raise_for_status()
        
        # Check content type
        content_type = response.headers.get('content-type', '').lower()
        if not content_type.startswith('image/'):
            raise ValueError(f"Not an image: {content_type}")
        
        # Download image data
        image_data = BytesIO()
        downloaded_size = 0
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                downloaded_size += len(chunk)
                if downloaded_size > 10 * 1024 * 1024:  # 10MB limit for download
                    raise ValueError("Image too large to download")
                image_data.write(chunk)
        
        image_data.seek(0)
        
        # Open and optimize image
        print(f"[Image] Optimizing image (size: {downloaded_size} bytes)")
        img = Image.open(image_data)
        
        # Convert to RGB if necessary (for JPEG)
        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Resize if too large
        width, height = img.size
        if width > _MAX_IMAGE_DIMENSION or height > _MAX_IMAGE_DIMENSION:
            ratio = min(_MAX_IMAGE_DIMENSION / width, _MAX_IMAGE_DIMENSION / height)
            new_width = int(width * ratio)
            new_height = int(height * ratio)
            print(f"[Image] Resizing from {width}x{height} to {new_width}x{new_height}")
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Save with compression
        cache_key = _get_image_cache_key(image_url)
        local_path = os.path.join(_IMAGE_CACHE_DIR, f"{cache_key}.jpg")
        
        # Save with quality optimization to meet size limit
        quality = 95
        while quality >= 50:
            img.save(local_path, 'JPEG', quality=quality, optimize=True)
            file_size = os.path.getsize(local_path)
            if file_size <= _MAX_IMAGE_SIZE:
                print(f"[Image] Optimized: {file_size} bytes (quality: {quality})")
                return local_path
            quality -= 5
        
        # If still too large after compression, resize more aggressively
        if os.path.getsize(local_path) > _MAX_IMAGE_SIZE:
            print(f"[Image] Still too large, resizing more aggressively")
            img = img.resize((int(img.width * 0.8), int(img.height * 0.8)), Image.Resampling.LANCZOS)
            img.save(local_path, 'JPEG', quality=85, optimize=True)
        
        print(f"[Image] Final size: {os.path.getsize(local_path)} bytes")
        return local_path
        
    except Exception as e:
        print(f"[Image] Error downloading/optimizing {image_url}: {e}")
        raise

def send_image_safe(bot, user_id: int, image_url: str, caption: str = "", reply_markup=None, parse_mode='HTML', max_retries: int = 2):
    """
    Send image with caching, optimization, and retry logic.
    Uses file_id if available, otherwise downloads and optimizes image.
    """
    if not image_url or not image_url.startswith(('http://', 'https://')):
        # No valid URL, send text only
        if caption:
            bot.send_message(user_id, caption, reply_markup=reply_markup, parse_mode=parse_mode)
        return
    
    try:
        # Check cache first
        cached = _get_cached_image_info(image_url)
        
        if cached and cached.get('file_id'):
            # Try to use file_id first (fastest)
            try:
                print(f"[Image] Using cached file_id for: {image_url}")
                bot.send_photo(user_id, cached['file_id'], caption=caption, reply_markup=reply_markup, parse_mode=parse_mode)
                return
            except Exception as e:
                print(f"[Image] file_id expired, downloading: {e}")
                # file_id expired, continue to download
        
        # Download and optimize image
        local_path = None
        if cached and cached.get('local_path') and os.path.exists(cached['local_path']):
            local_path = cached['local_path']
            print(f"[Image] Using cached local file: {local_path}")
        else:
            local_path = _download_and_optimize_image(image_url)
        
        # Send image with retry logic
        file_id = None
        for attempt in range(max_retries + 1):
            try:
                print(f"[Image] Sending image (attempt {attempt + 1}/{max_retries + 1})")
                with open(local_path, 'rb') as photo:
                    sent_message = bot.send_photo(user_id, photo, caption=caption, reply_markup=reply_markup, parse_mode=parse_mode)
                    # Extract file_id from sent message
                    if sent_message and sent_message.photo:
                        file_id = sent_message.photo[-1].file_id  # Get largest size
                        print(f"[Image] ✅ Sent successfully, file_id: {file_id}")
                        break
            except Exception as e:
                print(f"[Image] ❌ Attempt {attempt + 1} failed: {e}")
                if attempt < max_retries:
                    time.sleep(1)  # Wait before retry
                else:
                    raise
        
        # Save to cache
        if file_id and local_path:
            _save_image_cache(image_url, file_id, local_path)
            
    except Exception as e:
        print(f"[Image] ❌ Failed to send image, sending text only: {e}")
        # Fallback: send text only
        if caption:
            try:
                bot.send_message(user_id, caption, reply_markup=reply_markup, parse_mode=parse_mode)
            except Exception as e2:
                print(f"[Image] ❌ Even text fallback failed: {e2}")

def cleanup_old_images():
    """Clean up old cached images from disk and database"""
    try:
        conn = get_connection()
        cur = conn.cursor()
        now = int(time.time())
        
        # Find old cache entries
        cur.execute(
            "SELECT image_url, local_path FROM image_cache WHERE cached_at < ?",
            (now - _IMAGE_CACHE_TTL,)
        )
        old_entries = cur.fetchall()
        
        removed_count = 0
        for row in old_entries:
            local_path = row[1]
            if local_path and os.path.exists(local_path):
                try:
                    os.remove(local_path)
                    removed_count += 1
                except Exception as e:
                    print(f"[Image] Failed to remove {local_path}: {e}")
        
        # Remove from database
        cur.execute("DELETE FROM image_cache WHERE cached_at < ?", (now - _IMAGE_CACHE_TTL,))
        conn.commit()
        
        if removed_count > 0:
            print(f"[Image] Cleaned up {removed_count} old cached images")
    except Exception as e:
        print(f"[Image] Error during cleanup: {e}")

def get_prodamus_client(secret_key: str) -> ProdamusPy:
    """Create Prodamus client helper"""
    return ProdamusPy(secret_key or "")

def parse_prodamus_payload(raw_payload: str, secret_key: str) -> dict:
    """
    Parse Prodamus payload from raw query/body string into structured dict.
    Falls back to JSON parsing if needed.
    """
    if not raw_payload:
        return {}
    client = get_prodamus_client(secret_key)
    try:
        return client.parse(raw_payload)
    except Exception as e:
        print(f"[Prodamus] Failed to parse payload via query parser: {e}")
        try:
            data = json.loads(raw_payload)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return {}

def extract_prodamus_payload(req, secret_key: str) -> dict:
    """
    Extract Prodamus payload from a Flask request.
    
    According to Prodamus documentation, webhook sends data as 
    application/x-www-form-urlencoded in POST body. We need to parse
    the raw body as query string (URL-encoded format) using prodamuspy.
    """
    client = get_prodamus_client(secret_key)
    
    # Priority 1: Parse raw POST body as query string (official Prodamus format)
    try:
        raw_body = req.get_data(as_text=True)
        if raw_body:
            try:
                payload = client.parse(raw_body)
                if payload:
                    return payload
            except Exception as e:
                print(f"[Prodamus] Failed to parse raw body via prodamuspy: {e}")
    except Exception as e:
        print(f"[Prodamus] Failed to get raw body: {e}")
    
    # Priority 2: Try query string
    try:
        query_string = req.query_string.decode('utf-8', errors='ignore')
        if query_string:
            try:
                payload = client.parse(query_string)
                if payload:
                    return payload
            except Exception:
                pass
    except Exception:
        pass
    
    # Priority 3: Fallback to Flask's parsed form data (may not work for signature verification)
    if req.form:
        form_dict = req.form.to_dict(flat=True)
        if form_dict:
            print("[Prodamus] Using Flask form data (fallback - signature may fail)")
            return form_dict
    
    # Priority 4: Try JSON
    if req.is_json:
        data = req.get_json(silent=True) or {}
        if isinstance(data, dict) and data:
            return data
    
    # Priority 5: Try query args
    if req.args:
        return req.args.to_dict(flat=True)
    
    return {}

def resolve_prodamus_payment_link(long_url: str) -> str:
    """
    Resolve the final (short) Prodamus URL by following redirects.
    
    Prodamus generates short links like: https://domain.payform.ru/p/p5z2micwqc9c26/
    We need to follow the redirect from the long URL to get this short link.
    
    Falls back to the original URL if resolution fails.
    """
    if not long_url:
        return long_url
    
    try:
        # First, try with allow_redirects=False to capture the redirect location
        response = requests.get(long_url, allow_redirects=False, timeout=15)
        
        # Check for redirect (3xx status codes)
        if response.status_code in (301, 302, 303, 307, 308):
            location = response.headers.get("Location")
            if location:
                print(f"[Prodamus] Resolved short link: {location}")
                return location
        
        # If no redirect, try following redirects and get final URL
        response = requests.get(long_url, allow_redirects=True, timeout=15)
        final_url = response.url
        
        # Check if we got a short link format (contains /p/ path)
        if final_url and final_url != long_url:
            print(f"[Prodamus] Resolved via redirect chain: {final_url}")
            return final_url
        
        # Check response for redirect in HTML meta or JavaScript
        # Some systems use client-side redirects
        if response.status_code == 200:
            content = response.text[:2000]  # Check first 2000 chars
            # Look for meta refresh or window.location patterns
            import re
            meta_match = re.search(r'<meta[^>]*http-equiv=["\']refresh["\'][^>]*url=([^"\'>\s]+)', content, re.IGNORECASE)
            if meta_match:
                redirect_url = meta_match.group(1)
                print(f"[Prodamus] Found meta refresh redirect: {redirect_url}")
                return redirect_url
        
        print(f"[Prodamus] No redirect found, using original URL")
        return long_url
        
    except requests.exceptions.Timeout:
        print(f"[Prodamus] Timeout while resolving short link, using original URL")
        return long_url
    except Exception as e:
        print(f"[Prodamus] Failed to resolve short link: {e}")
        import traceback
        traceback.print_exc()
        return long_url


def decode_order_metadata(order_number: str):
    """
    Extract user_id and course_id from generated Prodamus order numbers.
    Format: PROD-{timestamp}{ms}-{user_id}-{course_id}
    Returns tuple (user_id:int, course_id:str) or (None, None) if parsing fails.
    """
    if not order_number or not order_number.startswith("PROD-"):
        return None, None
    parts = order_number.split("-")
    if len(parts) < 4:
        return None, None
    user_part = parts[-2]
    course_part = parts[-1]
    try:
        user_id = int(user_part)
    except (TypeError, ValueError):
        return None, None
    return user_id, course_part

# In-memory state for Prodamus email collection (per bot)
# Format: {bot_name: {user_id: {"course_id": course_id, "order_id": order_id, "price": price, "name": name}}}
prodamus_pending_emails = {}

# In-memory state for admin broadcast (per bot)
# Format: {bot_name: {user_id: {"type": "all"/"buyers"/"nonbuyers", "text": "...", "photo": file_id or None}}}
admin_broadcast_state = {}

# Helper to get bot-specific state
def get_prodamus_pending_emails():
    """Get Prodamus pending emails for current bot"""
    bot_name = get_bot_context() or CURRENT_BOT_NAME
    if bot_name not in prodamus_pending_emails:
        prodamus_pending_emails[bot_name] = {}
    return prodamus_pending_emails[bot_name]

def get_admin_broadcast_state():
    """Get admin broadcast state for current bot"""
    bot_name = get_bot_context() or CURRENT_BOT_NAME
    if bot_name not in admin_broadcast_state:
        admin_broadcast_state[bot_name] = {}
    return admin_broadcast_state[bot_name]

def safe_answer_callback_query(bot, callback_query_id: str, text: str = None, show_alert: bool = False, max_retries: int = 3):
    """
    Safely answer callback query with SSL error handling and retry logic.
    Handles various network errors and retries with exponential backoff.
    """
    for attempt in range(max_retries + 1):
        try:
            bot.answer_callback_query(callback_query_id, text=text, show_alert=show_alert, timeout=5)
            return True
        except Exception as e:
            error_msg = str(e).lower()
            # Check if it's a retryable error (SSL, connection, timeout, etc.)
            is_retryable = any(keyword in error_msg for keyword in [
                "ssl", "connection", "decryption", "timeout", "bad record mac",
                "max retries", "connection pool", "network", "temporary failure"
            ])
            
            if is_retryable and attempt < max_retries:
                wait_time = 0.5 * (attempt + 1)  # Exponential backoff: 0.5s, 1s, 1.5s
                print(f"[Callback] Retryable error (attempt {attempt + 1}/{max_retries + 1}): {type(e).__name__}, retrying in {wait_time}s...")
                time.sleep(wait_time)
                continue
            else:
                # Non-retryable error or max retries reached
                if attempt >= max_retries:
                    print(f"[Callback] Failed to answer callback_query after {max_retries + 1} attempts: {type(e).__name__}: {e}")
                else:
                    print(f"[Callback] Non-retryable error answering callback_query: {type(e).__name__}: {e}")
                return False
    return False

# HTML processing functions
def strip_html(text: str) -> str:
    """Remove all HTML tags from text"""
    if not text:
        return ""
    return re.sub(r'<[^>]+>', '', text)

def escape_html(text: str) -> str:
    """Escape HTML special characters"""
    if not text:
        return ""
    return (text.replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;'))

def format_text_for_telegram(text: str) -> str:
    """
    Convert Google Sheets formatting to Telegram HTML format.
    Protects valid HTML tags and escapes others.
    Converts literal \n to actual newlines.
    """
    if not text:
        return ""

    # Convert literal \n to actual newlines (for Google Sheets compatibility)
    text = text.replace('\\n', '\n')

    # Protect valid HTML tags (opening and closing)
    # Pattern matches: <tag>, <tag attr="value">, </tag>
    protected = []
    tag_pattern = r'<(/?)([a-zA-Z][a-zA-Z0-9]*)(?:\s[^>]*)?>'

    def protect_tag(match):
        tag_name = match.group(2).lower()
        # List of valid Telegram HTML tags
        valid_tags = {'b', 'strong', 'i', 'em', 'u', 's', 'strike', 'del', 'code', 'pre', 'a'}
        if tag_name in valid_tags:
            tag_id = f"__PROTECTED_TAG_{len(protected)}__"
            protected.append(match.group(0))
            return tag_id
        return match.group(0)

    # Protect valid tags
    text = re.sub(tag_pattern, protect_tag, text)

    # Escape all remaining HTML
    text = escape_html(text)

    # Restore protected tags
    for i, tag in enumerate(protected):
        text = text.replace(f"__PROTECTED_TAG_{i}__", tag)

    return text

# Payment helper functions
def rub_to_kopecks(rub: float) -> int:
    """Convert rubles to kopecks"""
    return int(float(rub) * 100)

def rub_str(rub: float) -> str:
    """Format rubles as string with 2 decimal places"""
    return f"{float(rub):.2f}"

# Prodamus signature verification
def verify_prodamus_signature(payload: dict, secret_key: str, signature: str) -> bool:
    """
    Verify Prodamus webhook signature using official prodamuspy library.
    
    Equivalent to PHP: Hmac::verify($_POST, $secret_key, $headers['Sign'])
    
    Args:
        payload: Parsed dict from POST request (parsed via prodamuspy.parse())
        secret_key: Prodamus secret key for this bot
        signature: Signature from 'Sign' header
    
    Returns:
        True if signature is valid, False otherwise
    """
    if not secret_key or not signature:
        print(f"[Prodamus] Missing secret_key or signature: secret_key={bool(secret_key)}, signature={bool(signature)}")
        return False

    if not payload:
        print(f"[Prodamus] Empty payload")
        return False

    try:
        client = get_prodamus_client(secret_key)
        # Use client.verify() directly (equivalent to Hmac::verify in PHP)
        is_valid = client.verify(payload, signature)
        
        if not is_valid:
            # Debug: show what we're comparing
            expected_sign = client.sign(payload)
            print(f"[Prodamus] Signature mismatch: expected={expected_sign}, provided={signature.strip().lower()}")
        
        return is_valid
    except Exception as e:
        print(f"[Prodamus] Signature verification error: {e}")
        import traceback
        traceback.print_exc()
        return False

def generate_prodamus_payment_url(order_number: str, amount: float, product_name: str, customer_email: str = "", customer_phone: str = "", extra_params: dict = None) -> str:
    """
    Build payment URL for Prodamus payform.
    
    Format: https://domain.payform.ru/?order_id=X&products[0][price]=Y&products[0][quantity]=1&products[0][name]=Z&do=pay
    """
    config = get_current_payment_config()
    base_url = config.get('PRODAMUS_PAYFORM_URL') or PRODAMUS_PAYFORM_URL
    if not base_url:
        raise RuntimeError("PRODAMUS_PAYFORM_URL is not configured")
    if not base_url.startswith("http"):
        base_url = f"https://{base_url}"
    
    # Clean product name
    clean_name = strip_html(product_name) if product_name else "Доступ к курсу"
    
    # Build parameters according to Prodamus documentation
    # Using products[] array format
    params = [
        ("order_id", order_number),
        ("products[0][price]", rub_str(amount)),
        ("products[0][quantity]", "1"),
        ("products[0][name]", clean_name),
        ("customer_extra", f"Оплата курса: {clean_name}"),
        ("do", "pay"),  # Auto-start payment
    ]
    
    # Add customer info
    if customer_email:
        params.append(("customer_email", customer_email))
    if customer_phone:
        # Normalize phone number
        phone = customer_phone.replace("+", "").replace(" ", "").replace("-", "")
        params.append(("customer_phone", phone))
    
    # Add system_id if configured
    system_id = config.get("PRODAMUS_SYSTEM_ID")
    if system_id:
        params.append(("sys", system_id))
    
    # Add extra parameters
    if extra_params:
        for key, value in extra_params.items():
            params.append((key, value))
    
    # Build URL with proper encoding
    query_string = "&".join(f"{quote(str(k), safe='[]')}={quote(str(v), safe='')}" for k, v in params)
    return f"{base_url}/?{query_string}"

# --- Text templates and helpers ---
ALREADY_PURCHASED_MSG = "Этот курс уже активен у вас."
COURSE_NOT_AVAILABLE_MSG = "Курс временно недоступен. Обратитесь в поддержку."
PURCHASE_SUCCESS_MSG = "✅ Оплата прошла!\nДоступ к курсу «{course_name}» открыт."
PURCHASE_RECEIPT_MSG = "Квитанция отправлена на email, указанный при оплате."
CATALOG_INTRO_DEFAULT = "📚 <b>Каталог курсов</b>\nВыберите интересующий курс:"
CATALOG_EMPTY_DEFAULT = "Каталог пока пуст. Загляните позже."
CATALOG_ERROR_DEFAULT = "Не удалось загрузить каталог. Попробуйте позже."
SUPPORT_TEXT_DEFAULT = "Напишите нам в поддержку: @your_support или info@example.com"
NO_ACTIVE_SUBS_DEFAULT = "У вас пока нет активных подписок."
ACTIVE_SUBS_HEADER_DEFAULT = "📘 Ваши активные курсы:"
OFERTA_URL_DEFAULT = "https://github.com/george-dvoryak/cdn/blob/main/oferta.pdf?raw=true"

_texts_cache = {}
_TEXTS_CACHE_TTL = 300  # seconds

def _get_texts_for_bot(bot_name: str) -> dict:
    now = time.time()
    cached = _texts_cache.get(bot_name)
    if cached and now - cached["ts"] < _TEXTS_CACHE_TTL:
        print(f"[Texts] Using cached texts for {bot_name} ({len(cached['data'])} entries)")
        return cached["data"]
    try:
        print(f"[Texts] Loading texts for bot: {bot_name}")
        data = get_texts_data(bot_name) or {}
        print(f"[Texts] Loaded {len(data)} text entries for {bot_name}")
        if data:
            print(f"[Texts] Sample keys: {list(data.keys())[:5]}")
    except Exception as e:
        print(f"[Texts] Failed to load texts for {bot_name}: {e}")
        import traceback
        traceback.print_exc()
        data = {}
    _texts_cache[bot_name] = {"ts": now, "data": data}
    return data

def get_text_value(key: str, default: str = "", bot_name: str = None) -> str:
    if bot_name is None:
        bot_name = get_bot_context() or CURRENT_BOT_NAME

    # Добавляем более детальное логирование для отладки
    print(f"[Texts] get_text_value: key='{key}', bot='{bot_name}', context='{get_bot_context()}'")

    if not bot_name:
        print(f"[Texts] ERROR: No bot context found! Using default '{CURRENT_BOT_NAME}'")
        bot_name = CURRENT_BOT_NAME

    texts = _get_texts_for_bot(bot_name)

    # Try exact match first
    value = texts.get(key)
    if isinstance(value, str) and value.strip():
        print(f"[Texts] ✅ Found exact match for '{key}': {value[:50]}...")
        return value.strip()

    # Try case-insensitive match
    key_lower = key.lower().strip()
    for k, v in texts.items():
        if k.lower().strip() == key_lower:
            if isinstance(v, str) and v.strip():
                print(f"[Texts] ✅ Found case-insensitive match for '{key}' with '{k}': {v[:50]}...")
                return v.strip()

    # Try match with spaces/underscores normalized
    key_normalized = key_lower.replace("_", " ").replace("-", " ")
    for k, v in texts.items():
        k_normalized = k.lower().strip().replace("_", " ").replace("-", " ")
        if k_normalized == key_normalized:
            if isinstance(v, str) and v.strip():
                print(f"[Texts] ✅ Found normalized match for '{key}' with '{k}': {v[:50]}...")
                return v.strip()

    print(f"[Texts] ❌ Key '{key}' not found in texts. Available keys: {sorted(texts.keys())[:15]}")
    if texts:
        print(f"[Texts] Sample values: {[(k, v[:30]) for k, v in list(texts.items())[:3]]}")
    return default

def build_main_menu(user_id: int) -> types.ReplyKeyboardMarkup:
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row("Каталог", "Активные подписки")
    keyboard.row("Поддержка", "Оферта")
    admin_ids = get_current_admin_ids()
    if user_id in admin_ids:
        keyboard.row("📊 Все подписки", "📋 Google Sheets")
        keyboard.add("📢 Рассылка")
    return keyboard

def send_catalog_message(user_id: int, edit_message: telebot.types.Message = None, edit_message_id: int = None, edit_chat_id: int = None):
    current_bot = get_current_bot()
    bot_name = get_bot_context() or CURRENT_BOT_NAME
    try:
        courses = get_courses_data(bot_name)  # Передаем bot_name явно
        print(f"[Catalog] Bot: {bot_name}, Total courses loaded: {len(courses)}")
        for c in courses:
            print(f"  - ID: {c.get('id')}, Name: {c.get('name')[:30] if c.get('name') else 'N/A'}, Active: {c.get('is_active')}, Image: {c.get('image_url', '')[:50] if c.get('image_url') else 'N/A'}")
    except Exception as e:
        print(f"Catalog load error for bot {bot_name}: {e}")
        import traceback
        traceback.print_exc()
        current_bot.send_message(user_id, get_text_value("catalog_error", CATALOG_ERROR_DEFAULT, bot_name))
        return
    active_courses = [c for c in courses if c.get("is_active", 1) == 1]
    print(f"[Catalog] Active courses: {len(active_courses)}")
    if not active_courses:
        current_bot.send_message(user_id, get_text_value("catalog_empty", CATALOG_EMPTY_DEFAULT, bot_name))
        return
    intro_text = format_text_for_telegram(get_text_value("catalog_intro", CATALOG_INTRO_DEFAULT, bot_name))

    # Получаем URL картинки каталога
    catalog_image_url = get_text_value("catalog_image_url", "", bot_name).strip()

    kb = types.InlineKeyboardMarkup()
    for course in active_courses:
        course_id = course.get("id")
        if not course_id:
            continue
        name = strip_html(course.get("name") or "Курс")
        price = course.get("price")
        label = name
        try:
            if price not in (None, ""):
                price_val = float(price)
                if price_val > 0:
                    label = f"{name} • {int(price_val)}₽"
        except (TypeError, ValueError):
            pass
        kb.add(types.InlineKeyboardButton(label[:64], callback_data=f"course_{course_id}"))
    text = intro_text

    # Delete previous message if provided
    message_chat_id = None
    message_id = None
    if edit_message:
        message_chat_id = edit_message.chat.id
        message_id = edit_message.message_id
    elif edit_chat_id and edit_message_id:
        message_chat_id = edit_chat_id
        message_id = edit_message_id

    if message_chat_id and message_id:
        try:
            current_bot.delete_message(chat_id=message_chat_id, message_id=message_id)
        except Exception as e:
            print(f"[Catalog] Failed to delete previous message: {e}")

    # Отправляем картинку каталога, если указана
    if catalog_image_url:
        send_image_safe(current_bot, user_id, catalog_image_url, caption=text, reply_markup=kb, parse_mode='HTML')
    else:
        current_bot.send_message(user_id, text, reply_markup=kb, parse_mode='HTML')

def ensure_user_record(user: telebot.types.User):
    if not user:
        return
    username = user.username if getattr(user, "username", None) else None
    try:
        add_user(user.id, username)
    except Exception as e:
        print(f"add_user error: {e}")

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
    current_bot = get_current_bot()
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if WEBHOOK_SECRET_TOKEN and secret != WEBHOOK_SECRET_TOKEN:
        abort(403)
    # Forward the update to pyTelegramBotAPI
    try:
        update = telebot.types.Update.de_json(request.stream.read().decode("utf-8"))
        current_bot.process_new_updates([update])
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
    if not get_current_payment_config()['PRODAMUS_TEST_WEBHOOK_URL']:
        return
    
    try:
        test_data = {
            "endpoint": endpoint_name,
            "method": method,
            "data": data,
            "timestamp": time.time()
        }
        requests.post(get_current_payment_config()['PRODAMUS_TEST_WEBHOOK_URL'], json=test_data, timeout=5)
        print(f"[Prodamus Test] Forwarded {endpoint_name} data to test webhook")
    except Exception as e:
        print(f"[Prodamus Test] Failed to forward to test webhook: {e}")

# Prodamus webhook handler (Result URL)
@application.route("/prodamus/result", methods=["GET", "POST"])
def prodamus_result():
    current_bot = get_current_bot()
    """
    Handle Prodamus Result URL notification (payment status update).
    Only this endpoint is required for processing payments.
    """
    try:
        payment_config = get_current_payment_config()
        secret_key = payment_config.get('PRODAMUS_SECRET_KEY', "")
        signature = request.headers.get("Sign") or request.headers.get("sign") or ""
        
        # Get raw POST body (URL-encoded string) - equivalent to $_POST in PHP
        raw_body = request.get_data(as_text=True, cache=False)
        
        if not raw_body:
            print("[Prodamus Result] Empty POST body")
            return "ERROR: Empty payload", 400
        
        # Parse using prodamuspy (handles PHP-style array notation)
        client = get_prodamus_client(secret_key)
        try:
            data = client.parse(raw_body)
        except Exception as e:
            print(f"[Prodamus Result] Failed to parse payload: {e}")
            return "ERROR: Failed to parse payload", 400

        if not data:
            print("[Prodamus Result] Empty payload after parsing")
            return "ERROR: Empty payload", 400

        print(f"[Prodamus Result] Payload: {data}")
        print(f"[Prodamus Result] Signature header: {signature}")
        print(f"[Prodamus Result] Secret key present: {bool(secret_key)}")

        forward_to_test_webhook("result", data, request.method)
        
        # Verify signature using client.verify() (equivalent to Hmac::verify in PHP)
        if not signature:
            print("[Prodamus Result] Signature header missing")
            return "ERROR: Signature header missing", 400
        
        if secret_key:
            if not client.verify(data, signature):
                calculated_sig = client.sign(data)
                print(f"[Prodamus Result] Invalid signature")
                print(f"[Prodamus Result] Calculated: {calculated_sig}")
                print(f"[Prodamus Result] Provided: {signature}")
                return "ERROR: Invalid signature", 400
            else:
                print("[Prodamus Result] ✅ Signature verified")
        
        order_number = data.get("order_num") or data.get("order_id") or data.get("order")
        amount = data.get("sum") or data.get("amount")
        payment_status = (data.get("payment_status") or data.get("payment_status_description") or data.get("status") or "").lower()
        
        if not order_number or not amount:
            print(f"[Prodamus Result] Missing required parameters. Received data: {data}")
            return "ERROR: Missing parameters", 400
        
        if payment_status not in ("success", "paid", "successful"):
            print(f"[Prodamus Result] Payment not successful, status: {payment_status}")
            return "OK", 200
        
        try:
            conn = sqlite3.connect(get_current_config()['DATABASE_PATH'])
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
            cur.execute("SELECT user_id, course_id, amount FROM pending_payments WHERE order_id = ? OR invoice_id = ?", (order_number, order_number))
            row = cur.fetchone()
            
            cleanup_conn = conn
            if row:
                user_id, course_id, expected_amount = row
                expected_amount = float(expected_amount)
            else:
                cleanup_conn = None
                conn.close()
                user_id, course_id = decode_order_metadata(order_number)
                if user_id is None or course_id is None:
                    print(f"[Prodamus Result] Payment not found for order/invoice {order_number}")
                    return "ERROR: Payment not found", 404
                expected_amount = float(amount)
                print(f"[Prodamus Result] Pending payment missing for {order_number}, using encoded metadata (user={user_id}, course={course_id})")
            
            if abs(float(amount) - float(expected_amount)) > 0.01:
                if cleanup_conn:
                    cleanup_conn.close()
                print(f"[Prodamus Result] Amount mismatch for order {order_number}: expected {expected_amount}, got {amount}")
                return "ERROR: Amount mismatch", 400
            
            try:
                courses = get_courses_data()
                course = next((x for x in courses if str(x.get("id")) == str(course_id)), None)
                if not course:
                    print(f"[Prodamus Result] Course {course_id} not found")
                    conn.close()
                    return "ERROR: Course not found", 404
                
                course_name = course.get("name", f"ID {course_id}")
                duration = course.get("duration_days")
                channel = str(course.get("channel", ""))
                
                add_user(user_id, None)
                
                add_purchase(user_id, str(course_id), course_name, channel, duration, payment_id=f"prodamus_{order_number}")
                
                if cleanup_conn:
                    cleanup_cur = cleanup_conn.cursor()
                    cleanup_cur.execute("DELETE FROM pending_payments WHERE order_id = ? OR invoice_id = ?", (order_number, order_number))
                    cleanup_conn.commit()
                    cleanup_conn.close()
                
                clean_course_name = strip_html(course_name) if course_name else f"ID {course_id}"
                text = f"✅ Оплата успешно получена!\n\nВам предоставлен доступ к курсу: {clean_course_name}"
                
                invite_link = None
                if channel:
                    try:
                        expire_date = datetime.datetime.now() + datetime.timedelta(days=1)
                        invite = current_bot.create_chat_invite_link(
                            chat_id=channel,
                            member_limit=1,
                            expire_date=expire_date
                        )
                        invite_link = invite.invite_link
                    except Exception as e:
                        print(f"create_chat_invite_link failed for {channel}: {e}")
                
                if invite_link:
                    kb = types.InlineKeyboardMarkup()
                    kb.add(types.InlineKeyboardButton("Перейти в канал курса", url=invite_link))
                    current_bot.send_message(user_id, text, reply_markup=kb)
                else:
                    current_bot.send_message(user_id, text)
                
                admin_text = f"💰 Оплата Prodamus: пользователь {user_id} купил {clean_course_name} на сумму {amount} руб. (Order: {order_number})"
                for admin_id in get_current_admin_ids():
                    try:
                        current_bot.send_message(admin_id, admin_text)
                    except Exception:
                        pass
                
                print(f"[Prodamus Result] ✅ Payment processed: user {user_id}, course {course_id}")
                return "OK", 200
            except Exception as e:
                conn.close()
                print(f"[Prodamus Result] Error processing payment: {e}")
                return "ERROR: Processing error", 500
        except Exception as e:
            print(f"[Prodamus Result] Database error: {e}")
            return "ERROR: Database error", 500
    except Exception as e:
        print(f"[Prodamus Result] Unexpected error: {e}")
        return "ERROR: Unexpected", 500

def _is_waiting_for_prodamus_email(message: telebot.types.Message) -> bool:
    """Filter helper that checks whether the user owes a Prodamus email in the current bot context."""
    return message.from_user.id in get_prodamus_pending_emails()

@bot.message_handler(func=_is_waiting_for_prodamus_email)
def handle_prodamus_email(message: telebot.types.Message):
    current_bot = get_current_bot()
    current_config = get_current_config()
    prodamus_emails = get_prodamus_pending_emails()
    user_id = message.from_user.id
    email_text = message.text.strip()
    
    # Validate email format
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email_text):
        current_bot.send_message(user_id, "❌ Неверный формат email адреса. Пожалуйста, отправьте корректный email (например: example@mail.ru)")
        return
    
    # Get pending payment info
    if user_id not in prodamus_emails:
        current_bot.send_message(user_id, "❌ Сессия истекла. Пожалуйста, начните оплату заново.")
        return
    
    payment_info = prodamus_emails.pop(user_id)
    course_id = payment_info["course_id"]
    order_id = payment_info["order_id"]
    price = payment_info["price"]
    clean_name = payment_info["name"]
    
    # Save email to user profile
    try:
        user = get_user(user_id)
        if user:
            # Update user email in database (if you have email field)
            conn = sqlite3.connect(get_current_config()['DATABASE_PATH'])
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
        payment_url = resolve_prodamus_payment_link(payment_url)
        
        # Store payment info in database
        try:
            conn = sqlite3.connect(get_current_config()['DATABASE_PATH'])
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
            
            if get_current_payment_config()['PRODAMUS_TEST_MODE']:
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
        
        current_bot.send_message(user_id, text, reply_markup=kb)
        
        if get_current_payment_config()['PRODAMUS_TEST_MODE']:
            print(f"[Prodamus TEST MODE] Generated payment URL with email for order_id {order_id}: {payment_url}")
            
    except Exception as e:
        error_msg = str(e)
        print(f"Error generating Prodamus payment URL: {error_msg}")
        current_bot.send_message(user_id, "❌ Ошибка при создании ссылки на оплату. Пожалуйста, попробуйте позже или обратитесь в поддержку.")


# Basic user-facing handlers
@bot.message_handler(commands=['start'])
def handle_start(message: telebot.types.Message):
    current_bot = get_current_bot()
    user_id = message.from_user.id
    bot_name = get_bot_context() or CURRENT_BOT_NAME
    ensure_user_record(message.from_user)
    greeting = format_text_for_telegram(get_text_value("greeting_text", "Привет! Я помогу выбрать и оплатить курс.", bot_name))

    # Отправляем картинку приветствия, если указана
    welcome_image_url = get_text_value("welcome_image_url", "", bot_name).strip()
    if welcome_image_url:
        send_image_safe(current_bot, user_id, welcome_image_url, caption=greeting, reply_markup=build_main_menu(user_id), parse_mode='HTML')
    else:
        current_bot.send_message(user_id, greeting, parse_mode='HTML', reply_markup=build_main_menu(user_id))

@bot.message_handler(func=lambda m: m.text == "Каталог")
def handle_catalog(message: telebot.types.Message):
    ensure_user_record(message.from_user)
    send_catalog_message(message.from_user.id)

@bot.message_handler(func=lambda m: m.text == "Активные подписки")
def handle_active(message: telebot.types.Message):
    current_bot = get_current_bot()
    user_id = message.from_user.id
    bot_name = get_bot_context() or CURRENT_BOT_NAME
    ensure_user_record(message.from_user)
    subscriptions = get_active_subscriptions(user_id) or []
    if not subscriptions:
        current_bot.send_message(
            user_id,
            get_text_value("no_active_subscriptions", NO_ACTIVE_SUBS_DEFAULT, bot_name),
            reply_markup=build_main_menu(user_id)
        )
        return
    header = get_text_value("active_subscriptions_header", ACTIVE_SUBS_HEADER_DEFAULT, bot_name)
    lines = [header, ""]
    links_keyboard = types.InlineKeyboardMarkup()
    has_links = False
    for idx, sub in enumerate(subscriptions, start=1):
        course_name = strip_html(sub["course_name"]) if sub["course_name"] else "Курс"
        expiry = sub["expiry"]
        if expiry and expiry > 0:
            expiry_text = datetime.datetime.fromtimestamp(expiry).strftime("%d.%m.%Y")
        else:
            expiry_text = "бессрочно"
        lines.append(f"{idx}. {course_name} — доступ до {expiry_text}")
        channel_id = sub["channel_id"]
        if channel_id:
            channel_str = str(channel_id)
            button_label = f"Открыть «{course_name[:20]}»"
            if channel_str.startswith("@"):
                links_keyboard.add(types.InlineKeyboardButton(button_label, url=f"https://t.me/{channel_str[1:]}"))
                has_links = True
            else:
                try:
                    expire_date = datetime.datetime.now() + datetime.timedelta(days=1)
                    invite = current_bot.create_chat_invite_link(
                        chat_id=channel_str,
                        member_limit=1,
                        expire_date=expire_date
                    )
                    links_keyboard.add(types.InlineKeyboardButton(button_label, url=invite.invite_link))
                    has_links = True
                except Exception as e:
                    print(f"Invite link error for {channel_id}: {e}")
    text = "\n".join(lines)
    current_bot.send_message(user_id, text, reply_markup=build_main_menu(user_id))
    if has_links:
        current_bot.send_message(user_id, "Быстрые ссылки на каналы:", reply_markup=links_keyboard)

@bot.message_handler(func=lambda m: m.text == "Поддержка")
def handle_support(message: telebot.types.Message):
    current_bot = get_current_bot()
    user_id = message.from_user.id
    bot_name = get_bot_context() or CURRENT_BOT_NAME
    ensure_user_record(message.from_user)
    support_text = format_text_for_telegram(get_text_value("support_text", SUPPORT_TEXT_DEFAULT, bot_name))
    current_bot.send_message(user_id, support_text, parse_mode='HTML', reply_markup=build_main_menu(user_id))

# Handler for "Оферта" button
@bot.message_handler(func=lambda m: m.text == "Оферта")
def handle_oferta(message: telebot.types.Message):
    current_bot = get_current_bot()
    user_id = message.from_user.id
    bot_name = get_bot_context() or CURRENT_BOT_NAME
    oferta_url = get_text_value("oferta_url", OFERTA_URL_DEFAULT, bot_name)
    try:
        current_bot.send_document(user_id, oferta_url, caption="Договор оферты (PDF)")
    except Exception:
        # Fallback: просто отправим ссылку, если по какой-то причине Telegram не скачал файл по URL
        current_bot.send_message(user_id, f"Договор оферты: {oferta_url}", disable_web_page_preview=False)

# Admin handlers
@bot.message_handler(func=lambda m: m.text == "📊 Все подписки")
def handle_admin_all_subscriptions(message: telebot.types.Message):
    current_bot = get_current_bot()
    """Admin handler: show all active subscriptions for all users"""
    user_id = message.from_user.id
    if user_id not in get_current_admin_ids():
        current_bot.send_message(user_id, "У вас нет доступа к этой функции.")
        return
    
    try:
        all_subs = get_all_active_subscriptions()
        all_subs = list(all_subs) if all_subs else []
        
        if not all_subs:
            current_bot.send_message(user_id, "Нет активных подписок.")
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
                # If expiry_ts is 0, subscription is unlimited
                if expiry_ts == 0:
                    text += f"  • {clean_course_name} (бессрочный доступ)\n"
                else:
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
                    current_bot.send_message(user_id, current_msg, disable_web_page_preview=True)
                    current_msg = part + "\n\n"
                else:
                    current_msg += part + "\n\n"
            if current_msg.strip():
                current_bot.send_message(user_id, current_msg, disable_web_page_preview=True)
        else:
            current_bot.send_message(user_id, text, disable_web_page_preview=True)
            
    except Exception as e:
        print(f"Error in handle_admin_all_subscriptions: {e}")
        current_bot.send_message(user_id, f"Ошибка при получении подписок: {e}")

@bot.message_handler(func=lambda m: m.text == "📋 Google Sheets")
def handle_admin_google_sheets(message: telebot.types.Message):
    current_bot = get_current_bot()
    """Admin handler: open Google Sheets link"""
    user_id = message.from_user.id
    if user_id not in get_current_admin_ids():
        current_bot.send_message(user_id, "У вас нет доступа к этой функции.")
        return
    
    # Get GSHEET_ID from current bot's config
    gsheet_id = get_current_config().get('GSHEET_ID', '')
    if not gsheet_id:
        current_bot.send_message(user_id, "Google Sheets ID не настроен.")
        return
    
    sheets_url = f"https://docs.google.com/spreadsheets/d/{gsheet_id}/edit"
    
    # Create inline keyboard with URL button
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("📋 Открыть Google Sheets", url=sheets_url))
    
    current_bot.send_message(
        user_id,
        "Нажмите на кнопку ниже, чтобы открыть Google Sheets:",
        reply_markup=keyboard
    )

@bot.callback_query_handler(func=lambda c: c.data.startswith("course_"))
def cb_course(c: telebot.types.CallbackQuery):
    current_bot = get_current_bot()
    user_id = c.from_user.id
    course_id = c.data.split("_", 1)[1]
    try:
        courses = get_courses_data()
    except Exception:
        current_bot.answer_callback_query(c.id, "Ошибка загрузки курса.", show_alert=True)
        return
    course = next((x for x in courses if str(x.get("id")) == str(course_id)), None)
    if not course:
        current_bot.answer_callback_query(c.id, "Курс не найден.", show_alert=True)
        return
    
    # Check if course is active (is_active == 1)
    if course.get("is_active", 1) != 1:
        current_bot.answer_callback_query(c.id, "Этот курс временно недоступен.", show_alert=True)
        return

    name = course.get("name", "")
    desc = course.get("description", "")
    price = course.get("price", 0)
    duration = course.get("duration_days")  # None if unlimited, int if limited
    image_url = course.get("image_url", "")
    channel_id = course.get("channel", "")
    
    # Debug logging
    print(f"[Course Detail] ID: {course_id}, Name: {name[:30] if name else 'N/A'}")
    print(f"[Course Detail] Image URL: '{image_url}' (length: {len(image_url) if image_url else 0})")

    original_chat_id = c.message.chat.id if c.message else None
    original_message_id = c.message.message_id if c.message else None
    original_deleted = False

    def delete_original_message():
        nonlocal original_deleted
        if original_deleted:
            return
        if original_chat_id and original_message_id:
            try:
                current_bot.delete_message(chat_id=original_chat_id, message_id=original_message_id)
            except Exception as e:
                print(f"[Catalog] Failed to delete original message: {e}")
            finally:
                original_deleted = True

    # Strip all HTML from course name and escape HTML special characters for safe use in HTML markup
    formatted_name = escape_html(strip_html(name)) if name else "Курс"

    if has_active_subscription(user_id, str(course_id)):
        # Format description with HTML support for Telegram
        formatted_desc = format_text_for_telegram(desc) if desc else ""
        # Escape ALREADY_PURCHASED_MSG for safe use in HTML markup
        escaped_msg = escape_html(ALREADY_PURCHASED_MSG)
        text = f"<b>{formatted_name}</b>\n{formatted_desc}\n\n✅ {escaped_msg}"
        ikb = types.InlineKeyboardMarkup()
        if channel_id:
            if str(channel_id).startswith("@"):
                url = f"https://t.me/{channel_id[1:]}"
                ikb.add(types.InlineKeyboardButton("Открыть канал курса", url=url))
            else:
                invite_link = None
                try:
                    # Set expire_date to 1 day from now
                    expire_date = datetime.datetime.now() + datetime.timedelta(days=1)
                    
                    # Create invite link with appropriate parameters
                    # member_limit=1 means single use (one-time link)
                    invite = current_bot.create_chat_invite_link(
                        chat_id=channel_id,
                        member_limit=1,  # Single use - one-time link
                        expire_date=expire_date  # Expires 1 day from now
                    )
                    invite_link = invite.invite_link
                except Exception as e:
                    print("Invite link error:", e)
                if invite_link:
                    ikb.add(types.InlineKeyboardButton("Перейти в канал курса", url=invite_link))
        ikb.add(types.InlineKeyboardButton("⬅️ Назад к каталогу", callback_data="back_to_catalog"))
        delete_original_message()
        try:
            if image_url:
                send_image_safe(current_bot, user_id, image_url, caption=text, reply_markup=ikb, parse_mode='HTML')
            else:
                current_bot.send_message(user_id, text, reply_markup=ikb, parse_mode='HTML')
        except Exception:
            current_bot.send_message(user_id, text, reply_markup=ikb, parse_mode='HTML')
        current_bot.answer_callback_query(c.id)
        return

    # Format description with HTML support for Telegram
    formatted_desc = format_text_for_telegram(desc) if desc else ""
    # Format duration: None/0 = unlimited, otherwise show days
    if duration is None or duration == 0:
        duration_text = "бессрочно"
    else:
        duration_text = f"{duration} дн." if duration == 1 else f"{duration} дн."
    # formatted_name is already escaped above
    text = f"<b>{formatted_name}</b>\n{formatted_desc}\n\nЦена: {price} руб.\nДоступ: {duration_text}"
    ikb = types.InlineKeyboardMarkup()
    # Add payment buttons
    if get_current_payment_config()['ENABLE_PRODAMUS'] and get_current_payment_config()['PRODAMUS_SECRET_KEY']:
        ikb.row(
            types.InlineKeyboardButton("Купить (ЮKassa)", callback_data=f"pay_yk_{course_id}"),
            types.InlineKeyboardButton("Купить (Prodamus)", callback_data=f"pay_prodamus_{course_id}")
        )
    else:
        ikb.add(types.InlineKeyboardButton("Купить (ЮKassa)", callback_data=f"pay_yk_{course_id}"))
    ikb.add(types.InlineKeyboardButton("⬅️ Назад к каталогу", callback_data="back_to_catalog"))
    
    delete_original_message()
    message_sent = False
    try:
        if image_url:
            send_image_safe(current_bot, user_id, image_url, caption=text, reply_markup=ikb, parse_mode='HTML')
        else:
            current_bot.send_message(user_id, text, reply_markup=ikb, parse_mode='HTML')
        message_sent = True
    except Exception as e:
        print(f"Error in course handler: {e}")
        if not message_sent:
            current_bot.send_message(user_id, text, reply_markup=ikb, parse_mode='HTML')
    current_bot.answer_callback_query(c.id)

@bot.callback_query_handler(func=lambda c: c.data == "back_to_catalog")
def cb_back_to_catalog(c: telebot.types.CallbackQuery):
    current_bot = get_current_bot()
    user_id = c.from_user.id
    if c.message:
        try:
            current_bot.delete_message(chat_id=c.message.chat.id, message_id=c.message.message_id)
        except Exception as e:
            print(f"[Catalog] Failed to delete course message: {e}")
    send_catalog_message(user_id)
    current_bot.answer_callback_query(c.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("buy_"))
def cb_buy(c: telebot.types.CallbackQuery):
    current_bot = get_current_bot()
    user_id = c.from_user.id
    course_id = c.data.split("_", 1)[1]
    try:
        courses = get_courses_data()
    except Exception:
        current_bot.answer_callback_query(c.id, "Не удалось получить данные курса.", show_alert=True)
        return
    course = next((x for x in courses if str(x.get("id")) == str(course_id)), None)
    if not course:
        current_bot.answer_callback_query(c.id, COURSE_NOT_AVAILABLE_MSG, show_alert=True)
        return
    # Check if course is active (is_active == 1)
    if course.get("is_active", 1) != 1:
        current_bot.answer_callback_query(c.id, "Этот курс временно недоступен для покупки.", show_alert=True)
        return
    if has_active_subscription(user_id, str(course_id)):
        current_bot.answer_callback_query(c.id, "У вас уже есть этот курс.", show_alert=True)
        return
    name = course.get("name", "Курс")
    price = float(course.get("price", 0))
    clean_name = strip_html(name) if name else "Курс"
    text = f"{clean_name}\nВыберите способ оплаты:"
    kb = types.InlineKeyboardMarkup()
    # Add payment buttons
    if get_current_payment_config()['ENABLE_PRODAMUS'] and get_current_payment_config()['PRODAMUS_SECRET_KEY']:
        kb.row(
            types.InlineKeyboardButton("ЮKassa", callback_data=f"pay_yk_{course_id}"),
            types.InlineKeyboardButton("Prodamus", callback_data=f"pay_prodamus_{course_id}")
        )
    else:
        kb.add(types.InlineKeyboardButton("ЮKassa", callback_data=f"pay_yk_{course_id}"))
    try:
        current_bot.send_message(user_id, text, reply_markup=kb)
        current_bot.answer_callback_query(c.id)
    except Exception:
        current_bot.answer_callback_query(c.id, "Ошибка при подготовке оплаты.", show_alert=True)

# Handler for ЮKassa payments
@bot.callback_query_handler(func=lambda c: c.data.startswith("pay_yk_"))
def cb_pay_yk(c: telebot.types.CallbackQuery):
    current_bot = get_current_bot()
    user_id = c.from_user.id
    course_id = c.data.split("_", 2)[2]
    try:
        courses = get_courses_data()
    except Exception:
        current_bot.answer_callback_query(c.id, "Не удалось получить данные курса.", show_alert=True)
        return
    course = next((x for x in courses if str(x.get("id")) == str(course_id)), None)
    if not course:
        current_bot.answer_callback_query(c.id, COURSE_NOT_AVAILABLE_MSG, show_alert=True)
        return
    # Check if course is active (is_active == 1)
    if course.get("is_active", 1) != 1:
        current_bot.answer_callback_query(c.id, "Этот курс временно недоступен для покупки.", show_alert=True)
        return
    if has_active_subscription(user_id, str(course_id)):
        current_bot.answer_callback_query(c.id, "У вас уже есть этот курс.", show_alert=True)
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
                    "amount": {"value": rub_str(price), "currency": get_current_payment_config()['CURRENCY']},
                    "vat_code": 1
                }
            ]
        }
    }
    provider_data_json = json.dumps(provider_data, ensure_ascii=False)

    # Strip HTML from invoice title
    clean_title_name = strip_html(name) if name else "Курс"
    try:
        current_bot.send_invoice(
            user_id,
            title=f"Курс: {clean_title_name}",
            description=invoice_description,
            provider_token=get_current_payment_config()['PAYMENT_PROVIDER_TOKEN'],
            currency=get_current_payment_config()['CURRENCY'],
            prices=prices,
            start_parameter="purchase-course",
            invoice_payload=payload,
            need_email=True,
            send_email_to_provider=True,
            provider_data=provider_data_json
        )
        current_bot.answer_callback_query(c.id)
    except Exception as e:
        print("send_invoice (YK) error:", e)
        current_bot.answer_callback_query(c.id, "Ошибка при выставлении счета (ЮKassa).", show_alert=True)

# Handler for Prodamus direct payments (via payment link)
@bot.callback_query_handler(func=lambda c: c.data.startswith("pay_prodamus_"))
def cb_pay_prodamus(c: telebot.types.CallbackQuery):
    current_bot = get_current_bot()
    user_id = c.from_user.id
    course_id = c.data.split("_", 2)[2]
    
    # Validate Prodamus configuration
    if not get_current_payment_config()['PRODAMUS_SECRET_KEY']:
        current_bot.answer_callback_query(c.id, "Prodamus не настроена. Обратитесь к администратору.", show_alert=True)
        return
    
    # Log test mode status
    if get_current_payment_config()['PRODAMUS_TEST_MODE']:
        print(f"[Prodamus TEST MODE] Payment request from user {user_id} for course {course_id}")
    
    try:
        courses = get_courses_data()
    except Exception as e:
        print(f"Error fetching courses for Prodamus payment: {e}")
        current_bot.answer_callback_query(c.id, "Не удалось получить данные курса.", show_alert=True)
        return
    
    course = next((x for x in courses if str(x.get("id")) == str(course_id)), None)
    if not course:
        current_bot.answer_callback_query(c.id, COURSE_NOT_AVAILABLE_MSG, show_alert=True)
        return
    
    # Check if course is active (is_active == 1)
    if course.get("is_active", 1) != 1:
        current_bot.answer_callback_query(c.id, "Этот курс временно недоступен для покупки.", show_alert=True)
        return
    
    if has_active_subscription(user_id, str(course_id)):
        current_bot.answer_callback_query(c.id, "У вас уже есть этот курс.", show_alert=True)
        return

    name = course.get("name", "Курс")
    price = float(course.get("price", 0))
    
    # Validate price
    if price <= 0:
        current_bot.answer_callback_query(c.id, "Неверная цена курса.", show_alert=True)
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
        if get_current_payment_config()['PRODAMUS_TEST_MODE']:
            print(f"[Prodamus] Error getting user email: {e}")
        pass
    
    # If no email, request it from user
    if not customer_email:
        # Store payment info in memory to continue after email is received
        prodamus_emails = get_prodamus_pending_emails()
        prodamus_emails[user_id] = {
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
        
        current_bot.send_message(user_id, text, reply_markup=kb)
        current_bot.answer_callback_query(c.id)
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
        payment_url = resolve_prodamus_payment_link(payment_url)
        
        # Store payment info in database for later verification
        try:
            conn = sqlite3.connect(get_current_config()['DATABASE_PATH'])
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
            
            if get_current_payment_config()['PRODAMUS_TEST_MODE']:
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
        
        current_bot.send_message(user_id, text, reply_markup=kb)
        current_bot.answer_callback_query(c.id)
        
        if get_current_payment_config()['PRODAMUS_TEST_MODE']:
            print(f"[Prodamus TEST MODE] Generated payment URL for order_id {order_id}: {payment_url}")
            
    except Exception as e:
        error_msg = str(e)
        print(f"Error generating Prodamus payment URL: {error_msg}")
        if get_current_payment_config()['PRODAMUS_TEST_MODE']:
            print(f"[Prodamus TEST MODE] Full error details: {repr(e)}")
        current_bot.answer_callback_query(c.id, "Ошибка при создании ссылки на оплату.", show_alert=True)

@bot.pre_checkout_query_handler(func=lambda q: True)
def handle_pre_checkout(q: telebot.types.PreCheckoutQuery):
    current_bot = get_current_bot()
    try:
        user_id = q.from_user.id
        payload = q.invoice_payload
        # Payload format: "user_id:course_id"
        parts = payload.split(":", 1)
        if len(parts) < 2:
            current_bot.answer_pre_checkout_query(q.id, ok=False, error_message="Неверный формат заказа.")
            return
        # Extract course_id (second part), user_id validation not needed here
        cid = parts[1]
        courses = get_courses_data()
        course = next((x for x in courses if str(x.get("id")) == str(cid)), None)
        if course is None:
            current_bot.answer_pre_checkout_query(q.id, ok=False, error_message=COURSE_NOT_AVAILABLE_MSG)
            return
        if has_active_subscription(user_id, str(cid)):
            current_bot.answer_pre_checkout_query(q.id, ok=False, error_message="Этот курс уже активен у вас.")
            return
        current_bot.answer_pre_checkout_query(q.id, ok=True)
    except Exception as e:
        print("pre_checkout error:", e)
        current_bot.answer_pre_checkout_query(q.id, ok=False, error_message="Ошибка проверки заказа.")

@bot.message_handler(content_types=['successful_payment'])
def handle_successful_payment(message: telebot.types.Message):
    current_bot = get_current_bot()
    payment = message.successful_payment
    user_id = message.from_user.id
    payload = payment.invoice_payload
    # Payload format: "user_id:course_id"
    parts = payload.split(":", 1)
    if len(parts) < 2:
        current_bot.send_message(user_id, "Ошибка: неверный формат заказа. Обратитесь в поддержку.")
        return
    # Extract course_id (second part)
    course_id = parts[1]

    try:
        courses = get_courses_data()
    except Exception:
        courses = []
    course = next((x for x in courses if str(x.get("id")) == str(course_id)), None)
    course_name = course.get("name", f"ID {course_id}") if course else f"ID {course_id}"
    duration = course.get("duration_days") if course else None  # None if unlimited
    channel = str(course.get("channel", "")) if course else ""

    # Ensure user exists in database before adding purchase (FOREIGN KEY constraint)
    username = message.from_user.username if message.from_user.username else None
    add_user(user_id, username)

    expiry_ts = add_purchase(user_id, str(course_id), course_name, channel, duration, payment_id=payment.telegram_payment_charge_id)

    invite_link = None
    if channel:
        try:
            # Set expire_date to 1 day from now
            expire_date = datetime.datetime.now() + datetime.timedelta(days=1)
            
            # Create invite link with appropriate parameters
            # member_limit=1 means single use (one-time link)
            invite = current_bot.create_chat_invite_link(
                chat_id=channel,
                member_limit=1,  # Single use - one-time link
                expire_date=expire_date  # Expires 1 day from now
            )
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
        current_bot.send_message(user_id, text, reply_markup=kb)
    else:
        current_bot.send_message(user_id, text)

    # Notify admins
    try:
        amount = payment.total_amount / 100.0
        cur = payment.currency
    except Exception:
        amount, cur = 0, get_current_payment_config()['CURRENCY']
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
    for aid in get_current_admin_ids():
        try:
            current_bot.send_message(aid, admin_text)
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
    current_bot = get_current_bot()
    """Admin command to manually trigger expired subscriptions cleanup"""
    if message.from_user.id not in get_current_admin_ids():
        return
    
    current_bot.reply_to(message, "🔄 Запуск очистки просроченных подписок...")
    
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
            current_bot.reply_to(message, report + "✅ Просроченных подписок не найдено.")
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
                            member = current_bot.get_chat_member(channel_id, user_id)
                            status = getattr(member, "status", "unknown")
                            if status in ("left", "kicked"):
                                ok = True
                        except:
                            ok = True  # Assume removed if can't check
                
                mark_subscription_expired(user_id, course_id)
                
                # Try to notify user
                try:
                    clean_course_name = strip_html(course_name) if course_name else "курсу"
                    current_bot.send_message(user_id, f"Доступ к курсу {clean_course_name} завершен. Спасибо, что были с нами!")
                except:
                    pass
                
                processed += 1
            except Exception as e:
                failed += 1
                print(f"Error processing expired subscription: {e}")
        
        report += f"✅ Обработано: {processed}\n"
        if failed > 0:
            report += f"⚠️ Ошибок: {failed}"
        
        current_bot.reply_to(message, report)
        
    except Exception as e:
        current_bot.reply_to(message, f"❌ Ошибка при очистке: {e}")
        import traceback
        print(f"Cleanup error: {traceback.format_exc()}")

# In-memory state for database clearing confirmation
# Format: {user_id: True} - user has confirmed they want to clear DB
db_clear_confirmations = {}

@bot.message_handler(commands=['clear_db'])
def handle_clear_db(message: telebot.types.Message):
    current_bot = get_current_bot()
    """Admin command to clear all database data"""
    user_id = message.from_user.id
    if user_id not in get_current_admin_ids():
        current_bot.reply_to(message, "❌ У вас нет доступа к этой команде.")
        return
    
    # Check if user already confirmed
    if user_id in db_clear_confirmations:
        # User confirmed, proceed with clearing
        del db_clear_confirmations[user_id]
        
        try:
            # Get statistics before clearing
            stats = clear_all_data()
            
            # Build report
            report = "🗑️ <b>База данных полностью очищена!</b>\n\n"
            report += "📊 Удалено:\n"
            report += f"• Пользователей: {stats['users']}\n"
            report += f"• Покупок: {stats['purchases']}\n"
            report += f"• Ожидающих платежей: {stats['pending_payments']}\n\n"
            report += "✅ База данных теперь пуста."
            
            current_bot.reply_to(message, report, parse_mode='HTML')
        except Exception as e:
            current_bot.reply_to(message, f"❌ Ошибка при очистке базы данных: {e}")
    else:
        # First time - show warning and ask for confirmation
        try:
            # Get current statistics
            from db import get_connection
            conn = get_connection()
            cur = conn.cursor()
            
            cur.execute("SELECT COUNT(*) FROM users")
            users_count = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM purchases")
            purchases_count = cur.fetchone()[0]
            
            try:
                cur.execute("SELECT COUNT(*) FROM pending_payments")
                pending_count = cur.fetchone()[0]
            except sqlite3.OperationalError:
                pending_count = 0
            
            warning = "⚠️ <b>ВНИМАНИЕ!</b>\n\n"
            warning += "Вы собираетесь <b>полностью очистить базу данных</b>.\n\n"
            warning += "📊 Текущая статистика:\n"
            warning += f"• Пользователей: {users_count}\n"
            warning += f"• Покупок: {purchases_count}\n"
            warning += f"• Ожидающих платежей: {pending_count}\n\n"
            warning += "❌ Это действие <b>необратимо</b>!\n"
            warning += "Все данные будут удалены навсегда.\n\n"
            warning += "Нажмите кнопку ниже для подтверждения:"
            
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("✅ Да, очистить базу данных", callback_data="confirm_clear_db"))
            kb.add(types.InlineKeyboardButton("❌ Отмена", callback_data="cancel_clear_db"))
            
            current_bot.reply_to(message, warning, reply_markup=kb, parse_mode='HTML')
        except Exception as e:
            current_bot.reply_to(message, f"❌ Ошибка при получении статистики: {e}")

@bot.callback_query_handler(func=lambda c: c.data == "confirm_clear_db")
def cb_confirm_clear_db(c: telebot.types.CallbackQuery):
    current_bot = get_current_bot()
    """Handle confirmation to clear database"""
    user_id = c.from_user.id
    if user_id not in get_current_admin_ids():
        current_bot.answer_callback_query(c.id, "❌ У вас нет доступа.", show_alert=True)
        return
    
    # Mark user as confirmed
    db_clear_confirmations[user_id] = True
    
    # Edit message to show confirmation
    try:
        current_bot.edit_message_text(
            "✅ Подтверждение получено. Отправьте команду /clear_db еще раз для выполнения очистки.",
            chat_id=c.message.chat.id,
            message_id=c.message.message_id
        )
    except Exception:
        pass
    
    current_bot.answer_callback_query(c.id, "Подтверждение получено. Отправьте /clear_db еще раз.")

@bot.callback_query_handler(func=lambda c: c.data == "cancel_clear_db")
def cb_cancel_clear_db(c: telebot.types.CallbackQuery):
    current_bot = get_current_bot()
    """Handle cancellation of database clearing"""
    user_id = c.from_user.id
    if user_id not in get_current_admin_ids():
        current_bot.answer_callback_query(c.id, "❌ У вас нет доступа.", show_alert=True)
        return
    
    # Remove from confirmations if exists
    if user_id in db_clear_confirmations:
        del db_clear_confirmations[user_id]
    
    # Edit message to show cancellation
    try:
        current_bot.edit_message_text(
            "❌ Очистка базы данных отменена.",
            chat_id=c.message.chat.id,
            message_id=c.message.message_id
        )
    except Exception:
        pass
    
    current_bot.answer_callback_query(c.id, "Очистка отменена.")

@bot.message_handler(commands=['broadcast_all', 'broadcast_buyers', 'broadcast_nonbuyers'])
def handle_broadcast(message: telebot.types.Message):
    current_bot = get_current_bot()
    if message.from_user.id not in get_current_admin_ids():
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        current_bot.reply_to(message, "После команды укажите текст сообщения.")
        return
    cmd = parts[0]
    text = parts[1]

    recipients = []
    try:
        # Use separate connection for broadcast to avoid conflicts
        conn = sqlite3.connect(get_current_config()['DATABASE_PATH'])
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
        current_bot.reply_to(message, f"Ошибка при получении списка получателей: {e}")
        return

    sent = 0
    failed = 0
    for uid in recipients:
        try:
            current_bot.send_message(uid, text, disable_web_page_preview=True)
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
    current_bot.reply_to(message, reply_msg)

def send_broadcast_messages(recipients: list, text: str, bot_instance, photo_file_id: str = None, progress_callback=None):
    """
    Send broadcast messages to recipients with rate limiting.
    bot_instance: TeleBot instance to use for sending messages
    progress_callback: Optional function(sent, failed, total) called periodically
    Returns tuple (sent_count, failed_count)
    """
    sent = 0
    failed = 0
    total = len(recipients)
    last_progress_update = 0
    consecutive_errors = 0
    max_consecutive_errors = 10  # Stop if too many consecutive errors
    
    for idx, uid in enumerate(recipients, 1):
        try:
            if photo_file_id:
                # Send photo with caption
                bot_instance.send_photo(uid, photo_file_id, caption=text, disable_web_page_preview=True, timeout=10)
            else:
                # Send text only
                bot_instance.send_message(uid, text, disable_web_page_preview=True, timeout=10)
            sent += 1
            consecutive_errors = 0  # Reset error counter on success
            
            # Update progress every 10 messages or every 3 seconds
            if progress_callback and (idx % 10 == 0 or time.time() - last_progress_update > 3):
                try:
                    progress_callback(sent, failed, total)
                    last_progress_update = time.time()
                except Exception as e:
                    # Don't let progress callback errors stop the broadcast
                    if idx % 50 == 0:  # Log only occasionally
                        print(f"[Broadcast] Progress callback error: {e}")
            
            # Rate limiting: delay every 10 messages to stay well under Telegram limits
            # Telegram allows ~30 messages/second, we'll do ~10/second to be safe
            if idx % 10 == 0 and idx < total:
                time.sleep(0.1)  # 100ms delay every 10 messages
                
        except Exception as e:
            failed += 1
            consecutive_errors += 1
            error_msg = str(e).lower()
            
            # Handle specific error types
            if "chat not found" in error_msg or "bot was blocked" in error_msg or "user is deactivated" in error_msg:
                # User blocked bot or deleted account - not a real failure, just skip
                consecutive_errors = 0  # Don't count blocked users as consecutive errors
                pass
            elif "too many requests" in error_msg or "rate limit" in error_msg:
                # Rate limit hit - wait longer and retry
                wait_time = 2  # Start with 2 seconds
                if "retry after" in error_msg:
                    # Try to extract retry_after value
                    try:
                        import re
                        match = re.search(r'retry after (\d+)', error_msg)
                        if match:
                            wait_time = int(match.group(1)) + 1
                    except:
                        pass
                
                print(f"[Broadcast] Rate limit hit at message {idx}, waiting {wait_time} seconds...")
                time.sleep(wait_time)
                consecutive_errors = 0  # Reset on retry
                
                # Retry this message
                try:
                    if photo_file_id:
                        bot_instance.send_photo(uid, photo_file_id, caption=text, disable_web_page_preview=True, timeout=10)
                    else:
                        bot_instance.send_message(uid, text, disable_web_page_preview=True, timeout=10)
                    sent += 1
                    failed -= 1
                except Exception as e2:
                    print(f"[Broadcast] Retry failed for user {uid}: {e2}")
            elif "timeout" in error_msg or "connection" in error_msg or "ssl" in error_msg:
                # Network error - wait a bit and continue
                print(f"[Broadcast] Network error for user {uid}, waiting 0.5s...")
                time.sleep(0.5)
                # Don't retry immediately, just continue
            else:
                # Log first few failures for debugging
                if failed <= 5:
                    print(f"[Broadcast] Failed to send to user {uid}: {e}")
            
            # Stop if too many consecutive errors (might indicate a bigger problem)
            if consecutive_errors >= max_consecutive_errors:
                print(f"[Broadcast] Too many consecutive errors ({consecutive_errors}), stopping broadcast")
                break
        
        # Update progress at the end of loop iteration if needed
        if progress_callback and idx == total:
            try:
                progress_callback(sent, failed, total)
            except Exception as e:
                print(f"[Broadcast] Final progress callback error: {e}")
    
    return sent, failed

# Admin broadcast handler - button in menu
# Note: We can't use get_current_admin_ids() in decorator directly, so we check in function body
@bot.message_handler(func=lambda m: m.text == "📢 Рассылка")
def handle_broadcast_button(message: telebot.types.Message):
    current_bot = get_current_bot()
    """Show broadcast type selection"""
    user_id = message.from_user.id
    
    # Reset broadcast state
    broadcast_state = get_admin_broadcast_state()
    broadcast_state[user_id] = {"type": None, "text": None, "photo": None}
    
    text = "📢 Выберите тип рассылки:"
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("👥 Всем пользователям", callback_data="broadcast_type_all"))
    kb.add(types.InlineKeyboardButton("💰 Покупателям", callback_data="broadcast_type_buyers"))
    kb.add(types.InlineKeyboardButton("🆕 Непокупателям", callback_data="broadcast_type_nonbuyers"))
    kb.add(types.InlineKeyboardButton("❌ Отмена", callback_data="broadcast_cancel"))
    
    current_bot.send_message(user_id, text, reply_markup=kb)

# Broadcast type selection callback
@bot.callback_query_handler(func=lambda c: c.data.startswith("broadcast_type_"))
def cb_broadcast_type(c: telebot.types.CallbackQuery):
    current_bot = get_current_bot()
    user_id = c.from_user.id
    if user_id not in get_current_admin_ids():
        safe_answer_callback_query(current_bot, c.id, "У вас нет доступа.", show_alert=True)
        return
    
    broadcast_type = c.data.split("_")[-1]  # all, buyers, nonbuyers
    
    # Initialize broadcast state
    broadcast_state = get_admin_broadcast_state()
    if user_id not in broadcast_state:
        broadcast_state[user_id] = {}
    broadcast_state[user_id]["type"] = broadcast_type
    
    type_names = {
        "all": "всем пользователям",
        "buyers": "покупателям",
        "nonbuyers": "непокупателям"
    }
    
    text = f"📢 Рассылка {type_names.get(broadcast_type, '')}\n\n"
    text += "Отправьте текст сообщения. Вы также можете прикрепить фото."
    
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("❌ Отмена", callback_data="broadcast_cancel"))
    
    try:
        current_bot.edit_message_text(text, chat_id=c.message.chat.id, message_id=c.message.message_id, reply_markup=kb)
    except Exception as e:
        print(f"[Broadcast] Failed to edit message: {e}")
        # Fallback: send new message
        current_bot.send_message(user_id, text, reply_markup=kb)
    
    safe_answer_callback_query(current_bot, c.id)

# Cancel broadcast
@bot.callback_query_handler(func=lambda c: c.data == "broadcast_cancel")
def cb_broadcast_cancel(c: telebot.types.CallbackQuery):
    current_bot = get_current_bot()
    user_id = c.from_user.id
    broadcast_state = get_admin_broadcast_state()
    if user_id in broadcast_state:
        del broadcast_state[user_id]
    
    try:
        current_bot.edit_message_text("❌ Рассылка отменена.", chat_id=c.message.chat.id, message_id=c.message.message_id)
    except Exception as e:
        print(f"[Broadcast] Failed to edit cancel message: {e}")
        # Fallback: send new message
        current_bot.send_message(user_id, "❌ Рассылка отменена.")
    
    safe_answer_callback_query(current_bot, c.id)

# Handle text message for broadcast
# This handler must be before other text handlers to catch broadcast text
# Note: We check admin_broadcast_state in decorator, but check admin status in function body
@bot.message_handler(func=lambda m: m.text and not m.text.startswith("/") and m.text not in ["Каталог", "Активные подписки", "Поддержка", "Оферта", "📊 Все подписки", "📋 Google Sheets", "📢 Рассылка"])
def handle_broadcast_text(message: telebot.types.Message):
    current_bot = get_current_bot()
    """Handle text input for broadcast"""
    user_id = message.from_user.id
    
    # Check if user is in broadcast state and is admin for current bot
    broadcast_state = get_admin_broadcast_state()
    if user_id not in broadcast_state:
        return
    
    if user_id not in get_current_admin_ids():
        return
    
    state = broadcast_state[user_id]
    
    if state.get("type") is None:
        return
    
    # Save text
    state["text"] = message.text
    
    # If photo already set, send immediately in background thread
    if state.get("photo"):
        # Answer callback immediately if this was triggered by callback
        # (though this is a message handler, so no callback to answer)
        # Get bot_name for context in background thread
        bot_name = get_bot_context() or CURRENT_BOT_NAME
        # Execute broadcast in background thread (non-blocking)
        thread = threading.Thread(target=execute_broadcast, args=(user_id, state, bot_name), daemon=True)
        thread.start()
    else:
        # Ask if want to add photo or send now
        text = f"📝 Текст сохранен:\n\n{message.text[:200]}{'...' if len(message.text) > 200 else ''}\n\n"
        text += "Вы можете прикрепить фото или отправить рассылку сейчас."
        
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("📷 Прикрепить фото", callback_data="broadcast_add_photo"))
        kb.add(types.InlineKeyboardButton("✅ Отправить сейчас", callback_data="broadcast_send"))
        kb.add(types.InlineKeyboardButton("❌ Отмена", callback_data="broadcast_cancel"))
        
        current_bot.send_message(user_id, text, reply_markup=kb)

# Handle photo for broadcast
# Note: We check admin_broadcast_state in decorator, but check admin status in function body
@bot.message_handler(func=lambda m: m.photo, content_types=['photo'])
def handle_broadcast_photo(message: telebot.types.Message):
    current_bot = get_current_bot()
    """Handle photo input for broadcast"""
    user_id = message.from_user.id
    
    # Check if user is in broadcast state and is admin for current bot
    broadcast_state = get_admin_broadcast_state()
    if user_id not in broadcast_state:
        return
    
    if user_id not in get_current_admin_ids():
        return
    
    state = broadcast_state[user_id]
    
    if state.get("type") is None:
        return
    
    # Get largest photo
    photo = message.photo[-1]
    state["photo"] = photo.file_id
    
    # If text already set, ask to send
    if state.get("text"):
        text = f"📷 Фото прикреплено\n📝 Текст: {state['text'][:200]}{'...' if len(state['text']) > 200 else ''}\n\n"
        text += "Готово к отправке!"
        
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("✅ Отправить рассылку", callback_data="broadcast_send"))
        kb.add(types.InlineKeyboardButton("❌ Отмена", callback_data="broadcast_cancel"))
        
        current_bot.send_message(user_id, text, reply_markup=kb)
    else:
        current_bot.send_message(user_id, "📷 Фото сохранено. Теперь отправьте текст сообщения.")

# Send broadcast callback
@bot.callback_query_handler(func=lambda c: c.data == "broadcast_send")
def cb_broadcast_send(c: telebot.types.CallbackQuery):
    current_bot = get_current_bot()
    user_id = c.from_user.id
    if user_id not in get_current_admin_ids():
        safe_answer_callback_query(current_bot, c.id, "У вас нет доступа.", show_alert=True)
        return
    
    broadcast_state = get_admin_broadcast_state()
    if user_id not in broadcast_state:
        safe_answer_callback_query(current_bot, c.id, "Ошибка: состояние рассылки не найдено.", show_alert=True)
        return
    
    state = broadcast_state[user_id]
    
    if not state.get("text"):
        safe_answer_callback_query(current_bot, c.id, "Ошибка: текст сообщения не указан.", show_alert=True)
        return
    
    # Answer callback immediately to prevent timeout
    safe_answer_callback_query(current_bot, c.id, "Начинаю рассылку...")
    
    # Get bot_name for context in background thread
    bot_name = get_bot_context() or CURRENT_BOT_NAME
    # Execute broadcast in background thread (non-blocking)
    thread = threading.Thread(target=execute_broadcast, args=(user_id, state, bot_name), daemon=True)
    thread.start()

# Add photo callback
@bot.callback_query_handler(func=lambda c: c.data == "broadcast_add_photo")
def cb_broadcast_add_photo(c: telebot.types.CallbackQuery):
    current_bot = get_current_bot()
    user_id = c.from_user.id
    if user_id not in get_current_admin_ids():
        safe_answer_callback_query(current_bot, c.id, "У вас нет доступа.", show_alert=True)
        return
    
    try:
        current_bot.edit_message_text("📷 Отправьте фото для рассылки.", chat_id=c.message.chat.id, message_id=c.message.message_id)
    except Exception as e:
        print(f"[Broadcast] Failed to edit add photo message: {e}")
        try:
            current_bot.send_message(user_id, "📷 Отправьте фото для рассылки.")
        except Exception as e2:
            print(f"[Broadcast] Failed to send add photo message: {e2}")
    
    safe_answer_callback_query(current_bot, c.id)

def execute_broadcast(user_id: int, state: dict, bot_name: str = None):
    """
    Execute broadcast with given state.
    This function runs in a background thread to avoid blocking webhook handlers.
    bot_name: Name of the bot to use (required for multi-bot context)
    """
    # Set bot context for this thread (critical for multi-bot support)
    if bot_name:
        set_bot_context(bot_name)
        print(f"[Broadcast] Starting broadcast for bot '{bot_name}', user {user_id}")
    else:
        print(f"[Broadcast] Warning: No bot_name provided, using default bot context")
    
    current_bot = get_current_bot()
    broadcast_state = get_admin_broadcast_state()
    
    try:
        broadcast_type = state.get("type")
        text = state.get("text")
        photo = state.get("photo")
        
        if not broadcast_type or not text:
            error_msg = "❌ Ошибка: не указан тип рассылки или текст."
            print(f"[Broadcast] {error_msg} (type={broadcast_type}, has_text={bool(text)})")
            try:
                current_bot.send_message(user_id, error_msg)
            except Exception as e:
                print(f"[Broadcast] Failed to send error message: {e}")
            finally:
                # Clear state on error
                if user_id in broadcast_state:
                    del broadcast_state[user_id]
            return
        
        # Get recipients
        recipients = []
        try:
            conn = sqlite3.connect(get_current_config()['DATABASE_PATH'])
            cur = conn.cursor()
            if broadcast_type == "all":
                cur.execute("SELECT user_id FROM users;")
            elif broadcast_type == "buyers":
                cur.execute("SELECT DISTINCT user_id FROM purchases;")
            elif broadcast_type == "nonbuyers":
                cur.execute("SELECT user_id FROM users WHERE user_id NOT IN (SELECT DISTINCT user_id FROM purchases);")
            rows = cur.fetchall()
            recipients = [r[0] for r in rows]
            conn.close()
        except Exception as e:
            print(f"[Broadcast] Database error: {e}")
            try:
                current_bot.send_message(user_id, f"❌ Ошибка при получении списка получателей: {e}")
            except Exception as e2:
                print(f"[Broadcast] Failed to send database error message: {e2}")
            finally:
                # Clear state on error
                if user_id in broadcast_state:
                    del broadcast_state[user_id]
            return
        
        if not recipients:
            try:
                current_bot.send_message(user_id, "❌ Получатели не найдены.")
            except Exception as e:
                print(f"[Broadcast] Failed to send no recipients message: {e}")
            finally:
                # Clear state
                if user_id in broadcast_state:
                    del broadcast_state[user_id]
            return
        
        # Send initial progress message
        type_names = {
            "all": "всем пользователям",
            "buyers": "покупателям",
            "nonbuyers": "непокупателям"
        }
        progress_msg = None
        try:
            initial_text = f"📤 Отправка рассылки {type_names.get(broadcast_type, '')}...\nПолучателей: {len(recipients)}\nОтправлено: 0"
            progress_msg = current_bot.send_message(user_id, initial_text, timeout=10)
            print(f"[Broadcast] Initial progress message sent. Recipients: {len(recipients)}")
            # Small delay to ensure message is sent before starting broadcast
            time.sleep(0.2)
        except Exception as e:
            print(f"[Broadcast] Failed to send initial progress message: {e}")
            # Try once more after a short delay
            try:
                time.sleep(0.5)
                progress_msg = current_bot.send_message(user_id, initial_text, timeout=10)
                print(f"[Broadcast] Initial progress message sent on retry")
            except Exception as e2:
                print(f"[Broadcast] Failed to send initial progress message on retry: {e2}")
                # Continue anyway - we'll try to send final stats
        
        # Progress update callback with fallback
        progress_update_failures = 0
        def update_progress(sent, failed, total):
            """Update progress message periodically with fallback to new message if edit fails"""
            nonlocal progress_msg, progress_update_failures
            if not progress_msg:
                return
            
            try:
                progress_text = f"📤 Отправка рассылки {type_names.get(broadcast_type, '')}...\n"
                progress_text += f"Получателей: {total}\n"
                progress_text += f"✅ Отправлено: {sent}\n"
                progress_text += f"❌ Ошибок: {failed}\n"
                progress_text += f"⏳ Осталось: {total - sent - failed}"
                
                # Try to edit existing message
                try:
                    current_bot.edit_message_text(
                        progress_text,
                        chat_id=progress_msg.chat.id,
                        message_id=progress_msg.message_id,
                        timeout=5
                    )
                    progress_update_failures = 0  # Reset failure counter on success
                except Exception as edit_error:
                    progress_update_failures += 1
                    # If edit fails multiple times, send a new message and update progress_msg
                    if progress_update_failures >= 3:
                        try:
                            # Send new progress message
                            new_msg = current_bot.send_message(user_id, progress_text, timeout=5)
                            progress_msg = new_msg
                            progress_update_failures = 0
                            print(f"[Broadcast] Switched to new progress message after {progress_update_failures} edit failures")
                        except Exception as send_error:
                            # If sending also fails, just log and continue
                            if sent % 50 == 0:  # Log only occasionally
                                print(f"[Broadcast] Both edit and send failed for progress update: {send_error}")
                    else:
                        # Log occasionally if edit fails but we haven't switched yet
                        if sent % 50 == 0:
                            print(f"[Broadcast] Progress edit failed (failures={progress_update_failures}): {edit_error}")
            except Exception as e:
                # Catch-all for any other errors in progress update
                if sent % 50 == 0:
                    print(f"[Broadcast] Progress update error: {e}")
        
        # Send messages with progress updates
        print(f"[Broadcast] Starting to send {len(recipients)} messages...")
        try:
            sent, failed = send_broadcast_messages(recipients, text, current_bot, photo, progress_callback=update_progress)
            print(f"[Broadcast] Broadcast completed: sent={sent}, failed={failed}, total={len(recipients)}")
        except Exception as send_error:
            print(f"[Broadcast] Critical error during message sending: {send_error}")
            import traceback
            traceback.print_exc()
            # Try to notify admin
            try:
                current_bot.send_message(user_id, f"❌ Критическая ошибка при отправке рассылки: {str(send_error)[:200]}")
            except:
                pass
            # Set sent/failed to 0 to indicate failure
            sent = 0
            failed = len(recipients)
        
        # Show final statistics (always try to send, even if broadcast failed)
        stats_text = f"📊 Статистика рассылки:\n\n"
        stats_text += f"✅ Отправлено: {sent}\n"
        stats_text += f"❌ Не удалось отправить: {failed}\n"
        stats_text += f"📊 Всего получателей: {len(recipients)}"
        
        # Try multiple methods to send final statistics
        stats_sent = False
        if progress_msg:
            # Method 1: Try to edit progress message
            try:
                current_bot.edit_message_text(
                    stats_text, 
                    chat_id=progress_msg.chat.id, 
                    message_id=progress_msg.message_id,
                    timeout=10
                )
                print(f"[Broadcast] Final statistics updated successfully via edit")
                stats_sent = True
            except Exception as e:
                print(f"[Broadcast] Failed to edit final progress message: {e}")
        
        # Method 2: If edit failed or no progress_msg, send new message
        if not stats_sent:
            try:
                current_bot.send_message(user_id, stats_text, timeout=10)
                print(f"[Broadcast] Final statistics sent as new message")
                stats_sent = True
            except Exception as e:
                print(f"[Broadcast] Failed to send final stats message: {e}")
                # Last resort: try one more time after a short delay
                try:
                    time.sleep(1)
                    current_bot.send_message(user_id, stats_text, timeout=10)
                    print(f"[Broadcast] Final statistics sent on retry")
                    stats_sent = True
                except Exception as e2:
                    print(f"[Broadcast] Failed to send stats message even on retry: {e2}")
        
        if not stats_sent:
            print(f"[Broadcast] WARNING: Could not send final statistics to admin")
    
    except Exception as e:
        print(f"[Broadcast] Unexpected error in execute_broadcast: {e}")
        import traceback
        traceback.print_exc()
        try:
            error_notification = f"❌ Произошла ошибка при выполнении рассылки: {str(e)[:200]}"
            current_bot.send_message(user_id, error_notification, timeout=10)
        except Exception as e2:
            print(f"[Broadcast] Failed to send error notification: {e2}")
    
    finally:
        # Always clear state, even on error (critical to prevent state leaks)
        try:
            if user_id in broadcast_state:
                del broadcast_state[user_id]
                print(f"[Broadcast] Broadcast state cleared for user {user_id}")
        except Exception as e:
            print(f"[Broadcast] Error clearing broadcast state: {e}")


def remove_user_from_channel(user_id: int, channel_id: str):
    current_bot = get_current_bot()
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
        member = current_bot.get_chat_member(chat_id=channel_id, user_id=user_id)
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
        current_bot.ban_chat_member(chat_id=channel_id, user_id=user_id, until_date=None)
        print(f"[{timestamp}] [remove_user_from_channel] Successfully banned user {user_id}")
        
        # Then immediately unban (allows them to rejoin if needed, but they're already removed)
        print(f"[{timestamp}] [remove_user_from_channel] Unbanning user {user_id}...")
        current_bot.unban_chat_member(chat_id=channel_id, user_id=user_id, only_if_banned=True)
        print(f"[{timestamp}] [remove_user_from_channel] Successfully unbanned user {user_id}")
        
        # Verify removal by checking status again
        try:
            member = current_bot.get_chat_member(chat_id=channel_id, user_id=user_id)
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
    current_bot = get_current_bot()
    """
    Проверяем корректность поля 'channel' у курсов и права бота.
    Возвращает человекочитаемый отчёт.
    """
    lines = []
    # Кто мы
    try:
        me = current_bot.get_me()
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
            chat = current_bot.get_chat(channel)
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
                admins = current_bot.get_chat_administrators(chat.id)
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
    current_bot = get_current_bot()
    if message.from_user.id not in get_current_admin_ids():
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
            current_bot.send_message(message.chat.id, "🔎 Диагностика каналов:\n" + p, disable_web_page_preview=True)
        except Exception:
            pass

if __name__ == "__main__":
    if USE_WEBHOOK:
        print("Webhook mode enabled. Run webhook_app.py (WSGI) on your server.")
    else:
        # Однократная проверка каналов при старте
        try:
            startup_report = check_course_channels()
            for aid in get_current_admin_ids():
                try:
                    bot.send_message(aid, "🔎 Диагностика каналов при старте:\n" + startup_report, disable_web_page_preview=True)
                except Exception:
                    pass
        except Exception as e:
            print("Channel diagnostics failed on startup:", e)
        print("Bot started in polling mode...")
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
