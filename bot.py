import asyncio
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    filters, ContextTypes, ConversationHandler
)
from telegram.error import Forbidden, BadRequest
import requests
from config import Config
from database import db_helper
from datetime import datetime

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# States for conversation
BROADCAST = 0

async def check_channel_membership(user_id, context):
    if not Config.FORCE_JOIN_CHANNEL:
        return True
        
    try:
        member = await context.bot.get_chat_member(
            Config.FORCE_JOIN_CHANNEL,
            user_id
        )
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    
    # Create user if not exists
    existing_user = await db_helper.get_user(user.id)
    if not existing_user:
        await db_helper.create_user(user.id, user.username)
        await db_helper.log_to_group(
            context.bot,
            f"#NewUser\n"
            f"ID: {user.id}\n"
            f"Username: @{user.username}\n"
            f"Total Users: {len(await db_helper.get_all_users())}"
        )
    
    # Check channel membership
    if not await check_channel_membership(user.id, context):
        keyboard = [[InlineKeyboardButton(
            "Join Channel", 
            url=f"https://t.me/{Config.FORCE_JOIN_CHANNEL.strip('@')}"
        )]]
        await update.message.reply_text(
            "⚠️ You must join the channel to use this bot!",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    # Show main menu
    keyboard = [
        [InlineKeyboardButton("Generate Image", callback_data="gen")],
        [InlineKeyboardButton("My Stats", callback_data="stats")],
        [InlineKeyboardButton("Refer & Earn", callback_data="refer")]
    ]
    
    await update.message.reply_text(
        f"👋 Hello {user.first_name}!\n\n"
        f"📸 <b>Image Generation Bot</b>\n\n"
        f"🎁 <b>Daily Limit:</b> 10 images\n"
        f"🎟️ <b>Referral Bonus:</b> 20 credits each\n\n"
        f"Use /help to see all commands",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
<b>📖 Available Commands:</b>

🎨 <b>Image Generation:</b>
/gen &lt;query&gt; - Generate an image

💰 <b>Credit Codes:</b>
/redeem &lt;code&gt; - Redeem credit code

📊 <b>User Commands:</b>
/start - Start the bot
/help - Show this help
/refer - Get referral link
/claim &lt;code&gt; - Claim referral code (⚠️ ONCE PER USER)
/stats - View your stats

👑 <b>Admin Commands:</b>
/gencode &lt;amount&gt; &lt;code&gt; - Generate credit code
/whitelist &lt;user_id&gt; - Add unlimited user
/rm_whitelist &lt;user_id&gt; - Remove from whitelist
/broadcast - Broadcast message
/stats - View bot statistics

👑 <b>Owner Commands:</b>
/add_admin &lt;user_id&gt; - Add admin
/rm_admin &lt;user_id&gt; - Remove admin
"""
    await update.message.reply_text(help_text, parse_mode="HTML")

async def generate_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # Check channel membership
    if not await check_channel_membership(user.id, context):
        await update.message.reply_text(
            "⚠️ Please join the channel first using /start"
        )
        return
    
    # Check permissions and limits
    can_gen, reason = await db_helper.can_generate(user.id)
    if not can_gen:
        await update.message.reply_text(f"❌ {reason}")
        return
    
    if not context.args:
        await update.message.reply_text("⚠️ Usage: /gen &lt;your prompt&gt;")
        return
    
    query = " ".join(context.args)
    await update.message.reply_text("🎨 Generating image...")
    
    try:
        # Call API
        response = requests.get(f"{Config.API_URL}{query}", timeout=30)
        data = response.json()
        
        if data.get("status") != "success":
            await update.message.reply_text("❌ Generation failed. Try again.")
            return
        
        image_url = data["image_link"].strip()
        
        # Send image
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=image_url,
            caption=f"✅ <b>Generated!</b>\n\nPrompt: <code>{query}</code>",
            parse_mode="HTML"
        )
        
        # Use credit
        await db_helper.use_credit(user.id)
        
        # Log to group
        await db_helper.log_to_group(
            context.bot,
            f"#ImageGenerated\n"
            f"User: {user.mention_html()}\n"
            f"ID: {user.id}\n"
            f"Prompt: {query}\n"
            f"URL: {image_url}"
        )
        
    except Exception as e:
        logger.error(f"Generation error: {e}")
        await update.message.reply_text("❌ Error generating image.")
        await db_helper.log_to_group(
            context.bot,
            f"#Error\nUser: {user.id}\nError: {str(e)}"
        )

async def refer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    code, expires_at = await db_helper.generate_referral_code(user.id)
    expires_str = expires_at.strftime("%H:%M:%S")
    
    await update.message.reply_text(
        f"🎟️ <b>Your Referral Code:</b>\n\n"
        f"<code>{code}</code>\n\n"
        f"⏰ Expires at: {expires_str}\n"
        f"📤 Share this code with friends!\n\n"
        f"Both will get 20 credits when claimed!",
        parse_mode="HTML"
    )

async def claim(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if not context.args:
        await update.message.reply_text("⚠️ Usage: /claim &lt;code&gt;")
        return
    
    code = context.args[0]
    success, message = await db_helper.claim_referral(code, user.id)
    
    if success:
        await update.message.reply_text(f"✅ {message}")
        await db_helper.log_to_group(
            context.bot,
            f"#ReferralClaimed\n"
            f"User: {user.mention_html()}\n"
            f"Code: {code}"
        )
    else:
        await update.message.reply_text(f"❌ {message}")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = await db_helper.get_user(user.id)
    
    if not user_data:
        await update.message.reply_text("Use /start first!")
        return
    
    daily_used = user_data.get("daily_count", 0)
    credits = user_data.get("total_credits", 0)
    role = user_data.get("role", "user")
    
    await update.message.reply_text(
        f"📊 <b>Your Stats</b>\n\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"👤 Username: @{user.username}\n"
        f"🎖️ Role: {role.upper()}\n"
        f"🎨 Daily Used: {daily_used}/10\n"
        f"🎟️ Credits: {credits}\n"
        f"📅 Last Reset: {user_data.get('last_reset')}",
        parse_mode="HTML"
    )

# Admin Commands
async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != Config.OWNER_ID:
        await update.message.reply_text("❌ Only owner can use this!")
        return
    
    if not context.args:
        await update.message.reply_text("⚠️ Usage: /add_admin &lt;user_id&gt;")
        return
    
    try:
        user_id = int(context.args[0])
        await db_helper.add_admin(user_id)
        await update.message.reply_text(f"✅ User {user_id} added as admin")
        await db_helper.log_to_group(
            context.bot,
            f"#AdminAdded\nUser ID: {user_id}\nBy: {update.effective_user.id}"
        )
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID")

async def remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != Config.OWNER_ID:
        await update.message.reply_text("❌ Only owner can use this!")
        return
    
    if not context.args:
        await update.message.reply_text("⚠️ Usage: /rm_admin &lt;user_id&gt;")
        return
    
    try:
        user_id = int(context.args[0])
        await db_helper.remove_admin(user_id)
        await update.message.reply_text(f"✅ User {user_id} removed from admin")
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID")

async def whitelist_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if not (await db_helper.is_admin(user.id) or await db_helper.is_owner(user.id)):
        await update.message.reply_text("❌ Admin only!")
        return
    
    if not context.args:
        await update.message.reply_text("⚠️ Usage: /whitelist &lt;user_id&gt;")
        return
    
    try:
        user_id = int(context.args[0])
        await db_helper.add_whitelist(user_id)
        await update.message.reply_text(f"✅ User {user_id} whitelisted")
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID")

async def remove_whitelist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if not (await db_helper.is_admin(user.id) or await db_helper.is_owner(user.id)):
        await update.message.reply_text("❌ Admin only!")
        return
    
    if not context.args:
        await update.message.reply_text("⚠️ Usage: /rm_whitelist &lt;user_id&gt;")
        return
    
    try:
        user_id = int(context.args[0])
        await db_helper.remove_whitelist(user_id)
        await update.message.reply_text(f"✅ User {user_id} removed from whitelist")
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID")

async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if not (await db_helper.is_admin(user.id) or await db_helper.is_owner(user.id)):
        await update.message.reply_text("❌ Admin only!")
        return
    
    await update.message.reply_text(
        "📢 Send me the message to broadcast. "
        "Send /cancel to abort."
    )
    return BROADCAST

async def broadcast_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if not (await db_helper.is_admin(user.id) or await db_helper.is_owner(user.id)):
        return ConversationHandler.END
    
    broadcast_msg = update.effective_message
    users = await db_helper.get_all_users()
    
    success = 0
    failed = 0
    
    await update.message.reply_text(f"📤 Broadcasting to {len(users)} users...")
    
    for user_doc in users:
        try:
            await broadcast_msg.copy(user_doc["user_id"])
            success += 1
            await asyncio.sleep(0.05)  # Avoid flood limits
        except (Forbidden, BadRequest):
            failed += 1
        except Exception as e:
            logger.error(f"Broadcast error: {e}")
            failed += 1
    
    await update.message.reply_text(
        f"✅ Broadcast Complete!\n"
        f"📤 Sent: {success}\n"
        f"❌ Failed: {failed}"
    )
    
    await db_helper.log_to_group(
        context.bot,
        f"#Broadcast\n"
        f"By: {user.mention_html()}\n"
        f"Sent: {success}\n"
        f"Failed: {failed}"
    )
    
    return ConversationHandler.END

async def broadcast_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Broadcast cancelled")
    return ConversationHandler.END

async def bot_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if not (await db_helper.is_admin(user.id) or await db_helper.is_owner(user.id)):
        await update.message.reply_text("❌ Admin only!")
        return
    
    users = await db_helper.get_all_users()
    
    role_counts = {"user": 0, "admin": 0, "whitelist": 0}
    for u in users:
        role_counts[u.get("role", "user")] += 1
    
    await update.message.reply_text(
        f"📊 <b>Bot Statistics</b>\n\n"
        f"👥 Total Users: {len(users)}\n"
        f"👤 Normal Users: {role_counts['user']}\n"
        f"👮 Admins: {role_counts['admin']}\n"
        f"⭐ Whitelisted: {role_counts['whitelist']}",
        parse_mode="HTML"
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "gen":
        await query.message.reply_text("Use /gen &lt;query&gt; to generate an image")
    elif query.data == "stats":
        await stats(update, context)
    elif query.data == "refer":
        await refer(update, context)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")
    if update and update.effective_user:
        await db_helper.log_to_group(
            context.bot,
            f"#Error\n"
            f"User: {update.effective_user.id}\n"
            f"Error: {str(context.error)}"
        )

def main():
    application = Application.builder().token(Config.BOT_TOKEN).build()
    
    # Command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("gen", generate_image))
    application.add_handler(CommandHandler("refer", refer))
    application.add_handler(CommandHandler("claim", claim))
    application.add_handler(CommandHandler("stats", stats))
    
    # Owner commands
    application.add_handler(CommandHandler("add_admin", add_admin))
    application.add_handler(CommandHandler("rm_admin", remove_admin))
    
    # Admin commands
    application.add_handler(CommandHandler("whitelist", whitelist_user))
    application.add_handler(CommandHandler("rm_whitelist", remove_whitelist))
    application.add_handler(CommandHandler("bot_stats", bot_stats))


    # Add these new command handlers

async def generate_credit_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate a credit code: /gencode <amount> <code>"""
    user = update.effective_user
    
    if not (await db_helper.is_admin(user.id) or await db_helper.is_owner(user.id)):
        await update.message.reply_text("❌ Admin/Owner only!")
        return
    
    if len(context.args) != 2:
        await update.message.reply_text("⚠️ Usage: /gencode <amount> <code>")
        return
    
    try:
        amount = int(context.args[0])
        code = context.args[1]
        
        if amount <= 0:
            await update.message.reply_text("❌ Amount must be positive!")
            return
        
        await db_helper.generate_credit_code(code, amount, user.id)
        await update.message.reply_text(
            f"✅ Credit code generated!\n\n"
            f"Code: <code>{code}</code>\n"
            f"Amount: {amount} credits",
            parse_mode="HTML"
        )
        
        await db_helper.log_to_group(
            context.bot,
            f"#CreditCodeGenerated\n"
            f"By: {user.mention_html()}\n"
            f"Code: {code}\n"
            f"Amount: {amount}"
        )
        
    except ValueError:
        await update.message.reply_text("❌ Amount must be a number")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: Code already exists")

async def redeem_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Redeem a credit code: /redeem <code>"""
    user = update.effective_user
    
    if not context.args:
        await update.message.reply_text("⚠️ Usage: /redeem <code>")
        return
    
    code = context.args[0]
    success, message = await db_helper.redeem_credit_code(code, user.id)
    
    if success:
        await update.message.reply_text(f"🎉 {message}")
        await db_helper.log_to_group(
            context.bot,
            f"#CodeRedeemed\n"
            f"User: {user.mention_html()} (ID: {user.id})\n"
            f"Code: {code}\n"
            f"Result: {message}"
        )
    else:
        await update.message.reply_text(f"❌ {message}")

# Modified claim command with one-time check
async def claim(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Claim referral code (one-time only per user)"""
    user = update.effective_user
    
    # Check if user has already claimed a referral
    if await db_helper.has_user_claimed_referral(user.id):
        await update.message.reply_text(
            "❌ You can only claim one referral code in your lifetime!"
        )
        return
    
    if not context.args:
        await update.message.reply_text("⚠️ Usage: /claim <code>")
        return
    
    code = context.args[0]
    success, message = await db_helper.claim_referral(code, user.id)
    
    if success:
        # Mark user as having claimed a referral
        await db_helper.mark_user_claimed_referral(user.id)
        
        await update.message.reply_text(f"✅ {message}")
        await db_helper.log_to_group(
            context.bot,
            f"#ReferralClaimed\n"
            f"User: {user.mention_html()} (ID: {user.id})\n"
            f"Code: {code}\n"
            f"Result: {message}"
        )
    else:
        await update.message.reply_text(f"❌ {message}")

# ... [Previous commands remain unchanged] ...

def main():
    application = Application.builder().token(Config.BOT_TOKEN).build()
    
    # Command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("gen", generate_image))
    application.add_handler(CommandHandler("gencode", generate_credit_code))  # NEW
    application.add_handler(CommandHandler("redeem", redeem_code))            # NEW
    application.add_handler(CommandHandler("refer", refer))
    application.add_handler(CommandHandler("claim", claim))
    application.add_handler(CommandHandler("stats", stats))
    
    # Owner commands
    application.add_handler(CommandHandler("add_admin", add_admin))
    application.add_handler(CommandHandler("rm_admin", remove_admin))
    
    # Admin commands
    application.add_handler(CommandHandler("whitelist", whitelist_user))
    application.add_handler(CommandHandler("rm_whitelist", remove_whitelist))
    application.add_handler(CommandHandler("bot_stats", bot_stats))
    
    # Broadcast conversation
    broadcast_conv = ConversationHandler(
        entry_points=[CommandHandler("broadcast", broadcast_start)],
        states={
            BROADCAST: [MessageHandler(filters.ALL & ~filters.COMMAND, broadcast_receive)]
        },
        fallbacks=[
            CommandHandler("cancel", broadcast_cancel),
            CommandHandler("broadcast", broadcast_start)
        ]
    )
    application.add_handler(broadcast_conv)
    
    # Callback query handler
    application.add_handler(update.callback_query_handler(button_handler))
    
    # Error handler
    application.add_error_handler(error_handler)
    
    application.run_polling()

if __name__ == "__main__":
    main()

    
    
    # Broadcast conversation
    broadcast_conv = ConversationHandler(
        entry_points=[CommandHandler("broadcast", broadcast_start)],
        states={
            BROADCAST: [MessageHandler(filters.ALL & ~filters.COMMAND, broadcast_receive)]
        },
        fallbacks=[
            CommandHandler("cancel", broadcast_cancel),
            CommandHandler("broadcast", broadcast_start)
        ]
    )
    application.add_handler(broadcast_conv)
    
    # Callback query handler
    application.add_handler(update.callback_query_handler(button_handler))
    
    # Error handler
    application.add_error_handler(error_handler)
    
    # Start bot
    application.run_polling()

if __name__ == "__main__":
    main()
