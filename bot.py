import os
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ChatMemberHandler,
    ContextTypes,
    filters
)

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
BOT_TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_IDS = list(map(int, os.environ.get('ADMIN_IDS', '').split(','))) if os.environ.get('ADMIN_IDS') else []
WEBHOOK_URL = os.environ.get('WEBHOOK_URL')
BAN_DURATION_HOURS = 1

# Validate required environment variables
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN environment variable is required!")
    exit(1)

if not ADMIN_IDS:
    logger.warning("⚠️ ADMIN_IDS environment variable not set. Admin commands will not work.")

if not WEBHOOK_URL:
    logger.warning("⚠️ WEBHOOK_URL environment variable not set. Webhook mode may not work properly.")

# Storage
user_join_times = {}
broadcast_data = {}
active_chats = set()

# Create application
try:
    application = Application.builder().token(BOT_TOKEN).build()
    logger.info("✅ Bot application created successfully")
except Exception as e:
    logger.error(f"❌ Failed to create bot application: {e}")
    exit(1)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    try:
        user = update.effective_user
        chat = update.effective_chat
        
        if chat:
            active_chats.add(chat.id)
            logger.info(f"Chat {chat.id} added to active chats")
        
        welcome_text = (
            f"👋 Hello {user.first_name}!\n\n"
            f"I'm a moderation bot that:\n"
            f"• 🚫 Bans users who leave within {BAN_DURATION_HOURS} hour of joining\n"
            f"• 📢 Supports broadcast messages\n\n"
            f"Add me to your group/channel and make me admin to start moderating!\n\n"
            f"Use /help to see all commands."
        )
        
        await update.message.reply_text(welcome_text)
        logger.info(f"Start command from user {user.id} in chat {chat.id if chat else 'unknown'}")
    except Exception as e:
        logger.error(f"Error in start command: {e}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    try:
        help_text = """
🤖 <b>Available Commands:</b>

<b>For Everyone:</b>
/start - Start the bot
/help - Show this help message

<b>For Admins:</b>
/broadcast - Start broadcast message collection
/send_broadcast - Send collected broadcast
/cancel_broadcast - Cancel broadcast
/stats - Show bot statistics

📝 <b>Note:</b> Make sure I have admin permissions in your groups/channels for the auto-ban feature to work properly.
        """
        await update.message.reply_text(help_text, parse_mode='HTML')
    except Exception as e:
        logger.error(f"Error in help command: {e}")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stats command"""
    try:
        user = update.effective_user
        
        # Check if user is admin
        if user.id not in ADMIN_IDS:
            await update.message.reply_text("❌ You are not authorized to use this command.")
            logger.warning(f"Unauthorized stats access attempt by user {user.id}")
            return
        
        stats_text = (
            f"📊 <b>Bot Statistics:</b>\n\n"
            f"• 👥 Tracked users: {len(user_join_times)}\n"
            f"• 💬 Active chats: {len(active_chats)}\n"
            f"• 📢 Active broadcasts: {len(broadcast_data)}\n"
            f"• 🚫 Ban duration: {BAN_DURATION_HOURS} hour(s)\n"
            f"• 👑 Admins: {len(ADMIN_IDS)}\n"
            f"• 🤖 Bot: {'🟢 Online' if application else '🔴 Offline'}"
        )
        await update.message.reply_text(stats_text, parse_mode='HTML')
        logger.info(f"Stats command executed by admin {user.id}")
    except Exception as e:
        logger.error(f"Error in stats command: {e}")

async def track_user_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Track when users join the chat"""
    try:
        if update.chat_member:
            chat = update.chat_member.chat
            user = update.chat_member.new_chat_member.user
            old_status = update.chat_member.old_chat_member.status
            new_status = update.chat_member.new_chat_member.status
            
            # User joined the chat
            if (old_status in ['left', 'kicked', 'restricted'] and 
                new_status in ['member', 'administrator', 'creator']):
                
                user_key = f"{chat.id}_{user.id}"
                user_join_times[user_key] = {
                    'join_time': datetime.now(),
                    'user_id': user.id,
                    'chat_id': chat.id,
                    'username': user.username or user.first_name,
                    'chat_title': chat.title or 'Unknown Chat'
                }
                active_chats.add(chat.id)
                
                logger.info(f"User {user.id} (@{user.username}) joined chat {chat.id} ({chat.title}) at {datetime.now()}")
                
                # Send welcome message (optional)
                try:
                    welcome_msg = f"👋 Welcome @{user.username or user.first_name} to the group! Please read the rules."
                    await context.bot.send_message(chat.id, welcome_msg)
                except Exception as e:
                    logger.warning(f"Could not send welcome message: {e}")
                    
    except Exception as e:
        logger.error(f"Error tracking user join: {e}")

async def track_user_leave(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Track when users leave and ban if within 1 hour"""
    try:
        if update.chat_member:
            chat = update.chat_member.chat
            user = update.chat_member.new_chat_member.user
            old_status = update.chat_member.old_chat_member.status
            new_status = update.chat_member.new_chat_member.status
            
            # User left or was kicked
            if (old_status in ['member', 'administrator', 'restricted'] and 
                new_status in ['left', 'kicked']):
                
                user_key = f"{chat.id}_{user.id}"
                user_data = user_join_times.get(user_key)
                
                if user_data:
                    join_time = user_data['join_time']
                    time_in_chat = datetime.now() - join_time
                    
                    # Check if user left within the ban duration
                    if time_in_chat < timedelta(hours=BAN_DURATION_HOURS):
                        try:
                            # Ban the user
                            await context.bot.ban_chat_member(
                                chat_id=chat.id,
                                user_id=user.id
                            )
                            
                            # Send ban notification
                            ban_message = (
                                f"🚫 <b>User Banned</b>\n\n"
                                f"• 👤 User: @{user.username or user.first_name}\n"
                                f"• ⏱️ Joined: {join_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                                f"• 🕒 Time in chat: {str(time_in_chat).split('.')[0]}\n"
                                f"• 📝 Reason: Left within {BAN_DURATION_HOURS} hour of joining"
                            )
                            
                            await context.bot.send_message(
                                chat_id=chat.id,
                                text=ban_message,
                                parse_mode='HTML'
                            )
                            
                            logger.info(f"Banned user {user.id} for leaving within {BAN_DURATION_HOURS} hour of joining")
                            
                        except Exception as ban_error:
                            logger.error(f"Failed to ban user {user.id}: {ban_error}")
                            # Try to send error message
                            try:
                                await context.bot.send_message(
                                    chat_id=chat.id,
                                    text=f"❌ Could not ban user @{user.username or user.first_name}. Make sure I have admin permissions."
                                )
                            except:
                                pass
                    
                    # Remove user from tracking regardless of ban
                    user_join_times.pop(user_key, None)
                    logger.info(f"User {user.id} left chat {chat.id}, removed from tracking")
                    
    except Exception as e:
        logger.error(f"Error tracking user leave: {e}")

# Broadcast functionality
async def start_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start broadcast message collection"""
    try:
        user = update.effective_user
        
        # Check if user is admin
        if user.id not in ADMIN_IDS:
            await update.message.reply_text("❌ You are not authorized to use this command.")
            return
        
        # Initialize broadcast data for this user
        broadcast_data[user.id] = {
            'messages': [],
            'start_time': datetime.now()
        }
        
        instructions = (
            "📢 <b>Broadcast Mode Started!</b>\n\n"
            "Now you can send me the messages you want to broadcast. I support:\n"
            "• 📝 Text messages\n"
            "• 🖼️ Photos with captions\n"
            "• 🎥 Videos with captions\n"
            "• 📎 Documents with captions\n"
            "• 😀 Stickers\n\n"
            "Send your messages one by one. When you're done, use:\n"
            "• /send_broadcast - To send all collected messages\n"
            "• /cancel_broadcast - To cancel and clear all messages\n\n"
            "<i>Currently collected: 0 messages</i>"
        )
        
        await update.message.reply_text(instructions, parse_mode='HTML')
        logger.info(f"Broadcast mode started by admin {user.id}")
        
    except Exception as e:
        logger.error(f"Error starting broadcast: {e}")

async def collect_broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Collect messages for broadcast"""
    try:
        user = update.effective_user
        
        # Check if user is in broadcast mode
        if user.id not in broadcast_data:
            return
        
        message = update.message
        message_data = {
            'message_id': message.message_id,
            'date': message.date,
            'chat_id': message.chat_id
        }
        
        # Handle different message types
        if message.text:
            message_data.update({
                'type': 'text',
                'content': message.text,
                'entities': message.entities
            })
            preview = f"📝 Text message: {message.text[:50]}{'...' if len(message.text) > 50 else ''}"
            
        elif message.photo:
            message_data.update({
                'type': 'photo',
                'file_id': message.photo[-1].file_id,  # Highest quality photo
                'caption': message.caption,
                'caption_entities': message.caption_entities
            })
            preview = f"🖼️ Photo" + (f" with caption: {message.caption[:30]}..." if message.caption else "")
            
        elif message.video:
            message_data.update({
                'type': 'video',
                'file_id': message.video.file_id,
                'caption': message.caption,
                'caption_entities': message.caption_entities
            })
            preview = f"🎥 Video" + (f" with caption: {message.caption[:30]}..." if message.caption else "")
            
        elif message.document:
            message_data.update({
                'type': 'document',
                'file_id': message.document.file_id,
                'caption': message.caption,
                'caption_entities': message.caption_entities
            })
            preview = f"📎 Document" + (f" with caption: {message.caption[:30]}..." if message.caption else "")
            
        elif message.sticker:
            message_data.update({
                'type': 'sticker',
                'file_id': message.sticker.file_id
            })
            preview = f"😀 Sticker"
            
        else:
            await message.reply_text("❌ Unsupported message type. Please send text, photo, video, document, or sticker.")
            return
        
        # Add message to broadcast collection
        broadcast_data[user.id]['messages'].append(message_data)
        total_messages = len(broadcast_data[user.id]['messages'])
        
        # Send confirmation
        confirmation = (
            f"✅ {preview}\n\n"
            f"📊 <b>Total collected:</b> {total_messages} message(s)\n\n"
            f"Send more messages or:\n"
            f"• /send_broadcast - To send to all chats\n"
            f"• /cancel_broadcast - To cancel"
        )
        
        await message.reply_text(confirmation, parse_mode='HTML')
        logger.info(f"Broadcast message collected by admin {user.id}, total: {total_messages}")
        
    except Exception as e:
        logger.error(f"Error collecting broadcast message: {e}")

async def send_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send broadcast to all active chats"""
    try:
        user = update.effective_user
        
        # Check if user is admin
        if user.id not in ADMIN_IDS:
            await update.message.reply_text("❌ You are not authorized to use this command.")
            return
        
        # Check if there are messages to broadcast
        if user.id not in broadcast_data or not broadcast_data[user.id]['messages']:
            await update.message.reply_text("❌ No messages to broadcast. Use /broadcast first to start collecting messages.")
            return
        
        await update.message.reply_text("🔄 Starting broadcast... This may take a while depending on the number of chats.")
        
        messages = broadcast_data[user.id]['messages']
        chats = list(active_chats)
        total_chats = len(chats)
        total_messages = len(messages)
        
        if not chats:
            await update.message.reply_text("❌ No active chats found for broadcasting.")
            return
        
        success_count = 0
        fail_count = 0
        
        # Send to each chat
        for index, chat_id in enumerate(chats):
            try:
                # Send each message to this chat
                for msg in messages:
                    if msg['type'] == 'text':
                        await context.bot.send_message(
                            chat_id=chat_id,
                            text=msg['content'],
                            entities=msg.get('entities'),
                            parse_mode='HTML'
                        )
                    elif msg['type'] == 'photo':
                        await context.bot.send_photo(
                            chat_id=chat_id,
                            photo=msg['file_id'],
                            caption=msg.get('caption'),
                            caption_entities=msg.get('caption_entities'),
                            parse_mode='HTML'
                        )
                    elif msg['type'] == 'video':
                        await context.bot.send_video(
                            chat_id=chat_id,
                            video=msg['file_id'],
                            caption=msg.get('caption'),
                            caption_entities=msg.get('caption_entities'),
                            parse_mode='HTML'
                        )
                    elif msg['type'] == 'document':
                        await context.bot.send_document(
                            chat_id=chat_id,
                            document=msg['file_id'],
                            caption=msg.get('caption'),
                            caption_entities=msg.get('caption_entities'),
                            parse_mode='HTML'
                        )
                    elif msg['type'] == 'sticker':
                        await context.bot.send_sticker(
                            chat_id=chat_id,
                            sticker=msg['file_id']
                        )
                
                success_count += 1
                logger.info(f"Broadcast sent to chat {chat_id} ({success_count}/{total_chats})")
                
                # Small delay to avoid rate limits
                await asyncio.sleep(0.5)
                
            except Exception as e:
                fail_count += 1
                logger.error(f"Failed to send broadcast to chat {chat_id}: {e}")
        
        # Clean up broadcast data
        message_count = len(broadcast_data[user.id]['messages'])
        broadcast_data.pop(user.id, None)
        
        # Send final report
        report = (
            f"📊 <b>Broadcast Completed!</b>\n\n"
            f"✅ <b>Successful:</b> {success_count} chats\n"
            f"❌ <b>Failed:</b> {fail_count} chats\n"
            f"📝 <b>Messages sent:</b> {message_count} per chat\n"
            f"📨 <b>Total deliveries:</b> {success_count * message_count}\n"
            f"⏱️ <b>Active chats:</b> {total_chats}"
        )
        
        await update.message.reply_text(report, parse_mode='HTML')
        logger.info(f"Broadcast completed by admin {user.id}. Success: {success_count}, Failed: {fail_count}")
        
    except Exception as e:
        logger.error(f"Error sending broadcast: {e}")

async def cancel_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel the broadcast process"""
    try:
        user = update.effective_user
        
        if user.id in broadcast_data:
            message_count = len(broadcast_data[user.id]['messages'])
            broadcast_data.pop(user.id)
            
            await update.message.reply_text(
                f"❌ Broadcast cancelled.\n"
                f"🗑️ {message_count} message(s) were not sent."
            )
            logger.info(f"Broadcast cancelled by admin {user.id}, {message_count} messages discarded")
        else:
            await update.message.reply_text("No active broadcast to cancel.")
            
    except Exception as e:
        logger.error(f"Error cancelling broadcast: {e}")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors in the telegram bot"""
    logger.error(f"Exception while handling an update: {context.error}")
    
    try:
        # Notify admin about the error
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=f"❌ Bot Error:\n{context.error}"
                )
            except:
                pass
    except:
        pass

# Setup all handlers
def setup_handlers():
    """Setup all telegram bot handlers"""
    try:
        # Basic commands
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("stats", stats))
        
        # Broadcast commands
        application.add_handler(CommandHandler("broadcast", start_broadcast))
        application.add_handler(CommandHandler("send_broadcast", send_broadcast))
        application.add_handler(CommandHandler("cancel_broadcast", cancel_broadcast))
        
        # Message handler for collecting broadcast messages (must be after command handlers)
        application.add_handler(MessageHandler(
            filters.ALL & ~filters.COMMAND,
            collect_broadcast_message
        ))
        
        # Chat member handlers for tracking joins/leaves
        application.add_handler(ChatMemberHandler(track_user_join, ChatMemberHandler.CHAT_MEMBER))
        application.add_handler(ChatMemberHandler(track_user_leave, ChatMemberHandler.CHAT_MEMBER))
        
        # Error handler
        application.add_error_handler(error_handler)
        
        logger.info("✅ All bot handlers setup successfully")
        
    except Exception as e:
        logger.error(f"❌ Failed to setup bot handlers: {e}")

# Initialize the bot
setup_handlers()

# For local testing with polling
if __name__ == '__main__':
    logger.info("Starting bot in polling mode...")
    application.run_polling()