# bot/utils/autodelete.py
import asyncio, logging, datetime as dt
from typing import Dict, List
from aiogram import Bot

log = logging.getLogger(__name__)

MESSAGE_CACHE: List[Dict] = []

def register_msg_for_autodelete(chat_id: int, message_id: int) -> None:
    MESSAGE_CACHE.append({
        "chat_id": chat_id,
        "message_id": message_id,
        "created": dt.datetime.utcnow(),
    })


async def _load_settings(db) -> Dict[int, int]:
    rows = await db.fetch_all(
        "SELECT chat_id, autodelete_minutes "
        "FROM progress_local WHERE autodelete_minutes > 0"
    )
    return {r["chat_id"]: r["autodelete_minutes"] for r in rows}


async def auto_cleanup_task(bot: Bot, db):
    log.info("🧹 auto-delete loop started")
    while True:
        try:
            settings = await _load_settings(db)
            now = dt.datetime.utcnow()

            # — фільтруємо кандидати —
            victims = [
                rec for rec in list(MESSAGE_CACHE)
                if (age := (now - rec["created"]).total_seconds()/60) >= settings.get(rec["chat_id"], 1e9)
            ]

            # — видаляємо —
            for rec in victims:
                try:
                    await bot.delete_message(rec["chat_id"], rec["message_id"])
                    log.debug(f"deleted {rec['message_id']} in {rec['chat_id']}")
                except Exception as e:
                    log.warning(f"cant delete {rec}: {e}")
                finally:
                    MESSAGE_CACHE.remove(rec)

        except Exception as e:
            # НЕ даємо таску померти «тихо»
            log.exception(f"auto_cleanup_task crashed: {e}")

        await asyncio.sleep(60)   # loop
