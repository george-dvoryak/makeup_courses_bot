# Webhook Troubleshooting Guide

## Problem: Bot Not Responding on PythonAnywhere

If your bot isn't responding when running as a webhook app, follow these steps:

## Step 1: Don't Run main.py Directly!

**❌ WRONG:**
```bash
python3.10 main.py
```

**✅ CORRECT:** The webhook app runs automatically via WSGI when you reload the web app.

## Step 2: Check Your .env File on PythonAnywhere

Your `.env` file on PythonAnywhere MUST have these settings:

```env
USE_WEBHOOK=True
WEBHOOK_HOST=goshadvoryak.pythonanywhere.com
WEBHOOK_PATH=/webhook
WEBHOOK_SECRET_TOKEN=your_secret_token_here
```

**Important:** Replace `goshadvoryak` with your actual PythonAnywhere username!

## Step 3: Verify WSGI Configuration

1. Go to **Web** tab in PythonAnywhere
2. Click on **WSGI configuration file** link
3. Make sure it contains:

```python
import sys

path = '/home/goshadvoryak/makeup_courses_bot'  # Replace with your username!
if path not in sys.path:
    sys.path.insert(0, path)

from webhook_app import app as application
```

## Step 4: Reload Web App

1. Go to **Web** tab
2. Click the green **Reload** button
3. Wait a few seconds

## Step 5: Check Error Log

1. Go to **Web** tab → **Error log**
2. Look for these messages:

**✅ SUCCESS messages:**
```
Webhook set to: https://goshadvoryak.pythonanywhere.com/webhook
[Auto-Cleanup] Background cleanup scheduler started (runs every hour + on startup)
```

**❌ ERROR messages to watch for:**
- `No module named 'webhook_app'` → Check WSGI file path
- `No module named 'config'` → Check dependencies installed
- `TELEGRAM_BOT_TOKEN is required` → Check .env file
- `Failed to set webhook` → Check bot token and internet connection

## Step 6: Test Webhook Status

Run the diagnostic script on PythonAnywhere:

```bash
cd ~/makeup_courses_bot
python3.10 check_webhook.py
```

This will show:
- Current webhook configuration
- Telegram webhook status
- Any errors

## Step 7: Test Bot

Send `/start` command to your bot in Telegram. If it responds, everything is working!

## Common Issues

### Issue: "Webhook mode enabled. Run webhook_app.py (WSGI) on your server."

**Solution:** This message appears when you run `main.py` directly. Don't run `main.py` - the web app handles it automatically via WSGI.

### Issue: Bot not responding to messages

**Check:**
1. Error log for webhook errors
2. Webhook URL matches your PythonAnywhere domain
3. WEBHOOK_SECRET_TOKEN matches (if configured)
4. Web app is reloaded

### Issue: "No module named 'webhook_app'"

**Solution:**
1. Check WSGI file path is correct
2. Verify `webhook_app.py` exists in project directory
3. Check Python version matches (3.10)

### Issue: Webhook URL mismatch

**Solution:**
1. Check `.env` file has correct `WEBHOOK_HOST`
2. Reload web app to set webhook again
3. Verify webhook path matches: `/webhook` or `/{BOT_TOKEN}`

## Quick Checklist

- [ ] `.env` file has `USE_WEBHOOK=True`
- [ ] `.env` file has correct `WEBHOOK_HOST` (your PythonAnywhere domain)
- [ ] `.env` file has `WEBHOOK_PATH=/webhook`
- [ ] WSGI file imports `from webhook_app import app as application`
- [ ] WSGI file path is correct (has your username)
- [ ] Web app is reloaded
- [ ] Error log shows "Webhook set to: ..."
- [ ] Bot responds to `/start` command

## Still Not Working?

1. **Check Error Log** for specific error messages
2. **Run diagnostic:** `python3.10 check_webhook.py`
3. **Verify webhook manually:**
   ```bash
   curl https://api.telegram.org/bot<YOUR_TOKEN>/getWebhookInfo
   ```
4. **Test webhook endpoint:**
   ```bash
   curl https://goshadvoryak.pythonanywhere.com/webhook
   ```
   Should return "OK" or 405 Method Not Allowed (POST only)

## Need Help?

Check these files:
- `PYTHONANYWHERE_DEPLOYMENT.md` - Full deployment guide
- `PYTHONANYWHERE_WSGI_SETUP.md` - WSGI configuration details
- `WEBHOOK_SECRET_TOKEN_GUIDE.md` - Webhook security setup

