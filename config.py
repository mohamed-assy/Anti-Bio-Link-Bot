# Anti Bio Link Bot
# Group: https://t.me/english_world_chatting

import re
import os
from dotenv import load_dotenv

load_dotenv()

API_ID    = os.getenv("API_ID")
API_HASH  = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

BAN_DURATION_DAYS = int(os.getenv("BAN_DURATION_DAYS", 30))

# Telegram links including invite links
URL_PATTERN = re.compile(
    r'(https?://)?(www\.)?(t\.me|telegram\.me|telegram\.dog)/[+a-zA-Z0-9_]+'
)
