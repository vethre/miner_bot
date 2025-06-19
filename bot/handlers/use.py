# bot/handlers/use.py
from aiogram import Router, types
from aiogram.filters import Command
from bot.db_local import cid_uid, get_inventory, add_item, db
import json

router = Router()

PICKAXES = {
    "wooden_pickaxe":   {"bonus": .10, "name": "деревяная кирка",   "emoji": "🔨", "dur": 75},
    "iron_pickaxe":     {"bonus": .15, "name": "железная кирка",     "emoji": "⛏️", "dur": 90},
    "gold_pickaxe":     {"bonus": .30, "name": "золотая кирка",      "emoji": "✨", "dur": 60},
    "roundstone_pickaxe":{"bonus": .05, "name": "булыжниковая кирка", "emoji": "🪨", "dur": 50},
    "crystal_pickaxe":  {"bonus":1.50, "name": "хрустальная кирка",  "emoji": "💎", "dur": 95},
    "amethyst_pickaxe": {"bonus": .70, "name": "аметистовая кирка",  "emoji": "🔮", "dur":100},
}

ALIAS = {
    "деревяная кирка":"wooden_pickaxe","дерев’яна кирка":"wooden_pickaxe",
    "железная кирка":"iron_pickaxe",    "золота кирка":"gold_pickaxe",
    "булыжниковая кирка":"roundstone_pickaxe",
    "хрустальная кирка":"crystal_pickaxe",
    "аметистовая кирка":"amethyst_pickaxe",
}

def _json2dict(raw):
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    # raw is str or asyncpg.Record -> пробуємо декодувати
    try:
        return json.loads(raw)
    except Exception:
        return dict(raw)

@router.message(Command("use"))
async def use_cmd(message: types.Message):
    cid, uid = await cid_uid(message)

    # 1️⃣ розбір аргументу
    try:
        _, arg = message.text.split(maxsplit=1)
    except ValueError:
        return await message.reply("Как выбрать кирку: /use 'название или ключ'")

    arg = arg.lower().replace("'", "’").strip()
    key = ALIAS.get(arg, arg)
    if key not in PICKAXES:
        return await message.reply(f"Нет кирки «{arg}» 😕")

    # 2️⃣ перевіряємо інвентар
    inv = {row["item"]: row["qty"] for row in await get_inventory(cid, uid)}
    if inv.get(key, 0) < 1:
        return await message.reply(f"У тебя нет {PICKAXES[key]['name']} 🙁")

    # 3️⃣ читаємо поточний прогрес
    prog = await db.fetch_one(
        "SELECT current_pickaxe, pick_dur_map, pick_dur_max_map "
        "FROM progress_local WHERE chat_id=:c AND user_id=:u",
        {"c": cid, "u": uid}
    )
    cur          = prog["current_pickaxe"]
    dur_map      = _json2dict(prog["pick_dur_map"])
    dur_max_map  = _json2dict(prog["pick_dur_max_map"])

    # 4️⃣ повертаємо попередню кирку до інвентарю (якщо була)
    if cur:
        await add_item(cid, uid, cur, +1)

    # 5️⃣ списуємо нову з інвентаря
    await add_item(cid, uid, key, -1)

    # 6️⃣ реєструємо durability у мапах
    if key not in dur_max_map:
        dur_max_map[key] = PICKAXES[key]["dur"]
    if key not in dur_map:
        dur_map[key] = dur_max_map[key]

    # 7️⃣ оновлюємо progress_local
    dm_json  = json.dumps(dur_map)      # -> str
    dmm_json = json.dumps(dur_max_map)  # -> str

    await db.execute(
        """
        UPDATE progress_local
        SET current_pickaxe   = :p,
            pick_dur_map      = :dm::jsonb,     -- явний cast
            pick_dur_max_map  = :dmm::jsonb
        WHERE chat_id = :c AND user_id = :u
        """,
        {"p": key, "dm": dm_json, "dmm": dmm_json, "c": cid, "u": uid}
    )

    # 8️⃣ повідомлення
    bonus_pct = int(PICKAXES[key]["bonus"] * 100)
    await message.reply(
        f"{PICKAXES[key]['emoji']} Взял <b>{PICKAXES[key]['name']}</b> "
        f"(бонус +{bonus_pct} %)",
        parse_mode="HTML"
    )
