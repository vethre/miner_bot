from aiogram import Router, types, F
from bot.db import create_user, get_user, db, add_item, get_inventory
import time
import random

router = Router()

ORE_DROP_RANGES = {
    "🪨 Камінь":       (5, 10),
    "🧱 Вугілля":      (3, 7),
    "⛏️ Залізна руда": (2, 6),
    "🪙 Золото":       (1, 3),
}

@router.message(F.text == "/start")
async def start_cmd(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.full_name

    await create_user(user_id, username)
    await message.reply(
        "Привіт, шахтарю! ⛏️ Ти щойно зареєструвався в системі. Напиши /mine щоб копати!"
    )

@router.message(F.text == "/mine")
async def mine_cmd(message: types.Message):
    user_id = message.from_user.id
    user = await get_user(user_id)

    if not user:
        await message.reply("Спершу введи /start, щоб тебе зареєструвати!")
        return

    now = int(time.time())
    cooldown = 30

    # user[3] — це last_mine
    if now - user["last_mine"] < cooldown:
        await message.reply(
            f"🕒 Ти вже копав! Спробуй знову через {cooldown - (now - user['last_mine'])} сек."
        )
        return

    loot = random.choice(list(ORE_DROP_RANGES.keys()))
    low, high = ORE_DROP_RANGES[loot]
    amount = random.randint(low, high)

    # Кладемо в інвентар і оновлюємо час
    await add_item(user_id, loot, amount)
    await db.execute(
        "UPDATE users SET last_mine = :now WHERE user_id = :user_id",
        {"now": now, "user_id": user_id}
    )

    await message.reply(f"Ти здобув <b>{amount}×{loot}</b>! Перевір /inventory 😎", parse_mode="HTML")

@router.message(F.text == "/inventory")
async def inventory_cmd(message: types.Message):
    user = await get_user(message.from_user.id)
    if not user:
        return await message.reply("Спершу /start")

    inv = await get_inventory(message.from_user.id)
    lines = [f"🧾 Баланс: {user['balance']} монет", "<b>📦 Інвентар:</b>"]
    for row in inv:
        lines.append(f"{row['item']}: {row['quantity']}")
    await message.reply("\n".join(lines), parse_mode="HTML")

@router.message(F.text == "/sell")
async def sell_cmd(message: types.Message):
    user_id = message.from_user.id
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        return await message.reply("Як продати: /sell <руда> <кількість>, наприклад `/sell Золото 3`")

    item, qty_str = parts[1], parts[2]
    try:
        qty = int(qty_str)
    except ValueError:
        return await message.reply("Кількість має бути числом!")

    inv = await get_inventory(user_id)
    inv_dict = {row["item"]: row["quantity"] for row in inv}
    have = inv_dict.get(item, 0)
    if have < qty:
        return await message.reply(f"У тебе лише {have} шт. {item}")

    # Ціна за одиницю
    PRICE = {"🪨 Камінь": 2, "🧱 Вугілля": 5, "🪙 Золото": 20, "⛏️ Залізна руда": 10}
    if item not in PRICE:
        return await message.reply("Ця руда не торгується 😕")

    # Оновлюємо інвентар і додаємо баланс
    await db.execute(
        "UPDATE inventory SET quantity = quantity - :qty WHERE user_id = :user_id AND item = :item",
        {"qty": qty, "user_id": user_id, "item": item}
    )
    earned = PRICE[item] * qty
    await db.execute(
        "UPDATE users SET balance = balance + :earned WHERE user_id = :user_id",
        {"earned": earned, "user_id": user_id}
    )

    await message.reply(f"Продано {qty}×{item} за {earned} монет 💰")

