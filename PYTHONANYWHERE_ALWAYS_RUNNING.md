# Keeping Your Bot Always Running on PythonAnywhere

## How the Bot Starts

Your bot runs as a **Flask web app** (`webhook_app.py`), which:
- ✅ Starts automatically when the web app loads
- ✅ Sets up Telegram webhook on startup
- ✅ Starts background cleanup scheduler (runs every hour)
- ✅ Handles webhook requests from Telegram

## Automatic Restart Methods

### Method 1: Web App (Recommended - Already Set Up!)

**How it works:**
- The web app automatically restarts when you click **Reload** in the Web tab
- On **free tier**: Web app goes to sleep after inactivity but wakes up automatically when Telegram sends a webhook
- On **paid tier**: Web app stays active 24/7

**To ensure it stays running:**

1. **Free Tier**:
   - Web app wakes up automatically when Telegram sends webhooks
   - No action needed - Telegram will wake it up when users interact
   - ⚠️ First request after sleep may take 5-10 seconds

2. **Paid Tier**:
   - Web app stays active 24/7 automatically
   - No sleep/wake delays

**To manually restart:**
- Go to **Web** tab → Click **Reload** button
- Check **Error log** to verify startup messages

### Method 2: Always-On Task (For Background Processes)

If you need a separate process that runs continuously (e.g., polling mode instead of webhooks):

1. Go to **Tasks** tab in PythonAnywhere
2. Click **Create a new always-on task**
3. Enter:
   ```
   Command: python3.10 /home/<your-username>/makeup_courses_bot/main.py
   ```
4. Click **Create**

**Note**: This is only needed if you want to run in polling mode. With webhooks (recommended), the web app handles everything.

## Current Setup (Webhook Mode - Recommended)

Your bot is configured to use **webhooks**, which means:

✅ **Web app handles everything:**
- Receives updates from Telegram via webhook
- Automatically restarts when web app reloads
- Background cleanup runs in the same process

✅ **No always-on task needed** - web app is sufficient!

## Monitoring and Health Checks

### Check if Bot is Running

1. **Check Error Log**:
   - Go to **Web** tab → **Error log**
   - Look for:
     ```
     Webhook set to: https://yourusername.pythonanywhere.com/webhook
     [Auto-Cleanup] Background cleanup scheduler started
     ```

2. **Test Bot**:
   - Send `/start` command to your bot in Telegram
   - If it responds, bot is running ✅

3. **Check Web App Status**:
   - Go to **Web** tab
   - Status should show: **Running** (green)

### Automatic Health Check (Optional)

You can add a simple health check endpoint to verify the bot is running:

```python
# Add to webhook_app.py
@app.route('/health')
def health():
    return "OK", 200
```

Then set up a monitoring service (like UptimeRobot) to ping:
```
https://yourusername.pythonanywhere.com/health
```

## Troubleshooting

### Bot Not Responding

1. **Check Error Log**:
   - Go to **Web** tab → **Error log**
   - Look for errors or import failures

2. **Reload Web App**:
   - Go to **Web** tab → Click **Reload**
   - Check Error log again

3. **Verify .env File**:
   - Make sure all required variables are set
   - Check that `TELEGRAM_BOT_TOKEN` is correct

4. **Check Dependencies**:
   ```bash
   pip list | grep -E "telebot|flask|requests"
   ```

### Web App Keeps Crashing

1. **Check Error Log** for specific errors
2. **Common issues**:
   - Missing dependencies: `pip install --user -r requirements.txt`
   - Wrong Python version: Use Python 3.10
   - Import errors: Check WSGI file path is correct
   - Database permissions: Check `DATABASE_PATH` is writable

### Background Cleanup Not Running

1. **Check Error Log** for `[Auto-Cleanup]` messages
2. **Verify scheduler started**:
   - Should see: `[Auto-Cleanup] Background cleanup scheduler started`
3. **Manual test**:
   - Send `/cleanup_expired` command (admin only)
   - Should see cleanup statistics

## Restart Strategies

### Manual Restart
- **Web** tab → **Reload** button

### Automatic Restart on Code Update
If you update code via Git:
```bash
cd ~/makeup_courses_bot
git pull
# Then reload web app manually
```

### Scheduled Restart (Paid Tier Only)
You can create a scheduled task to reload the web app:
1. Go to **Tasks** tab
2. Create scheduled task:
   - Command: `touch /var/www/yourusername_pythonanywhere_com_wsgi.py`
   - This triggers a reload
   - Schedule: Daily at 3 AM (or your preference)

**Note**: Usually not needed - web app handles restarts automatically.

## Best Practices

1. ✅ **Use Webhook Mode** (current setup) - most reliable
2. ✅ **Monitor Error Log** regularly
3. ✅ **Keep dependencies updated**: `pip install --user --upgrade -r requirements.txt`
4. ✅ **Test after updates**: Send `/start` command
5. ✅ **Backup database** periodically (if using SQLite)

## Summary

**Your bot is already set up to run automatically!**

- ✅ Starts when web app loads
- ✅ Restarts when you reload web app
- ✅ Wakes up automatically on free tier when Telegram sends webhooks
- ✅ Stays active 24/7 on paid tier
- ✅ Background cleanup runs automatically

**No always-on task needed** - the web app handles everything!

Just make sure:
1. Web app is created and configured ✅
2. WSGI file points to `webhook_app.py` ✅
3. `.env` file has all required variables ✅
4. Dependencies are installed ✅

Then click **Reload** and you're done! 🚀

