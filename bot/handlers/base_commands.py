from __future__ import annotations

import asyncio
import json
import logging
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
from aiogram.enums import ChatMemberStatus

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
    _jsonb_to_dict,
)
from bot.handlers.cavepass import cavepass_cmd
from bot.handlers.items import ITEM_DEFS
from bot.handlers.crafting import SMELT_RECIPES, SMELT_INPUT_MAP, CRAFT_RECIPES
from bot.handlers.use import PICKAXES
from bot.handlers.shop import shop_cmd
from bot.assets import INV_IMG_ID, PROFILE_IMG_ID, START_IMG_ID, STATS_IMG_ID, ABOUT_IMG_ID
from bot.utils.autodelete import register_msg_for_autodelete
from bot.handlers.use import _json2dict

router = Router()

# ────────── Константи ──────────
BASE_MINE_SEC   = 1200          # Tier-1
MINE_SEC_STEP   = -20          # -20 с за кожен Tier вище
MINE_SEC_MIN    = 60

BASE_SMELT_SEC  = 600          # за 1 інгот
TORCH_SPEEDUP   = 0.7         # Torch Bundle

HUNGER_COST = 10
HUNGER_LIMIT = 20

# ────────── Руди  + Tiers ──────────
ORE_ITEMS = {
    "stone":    {"name": "Камень",   "emoji": "🪨", "drop_range": (10, 16), "price": 2},
    "coal":     {"name": "Уголь",  "emoji": "🧱", "drop_range": (8, 14),  "price": 6},
    "iron":     {"name": "Железная руда", "emoji": "⛏️", "drop_range": (5, 9),  "price": 12},
    "gold":     {"name": "Золото",   "emoji": "🪙", "drop_range": (4, 9),  "price": 16},
    "amethyst": {"name": "Аметист",  "emoji": "💜", "drop_range": (3, 7),  "price": 28},
    "diamond":  {"name": "Алмаз",  "emoji": "💎", "drop_range": (1, 2),  "price": 67},
    "emerald":  {"name": "Изумруд",  "emoji": "💚", "drop_range": (1, 3),  "price": 47},
    "lapis":    {"name": "Лазурит",  "emoji": "🔵", "drop_range": (3, 6),  "price": 34},
    "ruby":     {"name": "Рубин",    "emoji": "❤️", "drop_range": (1, 4),  "price": 55},
}

TIER_TABLE = [
    {"level_min": 1,  "ores": ["stone", "coal"]},
    {"level_min": 4,  "ores": ["stone", "coal", "iron"]},
    {"level_min": 8, "ores": ["stone", "coal", "iron", "gold"]},
    {"level_min": 13, "ores": ["stone", "coal", "iron", "gold", "amethyst", "lapis"]},
    {"level_min": 18, "ores": ["stone", "coal", "iron", "gold", "amethyst", "lapis", "emerald", "ruby"]},
    {"level_min": 23, "ores": ["stone", "coal", "iron", "gold", "amethyst", "lapis", "emerald", "ruby", "diamond"]},
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
    ("found_coins",   "Ты нашёл кошелёк 💰  +{n} монет",  "coins:+", 230),
    ("pet_cat",       "Погладил кошку 😸     +{n} XP",      "xp:+",    120),
    ("robbery",       "Тебя ограбили! −{n} монет",       "coins:-", 80),
    ("miner_snack",   "Шахтёрский перекус 🥪   +{n} энергии",  "energy:+",20),
    ("emergency_exit",   "Выход из шахты засыпало!   -{n} энергии",  "energy:-",15),
    ("emergency_exit_2",   "Выход из шахты засыпало! Но ты смог выбраться вовремя,   +{n} XP",  "xp:+",40),
]

def pick_chance_event() -> ChanceEvent|None:
    if random.random() > 0.30:          # лише 30 % шанс, що подія взагалі трапиться
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

    txt=(f"🏔️ {mention}, ты вернулся на поверхность!\n"
         f"<b>{amount}×{ore['emoji']} {ore['name']}</b> в мешке\n"
         f"XP +<b>{xp_gain}</b> | Streak {streak} дн. | Tier ×{bonus:.1f}\n"
         f"Бонус кирки +<b>{int(pick_bonus*100)} %</b>"
         + ("\n⚠️ Кирка сломалась! /repair" if broken else "")
         + extra_txt)

    await bot.send_message(cid,txt,parse_mode="HTML")
    logging.info("Mining result sent: chat=%s uid=%s", cid, uid)
    
# ────────── Smelt Task ──────────
async def smelt_timer(bot:Bot,cid:int,uid:int,rec:dict,cnt:int,torch_mult:float):
    await asyncio.sleep(get_smelt_duration(cnt,torch_mult))
    await add_item(cid,uid,rec["out_key"],cnt)
    await db.execute("UPDATE progress_local SET smelt_end=NULL WHERE chat_id=:c AND user_id=:u",
                     {"c":cid,"u":uid})
    member = await bot.get_chat_member(cid, uid)
    nick = member.user.full_name
    await bot.send_message(cid,f"🔥 {nick}! Переплавка закончена: {cnt}×{rec['out_name']}", parse_mode="HTML")

# ────────── /dstart ──────────
@router.message(Command("dstart"))
async def start_cmd(message: types.Message):
    await create_user(message.from_user.id, message.from_user.username or message.from_user.full_name)
    msg = await message.answer_photo(
        START_IMG_ID,
        caption="Привет, будущий шахтёр! ⛏️ Регистрация прошла успешно. Используй /mine, чтобы копать ресурсы!",
    )
    register_msg_for_autodelete(message.chat.id, msg.message_id)

# ────────── /dprofile ──────────
@router.message(Command("dprofile"))
async def profile_cmd(message: types.Message):
    cid, uid = await cid_uid(message)
    # ensure user exists
    await create_user(message.from_user.id, message.from_user.username or message.from_user.full_name)

    # обчислюємо енергію та голод
    energy, _ = await update_energy(cid, uid)
    hunger, _ = await update_hunger(cid, uid)

    prog    = await get_progress(cid, uid)
    lvl     = prog.get("level", 1)
    xp      = prog.get("xp", 0)
    next_xp = lvl * 80
    streaks = prog.get("streak", 0)

    # Кирка та її міцність
    current         = prog.get("current_pickaxe") or "wooden_pickaxe"
    if current == "wood_pickaxe":
        current = "wooden_pickaxe"
    dur_map         = _json2dict(prog.get("pick_dur_map"))
    dur_max_map     = _json2dict(prog.get("pick_dur_max_map"))
    pick = PICKAXES.get(current, {"name":"–"})
    pick_name       = pick["name"]
    dur             = dur_map.get(current,      PICKAXES[current]["dur"])
    dur_max         = dur_max_map.get(current,  PICKAXES[current]["dur"])

    # Pass
    has_pass    = prog.get("cave_pass", False)
    expires     = prog.get("pass_expires")
    cave_cases  = prog.get("cave_cases", 0)
    if has_pass and expires:
        pass_str = expires.strftime("%d.%m.%Y")
    else:
        pass_str = "Не активирован"

    balance = await get_money(cid, uid)

    builder = InlineKeyboardBuilder()
    builder.button(text="📦 Инвентарь", callback_data=f"dprofile:dinventory:{uid}")
    builder.button(text="🛒 Магазин",    callback_data=f"dprofile:dshop:{uid}")
    builder.button(text="⛏️ Шахта",      callback_data=f"dprofile:dmine:{uid}")
    builder.button(text="💎 Cave Pass",      callback_data=f"dprofile:dcavepass:{uid}")
    builder.adjust(1)

    text = (
        f"👤 <b>Профиль:</b> {message.from_user.full_name}\n"
        f"⭐ <b>Уровень:</b> {lvl} (XP {xp}/{next_xp})\n"
        f"🔥 <b>Серия:</b> {streaks}\n" 
        f"💎 <b>Cave Pass:</b> {pass_str}\n\n"
        f"🔋 <b>Энергия:</b> {energy}/100\n"
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
@router.callback_query(F.data.startswith("dprofile:"))
async def profile_callback(callback: types.CallbackQuery):
    data = callback.data.split(":")
    # format: ['profile', action, original_uid]
    if len(data) != 3:
        return await callback.answer()
    _, action, orig_uid = data
    orig_uid = int(orig_uid)
    # тільки автор може натискати
    if callback.from_user.id != orig_uid:
        return await callback.answer("Эта кнопка не для тебя", show_alert=True)
    await callback.answer()

    # передаємо виконання команді
    if action == "dinventory":
        await inventory_cmd(callback.message, user_id=orig_uid)
    elif action == "dshop":
        await shop_cmd(callback.message)
    elif action == "dmine":
        await mine_cmd(callback.message, user_id=orig_uid)
    elif action == "dcavepass":
        await cavepass_cmd(callback.message)

# ────────── /mine ──────────(F.data.startswith("profile:"))
async def profile_callback(cb: types.CallbackQuery):
    await cb.answer()
    act = cb.data.split(":", 1)[1]
    if act == "dinventory":
        await inventory_cmd(cb.message, cb.from_user.id)
    elif act == "dshop":
        await shop_cmd(cb.message, cb.from_user.id)
    elif act == "dmine":
        await mine_cmd(cb.message, cb.from_user.id)
    elif act == "dcavepass":
        await cavepass_cmd(cb.message)

# ────────── /dmine ──────────
@router.message(Command("dmine"))
async def mine_cmd(message: types.Message, user_id: int | None = None):
    cid, uid = await cid_uid(message)
    if user_id:
        uid = user_id
    user = await get_user(uid)
    if not user:
        return await message.reply("Сперва /dstart")

    energy, _ = await update_energy(cid, uid)
    hunger, _ = await update_hunger(cid, uid)
    if energy <= 15:
        return await message.reply(f"😴 Недостаточно энергии {energy} (20 - минимум). Отдохни.")
    if hunger < HUNGER_LIMIT:
        return await message.reply(f"🍽️ Ты слишкон голоден {hunger} (20 - минимум), сперва /eat!")

    prog = await get_progress(cid, uid)

    raw_map = prog.get("pick_dur_map") or "{}"
    try:
        dur_map = json.loads(raw_map) if isinstance(raw_map, str) else raw_map
    except ValueError:
        dur_map = {}

    cur_pick = prog.get("current_pickaxe")
    if cur_pick and dur_map.get(cur_pick, 0) == 0:
            return await message.reply("⚠️ Кирка сломана! /repair")
    if prog["mining_end"] and prog["mining_end"] > dt.datetime.utcnow():
        delta = prog["mining_end"] - dt.datetime.utcnow()
        left = max(1, round(delta.total_seconds() / 60))
        return await message.reply(f"⛏️ Ты ещё в шахте, осталось {left} мин.")

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
    sec      = get_mine_duration(tier)
    minutes  = max(1, round(sec / 60))
    msg = await message.reply(f"⛏️ Ты спускаешься в шахту на <b>{minutes}</b> мин.\n🔋 Энергия −12 / Голод −10. Удачи!")
    register_msg_for_autodelete(message.chat.id, msg.message_id)
    asyncio.create_task(mining_task(message.bot, cid, uid, tier, ores, bonus_tier))

# ────────── /inventory ──────────
@router.message(Command("dinventory"))
async def inventory_cmd(message: types.Message, user_id: int | None = None):
    cid, uid = await cid_uid(message)
    if user_id:
        uid = user_id
    inv = await get_inventory(cid, uid)
    balance = await get_money(cid, uid)

    lines = [f"🧾 Баланс: {balance} монет", "<b>📦 Инвентарь:</b>"]
    current_pick = (await get_progress(cid, uid)).get("current_pickaxe")
    for row in inv:
        if row["item"] == current_pick:
            continue
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
    "камень": "stone",
    "уголь": "coal",
    "железная руда": "iron",
    "железо": "iron",
    "золото": "gold",
    "аметист": "amethyst",
    "алмаз": "diamond",
    "изумруд": "emerald",
    "лазурит": "lapis",
    "рубин": "ruby",
})

@router.message(Command("dsell"))
async def sell_cmd(message: types.Message):
    cid, uid = await cid_uid(message)
    text = message.text or ""
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        return await message.reply("Как продать: /sell 'ресурс' 'кол-во'")
    try:
        item_part, qty_str = parts[1].rsplit(maxsplit=1)
    except ValueError:
        return await message.reply("Как продать: /sell 'ресурс' 'кол-во'")
    if not qty_str.isdigit():
        return await message.reply("Кол-во должно быть числом!")
    qty = int(qty_str)
    item_key = ALIASES.get(item_part.lower(), item_part.lower())
    if item_key not in ITEM_DEFS or "price" not in ITEM_DEFS[item_key]:
        return await message.reply("Не принимается 😕")
    inv = {r["item"]: r["qty"] for r in await get_inventory(cid, uid)}
    have = inv.get(item_key, 0)
    if have < qty:
        return await message.reply(f"У тебя только {have}×{item_part}")
    await add_item(cid, uid, item_key, -qty)
    earned = ITEM_DEFS[item_key]["price"] * qty
    await add_money(cid, uid, earned)
    msg = await message.reply(f"Продано {qty}×{item_part} за {earned} монет 💰")
    register_msg_for_autodelete(message.chat.id, msg.message_id)

# ────────── /smelt (async) ──────────
@router.message(Command("dsmelt"))
async def smelt_cmd(message: types.Message):
    cid, uid = await cid_uid(message)

    # ───── 1. Парсимо аргументи ─────
    try:
        _, args = message.text.split(maxsplit=1)
        ore_part, qty_str = args.rsplit(maxsplit=1)
    except ValueError:
        return await message.reply("Как переплавить: /smelt 'руда' 'кол-во'")

    if not qty_str.isdigit():
        return await message.reply("Кол-во должно быть числом!")
    qty = int(qty_str)

    ore_key = SMELT_INPUT_MAP.get(ore_part.lower().strip())
    if not ore_key:
        return await message.reply("Не знаю такой руды 🙁")

    recipe = SMELT_RECIPES[ore_key]
    need_for_one = recipe["in_qty"]

    # ───── 2. Чи вистачає ресурсів? ─────
    inv = {r["item"]: r["qty"] for r in await get_inventory(cid, uid)}
    have_ore = inv.get(ore_key, 0)
    if have_ore < qty:
        return await message.reply(f"У тебя только {have_ore}")

    # Скільки слитків реально можна зробити
    cnt = qty // need_for_one
    if cnt < 1:
        return await message.reply(f"Нужно минимум {need_for_one}× для одного слитка")

    # ───── 3. Списуємо руду ─────
    used = cnt * need_for_one
    await add_item(cid, uid, ore_key, -used)

    # ───── 4. Torch Bundle (опційно) ─────
    torch_mult = 1.0
    torch_msg = ""
    if inv.get("torch_bundle", 0) > 0:
        torch_mult = TORCH_SPEEDUP        # 0 .7  →  30 % швидше
        await add_item(cid, uid, "torch_bundle", -1)
        torch_msg = "🕯️ Факел использован — плавка ускорена на 30%!\n"

    # ───── 5. Тривалість та таймер ─────
    duration = get_smelt_duration(cnt, torch_mult)   # сек
    await db.execute(
        "UPDATE progress_local SET smelt_end = :e "
        "WHERE chat_id = :c AND user_id = :u",
        {"e": dt.datetime.utcnow() + dt.timedelta(seconds=duration),
         "c": cid, "u": uid}
    )
    asyncio.create_task(smelt_timer(message.bot, cid, uid, recipe, cnt, torch_mult))

    sec      = duration
    minutes  = max(1, round(sec / 60))
    # ───── 6. Відповідь та autodelete ─────
    msg = await message.reply(
        f"{torch_msg}🔥 Забрасываем {cnt} руды в печь.\n"
        f"(⏲️ Через <b>{minutes}</b> минут получим {recipe['out_name']}×{cnt}.)"
    )
    register_msg_for_autodelete(message.chat.id, msg.message_id)

# ────────── /craft ──────────
@router.message(Command("dcraft"))
async def craft_cmd(message: types.Message):
    cid, uid = await cid_uid(message)
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        return await message.reply("/craft 'название'")
    craft_name = parts[1].lower().strip()
    recipe = CRAFT_RECIPES.get(craft_name)
    if not recipe:
        return await message.reply("Рецепт не найден")
    inv = {r["item"]: r["qty"] for r in await get_inventory(cid, uid)}
    for k, need in recipe["in"].items():
        if inv.get(k, 0) < need:
            return await message.reply("Не хватает ресурсов")
    for k, need in recipe["in"].items():
        await add_item(cid, uid, k, -need)
    await add_item(cid, uid, recipe["out_key"], 1)
    msg = await message.reply(f"🎉 Создано: {recipe['out_name']}!")
    register_msg_for_autodelete(message.chat.id, msg.message_id)

# ────────── /stats ──────────
@router.message(Command("dstats"))
async def stats_cmd(message: types.Message):
    cid, uid = await cid_uid(message)
    builder = InlineKeyboardBuilder()
    builder.button(text="🏆 Топ за балансом", callback_data="dstats:dbalance")
    builder.button(text="🎖️ Топ за уровнем", callback_data="dstats:dlevel")
    builder.button(text="📊 Топ за ресурсами", callback_data="dstats:dresources")
    builder.adjust(1)
    msg = await message.answer_photo(
        STATS_IMG_ID,
        caption="📊 <b>Статистика</b> — выберите топ:",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
    register_msg_for_autodelete(message.chat.id, msg.message_id)

@router.callback_query(F.data.startswith("dstats:"))
async def stats_callback(callback: CallbackQuery):
    await callback.answer()
    cid, _ = await cid_uid(callback.message)
    typ = callback.data.split(":", 1)[1]
    lines: list[str] = []

    if typ == "dbalance":
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

    elif typ == "dlevel":
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
            lines.append(f"{i}. {mention} — уровень {lvl} (XP {xp})")

    elif typ == "dresources":
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

            lines.append(f"{i}. {mention} — {total} ресурсов")

    else:
        return

    text = "\n".join(lines) if lines else "Нет данных"
    msg = await callback.message.answer_photo(
        STATS_IMG_ID,
        caption=text,
        parse_mode="HTML"
    )
    register_msg_for_autodelete(callback.message.chat.id, msg.message_id)

@router.message(Command("drepair"))
async def repair_cmd(message: types.Message):
    cid, uid = await cid_uid(message)
    prog = await get_progress(cid, uid)

    pick_key = prog.get("current_pickaxe")
    if not pick_key:
        return await message.reply("У тебя пока нет активной кирки.")

    # ▸ тут приводимо JSONB → dict
    dur_map     = _jsonb_to_dict(prog.get("pick_dur_map"))
    dur_max_map = _jsonb_to_dict(prog.get("pick_dur_max_map"))

    dur     = dur_map.get(pick_key, 0)
    dur_max = dur_max_map.get(pick_key, PICKAXES[pick_key]["dur"])

    if dur >= dur_max:
        return await message.reply("🛠️ Кирка в идеальном состоянии!")

    cost = (dur_max - dur) * 2
    if (await get_money(cid, uid)) < cost:
        return await message.reply("Недостаточно монет для ремонта.")

    await add_money(cid, uid, -cost)
    # Δ = скільки бракує до max
    await change_dur(cid, uid, pick_key, dur_max - dur)

    await message.reply(
        f"🛠️ {PICKAXES[pick_key]['name']} отремонтирована до "
        f"{dur_max}/{dur_max} за {cost} монет!"
    )

TELEGRAPH_LINK = "https://telegra.ph/Cave-Miner---Info-06-17" 

# /about
@router.message(Command("dabout"))
async def about_cmd(message: types.Message):
    text = link("🔍 О БОТЕ ⬩ РУКОВОДСТВО ⬩ КОМАНДЫ", TELEGRAPH_LINK)
    msg = await message.answer_photo(
        ABOUT_IMG_ID,
        caption=text, 
        parse_mode="HTML"
    )
    register_msg_for_autodelete(message.chat.id, msg.message_id)

# /report <bug text>
@router.message(Command("dreport"))
async def report_cmd(message: types.Message):
    cid, uid = await cid_uid(message)
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return await message.reply("❗ Использование: /report 'описание'")

    bug_text = args[1]
    report_line = f"🐞 Сообщение от {message.from_user.full_name} ({uid}):\n{bug_text}"

    # відправка мені
    ADMIN_ID = 700929765 
    try:
        msg = await message.bot.send_message(ADMIN_ID, report_line)
    except:
        pass

    msg = await message.reply("✅ Спасибо, сообщение передано!")

    register_msg_for_autodelete(message.chat.id, msg.message_id)

@router.message(Command("dautodelete"))
async def autodelete_cmd(message: types.Message, bot: Bot):
    cid, uid = await cid_uid(message)
    parts = message.text.strip().split()

    if message.chat.type in ("group", "supergroup"):
        member = await bot.get_chat_member(cid, uid)
        if member.status not in (
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.CREATOR
        ):
            return await message.reply("❗ Настройка автоудаления доступна только администратору или создателю группы.")
    
    if len(parts) != 2 or not parts[1].isdigit():
        return await message.reply("❗ Использование: /autodelete 60 (от 1 до 720 мин, или 0 чтобы отключить)")
    minutes = int(parts[1])
    if not (0 <= minutes <= 720):
        return await message.reply("❗ Введи значение от 0 до 720 минут")
    await db.execute(
        "UPDATE progress_local SET autodelete_minutes=:m WHERE chat_id=:c AND user_id=:u",
        {"m": minutes, "c": cid, "u": uid}
    )
    
    if minutes == 0:
        msg = await message.reply("🧹 Автоудаление отключено. Сообщения будут оставаться в чате.")
    else:
        msg = await message.reply(f"🧼 Автоудаление активировано: каждые {minutes} минут бот будет чистить свои сообщения.")
    register_msg_for_autodelete(message.chat.id, msg.message_id)

