import json
from aiogram import types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot.assets import ACHIEVE_IMG_ID
from bot.db_local import get_progress, db
from bot.utils.autodelete import register_msg_for_autodelete
from bot.utils.unlockachievement import ACHIEVEMENT_REQUIREMENTS, generate_progress_bar

ACHIEVEMENTS = {
    "repair_master": {
        "name": "Кир-мейстер",
        "emoji": "🛠️",
        "desc": "Починить кирку 10 раз"
    },
    "bear_miner": {
        "name": "Шахтерский медведь",
        "emoji": "🐻",
        "desc": "Сделать 30 копаний"
    },
    "streak_master": {
        "name": "Стрик-мейстер",
        "emoji": "🔥",
        "desc": "Иметь серию ≥ 10 дней"
    },
    "grizzly_miner": {
        "name": "Шахтерский гризли",
        "emoji": "🐻",
        "desc": "Сделать 300 копаний"
    },
    "cave_bot": {
        "name": "Cave Bot",
        "emoji": "⛏️",
        "desc": "Воспользуйся командой /cavebot"
    },
    "pre_pass": {
        "name": "Пасс-тестер",
        "emoji": "💎",
        "desc": "Купи/получи Cave Pass Pre-Season"
    },
    "cobble_player": {
        "name": "Фанат коблстоуна",
        "emoji": "🪨",
        "desc": "Скрафти булыжниковую кирку"
    },
    "eonite_owner": {
        "name": "Обладатель Эонита",
        "emoji": "🔮",
        "desc": "Получи/купи Cave Pass S1"
    },
    "eonite_pioneer": {
        "name": "Первооткрыватель Эонита",
        "emoji": "🧿",
        "desc": "Получи Эонит"
    },
    "ore_horder": {
        "name": "Коллекционер руды", "emoji": "🪨",
        "desc": "Держи 1 000 любой руды в инвентаре"
    },
    "big_sale": {
        "name": "Оптовик", "emoji": "💰",
        "desc": "Продай лут единой сделкой на ≥5 000 монет"
    },
}

async def achievements_menu(message: types.Message, uid: int):
    cid = message.chat.id
    prog = await get_progress(cid, uid)
    got = prog.get("achievements_unlocked") or {}
    if isinstance(got, str):
        try:
            got = json.loads(got)
        except Exception:
            got = {}

    user = await message.bot.get_chat(uid)
    mention = user.full_name
    lines = [f"🏆 <b>Ачивки шахтёра {mention}:</b>\n"]
    for code, a in ACHIEVEMENTS.items():
        unlocked = got.get(code)
        emoji = "✅" if unlocked else "🔓"

        line = f"{emoji} {a['emoji']} <b>{a['name']}</b> — {a['desc']}"
        
        req = ACHIEVEMENT_REQUIREMENTS.get(code)
        if req and not unlocked:
            current = prog.get(req["count_field"], 0)
            bar = generate_progress_bar(current, req["goal"])
            line += f"\n{bar}"

        if code == "ore_horder" and not unlocked:
            from bot.handlers.base_commands import ORE_ITEMS
    # суммируем всю руду (или ищем максимальную) прямо из inventory_local
            ore_array = "ARRAY[" + ",".join(["'{}'".format(k) for k in ORE_ITEMS]) + "]"

            row = await db.fetch_one(
                f"""
                SELECT COALESCE(SUM(qty),0) AS total
                FROM inventory_local
                WHERE chat_id=:c AND user_id=:u
                AND item = ANY({ore_array})
                """,
                {"c": cid, "u": uid}
            )
            total_ore = row["total"]
            bar = generate_progress_bar(total_ore, 1000)
            line += f"\n{bar}"

        lines.append(line)


    #kb = InlineKeyboardBuilder()
    # kb.button(text="◀ Назад", callback_data=f"dcavepass")
    msg = await message.answer_photo(
        ACHIEVE_IMG_ID,
        caption="\n".join(lines),
        parse_mode="HTML"
    )
    #msg = await message.answer("\n".join(lines), parse_mode="HTML") #reply_markup=kb.as_markup())
    register_msg_for_autodelete(message.chat.id, msg.message_id)