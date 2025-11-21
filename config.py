import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    DATABASE_NAME = os.getenv("DATABASE_NAME", "image_bot")
    FORCE_JOIN_CHANNEL = os.getenv("FORCE_JOIN_CHANNEL")  # @channelusername
    # In config.py, replace OWNER_ID line with this:

# Validate OWNER_ID
_raw_owner_id = os.getenv("OWNER_ID", "8554640355")
try:
    OWNER_ID = int(_raw_owner_id)
    print(f"✅ OWNER_ID set to: {OWNER_ID}")
except (ValueError, TypeError):
    print(f"❌ Invalid OWNER_ID: '{_raw_owner_id}'. Using default 8554640355")
    OWNER_ID = 123456789  # Fallback ID
    LOG_GROUP_ID = int(os.getenv("LOG_GROUP_ID", "-1001234567890"))
    API_URL = "https://nsfw.drsudo.workers.dev/?img="
