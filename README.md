# Telegram Image Generation Bot

## Setup

1. Clone repo
2. Copy `.env.example` to `.env` and fill values
3. Create MongoDB cluster
4. Create bot via @BotFather
5. Add bot to log group with admin rights
6. Deploy to Railway

### Environment Variables
- `BOT_TOKEN`: Bot token
- `MONGO_URI`: MongoDB connection string
- `DATABASE_NAME`: Database name
- `FORCE_JOIN_CHANNEL`: Channel username for force join
- `OWNER_ID`: Your Telegram user ID
- `LOG_GROUP_ID`: Private group ID for logs

## Commands
- `/gen &lt;prompt&gt;` - Generate image
- `/refer` - Get referral code
- `/claim &lt;code&gt;` - Claim referral
- `/stats` - User stats
- `/bot_stats` - Bot stats (admin)
