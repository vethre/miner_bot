# bot/handlers/eat.py
from aiogram import Router, types
from aiogram.filters import Command
import datetime as dt

from bot.db_local import cid_uid, get_inventory, update_hunger, add_item, db

router = Router()

FOOD_ITEMS = {
    "bread": {"name": "🍞 Хліб",  "hunger": 30},
    "meat":  {"name": "🍖 М’ясо", "hunger": 60},
}

@router.message(Command("eat"))
async def eat_cmd(message: types.Message):
    cid, uid = await cid_uid(message)
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        return await message.reply("Як їсти: /eat <назва їжі>")

    food_key = parts[1].strip().lower()
    food = FOOD_ITEMS.get(food_key)
    if not food:
        return await message.reply(f"Не знаю «{food_key}» 😕")

    inv = await get_inventory(cid, uid)
    have = next((r["qty"] for r in inv if r["item"] == food_key), 0)
    if have < 1:
        return await message.reply(f"У тебе немає {food['name']}")

    # Зменшуємо кількість їжі
    await add_item(cid, uid, food_key, -1)

    # Оновлюємо голод (спочатку робимо passive decay)
    current_hunger, _ = await update_hunger(cid, uid)
    # Додаємо приємок голоду, не більше 100
    new_hunger = min(100, current_hunger + food["hunger"])
    now = dt.datetime.utcnow()
    await db.execute(
        """
        UPDATE progress_local
           SET hunger = :h,
               last_hunger_update = :now
         WHERE chat_id = :c AND user_id = :u
        """,
        {"h": new_hunger, "now": now, "c": cid, "u": uid}
    )

    await message.reply(
        f"{food['name']} з’їдений 🍽️\nГолод: {new_hunger}/100"
    )
