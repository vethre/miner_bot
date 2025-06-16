# bot/handlers/base_commands.py
from aiogram import Router, types, F
from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot.db import (
    create_user, get_user, db, add_item,
    get_inventory, add_xp, update_energy
)
import time, random

router = Router()

# Опис руд
ORE_ITEMS = {
    "stone": {"name": "Камінь",       "emoji": "🪨", "drop_range": (1,5), "price": 2},
    "coal":  {"name": "Вугілля",      "emoji": "🧱", "drop_range": (1,4), "price": 5},
    "iron":  {"name": "Залізна руда", "emoji": "⛏️", "drop_range": (1,3), "price": 10},
    "gold":  {"name": "Золото",       "emoji": "🪙", "drop_range": (1,2), "price": 20},
}

# ===== Команди =====
@router.message(F.text == "/start")
async def start_cmd(message: types.Message):
    await create_user(
        message.from_user.id,
        message.from_user.username or message.from_user.full_name
    )
    await message.reply(
        "Привіт, шахтарю! ⛏️ Реєстрація пройшла успішно. Використовуй /mine, щоб копати ресурси!"
    )

@router.message(F.text == "/profile")
async def profile_cmd(message: types.Message):
    user = await get_user(message.from_user.id)
    if not user:
        return await message.reply("Спершу введи /start")
    # Оновлюємо енергію
    energy, _ = await update_energy(user)
    max_e = 5 + (user["level"] - 1) * 2
    lvl = user["level"]
    xp = user["xp"]
    next_xp = lvl * 100

    # Inline-кнопки для деталей
    builder = InlineKeyboardBuilder()
    builder.button(text="Основні", callback_data="profile:basic")
    builder.button(text="Секретні", callback_data="profile:secret")
    builder.adjust(2)

    await message.reply(
        f"👤 <b>Профіль</b> — вибери, що показати:",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )

@router.callback_query(F.data.startswith("profile:"))
async def profile_callback(callback: types.CallbackQuery):
    action = callback.data.split(':',1)[1]
    user = await get_user(callback.from_user.id)
    if not user:
        return await callback.message.reply("Спершу /start")

    if action == "basic":
        energy, _ = await update_energy(user)
        max_e = 5 + (user["level"] - 1) * 2
        lvl = user["level"]
        xp = user["xp"]
        next_xp = lvl * 100
        text = [
            f"👤 <b>Профіль:</b> {callback.from_user.full_name}",
            f"⭐ <b>Рівень:</b> {lvl} (XP: {xp}/{next_xp})",
            f"🔋 <b>Енергія:</b> {energy}/{max_e}",
            f"💰 <b>Баланс:</b> {user['balance']} монет"
        ]
    else:  # secret stats
        inv = await get_inventory(callback.from_user.id)
        total_items = sum(row['quantity'] for row in inv)
        distinct = len(inv)
        text = [
            f"🔍 <b>Секретна статистика</b>",
            f"🗃️ Різних ресурсів: {distinct}",
            f"📦 Загальна кількість ресурсів: {total_items}",
            f"💎 Загальний XP: {user['xp']}"
        ]
    # Відповідаємо і оновлюємо повідомлення
    await callback.message.edit_text(
        "\n".join(text),
        parse_mode="HTML"
    )

@router.message(F.text == "/mine")
async def mine_cmd(message: types.Message):
    user = await get_user(message.from_user.id)
    if not user:
        return await message.reply("Спершу /start")

    # Оновлюємо енергію
    energy, _ = await update_energy(user)
    if energy < 1:
        return await message.reply("😴 Недостатньо енергії. Зачекай відновлення.")

    # Віднімаємо 1 енергію
    await db.execute(
        "UPDATE users SET energy = energy - 1 WHERE user_id = :uid",
        {"uid": message.from_user.id}
    )

    # Генеруємо дроп
    ore_id = random.choice(list(ORE_ITEMS.keys()))
    low, high = ORE_ITEMS[ore_id]["drop_range"]
    amount = random.randint(low, high)

    await add_item(message.from_user.id, ore_id, amount)
    await db.execute(
        "UPDATE users SET last_mine = :now WHERE user_id = :uid",
        {"now": int(time.time()), "uid": message.from_user.id}
    )
    await add_xp(message.from_user.id, amount)

    ore = ORE_ITEMS[ore_id]
    await message.reply(
        f"Ти здобув <b>{amount}×{ore['emoji']} {ore['name']}</b>!\n"
        f"Енергія -1, XP +{amount}.",
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
