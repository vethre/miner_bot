from __future__ import annotations

import asyncio
import random
import time
import datetime as dt
from typing import List

from aiogram import Router, Bot, types, F
from aiogram.filters import Command, CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.db import db, create_user, get_user, update_streak
from bot.db_local import (
    cid_uid,
    add_item,
    add_money,
    add_xp,
    get_inventory,
    get_money,
    update_energy,
    update_hunger,
    get_progress,
)
from bot.handlers.items import ITEM_DEFS
from bot.handlers.crafting import SMELT_RECIPES, SMELT_INPUT_MAP, CRAFT_RECIPES
from bot.handlers.use import PICKAXES
from bot.handlers.shop import shop_cmd

router = Router()

# ────────── Константи ──────────
MINE_DURATION = 60  # sec (dev)
HUNGER_COST = 10
HUNGER_LIMIT = 20

# ────────── Руди  + Tiers ──────────
ORE_ITEMS = {
    "stone":    {"name": "Камінь",   "emoji": "🪨", "drop_range": (3, 10), "price": 2},
    "coal":     {"name": "Вугілля",  "emoji": "🧱", "drop_range": (3, 8),  "price": 5},
    "iron":     {"name": "Залізна руда", "emoji": "⛏️", "drop_range": (2, 7),  "price": 10},
    "gold":     {"name": "Золото",   "emoji": "🪙", "drop_range": (2, 6),  "price": 20},
    "amethyst": {"name": "Аметист",  "emoji": "💜", "drop_range": (1, 5),  "price": 40},
    "diamond":  {"name": "Діамант",  "emoji": "💎", "drop_range": (1, 2),  "price": 60},
    "emerald":  {"name": "Смарагд",  "emoji": "💚", "drop_range": (1, 3),  "price": 55},
    "lapis":    {"name": "Лазурит",  "emoji": "🔵", "drop_range": (3, 6),  "price": 35},
    "ruby":     {"name": "Рубін",    "emoji": "❤️", "drop_range": (1, 4),  "price": 50},
}

TIER_TABLE = [
    {"level_min": 1,  "ores": ["stone", "coal"]},
    {"level_min": 5,  "ores": ["stone", "coal", "iron"]},
    {"level_min": 10, "ores": ["stone", "coal", "iron", "gold"]},
    {"level_min": 15, "ores": ["stone", "coal", "iron", "gold", "amethyst", "lapis"]},
    {"level_min": 20, "ores": ["stone", "coal", "iron", "gold", "amethyst", "lapis", "emerald", "ruby"]},
    {"level_min": 25, "ores": ["stone", "coal", "iron", "gold", "amethyst", "lapis", "emerald", "ruby", "diamond"]},
]
BONUS_BY_TIER = {i + 1: 1.0 + i * 0.2 for i in range(len(TIER_TABLE))}

# ────────── Helper ──────────

def get_tier(level: int) -> int:
    tier = 1
    for i, row in enumerate(TIER_TABLE, start=1):
        if level >= row["level_min"]:
            tier = i
    return tier

# ────────── Mining Task ──────────
async def mining_task(bot: Bot, chat_id: int, user_id: int, tier: int, ores: List[str], bonus: float):
    try:
        await asyncio.sleep(MINE_DURATION)

        prog = await get_progress(chat_id, user_id)
        user = await get_user(user_id)

        ore_id = random.choice(ores)
        low, high = ORE_ITEMS[ore_id]["drop_range"]
        amount = random.randint(low, high)

        # Tier + кирка бонус
        amount = int(amount * bonus)
        pick_bonus = PICKAXES.get(prog["current_pickaxe"], {}).get("bonus", 0)
        amount += int(amount * pick_bonus)

        # Додаємо лут
        await add_item(chat_id, user_id, ore_id, amount)
        await add_xp(chat_id, user_id, amount)
        streak = await update_streak(user)  # streak поки глобальний

        # очищаємо таймер
        await db.execute(
            """UPDATE progress_local SET mining_end=NULL WHERE chat_id=:c AND user_id=:u""",
            {"c": chat_id, "u": user_id},
        )

        ore = ORE_ITEMS[ore_id]
        username = user["username"] or user["full_name"]
        mention = f'<a href="tg://user?id={user_id}">{username}</a>'

        await bot.send_message(
            chat_id,
            (
                f"🏔️ {mention}, ти повернувся з шахти!\n"
                f"<b>{amount}×{ore['emoji']} {ore['name']}</b>\n"
                f"Tier {tier} бонус ×{bonus:.1f}, кирка +{int(pick_bonus*100)}%, streak {streak} дн."
            ),
            parse_mode="HTML",
        )
    except Exception as e:
        print(f"Error in mining_task: {e}")(
            chat_id,
            (
                f"🏔️ {mention}, ти повернувся з шахти!\n"
                f"<b>{amount}×{ore['emoji']} {ore['name']}</b>\n"
                f"Tier {tier} бонус ×{bonus:.1f}, кирка +{int(pick_bonus*100)} %, streak {streak} дн."
            ),
            parse_mode="HTML",
    )

# ────────── Smelt Task ──────────
async def smelt_timer(bot: Bot, cid: int, uid: int, rec: dict, cnt: int):
    duration = cnt * 5
    await asyncio.sleep(duration)

    await add_item(cid, uid, rec["out_key"], cnt)
    await db.execute(
        "UPDATE progress_local SET smelt_end=NULL WHERE chat_id=:c AND user_id=:u",
        {"c": cid, "u": uid},
    )

    await bot.send_message(uid, f"🔥 Піч готова: {cnt}×{rec['out_name']}")

# ────────── /start ──────────
@router.message(CommandStart())
async def start_cmd(message: types.Message):
    await create_user(message.from_user.id, message.from_user.username or message.from_user.full_name)
    await message.reply("Привіт, шахтарю! ⛏️ Реєстрація пройшла успішно. Використовуй /mine, щоб копати ресурси!")

# ────────── /profile ──────────
@router.message(Command("profile"))
async def profile_cmd(message: types.Message):
    cid, uid = await cid_uid(message)
    # ensure user exists
    await create_user(message.from_user.id, message.from_user.username or message.from_user.full_name)

    # обчислюємо енергію та голод
    energy, _ = await update_energy(cid, uid)
    hunger, _ = await update_hunger(cid, uid)

    prog = await get_progress(cid, uid)
    lvl = prog.get("level", 1)
    xp = prog.get("xp", 0)
    next_xp = lvl * 100
    pick_name = PICKAXES.get(prog.get("current_pickaxe", "wood_pickaxe"), {}).get("name", "–")
    balance = await get_money(cid, uid)

    # Inline-кнопки тільки для автора
    builder = InlineKeyboardBuilder()
    builder.button(
        text="📦 Інвентар",
        callback_data=f"profile:inventory:{uid}"
    )
    builder.button(
        text="🛒 Магазин",
        callback_data=f"profile:shop:{uid}"
    )
    builder.button(
        text="⛏️ Шахта",
        callback_data=f"profile:mine:{uid}"
    )
    builder.adjust(2)

    text = (
        f"👤 <b>Профіль:</b> {message.from_user.full_name}\n"
        f"⭐ <b>Рівень:</b> {lvl} (XP {xp}/{next_xp})\n"
        f"🔋 <b>Енергія:</b> {energy}/100\n"
        f"🍗 <b>Голод:</b> {hunger}/100\n"
        f"⛏️ <b>Кирка:</b> {pick_name}\n"
        f"💰 <b>Баланс:</b> {balance} монет"
    )
    await message.reply(
        text,
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )

# Profile Callback
@router.callback_query(F.data.startswith("profile:"))
async def profile_callback(callback: types.CallbackQuery):
    data = callback.data.split(":")
    # format: ['profile', action, original_uid]
    if len(data) != 3:
        return await callback.answer()
    _, action, orig_uid = data
    orig_uid = int(orig_uid)
    # тільки автор може натискати
    if callback.from_user.id != orig_uid:
        return await callback.answer("Ця кнопка не для тебе", show_alert=True)
    await callback.answer()

    # передаємо виконання команді
    if action == "inventory":
        await inventory_cmd(callback.message, user_id=orig_uid)
    elif action == "shop":
        await shop_cmd(callback.message)
    elif action == "mine":
        await mine_cmd(callback.message, user_id=orig_uid)

# ────────── /mine ──────────(F.data.startswith("profile:"))
async def profile_callback(cb: types.CallbackQuery):
    await cb.answer()
    act = cb.data.split(":", 1)[1]
    if act == "inventory":
        await inventory_cmd(cb.message, cb.from_user.id)
    elif act == "shop":
        await shop_cmd(cb.message, cb.from_user.id)
    elif act == "mine":
        await mine_cmd(cb.message, cb.from_user.id)

# ────────── /mine ──────────
@router.message(Command("mine"))
async def mine_cmd(message: types.Message, user_id: int | None = None):
    cid, uid = await cid_uid(message)
    if user_id:
        uid = user_id
    user = await get_user(uid)
    if not user:
        return await message.reply("Спершу /start")

    energy, _ = await update_energy(cid, uid)
    hunger, _ = await update_hunger(cid, uid)
    if energy <= 15:
        return await message.reply("😴 Недостатньо енергії. Зачекай.")
    if hunger < HUNGER_LIMIT:
        return await message.reply("🍽️ Ти занадто голодний, спершу /eat!")

    prog = await get_progress(cid, uid)
    if prog["mining_end"] and prog["mining_end"] > dt.datetime.utcnow():
        left = int((prog["mining_end"] - dt.datetime.utcnow()).total_seconds())
        return await message.reply(f"⛏️ Ти ще в шахті, залишилось {left} сек.")

    tier = get_tier(prog["level"])
    bonus_tier = BONUS_BY_TIER[tier]
    ores = TIER_TABLE[tier - 1]["ores"]

    # списуємо енергію/голод + ставимо таймер
    await db.execute(
        """UPDATE progress_local
               SET energy = GREATEST(0, energy - 12),
                   hunger = GREATEST(0, hunger - :hc),
                   mining_end = :end
             WHERE chat_id=:c AND user_id=:u""",
        {
            "hc": HUNGER_COST,
            "end": dt.datetime.utcnow() + dt.timedelta(seconds=MINE_DURATION),
            "c": cid,
            "u": uid,
        },
    )

    await message.reply(f"⛏️ Іду в шахту на {MINE_DURATION} сек. Успіхів!")
    asyncio.create_task(mining_task(message.bot, cid, uid, tier, ores, bonus_tier))

# ────────── /inventory ──────────
@router.message(Command("inventory"))
async def inventory_cmd(message: types.Message, user_id: int | None = None):
    cid, uid = await cid_uid(message)
    if user_id:
        uid = user_id
    inv = await get_inventory(cid, uid)
    balance = await get_money(cid, uid)

    lines = [f"🧾 Баланс: {balance} монет", "<b>📦 Інвентар:</b>"]
    for row in inv:
        meta = ITEM_DEFS.get(row["item"], {"name": row["item"], "emoji": ""})
        pre = f"{meta['emoji']} " if meta.get("emoji") else ""
        lines.append(f"{pre}{meta['name']}: {row['qty']}")

    await message.reply("\n".join(lines), parse_mode="HTML")

# ────────── /sell (локальний) ──────────
ALIASES = {k: k for k in ORE_ITEMS}
ALIASES.update({
    "камінь": "stone",
    "вугілля": "coal",
    "залізна руда": "iron",
    "залізо": "iron",
    "золото": "gold",
    "аметист": "amethyst",
    "діамант": "diamond",
    "смарагд": "emerald",
    "лазурит": "lapis",
    "рубин": "ruby",
})

@router.message(Command("sell"))
async def sell_cmd(message: types.Message):
    cid, uid = await cid_uid(message)
    text = message.text or ""
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        return await message.reply("Як продати: /sell 'ресурс' 'к-сть'")
    try:
        item_part, qty_str = parts[1].rsplit(maxsplit=1)
    except ValueError:
        return await message.reply("Як продати: /sell 'ресурс' 'к-сть'")
    if not qty_str.isdigit():
        return await message.reply("Кількість має бути числом!")
    qty = int(qty_str)
    item_key = ALIASES.get(item_part.lower(), item_part.lower())
    if item_key not in ITEM_DEFS or "price" not in ITEM_DEFS[item_key]:
        return await message.reply("Не торгується 😕")
    inv = {r["item"]: r["qty"] for r in await get_inventory(cid, uid)}
    have = inv.get(item_key, 0)
    if have < qty:
        return await message.reply(f"У тебе лише {have}×{item_part}")
    await add_item(cid, uid, item_key, -qty)
    earned = ITEM_DEFS[item_key]["price"] * qty
    await add_money(cid, uid, earned)
    await message.reply(f"Продано {qty}×{item_part} за {earned} монет 💰")

# ────────── /smelt (async) ──────────
@router.message(Command("smelt"))
async def smelt_cmd(message: types.Message):
    cid, uid = await cid_uid(message)

    text = message.text or ""
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        return await message.reply("Як переплавити: /smelt 'руда' 'кількість'")
    try:
        ore_part, qty_str = parts[1].rsplit(maxsplit=1)
    except ValueError:
        return await message.reply("/smelt 'руда' 'кількість'")
    if not qty_str.isdigit():
        return await message.reply("Кількість має бути числом!")
    qty = int(qty_str)
    ore_key = SMELT_INPUT_MAP.get(ore_part.lower())
    if not ore_key:
        return await message.reply("Невідома руда")
    rec = SMELT_RECIPES[ore_key]
    inv = {r["item"]: r["qty"] for r in await get_inventory(cid, uid)}
    have = inv.get(ore_key, 0)
    if have < qty:
        return await message.reply(f"У тебе лише {have}")
    cnt = qty // rec["in_qty"]
    if cnt < 1:
        return await message.reply(f"Потрібно {rec['in_qty']}× для одного інгота")
    used = cnt * rec["in_qty"]
    await add_item(cid, uid, ore_key, -used)
    # Таймер
    duration = cnt * 5  # 5 сек за інгот (dev)
    await db.execute(
        "UPDATE progress_local SET smelt_end=:e WHERE chat_id=:c AND user_id=:u",
        {"e": dt.datetime.utcnow() + dt.timedelta(seconds=duration), "c": cid, "u": uid},
    )
    asyncio.create_task(smelt_timer(message.bot, cid, uid, rec, cnt))
    await message.reply(f"⏲️ Піч працює {duration} сек…")

# ────────── /craft ──────────
@router.message(Command("craft"))
async def craft_cmd(message: types.Message):
    cid, uid = await cid_uid(message)
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        return await message.reply("/craft 'назва'")
    craft_name = parts[1].lower().strip()
    recipe = CRAFT_RECIPES.get(craft_name)
    if not recipe:
        return await message.reply("Рецепт не знайдено")
    inv = {r["item"]: r["qty"] for r in await get_inventory(cid, uid)}
    for k, need in recipe["in"].items():
        if inv.get(k, 0) < need:
            return await message.reply("Не вистачає ресурсів")
    for k, need in recipe["in"].items():
        await add_item(cid, uid, k, -need)
    await add_item(cid, uid, recipe["out_key"], 1)
    await message.reply(f"🎉 Скрафтлено: {recipe['out_name']}!")
