import os
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any
import json

from telegram import (
    Update, 
    ChatPermissions, 
    User, 
    ChatMember, 
    Message,
    InputMediaPhoto,
    InputMediaVideo,
    InputMediaDocument
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ChatMemberHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)
from telegram.constants import ParseMode

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
BOT_TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_IDS = list(map(int, os.environ.get('ADMIN_IDS', '').split(','))) if os.environ.get('ADMIN_IDS') else []
BAN_DURATION_HOURS = 1  # Ban users who leave within 1 hour

# In-memory storage (for production, use a database)
user_join_times = {}
broadcast_data = {}

class UserTracker:
    @staticmethod
    async def track_user_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Track when users join the chat"""
        if update.chat_member:
            chat = update.chat_member.chat
            user = update.chat_member.new_chat_member.user
            old_status = update.chat_member.old_chat_member.status
            new_status = update.chat_member.new_chat_member.status
            
            # User joined
            if (old_status in ['left', 'kicked', 'restricted'] and 
                new_status in ['member', 'administrator', 'creator']):
                user_join_times[f"{chat.id}_{user.id}"] = {
                    'join_time': datetime.now(),
                    'user_id': user.id,
                    'chat_id': chat.id,
                    'username': user.username or user.first_name
                }
                logger.info(f"User {user.id} joined chat {chat.id} at {datetime.now()}")

    @staticmethod
    async def track_user_leave(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Track when users leave and ban if within 1 hour"""
        if update.chat_member:
            chat = update.chat_member.chat
            user = update.chat_member.new_chat_member.user
            old_status = update.chat_member.old_chat_member.status
            new_status = update.chat_member.new_chat_member.status
            
            # User left or was removed
            if (old_status in ['member', 'administrator', 'restricted'] and 
                new_status in ['left', 'kicked']):
                
                user_key = f"{chat.id}_{user.id}"
                user_data = user_join_times.get(user_key)
                
                if user_data:
                    join_time = user_data['join_time']
                    time_in_chat = datetime.now() - join_time
                    
                    # If user left within 1 hour, ban them
                    if time_in_chat < timedelta(hours=BAN_DURATION_HOURS):
                        try:
                            # Ban the user
                            await context.bot.ban_chat_member(
                                chat_id=chat.id,
                                user_id=user.id
                            )
                            
                            # Send notification
                            duration_hours = BAN_DURATION_HOURS
                            message = (
                                f"🚫 User @{user.username or user.first_name} has been banned!\n"
                                f"Reason: Left the group within {duration_hours} hour of joining.\n"
                                f"Join time: {join_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                                f"Time in chat: {str(time_in_chat).split('.')[0]}"
                            )
                            
                            await context.bot.send_message(
                                chat_id=chat.id,
                                text=message
                            )
                            logger.info(f"Banned user {user.id} for leaving within {BAN_DURATION_HOURS} hour")
                            
                        except Exception as e:
                            logger.error(f"Failed to ban user {user.id}: {e}")
                    
                    # Remove from tracking
                    user_join_times.pop(user_key, None)

class BroadcastHandler:
    @staticmethod
    async def start_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start broadcast process"""
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("❌ You are not authorized to use this command.")
            return
        
        broadcast_data[update.effective_user.id] = {
            'step': 'awaiting_message',
            'messages': []
        }
        
        await update.message.reply_text(
            "📢 Broadcast Mode Started!\n\n"
            "Please send the message you want to broadcast. "
            "You can send text, photos, videos, documents, or stickers.\n\n"
            "When you're done adding messages, use /send_broadcast to send or /cancel_broadcast to cancel."
        )

    @staticmethod
    async def collect_broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Collect messages for broadcast"""
        user_id = update.effective_user.id
        
        if user_id not in broadcast_data or broadcast_data[user_id]['step'] != 'awaiting_message':
            return
        
        message = update.message
        
        # Store message data based on type
        message_data = {
            'message_id': message.message_id,
            'chat_id': message.chat_id,
            'date': message.date.timestamp()
        }
        
        if message.text:
            message_data.update({
                'type': 'text',
                'text': message.text,
                'entities': message.entities,
                'parse_mode': ParseMode.HTML
            })
        elif message.photo:
            message_data.update({
                'type': 'photo',
                'photo': message.photo[-1].file_id,
                'caption': message.caption,
                'caption_entities': message.caption_entities
            })
        elif message.video:
            message_data.update({
                'type': 'video',
                'video': message.video.file_id,
                'caption': message.caption,
                'caption_entities': message.caption_entities
            })
        elif message.document:
            message_data.update({
                'type': 'document',
                'document': message.document.file_id,
                'caption': message.caption,
                'caption_entities': message.caption_entities
            })
        elif message.sticker:
            message_data.update({
                'type': 'sticker',
                'sticker': message.sticker.file_id
            })
        else:
            await message.reply_text("❌ Unsupported message type. Please send text, photo, video, document, or sticker.")
            return
        
        broadcast_data[user_id]['messages'].append(message_data)
        
        # Show preview and options
        preview_text = "✅ Message added to broadcast!\n\n"
        if message.text:
            preview_text += f"Text: {message.text[:100]}{'...' if len(message.text) > 100 else ''}"
        elif message.photo:
            preview_text += "Type: Photo"
        elif message.video:
            preview_text += "Type: Video"
        elif message.document:
            preview_text += "Type: Document"
        elif message.sticker:
            preview_text += "Type: Sticker"
        
        preview_text += f"\n\nTotal messages in broadcast: {len(broadcast_data[user_id]['messages'])}"
        preview_text += "\n\nSend more messages or use /send_broadcast to send or /cancel_broadcast to cancel."
        
        await message.reply_text(preview_text)

    @staticmethod
    async def send_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send broadcast to all chats"""
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("❌ You are not authorized to use this command.")
            return
        
        if user_id not in broadcast_data or not broadcast_data[user_id]['messages']:
            await update.message.reply_text("❌ No messages to broadcast. Use /broadcast first.")
            return
        
        await update.message.reply_text("🔄 Starting broadcast... This may take a while.")
        
        # Get all chats where bot is member (you might want to maintain a database of chats)
        # For now, we'll use a simple approach - you need to maintain chat list
        chats = []  # You should implement a way to store chat IDs
        
        if not chats:
            await update.message.reply_text("❌ No chats available for broadcasting.")
            return
        
        success_count = 0
        fail_count = 0
        
        for chat_id in chats:
            try:
                for message_data in broadcast_data[user_id]['messages']:
                    if message_data['type'] == 'text':
                        await context.bot.send_message(
                            chat_id=chat_id,
                            text=message_data['text'],
                            entities=message_data.get('entities'),
                            parse_mode=message_data.get('parse_mode')
                        )
                    elif message_data['type'] == 'photo':
                        await context.bot.send_photo(
                            chat_id=chat_id,
                            photo=message_data['photo'],
                            caption=message_data.get('caption'),
                            caption_entities=message_data.get('caption_entities')
                        )
                    elif message_data['type'] == 'video':
                        await context.bot.send_video(
                            chat_id=chat_id,
                            video=message_data['video'],
                            caption=message_data.get('caption'),
                            caption_entities=message_data.get('caption_entities')
                        )
                    elif message_data['type'] == 'document':
                        await context.bot.send_document(
                            chat_id=chat_id,
                            document=message_data['document'],
                            caption=message_data.get('caption'),
                            caption_entities=message_data.get('caption_entities')
                        )
                    elif message_data['type'] == 'sticker':
                        await context.bot.send_sticker(
                            chat_id=chat_id,
                            sticker=message_data['sticker']
                        )
                
                success_count += 1
                
            except Exception as e:
                logger.error(f"Failed to send broadcast to chat {chat_id}: {e}")
                fail_count += 1
            
            # Small delay to avoid rate limits
            await asyncio.sleep(0.1)
        
        # Cleanup
        broadcast_data.pop(user_id, None)
        
        await update.message.reply_text(
            f"📊 Broadcast Completed!\n\n"
            f"✅ Successful: {success_count}\n"
            f"❌ Failed: {fail_count}\n"
            f"📝 Total messages sent: {success_count * len(broadcast_data.get(user_id, {}).get('messages', []))}"
        )

    @staticmethod
    async def cancel_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel broadcast process"""
        user_id = update.effective_user.id
        
        if user_id in broadcast_data:
            broadcast_data.pop(user_id)
            await update.message.reply_text("❌ Broadcast cancelled.")
        else:
            await update.message.reply_text("No active broadcast to cancel.")

class AdminCommands:
    @staticmethod
    async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show bot statistics"""
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("❌ You are not authorized to use this command.")
            return
        
        stats_text = (
            f"🤖 Bot Statistics\n\n"
            f"📊 Tracked users: {len(user_join_times)}\n"
            f"👥 Active broadcasts: {len(broadcast_data)}\n"
            f"🕒 Ban duration: {BAN_DURATION_HOURS} hour(s)\n"
            f"👑 Admins: {len(ADMIN_IDS)}"
        )
        
        await update.message.reply_text(stats_text)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    user = update.effective_user
    await update.message.reply_text(
        f"👋 Hello {user.first_name}!\n\n"
        f"I'm a moderation bot that:\n"
        f"• 🚫 Bans users who leave within {BAN_DURATION_HOURS} hour of joining\n"
        f"• 📢 Supports broadcast messages\n\n"
        f"Add me to your group/channel and make me admin to start moderating!"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /help is issued."""
    help_text = """
🤖 Available Commands:

For Everyone:
/start - Start the bot
/help - Show this help message

For Admins:
/broadcast - Start broadcast message
/send_broadcast - Send collected broadcast
/cancel_broadcast - Cancel broadcast
/stats - Show bot statistics

📝 Note: Make sure the bot has admin permissions in your groups/channels for the auto-ban feature to work.
    """
    await update.message.reply_text(help_text)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors and handle them gracefully."""
    logger.error(f"Exception while handling an update: {context.error}")

def main():
    """Start the bot."""
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN environment variable is required!")
        return
    
    # Create Application
    application = Application.builder().token(BOT_TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", AdminCommands.stats))
    
    # Broadcast commands
    application.add_handler(CommandHandler("broadcast", BroadcastHandler.start_broadcast))
    application.add_handler(CommandHandler("send_broadcast", BroadcastHandler.send_broadcast))
    application.add_handler(CommandHandler("cancel_broadcast", BroadcastHandler.cancel_broadcast))
    
    # Message handler for collecting broadcast messages
    application.add_handler(MessageHandler(
        filters.ALL & ~filters.COMMAND, 
        BroadcastHandler.collect_broadcast_message
    ))
    
    # Chat member handlers for tracking joins/leaves
    application.add_handler(ChatMemberHandler(
        UserTracker.track_user_join, 
        ChatMemberHandler.CHAT_MEMBER
    ))
    application.add_handler(ChatMemberHandler(
        UserTracker.track_user_leave, 
        ChatMemberHandler.CHAT_MEMBER
    ))

    # Error handler
    application.add_error_handler(error_handler)

    # Start the Bot
    if os.environ.get('RENDER'):
        # Webhook for Render
        port = int(os.environ.get('PORT', 8443))
        webhook_url = os.environ.get('WEBHOOK_URL')
        
        if webhook_url:
            application.run_webhook(
                listen="0.0.0.0",
                port=port,
                url_path=BOT_TOKEN,
                webhook_url=f"{webhook_url}/{BOT_TOKEN}"
            )
        else:
            logger.warning("WEBHOOK_URL not set, using polling instead")
            application.run_polling()
    else:
        # Polling for local development
        application.run_polling()

if __name__ == '__main__':
    import asyncio
    main()
