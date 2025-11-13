from flask import Flask, request, jsonify
import logging
import os
import threading

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Bot components
BOT_TOKEN = os.environ.get('BOT_TOKEN')
WEBHOOK_URL = os.environ.get('WEBHOOK_URL')

# Import and setup bot
try:
    from bot import updater, dispatcher
    
    # Set webhook on startup
    if WEBHOOK_URL and BOT_TOKEN:
        webhook_url = f"{WEBHOOK_URL}/webhook"
        updater.bot.set_webhook(webhook_url)
        logger.info(f"✅ Webhook set to: {webhook_url}")
    else:
        logger.warning("⚠️ WEBHOOK_URL or BOT_TOKEN not set, webhook not configured")
        
except Exception as e:
    logger.error(f"❌ Failed to import bot: {e}")
    updater = None
    dispatcher = None

@app.route('/')
def home():
    return """
    <h1>🤖 Telegram Bot is Running!</h1>
    <p>Your bot is successfully deployed on Render.</p>
    <p>Endpoints:</p>
    <ul>
        <li><a href="/health">/health</a> - Health check</li>
        <li><a href="/set_webhook">/set_webhook</a> - Set webhook</li>
        <li><a href="/get_webhook_info">/get_webhook_info</a> - Check webhook status</li>
    </ul>
    """

@app.route('/health')
def health():
    status = {
        "status": "healthy",
        "service": "telegram-bot",
        "bot_initialized": updater is not None,
        "webhook_url": WEBHOOK_URL
    }
    return jsonify(status)

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle incoming updates from Telegram"""
    try:
        if updater is None:
            logger.error("Bot updater not initialized")
            return 'Bot not initialized', 500
            
        # Get the update from Telegram
        update = request.get_json()
        
        # Process the update in a thread to avoid blocking
        thread = threading.Thread(target=process_update, args=(update,))
        thread.start()
        
        return 'ok'
        
    except Exception as e:
        logger.error(f"Error in webhook handler: {e}")
        return 'error', 500

def process_update(update):
    """Process update in a separate thread"""
    try:
        # Use the dispatcher to process the update
        dispatcher.process_update(update)
    except Exception as e:
        logger.error(f"Error processing update: {e}")

@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    """Set webhook endpoint"""
    try:
        if updater is None:
            return jsonify({"success": False, "error": "Bot not initialized"})
            
        if not WEBHOOK_URL:
            return jsonify({"success": False, "error": "WEBHOOK_URL not set"})
            
        webhook_url = f"{WEBHOOK_URL}/webhook"
        result = updater.bot.set_webhook(webhook_url)
        
        logger.info(f"Webhook set to: {webhook_url}")
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
        if updater is None:
            return jsonify({"success": False, "error": "Bot not initialized"})
            
        result = updater.bot.delete_webhook()
        return jsonify({"success": True, "result": result})
        
    except Exception as e:
        logger.error(f"Error deleting webhook: {e}")
        return jsonify({"success": False, "error": str(e)})

@app.route('/get_webhook_info', methods=['GET'])
def get_webhook_info():
    """Get current webhook info"""
    try:
        if updater is None:
            return jsonify({"success": False, "error": "Bot not initialized"})
            
        info = updater.bot.get_webhook_info()
        return jsonify({
            "success": True,
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
    logger.info(f"Starting Flask app on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
