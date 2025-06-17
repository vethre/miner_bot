from aiogram import Router, types, Bot, F
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters import Command, CommandStart
from bot.db import (
    create_user, get_user, db, add_item,
    get_inventory, add_xp, update_energy, update_streak
)
from bot.handlers.crafting import SMELT_INPUT_MAP, SMELT_RECIPES, CRAFT_RECIPES
import time, random, asyncio

router = Router()

# Опис руд
ORE_ITEMS = {
    "stone": {"name": "Камінь",       "emoji": "🪨", "drop_range": (1,5), "price": 2},
    "coal":  {"name": "Вугілля",      "emoji": "🧱", "drop_range": (1,4), "price": 5},
    "iron":  {"name": "Залізна руда", "emoji": "⛏️", "drop_range": (1,3), "price": 10},
    "gold":  {"name": "Золото",       "emoji": "🪙", "drop_range": (1,2), "price": 20},
}

# Duration of mining
MINE_DURATION = 60 # test

async def mining_task(bot: Bot, user_id: int, chat_id: int):
    await asyncio.sleep(MINE_DURATION)
    user = await get_user(user_id)

    # drop
    ore_id = random.choice(list(ORE_ITEMS.keys()))
    low, high = ORE_ITEMS[ore_id]["drop_range"]
    amount = random.randint(low, high)

    await add_item(user_id, ore_id, amount)
    await add_xp(user_id, amount)
    streak = await update_streak(user)

    # очищаємо mining_end
    await db.execute(
        "UPDATE users SET mining_end = 0 WHERE user_id = :uid",
        {"uid": user_id}
    )

    ore = ORE_ITEMS[ore_id]
    await bot.send_message(
        chat_id,
        (
            f"🏔️ Повернувся з шахти!\n"
            f"Здобуто <b>{amount}×{ore['emoji']} {ore['name']}</b>\n"
            f"XP +{amount}, streak: {streak} днів."
        ),
        parse_mode="HTML"
    )

# ===== Команди =====
@router.message(CommandStart())
async def start_cmd(message: types.Message):
    await create_user(
        message.from_user.id,
        message.from_user.username or message.from_user.full_name
    )
    await message.reply(
        "Привіт, шахтарю! ⛏️ Реєстрація пройшла успішно. Використовуй /mine, щоб копати ресурси!"
    )

@router.message(Command("profile"))
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

@router.message(Command("mine"))
async def mine_cmd(message: types.Message):
    user = await get_user(message.from_user.id)
    if not user:
        return await message.reply("Спершу /start")

    # оновлюємо енергію
    energy, _ = await update_energy(user)
    if energy < 1:
        return await message.reply("😴 Недостатньо енергії. Зачекай.")

    now = int(time.time())
    if user["mining_end"] and user["mining_end"] > now:
        return await message.reply(f"⛏️ Ти ще в шахті, залишилось {user['mining_end']-now} сек.")

    # списуємо 1 енергію і ставимо mining_end
    await db.execute(
        """
        UPDATE users
           SET energy = energy - 1,
               mining_end = :end
         WHERE user_id = :uid
        """,
        {"end": now + MINE_DURATION, "uid": user["user_id"]}
    )

    await message.reply(f"⛏️ Іду в шахту на {MINE_DURATION} сек. Успіхів!")
    # фоновий похід
    asyncio.create_task(mining_task(message.bot, user["user_id"], message.chat.id))

@router.message(Command("inventory"))
async def inventory_cmd(message: types.Message):
    user = await get_user(message.from_user.id)
    if not user:
        return await message.reply("Спершу /start")
    inv = await get_inventory(message.from_user.id)
    lines = [f"🧾 Баланс: {user['balance']} монет", "<b>📦 Інвентар:</b>"]
    for row in inv:
        ore = ORE_ITEMS[row['item']]
        lines.append(f"{ore['emoji']} {ore['name']}: {row['quantity']}")
    return await message.reply("\n".join(lines), parse_mode="HTML")

@router.message(Command("sell"))
async def sell_cmd(message: types.Message, command: Command):
    args = command.args.split()  # усе після /sell
    if len(args) < 2:
        return await message.reply("Як продати: /sell <назва ресурсу> <кількість>")

    # Останній аргумент — це кількість
    try:
        qty = int(args[-1])
    except ValueError:
        return await message.reply("Кількість має бути числом!")

    # Усе решта — назва ресурсу (може складатися з кількох слів)
    item_name = " ".join(args[:-1]).lower()  # нормалізуємо регістр

    # Опис ресурсів (ключі мають бути в нижньому регістрі)
    PRICE = {
        "камінь": 2,
        "вугілля": 5,
        "залізна руда": 10,
        "золото": 20,
    }

    if item_name not in PRICE:
        return await message.reply(f"Ресурс «{item_name}» не торгується 😕")

    inv = await get_inventory(message.from_user.id)
    inv_dict = {row["item"]: row["quantity"] for row in inv}
    have = inv_dict.get(item_name, 0)
    if have < qty:
        return await message.reply(f"У тебе лише {have}×{item_name}")

    # Знімаємо з інвентаря і додаємо монети
    await db.execute(
        """
        UPDATE inventory
           SET quantity = quantity - :qty
         WHERE user_id = :uid AND item = :item
        """,
        {"qty": qty, "uid": message.from_user.id, "item": item_name}
    )
    earned = PRICE[item_name] * qty
    await db.execute(
        "UPDATE users SET balance = balance + :earned WHERE user_id = :uid",
        {"earned": earned, "uid": message.from_user.id}
    )

    return await message.reply(f"Продано {qty}×{item_name} за {earned} монет 💰")

@router.message(Command("smelt"))
async def smelt_cmd(message: types.Message, command: Command):
    args = command.args.split()
    if len(args) < 2:
        return await message.reply("Як переплавити: /smelt <руда> <кількість>")

    qty_str = args[-1]
    try:
        qty = int(qty_str)
    except ValueError:
        return await message.reply("Кількість має бути числом!")
    ore_name = " ".join(args[:-1]).lower()

    ore_key = SMELT_INPUT_MAP.get(ore_name)
    if not ore_key:
        return await message.reply(f"Не можу переплавити «{ore_name}» 😕")
    
    recipe = SMELT_RECIPES.get(ore_key)
    if not recipe:
        return await message.reply(f"«{ore_name}» не плавиться 🔥")
    
    inv = await get_inventory(message.from_user.id)
    inv_dict = {row["item"]: row["quantity"] for row in inv}
    have = inv_dict.get(ore_key, 0)
    if have < qty:
        return await message.reply(f"У тебе лише {have}×{ore_name}")
    
    in_qty = recipe["in_qty"]
    cnt = qty // in_qty
    if cnt < 1:
        return await message.reply(f"Потрібно щонайменше {in_qty}×{ore_name} для 1 {recipe['out_name']}")
    
    used = cnt * in_qty

    await db.execute("UPDATE inventory SET quantity = quantity - :used WHERE user_id = :uid AND item = :ore",
        {"used": used, "uid": message.from_user.id, "ore": ore_key})
    
    await add_item(message.from_user.id, recipe["out_key"], cnt)

    return await message.reply(
        f"🔔 Піч завершила: {cnt}×{recipe['out_name']} (витрачено {used}×{ore_name})"
    )

@router.message(Command("craft"))
async def craft_cmd(message: types.Message, command: Command):
    args = command.args.split()
    if not args:
        return await message.reply("Як крафтити: /craft <назва предмету>")

    craft_name = " ".join(args).lower()
    recipe = CRAFT_RECIPES.get(craft_name)
    if not recipe:
        return await message.reply(f"Рецепт для «{craft_name}» не знайдено 😕")

    # Перевірка інвентаря
    inv = await get_inventory(message.from_user.id)
    inv_dict = {row["item"]: row["quantity"] for row in inv}

    # Перевіряємо кожний інгредієнт
    for key, need in recipe["in"].items():
        have = inv_dict.get(key, 0)
        if have < need:
            name = recipe["out_name"]
            return await message.reply(f"Для {name} потрібно {need}×{key}, у тебе лише {have}")

    # Списуємо інгредієнти
    for key, need in recipe["in"].items():
        await db.execute(
            "UPDATE inventory SET quantity = quantity - :need WHERE user_id = :uid AND item = :key",
            {"need": need, "uid": message.from_user.id, "key": key}
        )
    # Додаємо готовий предмет
    await add_item(message.from_user.id, recipe["out_key"], 1)

    return await message.reply(f"🎉 Скрафтлено: {recipe['out_name']}!")
