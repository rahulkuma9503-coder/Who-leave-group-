from flask import Flask, request, jsonify
import logging
import os
import asyncio
from threading import Thread

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Import and initialize bot
from bot import application, BOT_TOKEN, WEBHOOK_URL

@app.route('/')
def home():
    return "🤖 Telegram Bot is running! Use /set_webhook to configure webhook."

@app.route('/health')
def health():
    return jsonify({"status": "healthy", "service": "telegram-bot"})

@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    """Set webhook endpoint"""
    try:
        webhook_url = f"{WEBHOOK_URL}/webhook"
        result = application.bot.set_webhook(webhook_url)
        return jsonify({
            "success": True,
            "message": "Webhook set successfully",
            "webhook_url": webhook_url,
            "result": result
        })
    except Exception as e:
        logger.error(f"Error setting webhook: {e}")
        return jsonify({"success": False, "error": str(e)})

@app.route('/delete_webhook', methods=['GET'])
def delete_webhook():
    """Delete webhook endpoint"""
    try:
        result = application.bot.delete_webhook()
        return jsonify({"success": True, "result": result})
    except Exception as e:
        logger.error(f"Error deleting webhook: {e}")
        return jsonify({"success": False, "error": str(e)})

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle incoming updates from Telegram"""
    try:
        update = request.get_json()
        
        # Process update in a separate thread to avoid blocking
        thread = Thread(target=process_update, args=(update,))
        thread.start()
        
        return 'ok'
    except Exception as e:
        logger.error(f"Error in webhook: {e}")
        return 'error', 500

def process_update(update):
    """Process update in a separate thread"""
    try:
        # Use asyncio to run the async function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Process the update
        loop.run_until_complete(application.process_update(update))
    except Exception as e:
        logger.error(f"Error processing update: {e}")

@app.route('/get_webhook_info', methods=['GET'])
def get_webhook_info():
    """Get current webhook info"""
    try:
        info = application.bot.get_webhook_info()
        return jsonify({
            "url": info.url,
            "has_custom_certificate": info.has_custom_certificate,
            "pending_update_count": info.pending_update_count,
            "last_error_date": info.last_error_date,
            "last_error_message": info.last_error_message
        })
    except Exception as e:
        logger.error(f"Error getting webhook info: {e}")
        return jsonify({"success": False, "error": str(e)})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    
    # Set webhook on startup
    try:
        webhook_url = f"{WEBHOOK_URL}/webhook"
        application.bot.set_webhook(webhook_url)
        logger.info(f"Webhook set to: {webhook_url}")
    except Exception as e:
        logger.error(f"Failed to set webhook on startup: {e}")
    
    app.run(host='0.0.0.0', port=port, debug=False)
