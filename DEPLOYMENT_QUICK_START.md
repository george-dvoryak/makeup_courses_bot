# Quick Start: PythonAnywhere Deployment

## 🚀 Fast Deployment Checklist

### 1. Upload Code

**Option A: Using SSH (Recommended)**
```bash
# On PythonAnywhere Bash console:
cd ~
# Clone specific branch using SSH
git clone -b feature/remove-robocasa git@github.com:george-dvoryak/makeup_courses_bot.git makeup_courses_bot
cd makeup_courses_bot
```

**Option B: Using HTTPS with Personal Access Token**
```bash
# On PythonAnywhere Bash console:
cd ~
# Clone specific branch (will prompt for username and token)
git clone -b feature/remove-robocasa https://github.com/george-dvoryak/makeup_courses_bot.git makeup_courses_bot
# Username: gosha.dvoryak@gmail.com
# Password: <your-personal-access-token> (NOT your GitHub password!)
cd makeup_courses_bot
```

**Note:** See [GITHUB_AUTHENTICATION.md](GITHUB_AUTHENTICATION.md) for detailed authentication setup.

### 2. Install Dependencies
```bash
pip install --user -r requirements.txt
```

### 3. Create .env File
Create `/home/<username>/makeup_courses_bot/.env` with:
```env
TELEGRAM_BOT_TOKEN=your_token
ADMIN_IDS=123456789
PAYMENT_PROVIDER_TOKEN=your_token
GSHEET_ID=your_sheet_id
USE_WEBHOOK=True
WEBHOOK_HOST=yourusername.pythonanywhere.com
WEBHOOK_PATH=/webhook
WEBHOOK_SECRET_TOKEN=your_secret_token_here
DATABASE_PATH=/home/yourusername/makeup_courses_bot/bot.db
```

**Generate WEBHOOK_SECRET_TOKEN:**
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```
Copy the output and use it as `WEBHOOK_SECRET_TOKEN` value.
See [WEBHOOK_SECRET_TOKEN_GUIDE.md](WEBHOOK_SECRET_TOKEN_GUIDE.md) for details.

### 4. Create Web App
- **Web** tab → **Add a new web app**
- Flask, Python 3.10
- **Path**: Enter `/home/<username>/makeup_courses_bot/webhook_app.py` (or any `.py` file path - we'll configure WSGI manually)

### 5. Configure WSGI
Replace WSGI file content with:
```python
import sys
path = '/home/<username>/makeup_courses_bot'
if path not in sys.path:
    sys.path.insert(0, path)
from webhook_app import app as application
```

### 6. Reload Web App
- Click **Reload** button
- Check **Error log** for: `Webhook set to:` and `[Auto-Cleanup] Background cleanup scheduler started`

### 7. Test Bot
Send `/start` to your bot in Telegram

## ✅ That's It!

**Bot runs automatically:**
- Starts when web app loads ✅
- Restarts when you reload web app ✅
- Wakes up automatically on free tier (when Telegram sends webhooks) ✅
- Stays active 24/7 on paid tier ✅

**Cleanup runs automatically:**
- On startup ✅
- Every hour ✅

**No always-on task or cron setup needed!** The web app handles everything.

## 📋 Verify Everything Works

1. **Check webhook**: Error log shows `Webhook set to: https://...`
2. **Check cleanup**: Error log shows `[Auto-Cleanup] Background cleanup scheduler started`
3. **Test bot**: Send `/start` command
4. **Test cleanup**: Send `/cleanup_expired` command (admin only)

## 🆘 Troubleshooting

- **Bot not responding?** → Check Error log, verify `.env` file
- **Cleanup not running?** → Check Error log for `[Auto-Cleanup]` messages
- **Import errors?** → Verify dependencies installed: `pip list`

For detailed instructions, see [PYTHONANYWHERE_DEPLOYMENT.md](PYTHONANYWHERE_DEPLOYMENT.md)

