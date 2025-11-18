# PythonAnywhere Deployment Guide

Complete guide for deploying the Telegram bot to PythonAnywhere.

## Prerequisites

1. PythonAnywhere account (free tier works, but paid is recommended for better reliability)
2. Your bot token from BotFather
3. Google Sheets ID with courses and texts
4. Admin Telegram user IDs

## Step 1: Upload Your Code

### Option A: Using Git (Recommended)

1. **On PythonAnywhere**, open a Bash console and clone:

   **Option A: Using SSH (Recommended - no authentication needed if SSH keys are set up)**
   ```bash
   cd ~
   # Clone specific branch using SSH
   git clone -b feature/remove-robocasa git@github.com:george-dvoryak/makeup_courses_bot.git makeup_courses_bot
   cd makeup_courses_bot
   ```
   
   **Option B: Using HTTPS with Personal Access Token**
   ```bash
   cd ~
   # Clone specific branch (GitHub will prompt for username and token)
   git clone -b feature/remove-robocasa https://github.com/george-dvoryak/makeup_courses_bot.git makeup_courses_bot
   # When prompted:
   # Username: gosha.dvoryak@gmail.com
   # Password: <your-personal-access-token> (NOT your GitHub password!) 
   # ывыв
   cd makeup_courses_bot
   ```
   
   **Option C: Clone main branch and checkout**
   ```bash
   cd ~
   git clone git@github.com:george-dvoryak/makeup_courses_bot.git makeup_courses_bot
   cd makeup_courses_bot
   git checkout feature/remove-robocasa  # Replace with your branch name
   ```

### Option B: Using Files Tab

1. Go to **Files** tab in PythonAnywhere
2. Navigate to `/home/<your-username>/`
3. Create folder `makeup_courses_bot`
4. Upload all files using the upload button

## Step 2: Install Dependencies

1. Open a **Bash console** in PythonAnywhere
2. Navigate to your project:
   ```bash
   cd ~/makeup_courses_bot
   ```

3. Create virtual environment (recommended):
   ```bash
   python3.10 -m venv venv
   source venv/bin/activate
   ```

4. Install dependencies:
   ```bash
   pip install --user -r requirements.txt
   ```

   **Note**: On PythonAnywhere free tier, use `--user` flag. On paid tier, you can install globally.

## Step 3: Configure Environment Variables

1. In PythonAnywhere **Files** tab, navigate to `/home/<your-username>/makeup_courses_bot/`
2. Create `.env` file (or upload if you have it locally)
3. Add all required variables:

```env
# Telegram Bot
TELEGRAM_BOT_TOKEN=your_bot_token_here
ADMIN_IDS=123456789,987654321

# Payments
PAYMENT_PROVIDER_TOKEN=your_yookassa_token
CURRENCY=RUB

# Google Sheets
GSHEET_ID=your_google_sheet_id
GSHEET_COURSES_NAME=Courses
GSHEET_TEXTS_NAME=Texts
GOOGLE_SHEETS_USE_API=False

# Webhook (PythonAnywhere)
USE_WEBHOOK=True
WEBHOOK_HOST=yourusername.pythonanywhere.com
WEBHOOK_PATH=/webhook
WEBHOOK_SECRET_TOKEN=your_secret_token_here
# Generate with: python3 -c "import secrets; print(secrets.token_urlsafe(32))"
# See WEBHOOK_SECRET_TOKEN_GUIDE.md for details

# Database
DATABASE_PATH=/home/yourusername/makeup_courses_bot/bot.db

# Prodamus (optional)
ENABLE_PRODAMUS=True
PRODAMUS_TEST_MODE=True
PRODAMUS_PAYFORM_URL=testwork1.payform.ru
PRODAMUS_SECRET_KEY=your_prodamus_secret
PRODAMUS_SYSTEM_ID=your_system_id
```

**Important**: Replace `yourusername` with your actual PythonAnywhere username!

## Step 4: Create Web App

1. Go to **Web** tab in PythonAnywhere
2. Click **Add a new web app**
3. Choose **Flask**
4. Select Python version (3.10 recommended)
5. **IMPORTANT**: When prompted for path, you can either:
   - **Option A**: Enter `/home/<your-username>/makeup_courses_bot/webhook_app.py` (full path to Flask app file)
   - **Option B**: Enter any valid Python filename like `/home/<your-username>/makeup_courses_bot/flask_app.py` (we'll replace the WSGI file content anyway)
   
   **Note**: Don't worry if Quickstart creates a default Flask app - we'll replace the WSGI file content in the next step.

## Step 5: Configure WSGI File

1. In **Web** tab, click on the WSGI configuration file link
2. Replace the entire content with:

```python
import sys

# Add your project directory to the path
path = '/home/<your-username>/makeup_courses_bot'
if path not in sys.path:
    sys.path.insert(0, path)

# Import the Flask app
from webhook_app import app as application

# The app will automatically:
# - Set up webhook on startup
# - Start background cleanup scheduler (runs every hour + on startup)
```

**Important**: Replace `<your-username>` with your actual username!

## Step 6: Configure Static Files (Optional)

If you have static files, add them in **Web** tab → **Static files**:
- URL: `/static/`
- Directory: `/home/<your-username>/makeup_courses_bot/static/`

## Step 7: Set Up Database

The database will be created automatically on first run. Make sure the path in `.env` is correct:
```
DATABASE_PATH=/home/yourusername/makeup_courses_bot/bot.db
```

## Step 8: Reload Web App

1. Go to **Web** tab
2. Click **Reload** button (green button)
3. Check **Error log** for any issues

## Step 9: Verify Webhook Setup

1. Check the **Error log** in **Web** tab
2. You should see: `Webhook set to: https://yourusername.pythonanywhere.com/webhook`
3. Test your bot by sending `/start` command

## Step 10: Test Automatic Cleanup

The cleanup scheduler runs automatically:
- **On startup**: Immediately when web app starts
- **Every hour**: Automatically in background

To verify:
1. Check **Error log** for messages like `[Auto-Cleanup] Running scheduled cleanup...`
2. Use `/cleanup_expired` command in bot to manually trigger and see statistics

## Optional: Set Up Scheduled Task (Backup Method)

Even though cleanup runs automatically in code, you can also set up a scheduled task as backup:

1. Go to **Tasks** tab
2. Click **Create a new scheduled task**
3. Configure:
   - **Command**: `cd /home/<your-username>/makeup_courses_bot && python3.10 remove_expired.py`
   - **Hour**: `*` (every hour)
   - **Minute**: `0` (at start of hour)
4. Save

**Note**: This is optional since cleanup already runs automatically in the code.

## Keeping Bot Always Running

### How It Works

Your bot runs as a **Flask web app** which:
- ✅ Starts automatically when web app loads
- ✅ Restarts when you click **Reload** in Web tab
- ✅ On **free tier**: Sleeps after inactivity but wakes up automatically when Telegram sends webhooks
- ✅ On **paid tier**: Stays active 24/7 automatically
- ✅ Background cleanup runs automatically in the same process

### No Always-On Task Needed!

Since you're using **webhook mode** (recommended), the web app handles everything. You don't need an always-on task.

**To restart manually:**
- Go to **Web** tab → Click **Reload** button
- Check **Error log** to verify startup messages

**To verify bot is running:**
- Send `/start` command to your bot in Telegram
- Check **Error log** for `Webhook set to:` and `[Auto-Cleanup]` messages

For more details, see [PYTHONANYWHERE_ALWAYS_RUNNING.md](PYTHONANYWHERE_ALWAYS_RUNNING.md)

## Troubleshooting

### Bot Not Responding

1. Check **Error log** in **Web** tab
2. Verify webhook is set: Look for `Webhook set to:` message
3. Check `.env` file has correct `TELEGRAM_BOT_TOKEN`
4. Verify bot token is correct in BotFather

### Database Errors

1. Check `DATABASE_PATH` in `.env` is correct
2. Ensure directory exists and is writable
3. Check file permissions: `chmod 664 bot.db`

### Import Errors

1. Verify all dependencies are installed: `pip list`
2. Check Python version matches (3.10 recommended)
3. Ensure virtual environment is activated if using one

### Cleanup Not Running

1. Check **Error log** for `[Auto-Cleanup]` messages
2. Verify cleanup scheduler started: Look for `Background cleanup scheduler started`
3. Test manually with `/cleanup_expired` command
4. Check database has expired subscriptions

### Webhook Not Working

1. Verify `WEBHOOK_URL` is correct in logs
2. Check `WEBHOOK_SECRET_TOKEN` matches if configured
3. Ensure web app is reloaded after changes
4. Check Telegram webhook status: `https://api.telegram.org/bot<TOKEN>/getWebhookInfo`

## File Structure on PythonAnywhere

```
/home/<your-username>/
└── makeup_courses_bot/
    ├── .env                    # Environment variables (IMPORTANT: keep secret!)
    ├── bot.db                 # SQLite database (created automatically)
    ├── config.py
    ├── db.py
    ├── main.py
    ├── webhook_app.py         # Flask app for PythonAnywhere
    ├── remove_expired.py      # Standalone cleanup script
    ├── google_sheets.py
    ├── requirements.txt
    └── ... (other files)
```

## Security Notes

1. **Never commit `.env` file** to git - it contains secrets
2. **Keep `WEBHOOK_SECRET_TOKEN` secret** - it protects your webhook
3. **Restrict file permissions**: `chmod 600 .env`
4. **Use strong secret tokens** for webhook protection

## Monitoring

### Check Logs

- **Error log**: Web tab → Error log (shows Flask/webhook errors)
- **Server log**: Web tab → Server log (shows general server messages)
- **Task logs**: Tasks tab → View logs (if using scheduled tasks)

### Monitor Bot Activity

- Use `/cleanup_expired` command to see statistics
- Check database periodically: `sqlite3 bot.db "SELECT COUNT(*) FROM purchases WHERE expiry > 0"`
- Monitor error logs for issues

## Updating Code

For detailed instructions, see [UPDATE_CODE_PYTHONANYWHERE.md](UPDATE_CODE_PYTHONANYWHERE.md)

**Quick steps:**

1. **If using Git**:
   ```bash
   cd ~/makeup_courses_bot
   git pull
   ```

2. **Install new dependencies** (if any):
   ```bash
   pip install --user -r requirements.txt
   ```

3. **Reload web app**: Web tab → Reload button

4. **Check logs**: Verify no errors after reload

5. **Test bot**: Send `/start` command to verify it works

## Free Tier Limitations

- **Web app sleeps after inactivity**: First request may be slow
- **Limited scheduled tasks**: Only 1 task on free tier
- **Limited CPU time**: Keep cleanup efficient
- **No custom domains**: Use `yourusername.pythonanywhere.com`

**Recommendation**: Upgrade to paid tier for production use.

## Support

If you encounter issues:
1. Check error logs first
2. Verify all configuration in `.env`
3. Test locally first if possible
4. Check PythonAnywhere status page

## Quick Checklist

- [ ] Code uploaded to PythonAnywhere
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] `.env` file created with all variables
- [ ] Web app created and configured
- [ ] WSGI file updated with correct path
- [ ] Web app reloaded
- [ ] Webhook set successfully (check logs)
- [ ] Bot responds to `/start` command
- [ ] Cleanup scheduler running (check logs)
- [ ] Database created (`bot.db` exists)

