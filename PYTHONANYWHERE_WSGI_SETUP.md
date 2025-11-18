# PythonAnywhere WSGI Configuration Guide

## Important: Skip Quickstart!

When creating a Flask web app in PythonAnywhere, **DO NOT** use the Quickstart feature if you already have a Flask app file (`webhook_app.py`). Instead, configure the WSGI file manually.

## Step-by-Step WSGI Setup

### Step 1: Create Web App

1. Go to **Web** tab in PythonAnywhere
2. Click **Add a new web app**
3. Choose **Flask**
4. Select Python version (3.10 recommended)
5. When prompted for path, enter:
   ```
   /home/<your-username>/makeup_courses_bot/webhook_app.py
   ```
   Or any valid Python file path ending in `.py`

**Note**: If Quickstart creates a default Flask app, that's fine - we'll replace the WSGI file content.

### Step 2: Find Your WSGI File

After creating the web app, PythonAnywhere will show you a link to your WSGI configuration file. It's usually:
```
/home/<your-username>/web/<your-web-app-name>.py
```

Or you can find it in the **Web** tab → **WSGI configuration file** link.

### Step 3: Replace WSGI File Content

Click on the WSGI configuration file link and **replace ALL content** with:

```python
import sys

# Add your project directory to the path
path = '/home/<your-username>/makeup_courses_bot'
if path not in sys.path:
    sys.path.insert(0, path)

# Import the Flask app from webhook_app.py
from webhook_app import app as application

# The app will automatically:
# - Set up webhook on startup
# - Start background cleanup scheduler (runs every hour + on startup)
```

**CRITICAL**: Replace `<your-username>` with your actual PythonAnywhere username!

### Step 4: Reload Web App

1. Go back to **Web** tab
2. Click the green **Reload** button
3. Check **Error log** for:
   - `Webhook set to: https://...`
   - `[Auto-Cleanup] Background cleanup scheduler started`

## Troubleshooting WSGI Errors

### "No module named 'webhook_app'"
- Check that `path` variable has correct username
- Verify the directory exists: `ls -la /home/<username>/makeup_courses_bot`
- Check that `webhook_app.py` exists in that directory

### "No module named 'config'"
- Make sure `.env` file exists in the project directory
- Check that all dependencies are installed: `pip install --user -r requirements.txt`

### Import errors
- Check Error log for specific error messages
- Verify Python version matches (3.10 recommended)
- Make sure all files are uploaded correctly

## Alternative: Manual WSGI File Creation

If you prefer to create the WSGI file manually:

1. Go to **Files** tab
2. Navigate to `/home/<your-username>/web/`
3. Find your WSGI file (usually named after your web app)
4. Edit it and replace content with the code above

## Verify Configuration

After reloading, check the Error log. You should see:
```
Webhook set to: https://yourusername.pythonanywhere.com/webhook
[Auto-Cleanup] Background cleanup scheduler started (runs every hour + on startup)
[Auto-Cleanup] Running initial cleanup on startup...
```

If you see these messages, everything is configured correctly!

