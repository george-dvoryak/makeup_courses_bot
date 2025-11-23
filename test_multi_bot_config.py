#!/usr/bin/env python3
"""
Test script to verify multi-bot configuration.
Checks that all required variables are set for each bot.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

def get_available_bots():
    """Get list of available bots from environment"""
    bots_env = os.getenv("BOTS_LIST", "")
    if bots_env:
        return [b.strip() for b in bots_env.split(",") if b.strip()]
    
    # Auto-detect
    bots = []
    for key in os.environ:
        if key.startswith("TELEGRAM_BOT_TOKEN_"):
            bot_name = key.replace("TELEGRAM_BOT_TOKEN_", "")
            if bot_name and bot_name not in bots:
                bots.append(bot_name)
    
    # Check for default
    if not bots and os.getenv("TELEGRAM_BOT_TOKEN"):
        bots = ["default"]
    
    return bots

def check_bot_config(bot_name: str) -> dict:
    """Check configuration for a specific bot"""
    errors = []
    warnings = []
    
    def get_bot_env(key: str, required: bool = False):
        bot_key = f"{key}_{bot_name}"
        value = os.getenv(bot_key)
        if value is None:
            value = os.getenv(key)  # Fallback to default
        if required and not value:
            errors.append(f"Missing required: {bot_key} (or {key})")
        return value
    
    # Required variables
    token = get_bot_env("TELEGRAM_BOT_TOKEN", required=True)
    admin_ids = get_bot_env("ADMIN_IDS", required=True)
    gsheet_id = get_bot_env("GSHEET_ID", required=True)
    payment_token = get_bot_env("PAYMENT_PROVIDER_TOKEN", required=True)
    
    # Optional but recommended
    db_path = get_bot_env("DATABASE_PATH", required=False)
    if not db_path:
        db_path = f"{bot_name}.db"
        warnings.append(f"DATABASE_PATH_{bot_name} not set, will use default: {db_path}")
    
    webhook_path = get_bot_env("WEBHOOK_PATH", required=False)
    if not webhook_path:
        webhook_path = f"/webhook/{bot_name}"
        warnings.append(f"WEBHOOK_PATH_{bot_name} not set, will use default: {webhook_path}")
    
    # Prodamus (optional)
    enable_prodamus = get_bot_env("ENABLE_PRODAMUS", required=False)
    if enable_prodamus and enable_prodamus.lower() in ("true", "1", "yes"):
        prodamus_secret = get_bot_env("PRODAMUS_SECRET_KEY", required=False)
        if not prodamus_secret:
            warnings.append(f"ENABLE_PRODAMUS_{bot_name} is True but PRODAMUS_SECRET_KEY_{bot_name} is not set")
    
    return {
        "bot_name": bot_name,
        "errors": errors,
        "warnings": warnings,
        "config": {
            "token": "✅ Set" if token else "❌ Missing",
            "admin_ids": "✅ Set" if admin_ids else "❌ Missing",
            "gsheet_id": "✅ Set" if gsheet_id else "❌ Missing",
            "payment_token": "✅ Set" if payment_token else "❌ Missing",
            "db_path": db_path,
            "webhook_path": webhook_path,
        }
    }

def main():
    print("=" * 60)
    print("MULTI-BOT CONFIGURATION CHECK")
    print("=" * 60)
    print()
    
    bots = get_available_bots()
    
    if not bots:
        print("❌ No bots found!")
        print("\nTo add bots, either:")
        print("1. Set BOTS_LIST=bot1,bot2 in .env")
        print("2. Add TELEGRAM_BOT_TOKEN_bot1, TELEGRAM_BOT_TOKEN_bot2, etc.")
        print("3. Use default: set TELEGRAM_BOT_TOKEN (without prefix)")
        return
    
    print(f"Found {len(bots)} bot(s): {', '.join(bots)}")
    print()
    
    all_ok = True
    
    for bot_name in bots:
        print(f"{'=' * 60}")
        print(f"BOT: {bot_name}")
        print(f"{'=' * 60}")
        
        result = check_bot_config(bot_name)
        
        print(f"\nConfiguration:")
        for key, value in result["config"].items():
            print(f"  {key}: {value}")
        
        if result["errors"]:
            print(f"\n❌ ERRORS:")
            for error in result["errors"]:
                print(f"  • {error}")
            all_ok = False
        
        if result["warnings"]:
            print(f"\n⚠️  WARNINGS:")
            for warning in result["warnings"]:
                print(f"  • {warning}")
        
        if not result["errors"] and not result["warnings"]:
            print(f"\n✅ Configuration OK!")
        
        print()
    
    print("=" * 60)
    if all_ok:
        print("✅ ALL BOTS CONFIGURED CORRECTLY!")
    else:
        print("❌ SOME BOTS HAVE ERRORS - PLEASE FIX THEM")
    print("=" * 60)

if __name__ == "__main__":
    main()

