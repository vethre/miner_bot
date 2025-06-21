# bot/handlers/eat.py
from aiogram import Router, types
from aiogram.filters import Command
import datetime as dt

from bot.db_local import (
    cid_uid, get_inventory, add_item,
    update_hunger, update_energy, add_energy, db
)
from bot.utils.autodelete import register_msg_for_autodelete

router = Router()

# ───── потребляемые предметы ────────────────────────────────────────────────
CONSUMABLES = {
    # еда → восстанавливает hunger
    "bread":        {"name": "🍞 Хлеб",  "hunger": 30},
    "meat":         {"name": "🍖 Мясо",  "hunger": 60},
    "borsch":       {"name": "🥣 Борщ",  "hunger": 100},
    # напитки / бустеры → восстанавливают energy
    "energy_drink": {"name": "🥤 Энергетик", "energy": 40},
}

ALIAS = {
    "хлеб": "bread",
    "мясо": "meat",
    "борщ": "borsch",
    "энергетик": "energy_drink",
    "борсч": "borsch",
    "borshch": "borsch",
}

@router.message(Command("deat"))
async def eat_cmd(message: types.Message):
    cid, uid = await cid_uid(message)

    # --- 1) аргумент --------------------------------------------------------
    try:
        _, raw_key = message.text.split(maxsplit=1)
    except ValueError:
        return await message.reply("📥 Как употреблять: /eat 'что-то съедобное'")

    key  = ALIAS.get(raw_key.lower().strip(), raw_key.lower().strip())
    item = CONSUMABLES.get(key)
    if not item:
        return await message.reply(f"Не знаю {raw_key} 🤔")

    # --- 2) инвентарь --------------------------------------------------------
    inv = {r["item"]: r["qty"] for r in await get_inventory(cid, uid)}
    if inv.get(key, 0) < 1:
        return await message.reply(f"У тебя нет {item['name']}")

    # --- 3) списываем предмет -----------------------------------------------
    await add_item(cid, uid, key, -1)

    now = dt.datetime.utcnow()

    # --- 4) едим или пьем ----------------------------------------------------
    if "hunger" in item:                                 # это еда
        curr_hunger, _ = await update_hunger(cid, uid)
        new_hunger = min(100, curr_hunger + item["hunger"])

        await db.execute(
            """UPDATE progress_local
                   SET hunger = :h,
                       last_hunger_update = :now
                 WHERE chat_id=:c AND user_id=:u""",
            {"h": new_hunger, "now": now, "c": cid, "u": uid}
        )
        txt = f"{item['name']} съедено 🍽️\nГолод: {new_hunger}/100"

    else:                                                # это напиток
        inc = item["energy"]
        await add_energy(cid, uid, inc)
        new_energy, _ = await update_energy(cid, uid)    # пересчитаем после add_energy
        txt = f"{item['name']} выпит 🥤\nЭнергия: {new_energy}/100"

    msg = await message.reply(txt)
    register_msg_for_autodelete(message.chat.id, msg.message_id)
