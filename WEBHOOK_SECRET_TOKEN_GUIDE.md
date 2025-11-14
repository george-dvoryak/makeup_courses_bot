# How to Generate Webhook Secret Token

## What is WEBHOOK_SECRET_TOKEN?

The `WEBHOOK_SECRET_TOKEN` is a **secret string you generate yourself** to secure your Telegram webhook endpoint. It ensures that only Telegram (with the correct token) can send requests to your bot.

**Important**: This is NOT provided by PythonAnywhere - you need to generate it yourself!

## How to Generate a Secret Token

### Method 1: Using Python (Recommended)

On PythonAnywhere Bash console or locally:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

This will generate a secure random token like:
```
xK9mP2vQ7wR4tY8uI0oP3aS6dF9gH2jK5lM8nQ1rT4vW7xY0zA3bC6dE9fG
```

### Method 2: Using OpenSSL

```bash
openssl rand -hex 32
```

This generates a hexadecimal token like:
```
a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456
```

### Method 3: Using Online Generator

You can use any secure random string generator online, or generate it manually:
- Use a password generator
- Make it at least 32 characters long
- Use letters, numbers, and special characters

### Method 4: Simple Random String

```bash
python3 -c "import random, string; print(''.join(random.choices(string.ascii_letters + string.digits, k=32)))"
```

## How to Use It

### Step 1: Generate the Token

Run one of the commands above to generate your secret token.

### Step 2: Add to .env File

On PythonAnywhere, edit your `.env` file:

```bash
cd ~/makeup_courses_bot
nano .env
```

Add this line (replace with your generated token):

```env
WEBHOOK_SECRET_TOKEN=xK9mP2vQ7wR4tY8uI0oP3aS6dF9gH2jK5lM8nQ1rT4vW7xY0zA3bC6dE9fG
```

Save and exit (Ctrl+X, then Y, then Enter).

### Step 3: Reload Web App

1. Go to **Web** tab in PythonAnywhere
2. Click **Reload** button
3. Check **Error log** - webhook should be set with the secret token

## How It Works

1. **You generate** a secret token and add it to `.env`
2. **Your bot** sets the webhook with this secret token
3. **Telegram** includes this token in the `X-Telegram-Bot-Api-Secret-Token` header when sending webhook requests
4. **Your bot** verifies the token matches before processing requests
5. **If token doesn't match**, the request is rejected (403 Forbidden)

## Security Notes

✅ **DO:**
- Generate a long, random token (at least 32 characters)
- Keep it secret - never commit to git
- Use different tokens for different environments (test/production)
- Store it securely in `.env` file

❌ **DON'T:**
- Use simple passwords like "password123"
- Share the token publicly
- Commit `.env` file to git
- Use the same token for multiple bots

## Optional: Token Not Required

If you don't want to use a secret token (less secure but simpler):

1. **Leave `WEBHOOK_SECRET_TOKEN` empty** in `.env`:
   ```env
   WEBHOOK_SECRET_TOKEN=
   ```

2. **Or omit it entirely** from `.env` file

**Note**: Without a secret token, anyone who knows your webhook URL could potentially send fake requests. Using a secret token is recommended for production.

## Troubleshooting

### "403 Forbidden" errors

- Check that `WEBHOOK_SECRET_TOKEN` in `.env` matches what Telegram is sending
- Verify the token doesn't have extra spaces or newlines
- Make sure you reloaded the web app after changing `.env`

### Webhook not working

- Check Error log for webhook setup messages
- Verify token is set correctly in `.env`
- Test webhook: `curl https://api.telegram.org/bot<TOKEN>/getWebhookInfo`

## Quick Setup on PythonAnywhere

```bash
# 1. Generate token
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# 2. Copy the output token

# 3. Add to .env
cd ~/makeup_courses_bot
echo "WEBHOOK_SECRET_TOKEN=your_generated_token_here" >> .env

# 4. Reload web app in Web tab
```

That's it! Your webhook is now secured with a secret token.

