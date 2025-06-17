# bot/main.py
import asyncio
import aiocron, pytz, datetime
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from bot.utils.config import BOT_TOKEN, DB_DSN
from bot.db import init_db, db
from bot.handlers import register_handlers

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CEST = pytz.timezone("Europe/Prague")
BOT: Bot | None = None

async def main():
    logger.info(f"▶️ Using DB_DSN: {DB_DSN!r}")
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

@aiocron.crontab('*/1 * * * *')
async def daily_reward():
    if BOT is None:
        return
    now  = datetime.datetime.now(tz=CEST)
    today= now.date()

    async with db.transaction():
        users = await db.fetch_all("SELECT user_id, level, last_daily FROM users")
        for u in users:
            if u["last_daily"].date() == today:
                continue  # вже видано

            # визначаємо суму
            lvl = u["level"]
            if lvl < 5:   money, xp = 60, 40
            elif lvl <10: money, xp =70, 50
            elif lvl <15: money, xp =130, 60
            else:         money, xp =300, 70

            await db.execute(
                """
                UPDATE users
                   SET balance = balance + :m,
                       xp      = xp + :xp,
                       last_daily = :now
                 WHERE user_id = :uid
                """,
                {"m": money, "xp": xp, "now": now, "uid": u["user_id"]}
            )

            # сповіщаємо юзера
            try:
                await BOT.send_message(
                    u["user_id"],
                    f"🎁 Щоденний бонус!\n+{money} монет, +{xp} XP. Гарного копання!"
                )
            except Exception:
                pass 

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.exception(f"🔥 Бот звалився з помилкою: {e}")
