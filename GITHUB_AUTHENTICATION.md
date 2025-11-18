# GitHub Authentication Guide

GitHub no longer supports password authentication for Git operations. You need to use one of these methods:

## Option 1: SSH Keys (Recommended)

### Setup SSH Keys (if not already done)

1. **Check if you have SSH keys**:
   ```bash
   ls -al ~/.ssh
   ```
   Look for `id_rsa.pub` or `id_ed25519.pub`

2. **Generate SSH key** (if you don't have one):
   ```bash
   ssh-keygen -t ed25519 -C "gosha.dvoryak@gmail.com"
   # Press Enter to accept default file location
   # Optionally set a passphrase
   ```

3. **Copy your public key**:
   ```bash
   cat ~/.ssh/id_ed25519.pub
   # Or if using RSA:
   cat ~/.ssh/id_rsa.pub
   ```

4. **Add SSH key to GitHub**:
   - Go to https://github.com/settings/keys
   - Click "New SSH key"
   - Paste your public key
   - Click "Add SSH key"

5. **Test SSH connection**:
   ```bash
   ssh -T git@github.com
   ```
   Should say: "Hi george-dvoryak! You've successfully authenticated..."

### Clone using SSH:
```bash
git clone -b feature/remove-robocasa git@github.com:george-dvoryak/makeup_courses_bot.git
```

## Option 2: Personal Access Token (PAT)

### Create Personal Access Token

1. **Go to GitHub Settings**:
   - https://github.com/settings/tokens
   - Or: GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)

2. **Generate new token**:
   - Click "Generate new token" → "Generate new token (classic)"
   - Give it a name: "PythonAnywhere Deployment"
   - Select expiration (90 days recommended)
   - Check scopes: `repo` (full control of private repositories)
   - Click "Generate token"

3. **Copy the token immediately** (you won't see it again!)

### Use Token for Cloning

When cloning, use the token as password:
```bash
git clone -b feature/remove-robocasa https://github.com/george-dvoryak/makeup_courses_bot.git
# Username: gosha.dvoryak@gmail.com
# Password: <paste-your-token-here>
```

### Store Token Securely (Optional)

**On Linux/Mac:**
```bash
# Store token in credential helper
git config --global credential.helper store
# Then clone - it will ask once and remember
```

**On PythonAnywhere:**
The token will be stored after first use if credential helper is configured.

## Option 3: GitHub CLI

### Install GitHub CLI

**On PythonAnywhere:**
```bash
pip install --user gh
```

**On Mac:**
```bash
brew install gh
```

### Authenticate
```bash
gh auth login
# Follow prompts:
# - Choose GitHub.com
# - Choose HTTPS
# - Authenticate via web browser
```

### Clone
```bash
gh repo clone george-dvoryak/makeup_courses_bot -- --branch feature/remove-robocasa
```

## For PythonAnywhere Deployment

### Recommended: Use SSH

1. **Set up SSH keys on your local machine** (if not done)
2. **Add SSH key to GitHub** (as shown above)
3. **On PythonAnywhere**, clone using SSH:
   ```bash
   cd ~
   git clone -b feature/remove-robocasa git@github.com:george-dvoryak/makeup_courses_bot.git makeup_courses_bot
   ```

### Alternative: Use Personal Access Token

1. **Create PAT** (as shown above)
2. **On PythonAnywhere**, clone using HTTPS:
   ```bash
   cd ~
   git clone -b feature/remove-robocasa https://github.com/george-dvoryak/makeup_courses_bot.git makeup_courses_bot
   # When prompted, use your email and PAT as password
   ```

## Troubleshooting

### "Permission denied (publickey)" error
- Make sure SSH key is added to GitHub
- Test connection: `ssh -T git@github.com`
- Check SSH agent: `ssh-add -l`

### "Invalid username or token" error
- Make sure you're using Personal Access Token, not password
- Check token hasn't expired
- Verify token has `repo` scope

### Token not working
- Regenerate token if it's expired
- Make sure token has correct permissions
- Check if token was copied correctly (no extra spaces)

## Security Notes

- **Never commit tokens or SSH keys** to git
- **Use SSH keys** for better security
- **Set token expiration** to limit exposure
- **Revoke tokens** if compromised
- **Use different tokens** for different purposes

