from datetime import datetime, timedelta
import random
from bot.db_local import db
from aiogram import Bot

async def check_afk_and_warn(bot: Bot):
    now = datetime.utcnow()
    yesterday = (now - timedelta(days=1)).date()

    rows = await db.fetch_all(
        "SELECT chat_id, user_id, mining_end FROM progress_local WHERE mining_end IS NOT NULL"
    )

    for row in rows:
        last_mine = row["mining_end"]
        if not last_mine:
            continue

        if last_mine.date() == yesterday:
            member = await bot.get_chat_member(row["chat_id"], row["user_id"])
            mention = f"@{member.user.username}" if member.user.username \
                      else f'<a href="tg://user?id={row["user_id"]}">{member.user.full_name}</a>'
            
            txts = [
                f"👷 {mention}, твой начальник недоволен. Уже сутки ты не спускаешься в шахту!",
                f"📉 {mention}, продуктивность упала до нуля. Пора копать!",
                f"📅 Вчера был последний раз в шахте? {mention}, давай без прогулов!",
                f"🛏️ {mention}, просыпайся! Руды сами себя не выкопают!",
            ]

            await bot.send_message(row["chat_id"], random.choice(txts), parse_mode="HTML")
