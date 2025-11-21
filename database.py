from pymongo import MongoClient
from datetime import datetime, timedelta
import uuid
from config import Config

client = MongoClient(Config.MONGO_URI)
db = client[Config.DATABASE_NAME]

class Database:
    def __init__(self):
        self.users = db.users
        self.referral_codes = db.referral_codes
        
        # Create indexes
        self.users.create_index("user_id", unique=True)
        self.referral_codes.create_index("code", unique=True)
        self.referral_codes.create_index("expires_at", expireAfterSeconds=0)

    async def get_user(self, user_id):
        return self.users.find_one({"user_id": user_id})

    async def create_user(self, user_id, username, referrer_id=None):
        user_data = {
            "user_id": user_id,
            "username": username,
            "role": "user",  # user, admin, whitelist
            "daily_count": 0,
            "total_credits": 20 if referrer_id else 10,
            "last_reset": datetime.now().date().isoformat(),
            "joined_channels": [],
            "created_at": datetime.now()
        }
        if referrer_id:
            user_data["referred_by"] = referrer_id
        self.users.insert_one(user_data)
        return user_data

    async def update_daily_count(self, user_id):
        today = datetime.now().date().isoformat()
        self.users.update_one(
            {"user_id": user_id, "last_reset": {"$ne": today}},
            {"$set": {"daily_count": 0, "last_reset": today}}
        )
        self.users.update_one(
            {"user_id": user_id},
            {"$inc": {"daily_count": 1}}
        )

    async def can_generate(self, user_id):
        user = await self.get_user(user_id)
        if not user: 
            return False, "User not found. Use /start first."
        
        if user.get("role") == "whitelist":
            return True, None
            
        # Check daily count
        today = datetime.now().date().isoformat()
        if user.get("last_reset") != today:
            await self.users.update_one(
                {"user_id": user_id},
                {"$set": {"daily_count": 0, "last_reset": today}}
            )
            user["daily_count"] = 0
            
        if user["daily_count"] >= 10 and user["total_credits"] <= 0:
            return False, "Daily limit reached! Use /refer to earn credits."
            
        return True, None

    async def use_credit(self, user_id):
        user = await self.get_user(user_id)
        if user.get("role") == "whitelist":
            return True
            
        if user["total_credits"] > 0:
            self.users.update_one(
                {"user_id": user_id},
                {"$inc": {"total_credits": -1}}
            )
        else:
            await self.update_daily_count(user_id)
        return True

    async def add_credits(self, user_id, amount):
        self.users.update_one(
            {"user_id": user_id},
            {"$inc": {"total_credits": amount}}
        )

    async def generate_referral_code(self, user_id):
        code = str(uuid.uuid4())[:8]
        expires_at = datetime.now() + timedelta(minutes=15)
        
        self.referral_codes.insert_one({
            "code": code,
            "generated_by": user_id,
            "used": False,
            "used_by": None,
            "expires_at": expires_at
        })
        return code, expires_at

    async def claim_referral(self, code, user_id):
        referral = self.referral_codes.find_one({
            "code": code,
            "used": False,
            "expires_at": {"$gt": datetime.now()}
        })
        
        if not referral:
            return False, "Invalid or expired code"
            
        # Mark as used
        self.referral_codes.update_one(
            {"code": code},
            {"$set": {"used": True, "used_by": user_id}}
        )
        
        # Add 20 credits to both users
        await self.add_credits(referral["generated_by"], 20)
        await self.add_credits(user_id, 20)
        
        return True, "Referral claimed! Both users got 20 credits"

    async def is_admin(self, user_id):
        user = await self.get_user(user_id)
        return user and user.get("role") in ["admin", "whitelist"] if user else False

    async def is_owner(self, user_id):
        return user_id == Config.OWNER_ID

    async def add_admin(self, user_id):
        self.users.update_one(
            {"user_id": user_id},
            {"$set": {"role": "admin"}},
            upsert=True
        )

    async def remove_admin(self, user_id):
        self.users.update_one(
            {"user_id": user_id},
            {"$set": {"role": "user"}}
        )

    async def add_whitelist(self, user_id):
        self.users.update_one(
            {"user_id": user_id},
            {"$set": {"role": "whitelist"}},
            upsert=True
        )

    async def remove_whitelist(self, user_id):
        self.users.update_one(
            {"user_id": user_id},
            {"$set": {"role": "user"}}
        )

    async def get_all_users(self):
        return list(self.users.find({}, {"_id": 0, "user_id": 1, "username": 1, "role": 1}))

    async def log_to_group(self, bot, message):
        try:
            await bot.send_message(
                Config.LOG_GROUP_ID,
                message,
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"Log failed: {e}")

db_helper = Database()
