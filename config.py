# config.py
import os
from dotenv import load_dotenv

load_dotenv()

def get_int_env(key: str, default: int = 0) -> int:
    """Safely get integer environment variable"""
    value = os.getenv(key)
    try:
        return int(value) if value else default
    except (ValueError, TypeError):
        print(f"⚠️  Invalid {key}: '{value}'. Using default: {default}")
        return default

class Config:
    # Bot Configuration
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    
    # Database
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    DATABASE_NAME = os.getenv("DATABASE_NAME", "image_bot")
    
    # Required IDs (with validation)
    OWNER_ID = get_int_env("OWNER_ID", 123456789)  # CHANGE DEFAULT TO YOUR ID
    
    # Optional but recommended
    FORCE_JOIN_CHANNEL = os.getenv("FORCE_JOIN_CHANNEL", "")  # Can be empty
    
    # Convert to int, handle errors
    LOG_GROUP_ID = get_int_env("LOG_GROUP_ID", -1001234567890)
    
    # API
    API_URL = "https://nsfw.drsudo.workers.dev/?img="
    
    # Validate critical settings
    @classmethod
    def validate(cls):
        errors = []
        if not cls.BOT_TOKEN:
            errors.append("❌ BOT_TOKEN is missing")
        if not cls.MONGO_URI:
            errors.append("❌ MONGO_URI is missing")
        
        print(f"✅ Configuration Loaded:")
        print(f"   Owner ID: {cls.OWNER_ID}")
        print(f"   Log Group: {cls.LOG_GROUP_ID}")
        print(f"   Force Join: {cls.FORCE_JOIN_CHANNEL or 'Disabled'}")
        
        if errors:
            print("\n".join(errors))
            return False
        return True

# Validate on import
Config.validate()
