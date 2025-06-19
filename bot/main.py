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
from bot.db_local import init_local
from bot.handlers import register_handlers
from bot.utils.autodelete import auto_cleanup_task

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CEST = pytz.timezone("Europe/Prague")

async def main():
    logger.info(f"▶️ Using DB_DSN: {DB_DSN!r}")
    logger.info("🔌 Ініціалізую бота...")
    global BOT
    BOT = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    # Підключаємо БД ()
    await init_db()
    await init_local()

    register_handlers(dp)

    aiocron.crontab(
        '0 7 * * *',          # 07:00 UTC ≈ 09:00 CEST
        func=daily_reward,
        start=True            # одразу активувати
    )

    async def _on_startup(BOT):
        asyncio.create_task(auto_cleanup_task(BOT, db))

    dp.startup.register(_on_startup)

    logger.info("🚀 Стартую polling...")
    await dp.start_polling(BOT)

    # По завершенню (якщо кине SIGTERM чи Exception)
    await db.disconnect()
    logger.info("📴 Polling завершено")

async def daily_reward():
    logger.debug("[CRON-DEBUG] tick")

    if BOT is None:
        return

    now   = datetime.datetime.utcnow()
    today = now.date()

    msgs = []        # сюди складемо строки для групи

    async with db.transaction():
        users = await db.fetch_all("SELECT user_id, level, username, last_daily FROM users")
        for u in users:
            if u["last_daily"].date() == today:
                continue

            # — сума бонусу —
            lvl = u["level"]
            if lvl < 5:   money, xp = 60, 40
            elif lvl <10: money, xp = 70, 50
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

            # — формуємо красивий mention —
            nick = u["username"]
            if nick:
                mention = f"@{nick}"
            else:
                mention = f'<a href="tg://user?id={u["user_id"]}">{u["full_name"]}</a>'

            msgs.append(f"{mention}  →  +{money}💰 +{xp} XP")

    if msgs:
        text = "🎁 <b>Щоденний бонус {}</b>\n".format(today.strftime('%d.%m.%Y')) + "\n".join(msgs)
        groups = await db.fetch_all("SELECT chat_id FROM groups")
        for g in groups:
            try:
                await BOT.send_message(g["chat_id"], text, parse_mode="HTML")
            except Exception:
                pass 
    logger.info("🎁 Daily reward batch complete")

@aiocron.crontab('0 * * * *')  # кожну годину на початку
async def hourly_pass_xp():
    now = datetime.datetime.utcnow()
    # даємо +10 XP всім з активним pass_expires > now
    await db.execute(
        """
        UPDATE progress_local
           SET xp = xp + 10
         WHERE cave_pass = TRUE
           AND pass_expires > :now
        """,
        {"now": now}
    )

# одразу під @aiocron.crontab …
    logger.debug(f"[CRON-DEBUG] BOT is {BOT!r}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.exception(f"🔥 Бот звалився з помилкою: {e}")
