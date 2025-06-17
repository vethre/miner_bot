# bot/handlers/groups.py
from aiogram import Router, types
from bot.db import db

router = Router()

@router.my_chat_member()
async def track_groups(update: types.ChatMemberUpdated):
    """
    Якщо статус бота в чаті став 'member' або 'administrator' — додаємо chat_id.
    Якщо 'kicked' чи 'left' — видаляємо.
    """
    new = update.new_chat_member.status
    chat_id = update.chat.id
    if new in ("member", "administrator"):
        await db.execute(
            """
            INSERT INTO groups (chat_id, title)
            VALUES (:cid, :title)
            ON CONFLICT (chat_id) DO UPDATE SET title = EXCLUDED.title
            """,
            {"cid": chat_id, "title": update.chat.title or ""}
        )
    elif new in ("left", "kicked"):
        await db.execute("DELETE FROM groups WHERE chat_id=:cid", {"cid": chat_id})
