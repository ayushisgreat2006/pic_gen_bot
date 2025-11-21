import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    DATABASE_NAME = os.getenv("DATABASE_NAME", "image_bot")
    FORCE_JOIN_CHANNEL = os.getenv("FORCE_JOIN_CHANNEL")  # @channelusername
    OWNER_ID = int(os.getenv("OWNER_ID", "123456789"))
    LOG_GROUP_ID = int(os.getenv("LOG_GROUP_ID", "-1001234567890"))
    API_URL = "https://nsfw.drsudo.workers.dev/?img="
