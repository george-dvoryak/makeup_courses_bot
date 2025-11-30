# config.py
import os
import json
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

# === MULTI-BOT SUPPORT ===
# Get bot name from environment or default to 'default'
# This allows running multiple bots in the same application
CURRENT_BOT_NAME = os.getenv("BOT_NAME", "default")


def _is_placeholder_token(token: str) -> bool:
    """Detect placeholder tokens like 'ваш_токен' or 'your_token', or empty values."""
    if not token:
        return True
    token_str = str(token).strip()
    if not token_str:
        return True
    lowered = token_str.lower()
    return "ваш" in lowered or "your" in lowered


def _build_minimal_config() -> dict:
    """Return a minimal safe config when no valid bot configuration is available."""
    return {
        'TELEGRAM_BOT_TOKEN': '',
        'ADMIN_IDS': [],
        'DATABASE_PATH': 'bot.db',
        'PAYMENT_PROVIDER_TOKEN': '',
        'CURRENCY': 'RUB',
        'ENABLE_PRODAMUS': False,
        'PRODAMUS_TEST_MODE': False,
        'PRODAMUS_PAYFORM_URL': '',
        'PRODAMUS_SECRET_KEY': '',
        'PRODAMUS_SYSTEM_ID': '',
        'PRODAMUS_TEST_WEBHOOK_URL': '',
        'USE_WEBHOOK': False,
        'WEBHOOK_HOST': '',
        'WEBHOOK_SECRET_TOKEN': '',
        'WEBHOOK_URL': '',
        'WEBHOOK_PATH': '',
        'GSHEET_ID': '',
        'GSHEET_COURSES_NAME': 'Courses',
        'GSHEET_TEXTS_NAME': 'Texts',
        'GOOGLE_SHEETS_USE_API': False,
        'GOOGLE_CREDENTIALS_FILE': 'google_credentials.json',
    }


# Dictionary to store bot configurations
_bot_configs = {}

def get_bot_config(bot_name: str = None) -> dict:
    """
    Get configuration for a specific bot.
    If bot_name is None, uses CURRENT_BOT_NAME.
    Configurations are cached after first load.
    """
    if bot_name is None:
        bot_name = CURRENT_BOT_NAME
    
    # Return cached config if available
    if bot_name in _bot_configs:
        return _bot_configs[bot_name]
    
    # Load configuration for this bot
    config = {}
    
    # Helper to get env var with bot-specific prefix
    def get_bot_env(key: str, default: str = None, required: bool = False):
        # Try bot-specific key first (e.g., TELEGRAM_BOT_TOKEN_bot1)
        bot_key = f"{key}_{bot_name}"
        value = os.getenv(bot_key)
        
        # If not found, try generic key (for backward compatibility)
        if value is None:
            value = os.getenv(key, default)
        
        if required and value is None:
            raise ValueError(f"{bot_key} or {key} is required. Please set it in .env file")
        
        return value
    
    def get_bot_bool_env(key: str, default: bool = False):
        bot_key = f"{key}_{bot_name}"
        value = os.getenv(bot_key)
        if value is None:
            value = os.getenv(key, str(default))
        return value.lower() in ("true", "1", "yes", "on")
    
    # === TELEGRAM ===
    config['TELEGRAM_BOT_TOKEN'] = get_bot_env("TELEGRAM_BOT_TOKEN", required=True)
    
    # === PAYMENTS (YooKassa via Telegram Payments) ===
    config['PAYMENT_PROVIDER_TOKEN'] = get_bot_env("PAYMENT_PROVIDER_TOKEN", required=True)
    config['CURRENCY'] = get_bot_env("CURRENCY", "RUB")
    
    # === PAYMENTS (Prodamus direct integration) ===
    config['ENABLE_PRODAMUS'] = get_bot_bool_env("ENABLE_PRODAMUS", True)
    config['PRODAMUS_TEST_MODE'] = get_bot_bool_env("PRODAMUS_TEST_MODE", True)
    config['PRODAMUS_PAYFORM_URL'] = get_bot_env("PRODAMUS_PAYFORM_URL", "testwork1.payform.ru")
    config['PRODAMUS_SECRET_KEY'] = get_bot_env("PRODAMUS_SECRET_KEY", "")
    config['PRODAMUS_SYSTEM_ID'] = get_bot_env("PRODAMUS_SYSTEM_ID", "")
    config['PRODAMUS_TEST_WEBHOOK_URL'] = get_bot_env("PRODAMUS_TEST_WEBHOOK_URL", "")
    
    # === SQLite DB ===
    # Default to bot_name.db if not specified
    config['DATABASE_PATH'] = get_bot_env("DATABASE_PATH", f"{bot_name}.db")
    
    # === Google Sheets (Admin panel) ===
    config['GSHEET_ID'] = get_bot_env("GSHEET_ID", required=True)
    config['GSHEET_COURSES_NAME'] = get_bot_env("GSHEET_COURSES_NAME", "Courses")
    config['GSHEET_TEXTS_NAME'] = get_bot_env("GSHEET_TEXTS_NAME", "Texts")
    config['GOOGLE_SHEETS_USE_API'] = get_bot_bool_env("GOOGLE_SHEETS_USE_API", False)
    config['GOOGLE_CREDENTIALS_FILE'] = get_bot_env("GOOGLE_CREDENTIALS_FILE", "google_credentials.json")
    
    # === Admins ===
    admin_ids_str = get_bot_env("ADMIN_IDS", required=True)
    # Validate and parse admin IDs, skip invalid values (like placeholders)
    admin_ids = []
    if admin_ids_str:
        for x in admin_ids_str.split(","):
            x = x.strip()
            if x:
                try:
                    admin_id = int(x)
                    admin_ids.append(admin_id)
                except ValueError:
                    # Skip invalid values (placeholders like "ваш_telegram_id")
                    continue
    config['ADMIN_IDS'] = admin_ids
    
    # === Webhook (PythonAnywhere) ===
    config['USE_WEBHOOK'] = get_bot_bool_env("USE_WEBHOOK", False)
    config['WEBHOOK_HOST'] = get_bot_env("WEBHOOK_HOST", "")
    config['WEBHOOK_SECRET_TOKEN'] = get_bot_env("WEBHOOK_SECRET_TOKEN", "")
    config['WEBHOOK_URL'] = get_bot_env("WEBHOOK_URL", "")
    config['WEBHOOK_PATH'] = get_bot_env("WEBHOOK_PATH", "")
    
    # Process WEBHOOK_PATH: construct if needed
    if not config['WEBHOOK_URL'] and config['WEBHOOK_HOST'] and not config['WEBHOOK_HOST'].startswith("<"):
        if not config['WEBHOOK_PATH']:
            # Default webhook path: /webhook/{bot_name}
            config['WEBHOOK_PATH'] = f"/webhook/{bot_name}"
        # Ensure WEBHOOK_PATH starts with "/"
        if config['WEBHOOK_PATH'] and not config['WEBHOOK_PATH'].startswith("/"):
            config['WEBHOOK_PATH'] = "/" + config['WEBHOOK_PATH']
        config['WEBHOOK_URL'] = f"https://{config['WEBHOOK_HOST'].rstrip('/')}{config['WEBHOOK_PATH']}"
    else:
        # Ensure WEBHOOK_PATH starts with "/" if it exists
        if config['WEBHOOK_PATH'] and not config['WEBHOOK_PATH'].startswith("/"):
            config['WEBHOOK_PATH'] = "/" + config['WEBHOOK_PATH']
    
    # Cache configuration
    _bot_configs[bot_name] = config
    
    return config

def get_available_bots() -> list:
    """
    Get list of available bot names from environment variables.
    Looks for TELEGRAM_BOT_TOKEN_{bot_name} patterns.
    """
    bots = []
    # Check for explicitly listed bots
    bots_env = os.getenv("BOTS_LIST", "")
    if bots_env:
        bots = [b.strip() for b in bots_env.split(",") if b.strip()]
    else:
        # Auto-detect bots from environment variables
        # Look for TELEGRAM_BOT_TOKEN_{bot_name} patterns
        for key in os.environ:
            if key.startswith("TELEGRAM_BOT_TOKEN_"):
                bot_name = key.replace("TELEGRAM_BOT_TOKEN_", "")
                if bot_name and bot_name not in bots:
                    bots.append(bot_name)
        
        # If no bot-specific tokens found, check for default
        if not bots and os.getenv("TELEGRAM_BOT_TOKEN"):
            bots = ["default"]
    
    return bots

# Get configuration for current bot (for backward compatibility)
# Try to load default bot, fallback to first available bot if default doesn't exist or has invalid config
def _resolve_current_config() -> dict:
    """Load the primary configuration, avoiding placeholder tokens."""
    try:
        config = get_bot_config(CURRENT_BOT_NAME)
        if _is_placeholder_token(config.get('TELEGRAM_BOT_TOKEN')):
            raise ValueError("Default bot has placeholder values")
        return config
    except (ValueError, KeyError):
        valid_config = None
        for bot_name in get_available_bots():
            try:
                candidate = get_bot_config(bot_name)
            except Exception:
                continue
            if _is_placeholder_token(candidate.get('TELEGRAM_BOT_TOKEN')):
                continue
            valid_config = candidate
            break
        if valid_config:
            return valid_config
        return _build_minimal_config()


_current_config = _resolve_current_config()

# Export current bot configuration as module-level variables (for backward compatibility)
TELEGRAM_BOT_TOKEN = _current_config['TELEGRAM_BOT_TOKEN']
PAYMENT_PROVIDER_TOKEN = _current_config['PAYMENT_PROVIDER_TOKEN']
CURRENCY = _current_config['CURRENCY']
ENABLE_PRODAMUS = _current_config['ENABLE_PRODAMUS']
PRODAMUS_TEST_MODE = _current_config['PRODAMUS_TEST_MODE']
PRODAMUS_PAYFORM_URL = _current_config['PRODAMUS_PAYFORM_URL']
PRODAMUS_SECRET_KEY = _current_config['PRODAMUS_SECRET_KEY']
PRODAMUS_SYSTEM_ID = _current_config['PRODAMUS_SYSTEM_ID']
PRODAMUS_TEST_WEBHOOK_URL = _current_config['PRODAMUS_TEST_WEBHOOK_URL']
DATABASE_PATH = _current_config['DATABASE_PATH']
GSHEET_ID = _current_config['GSHEET_ID']
GSHEET_COURSES_NAME = _current_config['GSHEET_COURSES_NAME']
GSHEET_TEXTS_NAME = _current_config['GSHEET_TEXTS_NAME']
GOOGLE_SHEETS_USE_API = _current_config['GOOGLE_SHEETS_USE_API']
GOOGLE_CREDENTIALS_FILE = _current_config['GOOGLE_CREDENTIALS_FILE']
ADMIN_IDS = _current_config['ADMIN_IDS']
USE_WEBHOOK = _current_config['USE_WEBHOOK']
WEBHOOK_HOST = _current_config['WEBHOOK_HOST']
WEBHOOK_SECRET_TOKEN = _current_config['WEBHOOK_SECRET_TOKEN']
WEBHOOK_URL = _current_config['WEBHOOK_URL']
WEBHOOK_PATH = _current_config['WEBHOOK_PATH']
