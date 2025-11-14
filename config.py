# config.py
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
# This will automatically load .env from the project root directory
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

# Helper function to convert string "True"/"False" to boolean
def get_bool_env(key: str, default: bool = False) -> bool:
    """Get boolean from environment variable. Accepts 'true', 'True', 'TRUE', '1', etc."""
    value = os.getenv(key, str(default))
    return value.lower() in ("true", "1", "yes", "on")

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

# === PAYMENTS (Prodamus direct integration) ===
# Feature flag to show Prodamus buttons/flows in the bot UI
ENABLE_PRODAMUS = get_bool_env("ENABLE_PRODAMUS", True)
# Test mode flag (use test environment for development/testing)
# Set to "True" to use test environment, "False" for production
PRODAMUS_TEST_MODE = get_bool_env("PRODAMUS_TEST_MODE", True)
# Payment form URL (test or production)
# Test: testwork1.payform.ru
# Production: your production payform domain
PRODAMUS_PAYFORM_URL = os.getenv("PRODAMUS_PAYFORM_URL", "testwork1.payform.ru")
# Secret key for webhook verification (from Prodamus dashboard)
PRODAMUS_SECRET_KEY = os.getenv("PRODAMUS_SECRET_KEY", "")
# System ID (if required by Prodamus API)
PRODAMUS_SYSTEM_ID = os.getenv("PRODAMUS_SYSTEM_ID", "")
# Test webhook URL for debugging (e.g., webhook.site URL)
# If set, all webhook data will also be forwarded to this URL for testing
PRODAMUS_TEST_WEBHOOK_URL = os.getenv("PRODAMUS_TEST_WEBHOOK_URL", "")

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
GOOGLE_SHEETS_USE_API = get_bool_env("GOOGLE_SHEETS_USE_API", False)
GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "google_credentials.json")

# === Admins ===
# Comma-separated TELEGRAM user IDs. Example: "123,456"
admin_ids_str = os.getenv("ADMIN_IDS", "")
if not admin_ids_str:
    raise ValueError("ADMIN_IDS is required. Please set it in .env file (comma-separated user IDs)")
ADMIN_IDS = [int(x.strip()) for x in admin_ids_str.split(",") if x.strip()]

# === Webhook (PythonAnywhere) ===
USE_WEBHOOK = get_bool_env("USE_WEBHOOK", False)
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST", "")
WEBHOOK_SECRET_TOKEN = os.getenv("WEBHOOK_SECRET_TOKEN", "")
# Construct WEBHOOK_URL if not explicitly set
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")

# Process WEBHOOK_PATH: get from env, construct if needed, ensure it starts with "/"
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "")
if not WEBHOOK_URL and WEBHOOK_HOST and not WEBHOOK_HOST.startswith("<"):
    # If WEBHOOK_URL is not set but WEBHOOK_HOST is, construct WEBHOOK_PATH if needed
    if not WEBHOOK_PATH:
        WEBHOOK_PATH = f"/{TELEGRAM_BOT_TOKEN}"
    # Ensure WEBHOOK_PATH starts with "/"
    if WEBHOOK_PATH and not WEBHOOK_PATH.startswith("/"):
        WEBHOOK_PATH = "/" + WEBHOOK_PATH
    WEBHOOK_URL = f"https://{WEBHOOK_HOST.rstrip('/')}{WEBHOOK_PATH}"
else:
    # Even if WEBHOOK_URL is set or WEBHOOK_HOST is not set, ensure WEBHOOK_PATH starts with "/" if it exists
    if WEBHOOK_PATH and not WEBHOOK_PATH.startswith("/"):
        WEBHOOK_PATH = "/" + WEBHOOK_PATH
