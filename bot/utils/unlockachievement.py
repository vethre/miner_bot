import json
from bot.db_local import db

# 📋 Вимоги до ачивок
ACHIEVEMENT_REQUIREMENTS = {
    "bear_miner": {
        "count_field": "mine_count",
        "goal": 30  # 🔼 Порог піднятий до 30
    },
    "repair_master": {
        "count_field": "repair_count",
        "goal": 10
    },
    "streak_master": {
        "count_field": "streak",
        "goal": 10
    },
    "grizzly_miner": {
        "count_field": "mine_count",
        "goal": 300
    },
}

# 🔳 Прогрес-бар у стилі ▰▱
def generate_progress_bar(current: int, total: int, size: int = 10) -> str:
    if total == 0:
        return "–"
    filled = int((current / total) * size)
    empty = size - filled
    return f"{'▰' * filled}{'▱' * empty} {min(current, total)}/{total}"

# 🏆 Основна функція
async def unlock_achievement(cid: int, uid: int, code: str) -> bool:
    row = await db.fetch_one("""
        SELECT achievements_unlocked, streak, mine_count, repair_count
        FROM progress_local
        WHERE chat_id = :c AND user_id = :u
    """, {"c": cid, "u": uid})

    # 🔐 Витягуємо ачивки
    got_raw = row["achievements_unlocked"]
    got = {}
    if got_raw:
        try:
            got = json.loads(got_raw) if isinstance(got_raw, str) else got_raw
        except json.JSONDecodeError:
            got = {}

    # 🔁 Якщо вже є — виходимо
    if got.get(code):
        return False

    # 📈 Перевірка прогресу
    req = ACHIEVEMENT_REQUIREMENTS.get(code)
    if req:
        val = row[req["count_field"]] or 0
        if val < req["goal"]:
            return False

    # ✅ Додаємо в список отриманих
    got[code] = True
    await db.execute("""
        UPDATE progress_local
           SET achievements_unlocked = :a
         WHERE chat_id = :c AND user_id = :u
    """, {"a": json.dumps(got), "c": cid, "u": uid})

    # 📢 Повідомлення про ачивку
    try:
        from bot.main import BOT
        from bot.handlers.achievements import ACHIEVEMENTS

        ach = ACHIEVEMENTS.get(code)
        if ach:
            user = await BOT.get_chat(uid)
            mention = (
                f"@{user.username}"
                if user.username else
                f'<a href="tg://user?id={uid}">{user.full_name}</a>'
            )
            await BOT.send_message(
                cid,
                f"🏆 {mention} открыл новую ачивку!\n"
                f"{ach['emoji']} <b>{ach['name']}</b> — {ach['desc']}",
                parse_mode="HTML"
            )
    except Exception as e:
        # Можна додати логування при бажанні
        pass

    return True