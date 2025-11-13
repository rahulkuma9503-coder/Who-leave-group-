from flask import Flask, request, jsonify
import logging
import os
from bot import setup_bot_application

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Initialize bot application
bot_app = setup_bot_application()

@app.route('/')
def home():
    return "🤖 Telegram Bot is running!"

@app.route('/health')
def health():
    return jsonify({"status": "healthy", "service": "telegram-bot"})

@app.route('/webhook/' + os.environ.get('BOT_TOKEN'), methods=['POST'])
def webhook():
    """Handle incoming updates from Telegram"""
    try:
        # Process the update
        update = request.get_json()
        bot_app.update_queue.put(update)
        return 'ok'
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        return 'error', 500

@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    """Set webhook endpoint (run this once after deployment)"""
    try:
        webhook_url = os.environ.get('WEBHOOK_URL') + '/' + os.environ.get('BOT_TOKEN')
        result = bot_app.bot.set_webhook(webhook_url)
        return jsonify({
            "success": True,
            "webhook_url": webhook_url,
            "result": result
        })
    except Exception as e:
        logger.error(f"Error setting webhook: {e}")
        return jsonify({"success": False, "error": str(e)})

@app.route('/delete_webhook', methods=['GET'])
def delete_webhook():
    """Delete webhook endpoint (use this if you want to switch to polling)"""
    try:
        result = bot_app.bot.delete_webhook()
        return jsonify({"success": True, "result": result})
    except Exception as e:
        logger.error(f"Error deleting webhook: {e}")
        return jsonify({"success": False, "error": str(e)})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
