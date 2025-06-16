from aiogram import Router, types, F
from bot.db import create_user, get_user, db, add_item, get_inventory
import time
import random

router = Router()

# Описи руд з ключами для зберігання в БД
ORE_ITEMS = {
    "stone": {
        "name": "Камінь",
        "emoji": "🪨",
        "drop_range": (1, 5),
        "price": 2,
    },
    "coal": {
        "name": "Вугілля",
        "emoji": "🧱",
        "drop_range": (1, 4),
        "price": 5,
    },
    "iron": {
        "name": "Залізна руда",
        "emoji": "⛏️",
        "drop_range": (1, 3),
        "price": 10,
    },
    "gold": {
        "name": "Золото",
        "emoji": "🪙",
        "drop_range": (1, 2),
        "price": 20,
    },
}

@router.message(F.text == "/start")
async def start_cmd(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.full_name
    await create_user(user_id, username)
    await message.reply(
        "Привіт, шахтарю! ⛏️ Ти щойно зареєструвався в системі. Напиши /mine, щоб копати ресурси!"
    )

@router.message(F.text == "/mine")
async def mine_cmd(message: types.Message):
    user_id = message.from_user.id
    user = await get_user(user_id)
    if not user:
        return await message.reply("Спершу введи /start")

    now = int(time.time())
    cooldown = 30
    if now - user["last_mine"] < cooldown:
        return await message.reply(
            f"🕒 Ти вже копав! Спробуй через {cooldown - (now - user['last_mine'])} сек."
        )

    # Випадковий тип руди
    ore_id = random.choice(list(ORE_ITEMS.keys()))
    low, high = ORE_ITEMS[ore_id]["drop_range"]
    amount = random.randint(low, high)

    # Додаємо до інвентаря та оновлюємо час копання
    await add_item(user_id, ore_id, amount)
    await db.execute(
        "UPDATE users SET last_mine = :now WHERE user_id = :user_id",
        {"now": now, "user_id": user_id}
    )

    emoji = ORE_ITEMS[ore_id]["emoji"]
    name = ORE_ITEMS[ore_id]["name"]
    await message.reply(
        f"Ти здобув <b>{amount}×{emoji} {name}</b>! Перевір /inventory 😎",
        parse_mode="HTML"
    )

@router.message(F.text == "/inventory")
async def inventory_cmd(message: types.Message):
    user_id = message.from_user.id
    user = await get_user(user_id)
    if not user:
        return await message.reply("Спершу введи /start")

    inv = await get_inventory(user_id)
    lines = [f"🧾 Баланс: {user['balance']} монет", "<b>📦 Інвентар:</b>"]
    for row in inv:
        ore = ORE_ITEMS.get(row['item'])
        if ore:
            lines.append(f"{ore['emoji']} {ore['name']}: {row['quantity']}")
    await message.reply("\n".join(lines), parse_mode="HTML")

@router.message(F.text.startswith("/sell"))
async def sell_cmd(message: types.Message):
    user_id = message.from_user.id
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        return await message.reply(
            "Як продати: /sell <назва> <кількість>, наприклад /sell Золото 3"
        )

    name_input = parts[1].strip()
    try:
        qty = int(parts[2].strip())
    except ValueError:
        return await message.reply("Кількість має бути числом!")

    # Знаходимо ore_id за назвою (без emoji)
    ore_id = next(
        (key for key, val in ORE_ITEMS.items() if val['name'].lower() == name_input.lower()),
        None
    )
    if not ore_id:
        return await message.reply("Ти не можеш торгувати цим ресурсом 😕")

    inv = await get_inventory(user_id)
    inv_dict = {row['item']: row['quantity'] for row in inv}
    have = inv_dict.get(ore_id, 0)
    if have < qty:
        return await message.reply(f"У тебе лише {have} шт. {ORE_ITEMS[ore_id]['name']}")

    price = ORE_ITEMS[ore_id]['price']
    earned = price * qty

    # Оновлюємо БД: віднімаємо руду та додаємо монети
    await db.execute(
        "UPDATE inventory SET quantity = quantity - :qty WHERE user_id = :user_id AND item = :ore_id",
        {"qty": qty, "user_id": user_id, "ore_id": ore_id}
    )
    await db.execute(
        "UPDATE users SET balance = balance + :earned WHERE user_id = :user_id",
        {"earned": earned, "user_id": user_id}
    )

    emoji = ORE_ITEMS[ore_id]['emoji']
    name = ORE_ITEMS[ore_id]['name']
    await message.reply(
        f"Продано {qty}×{emoji} {name} за {earned} монет 💰", parse_mode="HTML"
    )
