import json
from bot.db_local import db

ACHIEVEMENT_REQUIREMENTS = {
    "bear_miner": {"count_field": "mine_count", "goal": 20},
    "repair_master": {"count_field": "repair_count", "goal": 10},
    "streak_master": {"count_field": "streak", "goal": 10},
}

def generate_progress_bar(current: int, total: int, size: int = 10) -> str:
    """Генерує текстовий прогрес-бар: ▰▱"""
    if total == 0:
        return "–"
    filled = int((current / total) * size)
    empty = size - filled
    return f"{'▰' * filled}{'▱' * empty} {min(current, total)}/{total}"

async def unlock_achievement(cid: int, uid: int, code: str) -> bool:
    row = await db.fetch_one(
        "SELECT achievements_unlocked, streak, mine_count, repair_count FROM progress_local WHERE chat_id=:c AND user_id=:u",
        {"c": cid, "u": uid}
    )

    got = row["achievements_unlocked"] or {}
    if isinstance(got, str):
        try:
            got = json.loads(got)
        except Exception:
            got = {}

    if got.get(code):
        return False  # уже есть

    # прогрес-ачивки?
    req = ACHIEVEMENT_REQUIREMENTS.get(code)
    if req:
        val = row.get(req["count_field"], 0)
        if val < req["goal"]:
            return False  # еще не выполнено

    got[code] = True

    await db.execute(
        "UPDATE progress_local SET achievements_unlocked = :a WHERE chat_id=:c AND user_id=:u",
        {"a": json.dumps(got), "c": cid, "u": uid}
    )

    # 🎉 отправка сообщения
    from bot.main import BOT
    from bot.handlers.achievements import ACHIEVEMENTS  # твой словник

    ach = ACHIEVEMENTS.get(code)
    if ach:
        try:
            user = await BOT.get_chat(uid)
            mention = f"@{user.username}" if user.username else f'<a href="tg://user?id={uid}">{user.full_name}</a>'
            await BOT.send_message(
                cid,
                f"🏆 {mention} открыл новую ачивку!\n"
                f"{ach['emoji']} <b>{ach['name']}</b> — {ach['desc']}",
                parse_mode="HTML"
            )
        except:
            pass

    return True
