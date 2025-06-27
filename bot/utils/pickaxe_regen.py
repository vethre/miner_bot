from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from bot.handlers.use import PICKAXES, _json2dict
from bot.db_local import db

UTC = ZoneInfo("UTC")

async def apply_pickaxe_regen(cid: int, uid: int, pick_key: str):
    pick_def = PICKAXES.get(pick_key)
    if not pick_def or "regen" not in pick_def:
        return  # Немає регену

    # Отримаємо час останньої регенерації
    row = await db.fetch_one(
        "SELECT last_regen, pick_dur_map, pick_dur_max_map FROM progress_local WHERE chat_id=$1 AND user_id=$2",
        cid, uid
    )

    if not row:
        return

    now = datetime.now(tz=UTC)
    last_regen = row["last_regen"] or now
    hours_passed = int((now - last_regen).total_seconds() // 3600)
    if hours_passed < 1:
        return

    # Прочитаємо мапи
    dur_map = _json2dict(row["pick_dur_map"])
    dur_max_map = _json2dict(row["pick_dur_max_map"])
    cur_dur = dur_map.get(pick_key, pick_def["dur"])
    max_dur = dur_max_map.get(pick_key, pick_def["dur"])

    # Обчислимо нову прочність
    regen_amt = pick_def["regen"] * hours_passed
    new_dur = min(cur_dur + regen_amt, max_dur)
    dur_map[pick_key] = int(new_dur)

    await db.execute(
        "UPDATE progress_local SET pick_dur_map=$1, last_regen=$2 WHERE chat_id=$3 AND user_id=$4",
        dur_map, now, cid, uid
    )
