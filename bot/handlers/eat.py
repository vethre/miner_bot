# bot/handlers/eat.py
from aiogram import Router, types
from aiogram.filters import Command
import datetime as dt

from bot.db_local import (
    cid_uid, get_inventory, update_hunger,
    add_item, db
)
from bot.utils.autodelete import register_msg_for_autodelete   # якщо маєш автокеш

router = Router()

# _________________________ базові властивості їжі ____________________________
FOOD_ITEMS: dict[str, dict] = {
    "bread":  {"name": "🍞 Хліб",  "hunger": 30},
    "meat":   {"name": "🍖 Мʼясо", "hunger": 60},
    "borsch": {"name": "🥣 Борщ",  "hunger": 100},
}

# _________________________ аліаси мов/опечаток ______________________________
FOOD_ALIASES: dict[str, str] = {
    # хліб
    "хліб": "bread", "bread": "bread",
    # м'ясо
    "м'ясо": "meat", "мясо": "meat", "meat": "meat",
    # борщ
    "борщ": "borsch", "борщ": "borsch", "borsch": "borsch",
}

# ============================================================================
@router.message(Command("eat"))
async def eat_cmd(message: types.Message):
    cid, uid = await cid_uid(message)

    # 1) розбір параметра
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        return await message.reply("Як їсти: /eat <назва їжі>")

    alias   = parts[1].strip().lower()
    key     = FOOD_ALIASES.get(alias)            # canonical key
    if not key:
        return await message.reply(f"Не знаю такої їжі «{alias}» 😕")

    food = FOOD_ITEMS[key]

    # 2) перевіряємо інвентар
    inv = {row["item"]: row["qty"] for row in await get_inventory(cid, uid)}
    if inv.get(key, 0) < 1:
        return await message.reply(f"У тебе немає {food['name']}")

    # 3) списуємо 1 од. їжі
    await add_item(cid, uid, key, -1)

    # 4) апдейтимо голод (з урахуванням пасивного decay)
    curr_hunger, _ = await update_hunger(cid, uid)
    new_hunger     = min(100, curr_hunger + food["hunger"])

    await db.execute(
        "UPDATE progress_local "
        "SET hunger = :h, last_hunger_update = :now "
        "WHERE chat_id = :c AND user_id = :u",
        {"h": new_hunger, "now": dt.datetime.utcnow(), "c": cid, "u": uid}
    )

    # 5) відповідаємо й реєструємо на автовидалення (за бажанням)
    msg = await message.reply(
        f"{food['name']} зʼїдено 🍽️\nГолод: {new_hunger}/100"
    )
    register_msg_for_autodelete(message.chat.id, msg.message_id)   # можеш прибрати, якщо не треба
