# Telegram Auto-Ban & Broadcast Bot

A Telegram bot that automatically bans users who leave groups/channels within 1 hour of joining and supports broadcasting messages.

## Features

- 🚫 Auto-ban users who leave within 1 hour of joining
- 📢 Broadcast messages (text, photos, videos, documents, stickers)
- 👑 Admin-only commands
- 🎯 Cancel broadcast option
- 📊 Statistics
- 🌐 Flask web server for proper deployment

## Deployment on Render

### 1. Fork/Upload to GitHub
Upload these files to a GitHub repository.

### 2. Deploy on Render
1. Go to [Render.com](https://render.com)
2. Create a new "Web Service"
3. Connect your GitHub repository
4. Use these settings:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python app.py`

### 3. Environment Variables
Set these environment variables in Render:

- `BOT_TOKEN`: Your Telegram Bot Token from @BotFather
- `ADMIN_IDS`: Comma-separated list of admin user IDs
- `WEBHOOK_URL`: Your Render app URL (e.g., https://your-app-name.onrender.com)

### 4. Set Webhook
After deployment, visit:
