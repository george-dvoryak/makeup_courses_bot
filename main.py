# main.py
import datetime
import sqlite3
import json
import telebot
from telebot import types
import os
import time
import re
from flask import Flask, request, abort

from config import TELEGRAM_BOT_TOKEN, PAYMENT_PROVIDER_TOKEN, ADMIN_IDS, CURRENCY, USE_WEBHOOK, DATABASE_PATH, GSHEET_ID, OFFER_INN, OFFER_FULL_NAME
from db import add_user, get_user, add_purchase, get_active_subscriptions, has_active_subscription, mark_subscription_expired, get_all_active_subscriptions
from google_sheets import get_courses_data, get_texts_data


bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN, parse_mode=None, threaded=False)

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

# (Robokassa helper removed)

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


# Handler for "Оферта" button
@bot.message_handler(func=lambda m: m.text == "Оферта")
def handle_oferta(message: telebot.types.Message):
    user_id = message.from_user.id
    oferta_url = "https://github.com/george-dvoryak/cdn/blob/main/oferta.pdf?raw=true"
    try:
        caption = f"Договор оферты (PDF)\nИНН: {OFFER_INN}\nФИО: {OFFER_FULL_NAME}"
        bot.send_document(user_id, oferta_url, caption=caption)
    except Exception:
        # Fallback: просто отправим ссылку, если по какой-то причине Telegram не скачал файл по URL
        text = f"Договор оферты: {oferta_url}\n\nИНН: {OFFER_INN}\nФИО: {OFFER_FULL_NAME}"
        bot.send_message(user_id, text, disable_web_page_preview=False)

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
    duration = course.get("duration_days", 0)
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
    text = f"{formatted_name}\n{clean_desc}\n\nЦена: {price} руб.\nДоступ: {duration} дн."
    ikb = types.InlineKeyboardMarkup()
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

# (Robokassa handler removed)

@bot.pre_checkout_query_handler(func=lambda q: True)
def handle_pre_checkout(q: telebot.types.PreCheckoutQuery):
    try:
        user_id = q.from_user.id
        payload = q.invoice_payload
        # Payload format: "user_id:course_id" (YooKassa) or "user_id:course_id:invoice_id" (Robokassa)
        parts = payload.split(":", 2)
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
    # Payload format: "user_id:course_id" (YooKassa) or "user_id:course_id:invoice_id" (Robokassa)
    parts = payload.split(":", 2)
    if len(parts) < 2:
        bot.send_message(user_id, "Ошибка: неверный формат заказа. Обратитесь в поддержку.")
        return
    # Extract course_id (second part), ignore user_id (first part) and invoice_id (third part if present)
    course_id = parts[1]

    try:
        courses = get_courses_data()
    except Exception:
        courses = []
    course = next((x for x in courses if str(x.get("id")) == str(course_id)), None)
    course_name = course.get("name", f"ID {course_id}") if course else f"ID {course_id}"
    duration = int(course.get("duration_days", 0)) if course else 0
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
    try:
        bot.ban_chat_member(chat_id=channel_id, user_id=user_id)
        bot.unban_chat_member(chat_id=channel_id, user_id=user_id)
        return True
    except Exception as e:
        print(f"Failed to remove {user_id} from {channel_id}: {e}")
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
