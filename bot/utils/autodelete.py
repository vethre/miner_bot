# bot/utils/autodelete.py
import asyncio
import datetime as dt
from typing import Dict, List
from aiogram import Bot

#--- Пам'ять для повідомлень, які треба стерти
MESSAGE_CACHE: List[Dict] = []        # [{chat_id, message_id, created}, …]

def register_msg_for_autodelete(chat_id: int, message_id: int) -> None:
    """Кладемо повідомлення у кеш для майбутнього видалення."""
    MESSAGE_CACHE.append({
        "chat_id":   chat_id,
        "message_id": message_id,
        "created":   dt.datetime.utcnow(),
    })

#--- Читаємо налаштування з progress_local.autodelete_minutes
async def _load_settings(db) -> Dict[int, int]:
    rows = await db.fetch_all(
        "SELECT chat_id, autodelete_minutes FROM progress_local "
        "WHERE autodelete_minutes IS NOT NULL AND autodelete_minutes > 0"
    )
    return {r["chat_id"]: r["autodelete_minutes"] for r in rows}

#--- Фоновий цикл
async def auto_cleanup_task(bot: Bot, db):
    while True:
        settings = await _load_settings(db)
        now = dt.datetime.utcnow()
        to_remove = []

        for rec in MESSAGE_CACHE:
            interval = settings.get(rec["chat_id"])
            if not interval:
                continue                      # у цьому чаті авто-чистка вимкнена
            age_min = (now - rec["created"]).total_seconds() / 60
            if age_min >= interval:
                to_remove.append(rec)

        for rec in to_remove:
            try:
                await bot.delete_message(rec["chat_id"], rec["message_id"])
            except Exception:
                pass
            finally:
                MESSAGE_CACHE.remove(rec)

        await asyncio.sleep(60)      # перевіряємо щохвилини
