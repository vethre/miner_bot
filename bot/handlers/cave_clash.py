"""
Cave Clash core — season reset + rewards.
Все, что касается выпадения лута из Cave/Clash Case, теперь живёт в bot/handlers/cases.py.
Здесь мы только:
• считаем очки
• по понедельникам (10:00 Kyiv) раздаём награды (кейсы + голда + XP)
• публикуем финальный топ и обнуляем clash_points
"""

from __future__ import annotations

from zoneinfo import ZoneInfo

from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import Message
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from bot.db_local import db, add_item, add_money, add_xp

# ──────────────────────────────────────────────
# Globals
# ──────────────────────────────────────────────
router = Router()
scheduler = AsyncIOScheduler()

# 🏆 Награды TOP‑3
REWARD_TABLE = [
    {"clash_case": 3, "coins": 1000, "xp": 300},  # 🥇
    {"clash_case": 2, "coins": 700,  "xp": 250},  # 🥈
    {"clash_case": 1, "coins": 400,  "xp": 200},  # 🥉
]
# 🕳️ Утешительный пакет для остальных
CONS_SOLATION_REWARD = {"cave_case": 2, "coins": 250, "xp": 70}

# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────
async def add_clash_points(chat_id: int, user_id: int, points: int) -> None:
    """Плюсуем SP игроку (можно вызывать из других хендлеров)."""
    await db.execute(
        """
        UPDATE progress_local
           SET clash_points = clash_points + :p
         WHERE chat_id = :c AND user_id = :u
        """,
        {"c": chat_id, "u": user_id, "p": points},
    )


async def reward_user(
    chat_id: int,
    user_id: int,
    *,
    clash_case: int = 0,
    cave_case: int = 0,
    coins: int = 0,
    xp: int = 0,
) -> None:
    """Выдаём «пустышки» кейсов — их открывает cases.py."""
    if clash_case:
        await add_item(chat_id, user_id, "clash_case", clash_case)
    if cave_case:
        await add_item(chat_id, user_id, "cave_case", cave_case)
    if coins:
        await add_money(chat_id, user_id, coins)
    if xp:
        await add_xp(chat_id, user_id, xp)


# ──────────────────────────────────────────────
# Season processor
# ──────────────────────────────────────────────
async def _process_one_chat(bot: Bot, chat_id: int) -> None:
    rows = await db.fetch_all(
        """
        SELECT user_id, clash_points
          FROM progress_local
         WHERE chat_id = :c AND clash_points > 0
      ORDER BY clash_points DESC
        """,
        {"c": chat_id},
    )
    if not rows:
        return

    # Раздача призов
    for pos, row in enumerate(rows):
        payload = REWARD_TABLE[pos] if pos < 3 else CONS_SOLATION_REWARD
        await reward_user(chat_id, row["user_id"], **payload)

    # Сброс очков
    await db.execute(
        """
        UPDATE progress_local
           SET clash_points = 0,
               last_clash_reset = CURRENT_DATE
         WHERE chat_id = :c
        """,
        {"c": chat_id},
    )

    # Финальное сообщение
    medals = ["🥇", "🥈", "🥉"]
    text = [
        "<b>🏁🔥 Cave Clash — СЕЗОН ЗАВЕРШЁН!</b>",
        "<i>Новый сезон уже стартовал, копай по‑жесткому!</i>",
        "",
        "<b>Топ‑шахтёры недели:</b>",
    ]
    for pos, row in enumerate(rows[:10]):
        try:
            member = await bot.get_chat_member(chat_id, row["user_id"])
            name = member.user.full_name
        except Exception:
            name = f"Игрок {row['user_id']}"
        badge = medals[pos] if pos < 3 else f"{pos + 1}."
        text.append(f"{badge} {name} — <b>{row['clash_points']} SP</b>")

    text.append("")
    text.append("🏆 Награды уже у вас в инвентаре!")

    await bot.send_message(chat_id, "\n".join(text), parse_mode="HTML")


async def _season_job(bot: Bot):
    chats = await db.fetch_all("SELECT DISTINCT chat_id FROM progress_local WHERE clash_points > 0")
    for row in chats:
        await _process_one_chat(bot, row["chat_id"])


def setup_weekly_reset(bot: Bot) -> None:
    """Планируем крон на понедельник 10:00 (Kyiv)."""
    kyiv = ZoneInfo("Europe/Kyiv")
    scheduler.add_job(
        _season_job,
        CronTrigger(day_of_week="mon", hour=10, minute=0, timezone=kyiv),
        kwargs={"bot": bot},
        id="cave_clash_reset",
        replace_existing=True,
    )
    scheduler.start()


# ──────────────────────────────────────────────
# Public command
# ──────────────────────────────────────────────
@router.message(Command("clashrank"))
async def clash_leaderboard(message: Message):
    rows = await db.fetch_all(
        """
        SELECT user_id, clash_points
          FROM progress_local
         WHERE chat_id = :cid
      ORDER BY clash_points DESC
         LIMIT 10
        """,
        {"cid": message.chat.id},
    )
    if not rows:
        await message.answer("Пока ещё никто не соревновался на этой неделе 😴")
        return

    medals = ["🥇", "🥈", "🥉"]
    lines = ["<b>⛏️ Cave Clash — LIVE РАНК:</b>"]
    for i, r in enumerate(rows):
        try:
            mem = await message.bot.get_chat_member(message.chat.id, r["user_id"])
            name = mem.user.full_name
        except Exception:
            name = f"Игрок {r['user_id']}"
        badge = medals[i] if i < 3 else f"{i + 1}."
        lines.append(f"{badge} {name} — <b>{r['clash_points']} SP</b>")

    await message.answer("\n".join(lines), parse_mode="HTML")
