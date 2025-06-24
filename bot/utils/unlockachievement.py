import json
from bot.db_local import get_progress, db

async def unlock_achievement(cid: int, uid: int, code: str) -> bool:
    prog = await get_progress(cid, uid)
    got = prog.get("achievements_unlocked") or {}
    if isinstance(got, str):
        try:
            got = json.loads(got)
        except:
            got = {}

    if got.get(code):
        return False  # вже є

    got[code] = True
    await db.execute(
        "UPDATE progress_local SET achievements_unlocked = :data WHERE chat_id = :c AND user_id = :u",
        {"data": json.dumps(got), "c": cid, "u": uid}
    )
    return True
