# bot_factory.py
"""
Factory for creating and configuring bot instances for multi-bot support.
"""
import telebot
from telebot import types
from config import get_bot_config, get_available_bots
from bot_context import set_bot_context, get_bot_context

# Dictionary to store bot instances: {bot_name: TeleBot instance}
_bots = {}

def create_bot_instance(bot_name: str) -> telebot.TeleBot:
    """
    Create and configure a bot instance for a specific bot name.
    Registers all handlers for this bot.
    """
    if bot_name in _bots:
        return _bots[bot_name]
    
    # Get configuration for this bot
    config = get_bot_config(bot_name)
    
    # Create bot instance
    bot = telebot.TeleBot(config['TELEGRAM_BOT_TOKEN'], parse_mode=None, threaded=False)
    
    # Register all handlers for this bot
    # We'll import and register handlers from main.py
    # But we need to do this carefully to avoid circular imports
    
    # Store bot instance
    _bots[bot_name] = bot
    
    return bot

def get_bot_instance(bot_name: str = None) -> telebot.TeleBot:
    """
    Get bot instance for a specific bot name.
    If bot_name is None, tries to get from context or uses default.
    """
    if bot_name is None:
        bot_name = get_bot_context()
        if bot_name is None:
            # Fallback to default
            from config import CURRENT_BOT_NAME
            bot_name = CURRENT_BOT_NAME
    
    if bot_name not in _bots:
        return create_bot_instance(bot_name)
    
    return _bots[bot_name]

def initialize_all_bots():
    """
    Initialize all available bots.
    This should be called at application startup.
    """
    bots = get_available_bots()
    for bot_name in bots:
        try:
            create_bot_instance(bot_name)
            print(f"Initialized bot: {bot_name}")
        except Exception as e:
            print(f"Failed to initialize bot {bot_name}: {e}")
    
    return _bots

def get_all_bots() -> dict:
    """Get all initialized bot instances"""
    return _bots.copy()

