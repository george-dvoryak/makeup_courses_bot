# config.py
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
# This will automatically load .env from the project root directory
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

# === TELEGRAM ===
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN is required. Please set it in .env file")

# === PAYMENTS (YooKassa via Telegram Payments) ===
# Use BotFather-provided provider token linked to YooKassa shop.
PAYMENT_PROVIDER_TOKEN = os.getenv("PAYMENT_PROVIDER_TOKEN")
if not PAYMENT_PROVIDER_TOKEN:
    raise ValueError("PAYMENT_PROVIDER_TOKEN is required. Please set it in .env file")
CURRENCY = os.getenv("CURRENCY", "RUB")

# === PAYMENTS (Robokassa via Telegram Payments) ===
# Feature flag to show Robokassa buttons/flows in the bot UI
ENABLE_ROBOKASSA = os.getenv("ENABLE_ROBOKASSA", "False").lower() == "true"
# BotFather provider token for Robokassa
# For TEST environment: Get test token from BotFather after connecting Robokassa test shop
# For PRODUCTION: Get production token from BotFather after connecting Robokassa production shop
# Format: "MerchantLogin:TEST:Password" (test) or "MerchantLogin:LIVE:Password" (production)
ROBOKASSA_PROVIDER_TOKEN = os.getenv("ROBOKASSA_PROVIDER_TOKEN", "")
# Test mode flag (use test environment for development/testing)
# Set to "True" to use test environment, "False" for production
RBK_TEST_MODE = os.getenv("RBK_TEST_MODE", "True").lower() == "true"
# Receipt defaults tuned for self-employed (НПД). Adjust if ваш кейс требует иного:
#   sno: one of ["osn","usn_income","usn_income_outcome","envd","esn","patent"]
#   tax: 'none' for НПД (без НДС), or 'vat0', 'vat10', 'vat20', 'vat110', 'vat120'
#   payment_object: typically 'service' for онлайн-курсов
#   payment_method: usually 'full_payment'
RBK_SNO = os.getenv("RBK_SNO", "usn_income")
RBK_TAX = os.getenv("RBK_TAX", "none")
RBK_PAYMENT_OBJECT = os.getenv("RBK_PAYMENT_OBJECT", "service")
RBK_PAYMENT_METHOD = os.getenv("RBK_PAYMENT_METHOD", "full_payment")

# === SQLite DB ===
DATABASE_PATH = os.getenv("DATABASE_PATH", "bot.db")

# === Google Sheets (Admin panel) ===
# Put your Google Sheet ID (from its URL). We'll fetch CSV exports for simplicity.
GSHEET_ID = os.getenv("GSHEET_ID")
if not GSHEET_ID:
    raise ValueError("GSHEET_ID is required. Please set it in .env file")
GSHEET_COURSES_NAME = os.getenv("GSHEET_COURSES_NAME", "Courses")
GSHEET_TEXTS_NAME = os.getenv("GSHEET_TEXTS_NAME", "Texts")

# Set to True if you want to use Google API via service account (gspread). Otherwise we use CSV export.
GOOGLE_SHEETS_USE_API = os.getenv("GOOGLE_SHEETS_USE_API", "False").lower() == "true"
GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "google_credentials.json")

# === Admins ===
# Comma-separated TELEGRAM user IDs. Example: "123,456"
admin_ids_str = os.getenv("ADMIN_IDS", "")
if not admin_ids_str:
    raise ValueError("ADMIN_IDS is required. Please set it in .env file (comma-separated user IDs)")
ADMIN_IDS = [int(x.strip()) for x in admin_ids_str.split(",") if x.strip()]

# === Webhook (PythonAnywhere) ===
USE_WEBHOOK = os.getenv("USE_WEBHOOK", "False").lower() == "true"
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST", "")
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "")
WEBHOOK_SECRET_TOKEN = os.getenv("WEBHOOK_SECRET_TOKEN", "")
# Construct WEBHOOK_URL if not explicitly set
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
if not WEBHOOK_URL and WEBHOOK_HOST and not WEBHOOK_HOST.startswith("<"):
    if not WEBHOOK_PATH:
        WEBHOOK_PATH = f"/{TELEGRAM_BOT_TOKEN}"
    WEBHOOK_URL = f"https://{WEBHOOK_HOST.rstrip('/')}{WEBHOOK_PATH}"
