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
}

@router.message(Command("eat"))
async def eat_cmd(message: types.Message):
    cid, uid = await cid_uid(message)

    # ─── разбор аргумента ───────────────────────────────────────────────────
    try:
        _, raw_key = message.text.split(maxsplit=1)
    except ValueError:
        return await message.reply("📥 Как употреблять: /eat <что-то съедобное>")

    key = ALIAS.get(raw_key.lower().strip(), raw_key.lower().strip())
    item = CONSUMABLES.get(key)
    if not item:
        return await message.reply(f"Не знаю `{raw_key}` 🤔")

    # ─── проверяем инвентарь ────────────────────────────────────────────────
    inv = {r["item"]: r["qty"] for r in await get_inventory(cid, uid)}
    if inv.get(key, 0) < 1:
        return await message.reply(f"У тебя нет {item['name']}")

    # ─── списываем предмет ──────────────────────────────────────────────────
    await add_item(cid, uid, key, -1)

    # ─── обновляем показатели ───────────────────────────────────────────────
    if "hunger" in item:                          # это еда
        curr_hunger, _ = await update_hunger(cid, uid)
        new_hunger = min(100, curr_hunger + item["hunger"])
        await db.execute(
            """UPDATE progress_local
                 SET hunger=:h, last_hunger_update=:now
               WHERE chat_id=:c AND user_id=:u""",
            {"h": new_hunger, "now": dt.datetime.utcnow(),
             "c": cid, "u": uid}
        )
        msg = await message.reply(
            f"Вы съели: {item['name']} 🍽️\nГолод: {new_hunger}/100"
        )
        register_msg_for_autodelete(message.chat.id, msg.message_id)

    else:                                         # это напиток (energy)
        curr_energy, _ = await update_energy(cid, uid)
        inc = item["energy"]
        await add_energy(cid, uid, inc)
        new_energy = min(100, curr_energy + inc)
        msg = await message.reply(
            f"{item['name']} выпит 🥤\nЭнергия: {new_energy}/100"
        )
        register_msg_for_autodelete(message.chat.id, msg.message_id)
