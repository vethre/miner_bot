# bot/main.py
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from bot.utils.config import BOT_TOKEN
from bot.db import init_db, db
from bot.handlers import register_handlers

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    logger.info("🔌 Ініціалізую бота...")
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    # Підключаємо БД (Supabase)
    await init_db()

    register_handlers(dp)

    logger.info("🚀 Стартую polling...")
    await dp.start_polling(bot)

    # По завершенню (якщо кине SIGTERM чи Exception)
    await db.disconnect()
    logger.info("📴 Polling завершено")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.exception(f"🔥 Бот звалився з помилкою: {e}")
