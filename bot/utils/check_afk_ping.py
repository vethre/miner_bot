from datetime import datetime, timedelta
import random
from aiogram import Bot
from bot.db_local import db  # твоя обгортка для БД

AFK_PHRASES = [
    "👷 {m}, твой начальник недоволен. Уже сутки ты не спускаешься в шахту!",
    "📉 {m}, продуктивность упала до нуля. Пора копать!",
    "😴 {m}, вчера ты не копал ни разу. Просыпайся!",
    "🛏️ {m}, руда сама себя не выкопает!",
]

async def check_afk_and_warn(bot: Bot) -> None:
    """Пінгуємо юзерів, у яких mining_end < (now - 1 day)."""
    cutoff = datetime.utcnow() - timedelta(days=1)

    rows = await db.fetch_all(
        """
        SELECT chat_id, user_id
          FROM progress_local
         WHERE mining_end IS NOT NULL
           AND mining_end < :cut
        """,
        {"cut": cutoff},
    )

    for row in rows:
        try:
            member = await bot.get_chat_member(row["chat_id"], row["user_id"])
            mention = (
                f"@{member.user.username}"
                if member.user.username
                else f'<a href="tg://user?id={row["user_id"]}">{member.user.full_name}</a>'
            )
            text = random.choice(AFK_PHRASES).format(m=mention)
            await bot.send_message(row["chat_id"], text, parse_mode="HTML")
        except Exception:
            # користувач міг піти з чату, не страшно
            continue
