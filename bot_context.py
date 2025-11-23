# bot_context.py
"""
Context management for multi-bot support.
Allows functions to know which bot is currently processing a request.
"""
import threading

# Thread-local storage for bot context
_context = threading.local()

def set_bot_context(bot_name: str):
    """Set the current bot context for this thread"""
    _context.bot_name = bot_name

def get_bot_context() -> str:
    """Get the current bot context for this thread"""
    return getattr(_context, 'bot_name', None)

def clear_bot_context():
    """Clear the current bot context for this thread"""
    if hasattr(_context, 'bot_name'):
        delattr(_context, 'bot_name')

