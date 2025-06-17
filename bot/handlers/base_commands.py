from aiogram import Router, types, Bot, F
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters import Command, CommandStart
from bot.db import (
    create_user, get_user, db, add_item,
    get_inventory, add_xp, update_energy, update_streak, update_hunger
)
from bot.handlers.crafting import SMELT_INPUT_MAP, SMELT_RECIPES, CRAFT_RECIPES
from bot.handlers.items import ITEM_DEFS
from bot.handlers.use import PICKAXES
from bot.handlers.shop import shop_cmd
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

    # поновлюємо енергію та голод
    energy, _ = await update_energy(user)
    hunger, _ = await update_hunger(user)

    # рівень і XP
    lvl = user["level"]
    xp = user["xp"]
    next_xp = lvl * 100

    # поточна кирка
    try:
        current = user["current_pickaxe"] or "none"
    except KeyError:
        current = "none"

    pick    = PICKAXES.get(current)
    pick_name = pick["name"] if pick else "–"

    # будуємо інлайн-кнопки
    builder = InlineKeyboardBuilder()
    builder.button(text="📦 Інвентар",    callback_data="profile:inventory")
    builder.button(text="🛒 Магазин",     callback_data="profile:shop")
    builder.button(text="⛏️ Шахта",       callback_data="profile:mine")
    # builder.button(text="🏆 Ачивки",      callback_data="profile:achievements")
    builder.adjust(2)

    text = [
        f"👤 <b>Профіль:</b> {message.from_user.full_name}",
        f"⭐ <b>Рівень:</b> {lvl} (XP: {xp}/{next_xp})",
        f"🔋 <b>Енергія:</b> {energy}/100",
        f"🍗 <b>Голод:</b> {hunger}/100",
        f"⛏️ <b>Кирка:</b> {pick_name}",
        f"💰 <b>Баланс:</b> {user['balance']} монет"
    ]
    await message.reply(
        "\n".join(text),
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
# Profile Callback
@router.callback_query(F.data.startswith("profile:"))
async def profile_callback(callback: types.CallbackQuery):
    await callback.answer()                # прибираємо спінер на кнопці
    action = callback.data.split(":", 1)[1]

    if action == "inventory":
        await inventory_cmd(callback.message, user_id=callback.from_user.id)
    elif action == "shop":
        await shop_cmd(callback.message, user_id=callback.from_user.id)
    elif action == "mine":
        await mine_cmd(callback.message, user_id=callback.from_user.id)
        

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
        key = row["item"]
        qty = row["quantity"]
        item = ITEM_DEFS.get(key, {"name": key, "emoji": ""})
        # Якщо є emoji — додаємо зліва
        prefix = f"{item['emoji']} " if item["emoji"] else ""
        lines.append(f"{prefix}{item['name']}: {qty}")

    await message.reply("\n".join(lines), parse_mode="HTML")

@router.message(Command("sell"))
async def sell_cmd(message: types.Message):
    text = message.text or ""
    parts = text.split(maxsplit=1)  # ['/sell', '<ресурс> <к-сть>']
    if len(parts) < 2:
        return await message.reply("Як продати: /sell 'назва ресурсу' 'кількість'")

    rest = parts[1]
    try:
        item_part, qty_str = rest.rsplit(maxsplit=1)  # ['Залізна руда', '3']
    except ValueError:
        return await message.reply("Як продати: /sell 'назва ресурсу' 'кількість'")

    item_name = item_part.lower().strip()
    if not qty_str.isdigit():
        return await message.reply("Кількість має бути числом!")
    qty = int(qty_str)

    # Ціни
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

    # Списуємо ресурси
    await db.execute(
        """
        UPDATE inventory
           SET quantity = quantity - :qty
         WHERE user_id = :uid AND item = :item
        """,
        {"qty": qty, "uid": message.from_user.id, "item": item_name}
    )
    earned = PRICE[item_name] * qty
    # Додаємо монети
    await db.execute(
        "UPDATE users SET balance = balance + :earned WHERE user_id = :uid",
        {"earned": earned, "uid": message.from_user.id}
    )

    await message.reply(f"Продано {qty}×{item_name} за {earned} монет 💰")

@router.message(Command("smelt"))
async def smelt_cmd(message: types.Message):
    text = message.text or ""
    parts = text.split(maxsplit=1)  # ['/smelt', 'Залізна руда 17']
    if len(parts) < 2:
        return await message.reply("Як переплавити: /smelt 'руда' 'кількість'")

    rest = parts[1]  # 'Залізна руда 17'
    try:
        ore_part, qty_str = rest.rsplit(maxsplit=1)  # ['Залізна руда', '17']
    except ValueError:
        return await message.reply("Як переплавити: /smelt 'руда' 'кількість'")

    ore_name = ore_part.lower()
    if not qty_str.isdigit():
        return await message.reply("Кількість має бути числом!")

    qty = int(qty_str)

    # Твоя мапа input→ключ
    ore_key = SMELT_INPUT_MAP.get(ore_name)
    if not ore_key:
        return await message.reply(f"Не знаю таку руду «{ore_name}» 😕")

    recipe = SMELT_RECIPES[ore_key]
    have = {row["item"]: row["quantity"] for row in await get_inventory(message.from_user.id)}.get(ore_key, 0)
    if have < qty:
        return await message.reply(f"У тебе лише {have}×{ore_name}")

    cnt = qty // recipe["in_qty"]
    if cnt < 1:
        return await message.reply(f"Потрібно щонайменше {recipe['in_qty']}×{ore_name} для 1×{recipe['out_name']}")

    used = cnt * recipe["in_qty"]
    # Списуємо руду
    await db.execute(
        "UPDATE inventory SET quantity = quantity - :used WHERE user_id = :uid AND item = :ore",
        {"used": used, "uid": message.from_user.id, "ore": ore_key}
    )
    # Додаємо інготи
    await add_item(message.from_user.id, recipe["out_key"], cnt)

    return await message.reply(
        f"🔔 Піч завершила: {cnt}×{recipe['out_name']} (витрачено {used}×{ore_name})"
    )

@router.message(Command("craft"))
async def craft_cmd(message: types.Message):
    text = message.text or ""
    parts = text.split(maxsplit=1)  # ['/craft', '<назва предмету>']
    if len(parts) < 2:
        return await message.reply("Як крафтити: /craft 'назва предмету'")

    craft_name = parts[1].lower().strip()  # вся решта — назва
    recipe = CRAFT_RECIPES.get(craft_name)
    if not recipe:
        return await message.reply(f"Рецепт для «{craft_name}» не знайдено 😕")

    # Перевіряємо інвентар
    inv = await get_inventory(message.from_user.id)
    inv_dict = {row["item"]: row["quantity"] for row in inv}

    for key, need in recipe["in"].items():
        have = inv_dict.get(key, 0)
        if have < need:
            return await message.reply(
                f"Для {recipe['out_name']} потрібно {need}×{key}, у тебе лише {have}"
            )

    # Списуємо інгредієнти
    for key, need in recipe["in"].items():
        await db.execute(
            """
            UPDATE inventory
               SET quantity = quantity - :need
             WHERE user_id = :uid AND item = :key
            """,
            {"need": need, "uid": message.from_user.id, "key": key}
        )

    # Додаємо готовий предмет
    await add_item(message.from_user.id, recipe["out_key"], 1)

    await message.reply(f"🎉 Скрафтлено: {recipe['out_name']}!")
