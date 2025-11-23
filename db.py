# db.py
import sqlite3
import time

from config import DATABASE_PATH, get_bot_config
from bot_context import get_bot_context

# Dictionary to store connections per bot
_connections = {}

def get_connection(bot_name: str = None, database_path: str = None):
    """
    Get database connection for a specific bot.
    If bot_name is provided, uses configuration for that bot.
    If database_path is provided, uses that path directly.
    Otherwise, tries to get bot_name from context, or uses current bot configuration.
    """
    # Determine which database to use
    if database_path:
        db_path = database_path
        cache_key = db_path
    elif bot_name:
        config = get_bot_config(bot_name)
        db_path = config['DATABASE_PATH']
        cache_key = bot_name
    else:
        # Try to get bot_name from context
        context_bot_name = get_bot_context()
        if context_bot_name:
            config = get_bot_config(context_bot_name)
            db_path = config['DATABASE_PATH']
            cache_key = context_bot_name
        else:
            # Fallback to default
            db_path = DATABASE_PATH
            cache_key = 'default'
    
    # Return cached connection if available
    if cache_key in _connections:
        return _connections[cache_key]
    
    # Create new connection
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    
    # Cache connection
    _connections[cache_key] = conn
    
    return conn

def init_db(conn):
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            course_id TEXT,
            course_name TEXT,
            channel_id TEXT,
            expiry INTEGER,    -- UNIX timestamp (UTC)
            payment_id TEXT,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
        """
    )
    conn.commit()

def add_user(user_id: int, username: str = None):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO users (user_id, username) VALUES (?, ?);", (user_id, username))
    except sqlite3.IntegrityError:
        cur.execute("UPDATE users SET username = ? WHERE user_id = ?;", (username, user_id))
    conn.commit()

def get_user(user_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE user_id = ?;", (user_id,))
    return cur.fetchone()

def add_purchase(user_id: int, course_id: str, course_name: str, channel_id: str, duration_days: int = None, payment_id: str = None):
    """
    Add a purchase. If duration_days is None or 0, subscription is unlimited (expiry = 0).
    duration_days: number of days, or None/0 for unlimited access
    """
    conn = get_connection()
    cur = conn.cursor()
    now = int(time.time())
    # If duration_days is None, 0, or empty, set expiry to 0 (unlimited access)
    if duration_days is None or duration_days == 0:
        expiry_ts = 0  # 0 means unlimited access
    else:
        expiry_ts = now + int(duration_days) * 24 * 60 * 60  # Convert days to seconds
    cur.execute(
        """
        INSERT INTO purchases (user_id, course_id, course_name, channel_id, expiry, payment_id)
        VALUES (?, ?, ?, ?, ?, ?);
        """,
        (user_id, course_id, course_name, channel_id, expiry_ts, payment_id)
    )
    conn.commit()
    return expiry_ts

def get_active_subscriptions(user_id: int):
    """
    Get active subscriptions. expiry = 0 means unlimited access (always active).
    """
    conn = get_connection()
    cur = conn.cursor()
    now = int(time.time())
    cur.execute(
        """
        SELECT course_name, channel_id, expiry FROM purchases
        WHERE user_id = ? AND (expiry = 0 OR expiry > ?);
        """,
        (user_id, now)
    )
    return cur.fetchall()

def has_active_subscription(user_id: int, course_id: str):
    """
    Check if user has active subscription. expiry = 0 means unlimited access (always active).
    """
    conn = get_connection()
    cur = conn.cursor()
    now = int(time.time())
    cur.execute(
        """
        SELECT 1 FROM purchases WHERE user_id = ? AND course_id = ? AND (expiry = 0 OR expiry > ?);
        """,
        (user_id, course_id, now)
    )
    return cur.fetchone() is not None

def mark_subscription_expired(user_id: int, course_id: str):
    """
    Mark subscription as expired by setting expiry to 0 (processed flag).
    Using 0 instead of current time to distinguish processed from unprocessed expired subscriptions.
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE purchases SET expiry = 0
        WHERE user_id = ? AND course_id = ?;
        """,
        (user_id, course_id)
    )
    conn.commit()

def get_expired_subscriptions():
    """
    Get subscriptions that have expired but haven't been processed yet.
    Only returns subscriptions where expiry > 0 (not yet marked as processed).
    Excludes unlimited subscriptions (expiry = 0).
    """
    conn = get_connection()
    cur = conn.cursor()
    now = int(time.time())
    cur.execute(
        """
        SELECT user_id, course_id, course_name, channel_id, expiry
        FROM purchases
        WHERE expiry > 0 AND expiry <= ?
        ORDER BY expiry ASC;
        """,
        (now,)
    )
    return cur.fetchall()

def get_all_active_subscriptions():
    """
    Get all active subscriptions for all users (admin function).
    Includes unlimited subscriptions (expiry = 0).
    """
    conn = get_connection()
    cur = conn.cursor()
    now = int(time.time())
    cur.execute(
        """
        SELECT user_id, course_id, course_name, channel_id, expiry
        FROM purchases
        WHERE expiry = 0 OR expiry > ?
        ORDER BY expiry DESC;
        """,
        (now,)
    )
    return cur.fetchall()

def clear_all_data():
    """
    Clear all data from database tables.
    WARNING: This will delete ALL users, purchases, and pending payments!
    Returns statistics about what was deleted.
    """
    conn = get_connection()
    cur = conn.cursor()
    
    # Get statistics before deletion
    stats = {}
    
    # Count users
    cur.execute("SELECT COUNT(*) FROM users")
    stats['users'] = cur.fetchone()[0]
    
    # Count purchases
    cur.execute("SELECT COUNT(*) FROM purchases")
    stats['purchases'] = cur.fetchone()[0]
    
    # Count pending payments (table might not exist)
    try:
        cur.execute("SELECT COUNT(*) FROM pending_payments")
        stats['pending_payments'] = cur.fetchone()[0]
    except sqlite3.OperationalError:
        stats['pending_payments'] = 0
    
    # Delete all data
    cur.execute("DELETE FROM purchases")
    cur.execute("DELETE FROM users")
    
    # Delete pending_payments if table exists
    try:
        cur.execute("DELETE FROM pending_payments")
    except sqlite3.OperationalError:
        pass  # Table doesn't exist, ignore
    
    conn.commit()
    
    return stats
