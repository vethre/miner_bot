"""
Cave Clash core — season reset + rewards.
Loot‑кейсами (Cave/Clash) управляет bot/handlers/cases.py. Здесь — только очки, ресет, награды.
"""

from __future__ import annotations

from zoneinfo import ZoneInfo

from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import Message
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from bot.db_local import db, add_money, add_xp
from bot.utils.autodelete import register_msg_for_autodelete

# ── Globals ─────────────────────────────────────────
router = Router()
scheduler = AsyncIOScheduler()

# TOP‑3 reward tiers (кол‑во «пустых» кейсов + золото + XP)
REWARD_TABLE = [
    {"clash_case": 3, "coins": 1000, "xp": 300},  # 🥇
    {"clash_case": 2, "coins": 700,  "xp": 250},  # 🥈
    {"clash_case": 1, "coins": 400,  "xp": 200},  # 🥉
]
# Everyone else gets this consolation pack
CONS_SOLATION_REWARD = {"cave_case": 2, "coins": 250, "xp": 70}

# ── Helpers ─────────────────────────────────────────
async def add_clash_points(chat_id: int, user_id: int, points: int) -> None:
    """External call: +points к текущему счёту игрока."""
    await db.execute(
        "UPDATE progress_local SET clash_points = clash_points + :p WHERE chat_id=:c AND user_id=:u",
        {"c": chat_id, "u": user_id, "p": points},
    )


async def _give_cases(chat_id: int, user_id: int, *, clash: int = 0, cave: int = 0) -> None:
    """Инкремент счётчиков cave_cases / clash_cases в progress_local."""
    if cave:
        await db.execute(
            "UPDATE progress_local SET cave_cases = cave_cases + :n WHERE chat_id=:c AND user_id=:u",
            {"n": cave, "c": chat_id, "u": user_id},
        )
    if clash:
        await db.execute(
            "UPDATE progress_local SET clash_cases = clash_cases + :n WHERE chat_id=:c AND user_id=:u",
            {"n": clash, "c": chat_id, "u": user_id},
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
    """Выдаём приз: инкремент счётчиков кейсов, золото, XP."""
    await _give_cases(chat_id, user_id, clash=clash_case, cave=cave_case)
    if coins:
        await add_money(chat_id, user_id, coins)
    if xp:
        await add_xp(chat_id, user_id, xp)


# ── Season reset job ───────────────────────────────
async def _process_chat(b: Bot, chat_id: int):
    players = await db.fetch_all(
        "SELECT user_id, clash_points FROM progress_local WHERE chat_id=:c AND clash_points>0 ORDER BY clash_points DESC",
        {"c": chat_id},
    )
    if not players:
        return

    # distribute rewards
    for idx, p in enumerate(players):
        payload = REWARD_TABLE[idx] if idx < 3 else CONS_SOLATION_REWARD
        await reward_user(chat_id, p["user_id"], **payload)

    # reset points
    await db.execute(
        "UPDATE progress_local SET clash_points = 0, last_clash_reset = CURRENT_DATE WHERE chat_id=:c",
        {"c": chat_id},
    )

    # fancy announce
    medals = ["🥇", "🥈", "🥉"]
    msg = [
        "<b>🏁🔥 Cave Clash — СЕЗОН ОКОНЧЕН!</b>",
        "<i>Новый сезон стартовал! Добывай SP.</i>",
        "",
        "<b>Топ‑шахтёры:</b>",
    ]
    for idx, p in enumerate(players[:10]):
        try:
            member = await b.get_chat_member(chat_id, p["user_id"])
            name = member.user.full_name
        except Exception:
            name = f"Игрок {p['user_id']}"
        badge = medals[idx] if idx < 3 else f"{idx+1}."
        msg.append(f"{badge} {name} — <b>{p['clash_points']} SP</b>")
    msg.append("\n🏆 Кейсы и бонусы начислены!")

    msg = await b.send_message(chat_id, "\n".join(msg), parse_mode="HTML")
    register_msg_for_autodelete(chat_id, msg.message_id)


async def _season_job(b: Bot):
    chats = await db.fetch_all("SELECT DISTINCT chat_id FROM progress_local WHERE clash_points>0")
    for row in chats:
        await _process_chat(b, row["chat_id"])


def setup_weekly_reset(bot: Bot):
    prague = ZoneInfo("Europe/Prague")
    try:
        scheduler.add_job(
            _season_job,
            CronTrigger(day_of_week="mon", hour=9, minute=40, timezone=prague),
            kwargs={"bot": bot},
            id="cave_clash_reset",
            replace_existing=True,
        )
    except Exception:  # ConflictingIdError
        pass  # job уже существует

    if not scheduler.running:
        scheduler.start()


# ── Live leaderboard ───────────────────────────────
@router.message(Command("clashrank"))
async def clashrank(message: Message):
    rows = await db.fetch_all(
        "SELECT user_id, clash_points FROM progress_local WHERE chat_id=:cid ORDER BY clash_points DESC LIMIT 10",
        {"cid": message.chat.id},
    )
    if not rows:
        await message.answer("Пока никто не соревновался 😴")
        return

    medals = ["🥇", "🥈", "🥉"]
    lines = ["<b>⛏️ Cave Clash — LIVE TOP:</b>"]
    for i, r in enumerate(rows):
        try:
            m = await message.bot.get_chat_member(message.chat.id, r["user_id"])
            name = m.user.full_name
        except Exception:
            name = f"Игрок {r['user_id']}"
        badge = medals[i] if i < 3 else f"{i+1}."
        lines.append(f"{badge} {name} — <b>{r['clash_points']} SP</b>")
    msg = await message.answer("\n".join(lines), parse_mode="HTML")
    register_msg_for_autodelete(message.chat.id, msg.message_id)


# ── Integration helper ─────────────────────────────

def register_cave_clash(dp, bot):
    """Include router + schedule job (single call!)."""
    dp.include_router(router)
    setup_weekly_reset(bot)
