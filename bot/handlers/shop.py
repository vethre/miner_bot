from aiogram import Router, types, F
from bot.db import get_user, add_item
# Простий список товарів
SHOP_ITEMS = {
    "🪓 Дерев’яна кирка":   {"price": 50, "bonus": 1},
    "⛏️ Кам’яна кирка":      {"price": 200, "bonus": 5},
    "💎 Золота кирка":       {"price": 1000, "bonus": 20},
}

router = Router()

@router.message(F.text == "/shop")
async def shop_cmd(message: types.Message):
    text = ["🛒 <b>Магазин кирок</b>"]
    for name, props in SHOP_ITEMS.items():
        text.append(f"{name} — {props['price']} монет (+{props['bonus']} дропу)")
    await message.reply("\n".join(text), parse_mode="HTML")

@router.message(F.text.startswith("/buy"))
async def buy_cmd(message: types.Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply("Вкажи, що купити: /buy <назва товару>")
        return

    choice = parts[1].strip()
    user = await get_user(message.from_user.id)
    if not user:
        return await message.reply("Спершу /start")

    balance = user[2]
    item = SHOP_ITEMS.get(choice)
    if not item:
        return await message.reply("Товар не знайдено в магазині 😕")

    if balance < item["price"]:
        return await message.reply("Недостатньо монет 💸")

    # Віднімаємо гроші й даємо в інвентар
    from bot.db import aiosqlite, DATABASE_PATH
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (item["price"], message.from_user.id))
        await db.commit()
    await add_item(message.from_user.id, choice, 1)
    await message.reply(f"Ти придбав {choice}! 🎉")
