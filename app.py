from flask import Flask, request, jsonify
import logging
import os
import asyncio
from threading import Thread
import time

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Bot application will be imported after setup
bot_application = None
BOT_TOKEN = os.environ.get('BOT_TOKEN')
WEBHOOK_URL = os.environ.get('WEBHOOK_URL')

def initialize_bot():
    """Initialize the bot application"""
    global bot_application
    
    try:
        from bot import application as bot_app
        bot_application = bot_app
        
        if bot_application:
            logger.info("✅ Bot application imported successfully")
            
            # Set webhook if we have the URL
            if WEBHOOK_URL and BOT_TOKEN:
                try:
                    webhook_url = f"{WEBHOOK_URL}/webhook"
                    bot_application.bot.set_webhook(webhook_url)
                    logger.info(f"✅ Webhook set to: {webhook_url}")
                except Exception as e:
                    logger.error(f"❌ Failed to set webhook: {e}")
        else:
            logger.error("❌ Failed to import bot application")
            
    except Exception as e:
        logger.error(f"❌ Error initializing bot: {e}")

# Initialize bot when app starts
initialize_bot()

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
        "bot_initialized": bot_application is not None,
        "webhook_url": WEBHOOK_URL,
        "timestamp": time.time()
    }
    return jsonify(status)

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle incoming updates from Telegram"""
    try:
        if bot_application is None:
            logger.error("Bot application not initialized")
            return 'Bot not initialized', 500
            
        # Get the update from Telegram
        update_data = request.get_json()
        
        # Process the update in a thread to avoid blocking
        thread = Thread(target=process_update, args=(update_data,))
        thread.start()
        
        return 'ok'
        
    except Exception as e:
        logger.error(f"Error in webhook handler: {e}")
        return 'error', 500

def process_update(update_data):
    """Process update in a separate thread"""
    try:
        # Create a new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Process the update
        update = bot_application.update_queue.put(update_data)
        
    except Exception as e:
        logger.error(f"Error processing update: {e}")

@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    """Set webhook endpoint"""
    try:
        if bot_application is None:
            return jsonify({"success": False, "error": "Bot not initialized"})
            
        if not WEBHOOK_URL:
            return jsonify({"success": False, "error": "WEBHOOK_URL not set"})
            
        webhook_url = f"{WEBHOOK_URL}/webhook"
        result = bot_application.bot.set_webhook(webhook_url)
        
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
        if bot_application is None:
            return jsonify({"success": False, "error": "Bot not initialized"})
            
        result = bot_application.bot.delete_webhook()
        return jsonify({"success": True, "result": result})
        
    except Exception as e:
        logger.error(f"Error deleting webhook: {e}")
        return jsonify({"success": False, "error": str(e)})

@app.route('/get_webhook_info', methods=['GET'])
def get_webhook_info():
    """Get current webhook info"""
    try:
        if bot_application is None:
            return jsonify({"success": False, "error": "Bot not initialized"})
            
        info = bot_application.bot.get_webhook_info()
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

@app.route('/restart_bot', methods=['GET'])
def restart_bot():
    """Restart bot initialization"""
    try:
        initialize_bot()
        return jsonify({
            "success": True,
            "message": "Bot reinitialization triggered",
            "bot_initialized": bot_application is not None
        })
    except Exception as e:
        logger.error(f"Error restarting bot: {e}")
        return jsonify({"success": False, "error": str(e)})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"Starting Flask app on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
