import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL:
    DB_DSN = DATABASE_URL
else:
    DB_DSN = os.getenv("DATABASE_PATH", "data/database.db")