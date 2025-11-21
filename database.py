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
        self.credit_codes = db.credit_codes
        
        # Create indexes
        self.users.create_index("user_id", unique=True)
        self.referral_codes.create_index("code", unique=True)
        self.referral_codes.create_index("expires_at", expireAfterSeconds=0)
        self.credit_codes.create_index("code", unique=True)

    # ... [Previous methods remain unchanged] ...

    async def generate_credit_code(self, code: str, amount: int, generated_by: int):
        """Generate a one-time credit code"""
        self.credit_codes.insert_one({
            "code": code,
            "amount": amount,
            "generated_by": generated_by,
            "used": False,
            "used_by": None,
            "created_at": datetime.now()
        })

    async def redeem_credit_code(self, code: str, user_id: int):
        """Redeem a credit code and award credits"""
        code_doc = self.credit_codes.find_one({
            "code": code,
            "used": False
        })
        
        if not code_doc:
            return False, "Invalid or already used code"
        
        # Mark as used
        self.credit_codes.update_one(
            {"code": code},
            {"$set": {"used": True, "used_by": user_id}}
        )
        
        # Add credits to user
        self.users.update_one(
            {"user_id": user_id},
            {"$inc": {"total_credits": code_doc["amount"]}}
        )
        
        return True, f"{code_doc['amount']} credits added to your account!"

    async def has_user_claimed_referral(self, user_id: int) -> bool:
        """Check if user has ever claimed a referral"""
        user = await self.get_user(user_id)
        return user and user.get("has_claimed_referral", False)

    async def mark_user_claimed_referral(self, user_id: int):
        """Mark user as having claimed a referral (one-time only)"""
        self.users.update_one(
            {"user_id": user_id},
            {"$set": {"has_claimed_referral": True}}
        )

db_helper = Database()
