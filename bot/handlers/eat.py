from aiogram import Router, types
from aiogram.filters import Command
from bot.db import get_inventory, get_user, db, update_hunger

FOOD_ITEMS = {
    "bread": {"name":"🍞 Хліб", "hunger":30},
    "meat":  {"name":"🍖 М’ясо","hunger":60},
}

router = Router()

@router.message(Command("eat"))
async def eat_cmd(message: types.Message):
    text = message.text or ""
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        return await message.reply("Як їсти: /eat 'назва їжі'")
    
    food_key = parts[1].strip().lower()
    recipe = FOOD_ITEMS.get(food_key)
    if not recipe:
        return await message.reply(f"Не знаю «{food_key}» 😕")
    
    inv = await get_inventory(message.from_user.id)
    have = {r["item"]: r["quantity"] for r in inv}.get(food_key,0)
    if have < 1:
        return await message.reply(f"У тебе немає {recipe['name']}")
    
    await db.execute("UPDATE inventory SET quantity = quantity - 1 WHERE user_id=:uid AND item=:key",
        {"uid": message.from_user.id, "key": food_key})
    
    user = await get_user(message.from_user.id)
    new_h, _ = await update_hunger(user)
    new_h = min(100, new_h + recipe["hunger"])
    await db.execute("UPDATE users SET hunger = :h WHERE user_id=:uid",
        {"h": new_h, "uid": message.from_user.id})
    
    return await message.reply(
        f"{recipe['name']} з’їдений 🍽️\nГолод: {new_h}/100"
    )
