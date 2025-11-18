# remove_expired.py
import sys
import traceback
from datetime import datetime
import time

def format_timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Log to stderr so it appears even if stdout is redirected
def log(message):
    print(message, file=sys.stderr)
    print(message)  # Also print to stdout

log(f"[{format_timestamp()}] ========== Starting expired subscriptions cleanup ==========")

try:
    log(f"[{format_timestamp()}] Importing modules...")
    from db import get_expired_subscriptions, mark_subscription_expired, get_connection
    log(f"[{format_timestamp()}] Database module imported successfully")
    
    from main import remove_user_from_channel, bot
    log(f"[{format_timestamp()}] Main module imported successfully")
    
    # Diagnostic: Check database state
    log(f"[{format_timestamp()}] Running diagnostics...")
    conn = get_connection()
    cur = conn.cursor()
    now = int(time.time())
    
    # Check total subscriptions
    cur.execute("SELECT COUNT(*) FROM purchases")
    total_count = cur.fetchone()[0]
    log(f"[{format_timestamp()}] Total subscriptions in database: {total_count}")
    
    # Check active subscriptions
    cur.execute("SELECT COUNT(*) FROM purchases WHERE expiry > ?", (now,))
    active_count = cur.fetchone()[0]
    log(f"[{format_timestamp()}] Active subscriptions (expiry > {now}): {active_count}")
    
    # Check expired but unprocessed subscriptions
    cur.execute("SELECT COUNT(*) FROM purchases WHERE expiry > 0 AND expiry <= ?", (now,))
    expired_unprocessed = cur.fetchone()[0]
    log(f"[{format_timestamp()}] Expired but unprocessed subscriptions: {expired_unprocessed}")
    
    # Check processed subscriptions (expiry = 0)
    cur.execute("SELECT COUNT(*) FROM purchases WHERE expiry = 0")
    processed_count = cur.fetchone()[0]
    log(f"[{format_timestamp()}] Already processed subscriptions (expiry = 0): {processed_count}")
    
    # Show some example expiry times for debugging
    cur.execute("SELECT user_id, course_id, expiry FROM purchases WHERE expiry > 0 ORDER BY expiry LIMIT 5")
    examples = cur.fetchall()
    if examples:
        log(f"[{format_timestamp()}] Sample subscriptions (next 5):")
        for ex in examples:
            expiry_dt = datetime.fromtimestamp(ex["expiry"])
            is_expired = "EXPIRED" if ex["expiry"] <= now else "ACTIVE"
            log(f"  - User {ex['user_id']}, Course {ex['course_id']}, Expiry: {ex['expiry']} ({expiry_dt}), Status: {is_expired}")
    
    log(f"[{format_timestamp()}] Diagnostics completed")
    
except Exception as e:
    log(f"[{format_timestamp()}] ❌ CRITICAL ERROR during import or diagnostics: {e}")
    log(f"[{format_timestamp()}] Traceback: {traceback.format_exc()}")
    sys.exit(1)

try:
    log(f"[{format_timestamp()}] Fetching expired subscriptions...")
    expired = get_expired_subscriptions()
    log(f"[{format_timestamp()}] Query completed, found {len(expired) if expired else 0} expired subscriptions")
    if not expired:
        log(f"[{format_timestamp()}] No expired subscriptions found.")
    else:
        log(f"[{format_timestamp()}] Found {len(expired)} expired subscription(s) to process.")
        
        for idx, rec in enumerate(expired, 1):
            try:
                user_id = rec["user_id"]
                course_id = rec["course_id"]
                course_name = rec["course_name"]
                channel_id = rec["channel_id"]
                
                log(f"\n[{format_timestamp()}] [{idx}/{len(expired)}] Processing subscription:")
                log(f"  - User ID: {user_id}")
                log(f"  - Course ID: {course_id}")
                log(f"  - Course Name: {course_name}")
                log(f"  - Channel ID: {channel_id}")

                if not channel_id:
                    log(f"[{format_timestamp()}] ⚠️ Skipping user {user_id} - course {course_id} has no channel_id")
                    # Mark as expired even if no channel (subscription expired anyway)
                    mark_subscription_expired(user_id, course_id)
                    log(f"[{format_timestamp()}] Marked subscription as expired (no channel)")
                    continue

                log(f"[{format_timestamp()}] Attempting to remove user {user_id} from channel {channel_id}...")
                removal_start = time.time()
                
                ok = remove_user_from_channel(user_id, channel_id)
                
                removal_duration = time.time() - removal_start
                log(f"[{format_timestamp()}] Removal attempt completed in {removal_duration:.2f} seconds. Result: {'SUCCESS' if ok else 'FAILED'}")
                
                if not ok:
                    # Если кик не удался, проверим, не ушёл ли пользователь уже сам
                    log(f"[{format_timestamp()}] Ban/unban returned False, double-checking user status...")
                    try:
                        member = bot.get_chat_member(channel_id, user_id)
                        status = getattr(member, "status", "unknown")
                        log(f"[{format_timestamp()}] User {user_id} current status in channel {channel_id}: {status}")
                        if status in ("left", "kicked"):
                            ok = True
                            log(f"[{format_timestamp()}] ✅ User {user_id} already left/kicked from {channel_id}, considering removal successful")
                        else:
                            log(f"[{format_timestamp()}] ⚠️ User {user_id} still has status '{status}' in channel")
                    except Exception as e:
                        # Если API говорит, что пользователя/чата нет — считаем удалённым
                        msg = str(e).lower()
                        log(f"[{format_timestamp()}] get_chat_member error: {e}")
                        if any(s in msg for s in ("user not found", "user is not a member", "chat not found", "not enough rights", "can't get chat member")):
                            ok = True
                            log(f"[{format_timestamp()}] ✅ User {user_id} considered removed (API error indicates removal)")
                        else:
                            log(f"[{format_timestamp()}] ⚠️ Unexpected error checking membership: {e}")
                
                if ok:
                    log(f"[{format_timestamp()}] Marking subscription as expired in database...")
                    mark_subscription_expired(user_id, course_id)
                    log(f"[{format_timestamp()}] Subscription marked as expired")
                    
                    try:
                        # Strip HTML from course name (bot uses parse_mode=None)
                        from main import strip_html
                        clean_course_name = strip_html(course_name) if course_name else "курсу"
                        log(f"[{format_timestamp()}] Sending notification message to user {user_id}...")
                        bot.send_message(user_id, f"Доступ к курсу {clean_course_name} завершен. Спасибо, что были с нами!")
                        log(f"[{format_timestamp()}] ✅ Notification sent successfully")
                    except Exception as e:
                        log(f"[{format_timestamp()}] ⚠️ Failed to notify user {user_id}: {e}")
                        log(f"[{format_timestamp()}] Error details: {traceback.format_exc()}")
                    
                    log(f"[{format_timestamp()}] ✅ Successfully processed expired subscription: user {user_id}, course {course_id}, channel {channel_id}")
                else:
                    # Even if removal failed, mark as expired to prevent infinite retries
                    # But log the error for manual investigation
                    log(f"[{format_timestamp()}] ⚠️ Failed to remove user {user_id} from {channel_id}, but marking as expired to prevent retries")
                    mark_subscription_expired(user_id, course_id)
                    log(f"[{format_timestamp()}] Subscription marked as expired despite removal failure")
                    
            except Exception as e:
                log(f"[{format_timestamp()}] ❌ ERROR processing subscription {idx}: {e}")
                log(f"[{format_timestamp()}] Traceback: {traceback.format_exc()}")
                # Continue with next subscription
                continue

except Exception as e:
    log(f"[{format_timestamp()}] ❌ CRITICAL ERROR during processing: {e}")
    log(f"[{format_timestamp()}] Traceback: {traceback.format_exc()}")
    sys.exit(1)

log(f"\n[{format_timestamp()}] ========== Expired subscriptions cleanup completed ==========")
