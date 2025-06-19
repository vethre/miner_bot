from __future__ import annotations

import asyncio
from typing import List, Dict
from aiogram.utils.markdown import link
import random
import time
import datetime as dt
from typing import List

from aiogram import Router, Bot, types, F
from aiogram.filters import Command, CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import CallbackQuery

from bot.db import db, create_user, get_user
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
    update_streak,
    add_energy,
    change_dur,
)
from bot.handlers.cavepass import cavepass_cmd
from bot.handlers.items import ITEM_DEFS
from bot.handlers.crafting import SMELT_RECIPES, SMELT_INPUT_MAP, CRAFT_RECIPES
from bot.handlers.use import PICKAXES
from bot.handlers.shop import shop_cmd
from bot.assets import INV_IMG_ID, PROFILE_IMG_ID
from bot.utils.autodelete import register_msg_for_autodelete

router = Router()

# ────────── Константи ──────────
BASE_MINE_SEC   = 45          # Tier-1
MINE_SEC_STEP   = -5          # −5 с за кожен Tier вище
MINE_SEC_MIN    = 20

BASE_SMELT_SEC  = 30          # за 1 інгот
TORCH_SPEEDUP   = 0.7         # Torch Bundle

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

def get_tier(level:int)->int:
    t = 1
    for i,row in enumerate(TIER_TABLE,1):
        if level>=row["level_min"]: t=i
    return t

def get_mine_duration(tier:int)->int:
    return max(BASE_MINE_SEC + MINE_SEC_STEP*(tier-1), MINE_SEC_MIN)

def get_smelt_duration(cnt:int, torch_mult:float=1.0)->int:
    return round(BASE_SMELT_SEC * cnt * torch_mult)

# ─────────────── “Картки шансу” ───────────────
ChanceEvent = tuple[str, str, str, int]    
#          (key , text , effect , weight)

CHANCE_EVENTS: list[ChanceEvent] = [
    ("found_coins",   "Ти знайшов гаманець 💰  +{n} монет",  "coins:+", 35),
    ("pet_cat",       "Погладжено кота 😸     +{n} XP",      "xp:+",    30),
    ("robbery",       "Тебе пограбували! −{n} монет",       "coins:-", 20),
    ("miner_snack",   "Шахтарський снек 🥪   +{n} енергії",  "energy:+",15),
]

def pick_chance_event() -> ChanceEvent|None:
    if random.random() > 0.25:          # лише 25 % шанс, що подія взагалі трапиться
        return None
    pool: list[ChanceEvent] = []
    for ev in CHANCE_EVENTS:
        pool += [ev] * ev[3]            # ваги
    return random.choice(pool)

async def apply_chance_event(ev: ChanceEvent, cid: int, uid: int) -> str:
    n = random.randint(10, 60)
    field, sign = ev[2].split(":")      # "coins", "+/-"
    delta =  n if sign == "+" else -n

    if field == "coins":
        await add_money(cid, uid, delta)
    elif field == "xp":
        await add_xp(cid, uid, delta)
    elif field == "energy":
        await add_energy(cid, uid, delta)   # нова утиліта

    return ev[1].format(n=abs(delta))

# ────────── Mining Task ──────────
async def mining_task(bot:Bot, cid:int, uid:int, tier:int, ores:List[str], bonus:float):
    await asyncio.sleep(get_mine_duration(tier))

    prog = await get_progress(cid,uid)
    ore_id = random.choice(ores)
    ore    = ORE_ITEMS[ore_id]
    amount = random.randint(*ore["drop_range"])
    amount = int(amount*bonus)
    pick_bonus = PICKAXES.get(prog.get("current_pickaxe"),{}).get("bonus",0)
    amount+= int(amount*pick_bonus)

    xp_gain=amount
    if prog.get("cave_pass") and prog["pass_expires"]>dt.datetime.utcnow():
        xp_gain=int(xp_gain*1.5)

    await add_item(cid,uid,ore_id,amount)
    await add_xp  (cid,uid,xp_gain)
    streak=await update_streak(cid,uid)

    # ---- прочність конкретної кирки (JSON-мапа) ----
    broken = False
    if cur := prog.get("current_pickaxe"):
        dur, dur_max = await change_dur(cid, uid, cur, -1)
        broken = dur == 0

    # ---- випадкова подія ----
    extra_txt=""
    ev = pick_chance_event()
    if ev:
        extra_txt = "\n" + await apply_chance_event(ev, cid, uid)

    member=await bot.get_chat_member(cid,uid)
    mention = f"@{member.user.username}" if member.user.username \
              else f'<a href="tg://user?id={uid}">{member.user.full_name}</a>'
    
    await db.execute(
        "UPDATE progress_local SET mining_end=NULL "
        "WHERE chat_id=:c AND user_id=:u",
        {"c": cid, "u": uid}
    )

    txt=(f"🏔 {mention}, ти повернувся з шахти!\n"
         f"<b>{amount}×{ore['emoji']} {ore['name']}</b>\n"
         f"XP +{xp_gain}\n"
         f"Tier×{bonus:.1f} | кирка+{int(pick_bonus*100)} % | streak {streak} дн."
         + ("\n⚠️ Кирка зламалася! /repair" if broken else "")
         + extra_txt)

    msg=await bot.send_message(cid,txt,parse_mode="HTML")
    register_msg_for_autodelete(cid,msg.message_id)
    
# ────────── Smelt Task ──────────
async def smelt_timer(bot:Bot,cid:int,uid:int,rec:dict,cnt:int,torch_mult:float):
    await asyncio.sleep(get_smelt_duration(cnt,torch_mult))
    await add_item(cid,uid,rec["out_key"],cnt)
    await db.execute("UPDATE progress_local SET smelt_end=NULL WHERE chat_id=:c AND user_id=:u",
                     {"c":cid,"u":uid})
    await bot.send_message(cid,f"🔥 Піч готова: {cnt}×{rec['out_name']}")

# ────────── /start ──────────
@router.message(CommandStart())
async def start_cmd(message: types.Message):
    await create_user(message.from_user.id, message.from_user.username or message.from_user.full_name)
    msg = await message.reply("Привіт, шахтарю! ⛏️ Реєстрація пройшла успішно. Використовуй /mine, щоб копати ресурси!")
    register_msg_for_autodelete(message.chat.id, msg.message_id)

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

    # Кирка та її міцність
    current = prog.get("current_pickaxe") or "wooden_pickaxe"
    pick = PICKAXES.get(current, {"name":"–"})
    pick_name = pick["name"]
    dur = prog.get("pick_dur", 0)
    dur_max = prog.get("pick_dur_max", 100)
    cave_cases = prog.get("cave_cases", 0)

    # Pass
    has_pass = prog.get("cave_pass", False)
    expires  = prog.get("pass_expires")
    if has_pass and expires:
        pass_str = expires.strftime("%d.%m.%Y")
    else:
        pass_str = "неактивний"

    balance = await get_money(cid, uid)

    builder = InlineKeyboardBuilder()
    builder.button(text="📦 Інвентар", callback_data=f"profile:inventory:{uid}")
    builder.button(text="🛒 Магазин",    callback_data=f"profile:shop:{uid}")
    builder.button(text="⛏️ Шахта",      callback_data=f"profile:mine:{uid}")
    builder.button(text="💎 Cave Pass",      callback_data=f"profile:cavepass:{uid}")
    builder.adjust(1)

    text = (
        f"👤 <b>Профіль:</b> {message.from_user.full_name}\n"
        f"⭐ <b>Рівень:</b> {lvl} (XP {xp}/{next_xp})\n"
        f"💎 <b>Cave Pass:</b> {pass_str}\n\n"
        f"🔋 <b>Енергія:</b> {energy}/100\n"
        f"🍗 <b>Голод:</b> {hunger}/100\n\n"
        f"📦 <b>Cave Cases:</b> {cave_cases}\n"
        f"💰 <b>Баланс:</b> {balance} монет\n\n"
        f"⛏️ <b>Кирка:</b> {pick_name} ({dur}/{dur_max})"
    )

    msg = await message.answer_photo(
        photo=PROFILE_IMG_ID,
        caption=text,
        parse_mode="HTML",
        reply_to_message_id=message.message_id,
        reply_markup=builder.as_markup()
    )
    register_msg_for_autodelete(message.chat.id, msg.message_id)
    # await message.reply(text, parse_mode="HTML", reply_markup=builder.as_markup())

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
    elif action == "cavepass":
        await cavepass_cmd(callback.message)

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
    elif act == "cavepass":
        await cavepass_cmd(cb.message)

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
            "end": dt.datetime.utcnow() + dt.timedelta(seconds=get_mine_duration(tier)),
            "c": cid,
            "u": uid,
        },
    )

    msg = await message.reply(f"⛏️ Іду в шахту на {get_mine_duration(tier)} сек. Успіхів!")
    register_msg_for_autodelete(message.chat.id, msg.message_id)
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

    msg = await message.answer_photo(
        photo=INV_IMG_ID,
        caption="\n".join(lines),
        parse_mode="HTML",
        reply_to_message_id=message.message_id
    )

    register_msg_for_autodelete(message.chat.id, msg.message_id)
    #await message.reply("\n".join(lines), parse_mode="HTML")

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
    msg = await message.reply(f"Продано {qty}×{item_part} за {earned} монет 💰")
    register_msg_for_autodelete(message.chat.id, msg.message_id)

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
    torch_mult = 1.0
    if any(r["item"]=="torch_bundle" for r in inv):
        torch_mult = TORCH_SPEEDUP
        await add_item(cid, uid, "torch_bundle", -1)

    duration = get_smelt_duration(cnt, torch_mult)
    await db.execute(
        "UPDATE progress_local SET smelt_end=:e WHERE chat_id=:c AND user_id=:u",
        {"e": dt.datetime.utcnow() + dt.timedelta(seconds=duration), "c": cid, "u": uid},
    )
    asyncio.create_task(smelt_timer(message.bot, cid, uid, rec, cnt))
    msg = await message.reply(f"⏲️ Піч працює {duration} сек…")
    register_msg_for_autodelete(message.chat.id, msg.message_id)

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
    msg = await message.reply(f"🎉 Скрафтлено: {recipe['out_name']}!")
    register_msg_for_autodelete(message.chat.id, msg.message_id)

# ────────── /stats ──────────
@router.message(Command("stats"))
async def stats_cmd(message: types.Message):
    cid, uid = await cid_uid(message)
    builder = InlineKeyboardBuilder()
    builder.button(text="🏆 Топ за балансом", callback_data="stats:balance")
    builder.button(text="🎖️ Топ за рівнем", callback_data="stats:level")
    builder.button(text="📊 Топ за ресурсами", callback_data="stats:resources")
    builder.adjust(1)
    msg = await message.reply(
        "📊 <b>Статистика</b> — оберіть топ:",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
    register_msg_for_autodelete(message.chat.id, msg.message_id)

@router.callback_query(F.data.startswith("stats:"))
async def stats_callback(callback: CallbackQuery):
    await callback.answer()
    cid, _ = await cid_uid(callback.message)
    typ = callback.data.split(":", 1)[1]
    lines: list[str] = []

    if typ == "balance":
        rows = await db.fetch_all(
            "SELECT user_id, coins FROM balance_local "
            "WHERE chat_id=:c ORDER BY coins DESC LIMIT 10",
            {"c": cid}
        )
        for i, r in enumerate(rows, start=1):
            uid = r["user_id"]
            coins = r["coins"]
            member = await callback.bot.get_chat_member(cid, uid)
            user = member.user
            if user.username:
                mention = f"{user.username}"
            else:
                mention = f'<a href="tg://user?id={uid}">{user.full_name}</a>'
            lines.append(f"{i}. {mention} — {coins} монет")

    elif typ == "level":
        rows = await db.fetch_all(
            "SELECT user_id, level, xp FROM progress_local "
            "WHERE chat_id=:c ORDER BY level DESC, xp DESC LIMIT 10",
            {"c": cid}
        )
        for i, r in enumerate(rows, start=1):
            uid = r["user_id"]
            lvl = r["level"]
            xp = r["xp"]
            member = await callback.bot.get_chat_member(cid, uid)
            user = member.user
            if user.username:
                mention = f"@{user.username}"
            else:
                mention = f'<a href="tg://user?id={uid}">{user.full_name}</a>'
            lines.append(f"{i}. {mention} — рівень {lvl} (XP {xp})")

    elif typ == "resources":
        rows = await db.fetch_all(
            "SELECT user_id, SUM(qty) AS total FROM inventory_local "
            "WHERE chat_id=:c GROUP BY user_id ORDER BY total DESC LIMIT 10",
            {"c": cid}
        )
        for i, r in enumerate(rows, start=1):
            uid = r["user_id"]
            total = r["total"]
            member = await callback.bot.get_chat_member(cid, uid)
            user = member.user
            if user.username:
                mention = f"@{user.username}"
            else:
                mention = f'<a href="tg://user?id={uid}">{user.full_name}</a>'
            lines.append(f"{i}. {mention} — {total} ресурсів")

    else:
        return

    text = "\n".join(lines) if lines else "Немає даних для показу"
    msg = await callback.message.edit_text(text, parse_mode="HTML")
    register_msg_for_autodelete(callback.message.chat.id, msg.message_id)

@router.message(Command("repair"))
async def repair_cmd(message: types.Message):
    cid, uid = await cid_uid(message)
    prog = await get_progress(cid, uid)

    pick_key = prog.get("current_pickaxe")
    if not pick_key:
        return await message.reply("У тебе зараз немає активної кирки.")

    dur_map     = prog.get("pick_dur_map"    , {})
    dur_max_map = prog.get("pick_dur_max_map", {})
    dur     = dur_map.get(pick_key, 0)
    dur_max = dur_max_map.get(pick_key, 100)

    if dur >= dur_max:
        return await message.reply("🛠️ Кирка в ідеальному стані!")

    cost = (dur_max - dur) * 2   # 2 монети за 1 міцності
    if (bal := await get_money(cid, uid)) < cost:
        return await message.reply("Недостатньо монет для ремонту.")

    await add_money(cid, uid, -cost)
    await change_dur(cid, uid, pick_key, dur_max - dur)   # повертаємо до макс.

    await message.reply(f"🛠️ {PICKAXES[pick_key]['name']} відремонтована до {dur_max}/{dur_max} за {cost} монет!")

TELEGRAPH_LINK = "https://telegra.ph/Cave-Miner---Info-06-17" 

# /about
@router.message(Command("about"))
async def about_cmd(message: types.Message):
    msg = await message.reply(f"🔍 Детальніше про бота — {link('читати на Telegraph', TELEGRAPH_LINK)}", parse_mode="HTML")
    register_msg_for_autodelete(message.chat.id, msg.message_id)

# /report <bug text>
@router.message(Command("report"))
async def report_cmd(message: types.Message):
    cid, uid = await cid_uid(message)
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return await message.reply("❗ Використання: /report 'опис багу'")

    bug_text = args[1]
    report_line = f"🐞 Баг від {message.from_user.full_name} ({uid}):\n{bug_text}"

    # відправка мені
    ADMIN_ID = 700929765 
    try:
        msg = await message.bot.send_message(ADMIN_ID, report_line)
    except:
        pass

    msg = await message.reply("✅ Дякую, баг передано!")

    register_msg_for_autodelete(message.chat.id, msg.message_id)

@router.message(Command("autodelete"))
async def autodelete_cmd(message: types.Message):
    cid, uid = await cid_uid(message)
    parts = message.text.strip().split()
    
    if len(parts) != 2 or not parts[1].isdigit():
        return await message.reply("❗ Використання: /autodelete 60 (від 1 до 720 хв, або 0 щоб вимкнути)")

    minutes = int(parts[1])
    if not (0 <= minutes <= 720):
        return await message.reply("❗ Введи значення від 0 до 720 хвилин")

    await db.execute(
        "UPDATE progress_local SET autodelete_minutes=:m WHERE chat_id=:c AND user_id=:u",
        {"m": minutes, "c": cid, "u": uid}
    )
    
    if minutes == 0:
        msg = await message.reply("🧹 Автовидалення вимкнено. Повідомлення залишатимуться в чаті.")
    else:
        msg = await message.reply(f"🧼 Автовидалення активовано: кожні {minutes} хвилин бот чиститиме свої повідомлення.")
    register_msg_for_autodelete(message.chat.id, msg.message_id)

@router.message(Command("pickaxes"))
async def list_pickaxes(message: types.Message):
    lines = [f"{v['emoji']} <b>{v['name']}</b> — /use {k}" for k,v in PICKAXES.items()]
    msg = await message.reply("\n".join(lines), parse_mode="HTML")
    register_msg_for_autodelete(message.chat.id, msg.message_id)
