# bot/main.py
import asyncio
import aiocron, pytz, datetime
import logging
from zoneinfo import ZoneInfo
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from bot.utils.config import BOT_TOKEN, DB_DSN
from bot.db import init_db, db
from bot.db_local import add_xp, init_local
from bot.handlers import register_handlers
from bot.utils.autodelete import auto_cleanup_task

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CEST = pytz.timezone("Europe/Prague")
UTC = ZoneInfo("UTC")
ENERGY_MAX = 100
HUNGER_MAX = 100

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

    aiocron.crontab(
        '0 */1 * * *',
        func=hourly_pass_xp,
        start=True
    )

    aiocron.crontab(
        '*/30 * * * *',  # кожні 30 хвилин
        func=restore_energy,
        start=True
    )

    aiocron.crontab(
        '0 * * * *',  # кожну годину на 00 хв
        func=reduce_hunger,
        start=True
    )

    async def _on_startup(bot: Bot):
        asyncio.create_task(auto_cleanup_task(bot, db), name="auto-delete")

    dp.startup.register(_on_startup)

    logger.info("🚀 Стартую polling...")
    await dp.start_polling(BOT)

    # По завершенню (якщо кине SIGTERM чи Exception)
    await db.disconnect()
    logger.info("📴 Polling завершено")

async def restore_energy():
    logger.debug("[CRON] Відновлення енергії")
    await db.execute("""
        UPDATE progress_local
           SET energy = LEAST(:max, energy + :step),
               last_energy_update = :now
         WHERE energy < :max
    """, {
        "step": 10,
        "max": ENERGY_MAX,
        "now": datetime.datetime.now(tz=UTC)
    })

async def reduce_hunger():
    logger.debug("[CRON] Зменшення голоду")
    await db.execute("""
        UPDATE progress_local
           SET hunger = GREATEST(0, hunger - :step),
               last_hunger_update = :now
         WHERE hunger > 0
    """, {
        "step": 10,
        "now": datetime.datetime.now(tz=UTC)
    })

async def daily_reward():
    if BOT is None:
        return

    today = datetime.date.today()

    # берём ВСЕ группы, которые бот «знает»
    groups = await db.fetch_all("SELECT chat_id FROM groups")

    for g in groups:
        chat_id = g["chat_id"]

        # одна выборка — все юзеры ЭТОГО чата, кому ещё не выдавали бонус
        rows = await db.fetch_all("""
            SELECT pl.user_id,
                   pl.level,
                   COALESCE(b.coins,0)   AS coins,
                   u.username
            FROM   progress_local pl
                   LEFT JOIN balance_local b
                          ON b.chat_id = pl.chat_id AND b.user_id = pl.user_id
                   LEFT JOIN users u       -- только ради username
                          ON u.user_id = pl.user_id
            WHERE  pl.chat_id   = :chat
              AND  (pl.last_daily IS NULL
                    OR pl.last_daily < :today)
        """, {"chat": chat_id, "today": today})

        if not rows:
            continue

        messages = []
        async with db.transaction():
            for r in rows:
                lvl = r["level"]
                # — простенькая шкала —
                if   lvl < 5:   money, xp =  60, 40
                elif lvl < 10:  money, xp =  70, 50
                elif lvl < 15:  money, xp = 130, 60
                else:           money, xp = 300, 70

                # баланс
                await db.execute("""
                    INSERT INTO balance_local(chat_id,user_id,coins)
                         VALUES(:c,:u,:m)
                    ON CONFLICT (chat_id,user_id) DO
                         UPDATE SET coins = balance_local.coins + :m
                """, {"c": chat_id, "u": r["user_id"], "m": money})

                # XP
                await add_xp(chat_id, r["user_id"], xp)

                # отметка «бонус получен»
                await db.execute("""
                    UPDATE progress_local
                       SET last_daily = :today
                     WHERE chat_id=:c AND user_id=:u
                """, {"today": today, "c": chat_id, "u": r["user_id"]})

                # красивый mention
                nick = r["username"]
                mention = f"@{nick}" if nick else f'<a href="tg://user?id={r["user_id"]}">шахтёр</a>'
                messages.append(f"{mention} →  +{money}💰  +{xp} XP")

        # рассылаем готовый список только в эту группу
        try:
            text = (
                f"🎁 <b>Ежедневный бонус {today.strftime('%d.%m.%Y')}</b>\n"
                + "\n".join(messages)
            )
            await BOT.send_message(chat_id, text, parse_mode="HTML")
        except Exception:
            pass  # группа могла запретить боту писать


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
