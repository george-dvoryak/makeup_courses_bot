# remove_expired.py
from datetime import datetime
from db import get_expired_subscriptions, mark_subscription_expired
from main import remove_user_from_channel, bot

expired = get_expired_subscriptions()
if not expired:
    print(f"{datetime.now()}: No expired subscriptions.")
else:
    for rec in expired:
        user_id = rec["user_id"]
        course_id = rec["course_id"]
        course_name = rec["course_name"]
        channel_id = rec["channel_id"]

        ok = remove_user_from_channel(user_id, channel_id)
        if not ok:
            # Если кик не удался, проверим, не ушёл ли пользователь уже сам
            try:
                member = bot.get_chat_member(channel_id, user_id)
                status = getattr(member, "status", "")
                if status in ("left", "kicked"):
                    ok = True
            except Exception as e:
                # Если API говорит, что пользователя/чата нет — считаем удалённым
                msg = str(e).lower()
                if any(s in msg for s in ("user not found", "user is not a member", "chat not found")):
                    ok = True
        if ok:
            mark_subscription_expired(user_id, course_id)
            try:
                # Strip HTML from course name (bot uses parse_mode=None)
                from main import strip_html
                clean_course_name = strip_html(course_name) if course_name else "курсу"
                bot.send_message(user_id, f"Доступ к курсу {clean_course_name} завершен. Спасибо, что были с нами!")
            except Exception as e:
                print(f"Notify user {user_id} failed: {e}")
            print(f"{datetime.now()}: Removed user {user_id} from {channel_id} ({course_id}).")
        else:
            print(f"{datetime.now()}: Failed to remove user {user_id} from {channel_id}.")
