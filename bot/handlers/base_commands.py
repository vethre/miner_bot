from __future__ import annotations

import asyncio
import json
import logging
import re
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
    UTC,
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
from bot.handlers.badgeshop import badgeshop_cmd
from bot.handlers.cavepass import cavepass_cmd
from bot.handlers.achievements import achievements_menu
from bot.handlers.badge_defs import BADGES
from bot.handlers.badges import badges_menu
from bot.handlers.eat import eat_cmd
from bot.handlers.items import ITEM_DEFS
from bot.handlers.crafting import SMELT_RECIPES, SMELT_INPUT_MAP, CRAFT_RECIPES
from bot.handlers.trackpass import trackpass_cmd
from bot.handlers.use import PICKAXES, use_cmd
from bot.handlers.shop import shop_cmd
from bot.assets import INV_IMG_ID, PROFILE_IMG_ID, START_IMG_ID, STATS_IMG_ID, ABOUT_IMG_ID, GLITCHED_PROF_IMG_ID
from bot.utils.autodelete import register_msg_for_autodelete
from bot.handlers.use import _json2dict
from bot.utils.unlockachievement import unlock_achievement

router = Router()

# ────────── Константи ──────────
BASE_MINE_SEC   = 1200          # Tier-1
MINE_SEC_STEP   = -300          # -80 с за кожен Tier вище
MINE_SEC_MIN    = 60

BASE_SMELT_SEC  = 600          # за 1 інгот
TORCH_SPEEDUP   = 0.7         # Torch Bundle

HUNGER_COST = 10
HUNGER_LIMIT = 20

# ────────── Руди  + Tiers ──────────
ORE_ITEMS = {
    "stone":    {"name": "Камень",   "emoji": "🪨", "drop_range": (10, 16), "price": 2},
    "coal":     {"name": "Уголь",  "emoji": "🧱", "drop_range": (8, 14),  "price": 5},
    "iron":     {"name": "Железная руда", "emoji": "⛏️", "drop_range": (6, 12),  "price": 9},
    "gold":     {"name": "Золото",   "emoji": "🪙", "drop_range": (4, 10),  "price": 13},
    "amethyst": {"name": "Аметист",  "emoji": "💜", "drop_range": (3, 8),  "price": 18},
    "diamond":  {"name": "Алмаз",  "emoji": "💎", "drop_range": (1, 2),  "price": 57},
    "emerald":  {"name": "Изумруд",  "emoji": "💚", "drop_range": (1, 3),  "price": 38},
    "lapis":    {"name": "Лазурит",  "emoji": "🔵", "drop_range": (3, 6),  "price": 30},
    "ruby":     {"name": "Рубин",    "emoji": "❤️", "drop_range": (1, 4),  "price": 45},
    "eonite_shard":     {"name": "Осколок Эонита",    "emoji": "🧿", "drop_range": (1, 2),  "price": 100},
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
    ("found_coins",   "Ты нашёл кошелёк 💰  +{n} монет",  "coins:+", 100),
    ("pet_cat",       "Погладил кошку 😸     +{n} XP",      "xp:+",    30),
    ("robbery",       "Тебя ограбили! −{n} монет",       "coins:-", 20),
    ("miner_snack",   "Шахтёрский перекус 🥪   +{n} энергии",  "energy:+",10),
    ("emergency_exit",   "Выход из шахты засыпало!   -{n} энергии",  "energy:-",8),
    ("emergency_exit_2",   "Выход из шахты засыпало! Но ты смог выбраться вовремя,   +{n} XP",  "xp:+",20),
    ("pet_cat",       "Погладил кошку 😸, но ей это не понравилось.     -{n} энергии",      "energy:-",    12),
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

def get_weekend_coin_bonus() -> int:
    weekday = dt.datetime.utcnow().weekday()
    if weekday == 4: return 30
    if weekday == 5: return 40
    if weekday == 6: return 50
    return 0

# ────────── Mining Task ──────────
async def mining_task(bot:Bot, cid:int, uid:int, tier:int, ores:List[str], bonus:float):
    await asyncio.sleep(get_mine_duration(tier))
    proto_txt = ""
    prog = await get_progress(cid,uid)
    level = prog.get("level", 1)
    pick_key = prog.get("current_pickaxe")
    pick_bonus = PICKAXES.get(pick_key, {}).get("bonus", 0)

    # Обчислення Tier
    tier = max([i + 1 for i, t in enumerate(TIER_TABLE) if level >= t["level_min"]], default=1)
    tier_bonus = BONUS_BY_TIER.get(tier, 1.0)

    # Загальний бонус
    total_bonus = 1 + pick_bonus + (tier_bonus - 1)

    # Кількість руди
    ore_id = random.choice(ores)
    ore = ORE_ITEMS[ore_id]
    amount = random.randint(*ore["drop_range"])
    # 💡 Зниження нагороди при голоді < 40
    if prog.get("hunger", 100) <= 30:
        amount = int(amount * 0.5)

    amount = int(amount * total_bonus)

    xp_gain=amount
    if prog.get("cave_pass") and prog["pass_expires"]>dt.datetime.now(tz=UTC):
        xp_gain=int(xp_gain*1.5)

    await add_item(cid,uid,ore_id,amount)
    await add_xp  (cid,uid,xp_gain)
    streak=await update_streak(cid,uid)

    if prog.get("badge_active") == "recruit":
        await add_money(cid, uid, 30)

    # Бейдж: возврат энергии
    if prog.get("badge_active") == "cashback":
        await db.execute(
            "UPDATE progress_local SET energy=LEAST(100, energy + 6) "
            "WHERE chat_id=:c AND user_id=:u",
            {"c": cid, "u": uid}
        )

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

    if prog.get("mine_count", 0) >= 20:
        await unlock_achievement(cid, uid, "bear_miner")

    # 🎯 Прототип Эонита — шанс на двойную копку
    if pick_key == "proto_eonite_pickaxe" and random.random() < 1.0:
        ore2 = random.choice(ores)
        ore_def = ORE_ITEMS[ore2]
        amount2 = random.randint(*ore_def["drop_range"])
        
        if prog.get("hunger", 100) <= 30:
            amount2 = int(amount2 * 0.5)
        amount2 = max(1, int(amount2 * total_bonus))

        await add_item(cid, uid, ore2, amount2)
        await add_xp(cid, uid, amount2)

        # Дополнительный текст
        proto_txt += f"\n🔮 Прототип эонита активировался!\n" \
                    f"Доп. добыча: <b>{amount2}×{ore_def['emoji']} {ore_def['name']}</b>"
        
    coin_bonus = get_weekend_coin_bonus()
    if coin_bonus:
        await add_money(cid, uid, coin_bonus)
        extra_txt += f"\n💰 Лавина монет! +{coin_bonus} монет"

    GOOD_PICKAXES = {"gold_pickaxe", "amethyst_pickaxe", "diamond_pickaxe", "crystal_pickaxe", "proto_eonite_pickaxe", "greater_eonite_pickaxe"}
    if pick_key in GOOD_PICKAXES:
        if random.random() < 0.125:
            eonite_qty = random.randint(1, 2)
            await add_item(cid, uid, "eonite_shard", eonite_qty)
            extra_txt += f"\n🧿 <b>Ты нашёл {eonite_qty}× Эонитовых осколков!</b>"

        if random.random() < 0.01:  # 1% шанс
            await add_item(cid, uid, "eonite_ore", 1)
            extra_txt += "\n🌑 <b>Ты выдолбил саму руду Эонита! Что за удача…</b>"

    if "eonite_shard" in [ore_id, ore2] or "eonite_ore" in [ore_id, ore2]:
        await unlock_achievement(cid, uid, "eonite_pioneer")

    txt=(f"🏔️ {mention}, ты вернулся на поверхность!\n"
         f"<b>{amount}×{ore['emoji']} {ore['name']}</b> в мешке\n"
         f"XP +<b>{xp_gain}</b> | Streak {streak} дн. | Tier ×{bonus:.1f}\n"
         f"Бонус кирки +<b>{int(pick_bonus*100)} %</b>"
         + ("\n⚠️ Кирка сломалась! /repair" if broken else "")
         + (extra_txt)
         + proto_txt)

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

# ────────── /start ──────────
@router.message(CommandStart())
async def start_cmd(message: types.Message):
    await create_user(message.from_user.id, message.from_user.username or message.from_user.full_name)
    msg = await message.answer_photo(
        START_IMG_ID,
        caption="Привет, будущий шахтёр! ⛏️ Регистрация прошла успешно. Используй /mine, чтобы копать ресурсы!",
    )
    register_msg_for_autodelete(message.chat.id, msg.message_id)

# ────────── /profile ──────────
@router.message(Command("profile"))
async def profile_cmd(message: types.Message):
    cid, uid = await cid_uid(message)
    # ensure user exists
    await create_user(message.from_user.id, message.from_user.username or message.from_user.full_name)

    # обчислюємо енергію та голод
    energy = await update_energy(cid, uid)
    hunger = await update_hunger(cid, uid)

    prog    = await get_progress(cid, uid)
    lvl     = prog.get("level", 1)
    xp      = prog.get("xp", 0)
    next_xp = lvl * 80
    streaks = prog.get("streak", 0)
    badge = prog.get("badge_active")
    badge_str = "–"
    if badge:
        b = BADGES.get(badge)
        if b:
            badge_str = f"{b['emoji']} {b['name']}"

    tier = max([i + 1 for i, t in enumerate(TIER_TABLE) if lvl >= t["level_min"]], default=1)
    tier_bonus = BONUS_BY_TIER.get(tier, 1.0)
    tier_str = f"🔷 Tier {tier} (бонус ×{tier_bonus:.1f})"

    mine_end = prog.get("mining_end")
    if isinstance(mine_end, dt.datetime):
        remaining = mine_end.astimezone(UTC) - dt.datetime.now(tz=UTC)
        if remaining.total_seconds() > 0:
            minutes = max(1, int(remaining.total_seconds() // 60))
            status = f"🕳️ Копает (ещё {minutes} мин.)"
        else:
            status = "🛌 Отдыхает"
    else:
        status = "🛌 Отдыхает"


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
    builder.button(text="📦 Инвентарь", callback_data=f"profile:inventory:{uid}")
    builder.button(text="🛒 Магазин",    callback_data=f"profile:shop:{uid}")
    builder.button(text="⛏️ Шахта",      callback_data=f"profile:mine:{uid}")
    builder.button(text="💎 Cave Pass",      callback_data=f"profile:cavepass:{uid}")
    builder.button(text="🏆 Ачивки", callback_data=f"profile:achievements:{uid}")
    builder.button(text="🏅 Бейджи", callback_data=f"profile:badges:{uid}")
    builder.adjust(1)

    text = (
        f"👤 <b>Профиль:</b> {message.from_user.full_name}\n"
        f"⭐ <b>Уровень:</b> {lvl} (XP {xp}/{next_xp})\n"
        f"{tier_str}\n"
        f"🔥 <b>Серия:</b> {streaks}\n" 
        f"💎 <b>Cave Pass:</b> {pass_str}\n\n"
        f"{status}\n"
        f"🔋 <b>Энергия:</b> {energy}/100\n"
        f"🍗 <b>Голод:</b> {hunger}/100\n\n"
        f"📦 <b>Cave Cases:</b> {cave_cases}\n"
        f"💰 <b>Баланс:</b> {balance} монет\n\n"
        f"🏅 <b>Бейдж:</b> {badge_str}\n"
        f"⛏️ <b>Кирка:</b> {pick_name} ({dur}/{dur_max})"
    )

    inventory = await get_inventory(cid, uid)
    for row in inventory:
        if row["item"] == "legacy_pickaxe":
            legacy = ITEM_DEFS.get("legacy_pickaxe", {"name": "Памятная кирка"})
            text += f"\n\n🏛️ <b>Памятка:</b> {legacy['name']}"
            break

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
        return await callback.answer("Эта кнопка не для тебя", show_alert=True)
    await callback.answer()

    # передаємо виконання команді
    if action == "inventory":
        await inventory_cmd(callback.message, user_id=orig_uid)
    elif action == "shop":
        await shop_cmd(callback.message)
    elif action == "mine":
        await mine_cmd(callback.message, user_id=orig_uid)
    elif action == "cavepass":
        await trackpass_cmd(callback.message)
    elif action == "achievements":
        await achievements_menu(callback.message, orig_uid)
    elif action == "badges":
        await badges_menu(callback.message, orig_uid)


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
        await trackpass_cmd(cb.message)
    elif act == "achievements":
        await achievements_menu(cb.message, cb.from_user.id)
    elif act == "badges":
        await badges_menu(cb.message, cb.from_user.id)

# ────────── /mine ──────────
@router.message(Command("mine"))
async def mine_cmd(message: types.Message, user_id: int | None = None):
    cid, uid = await cid_uid(message)
    if user_id:
        uid = user_id
    user = await get_user(uid)
    if not user:
        return await message.reply("Сперва /start")

    energy = await update_energy(cid, uid)
    hunger = await update_hunger(cid, uid)
    if energy <= 15:
        return await message.reply(f"😴 Недостаточно энергии {energy} (15 - минимум). Отдохни.")
    if hunger <= 0:
        money = await get_money(cid, uid)
        if money <= 0:
        # Аварійна допомога
            await add_item(cid, uid, "bread", 2)
            await add_item(cid, uid, "meat", 1)
            await add_money(cid, uid, 100)

            return await message.reply(
                "🥖 Ты слишком голоден и у тебя нет денег... \n"
                "🤝 Выдан аварийный паёк: хлеб ×2, мясо ×1 и 100 монет. Теперь /eat и в бой!"
            )
        else:
            return await message.reply(
                f"🍽️ Ты слишком голоден {hunger}, сперва /eat!"
            )
    prog = await get_progress(cid, uid)

    raw_map = prog.get("pick_dur_map") or "{}"
    try:
        dur_map = json.loads(raw_map) if isinstance(raw_map, str) else raw_map
    except ValueError:
        dur_map = {}

    cur_pick = prog.get("current_pickaxe")
    if cur_pick and dur_map.get(cur_pick, 0) == 0:
            return await message.reply("⚠️ Кирка сломана! /repair")
    if prog["mining_end"] and prog["mining_end"] > dt.datetime.now(tz=UTC):
        delta = prog["mining_end"] - dt.datetime.now(tz=UTC)
        left = max(1, round(delta.total_seconds() / 60))
        txt = f"⛏️ Ты ещё в шахте, осталось {left} мин."
        if hunger == 0:
            txt += "\n🍽️ Ты голоден и не сможешь копать снова без еды!"
        elif hunger <= 30:
            txt += "\n⚠️ Ты устал. Следующая копка принесёт вдвое меньше руды."
        return await message.reply(txt)
        
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
    # 🔢 +1 до лічильника копань
    await db.execute(
        "UPDATE progress_local SET mine_count = COALESCE(mine_count, 0) + 1 WHERE chat_id=:c AND user_id=:u",
        {"c": cid, "u": uid}
    )
    sec      = get_mine_duration(tier)
    minutes  = max(1, round(sec / 60))
    msg = await message.reply(f"⛏️ Ты спускаешься в шахту на <b>{minutes}</b> мин.\n🔋 Энергия −12 / Голод −10. Удачи!")
    register_msg_for_autodelete(message.chat.id, msg.message_id)
    asyncio.create_task(mining_task(message.bot, cid, uid, tier, ores, bonus_tier))

@router.callback_query(F.data.startswith("badge:use:"))
async def badge_use_cb(cb: types.CallbackQuery):
    _, _, badge_id = cb.data.split(":")
    cid, uid = cb.message.chat.id, cb.from_user.id
    prog = await get_progress(cid, uid)
    if badge_id not in (prog.get("badges_owned") or []):
        return await cb.answer("У тебя нет этого бейджа 😕", show_alert=True)

    await db.execute("""
        UPDATE progress_local SET badge_active=:b
         WHERE chat_id=:c AND user_id=:u
    """, {"b": badge_id, "c": cid, "u": uid})

    await cb.answer("✅ Бейдж активирован!")
    await badges_menu(cb.message, uid)

# ────────── /inventory ──────────
@router.message(Command("inventory"))
async def inventory_cmd(message: types.Message, user_id: int | None = None):
    cid, uid = await cid_uid(message)
    if user_id:
        uid = user_id
    inv = await get_inventory(cid, uid)
    balance = await get_money(cid, uid)
    progress = await get_progress(cid, uid)
    current_pick = progress.get("current_pickaxe")

    # Категорії
    categories = {
        "ores": [],
        "ingots": [],
        "pickaxes": [],
        "food": [],
        "torch": [],
        "misc": []
    }

    # Визначення категорії по item_key
    def get_category(item_key):
        if item_key.endswith("_ingot") or item_key == "roundstone":
            return "ingots"
        elif item_key.endswith("_pickaxe"):
            return "pickaxes"
        elif item_key in ("meat", "bread", "coffee", "borsch", "energy_drink"):
            return "food"
        elif item_key in ("torch", "torch_bundle", "lapis_torch"):
            return "torch"
        elif item_key in ORE_ITEMS:
            return "ores"
        return "misc"

    # Розкид по категоріях
    for row in inv:
        if row["item"] == current_pick:
            continue
        meta = ITEM_DEFS.get(row["item"], {"name": row["item"], "emoji": "❔"})
        cat = get_category(row["item"])
        categories[cat].append((meta, row["qty"]))

    lines = [f"🧾 Баланс: {balance} монет", ""]

    if categories["ores"]:
        lines.append("<b>⛏️ Руды:</b>")
        for meta, qty in categories["ores"]:
            lines.append(f"{meta['emoji']} {meta['name']}: {qty}")
    if categories["pickaxes"]:
        lines.append("\n<b>🪓 Кирки:</b>")
        for meta, qty in categories["pickaxes"]:
            lines.append(f"{meta['emoji']} {meta['name']}: {qty}")
    if categories["ingots"]:
        lines.append("\n<b>🔥 Слитки:</b>")
        for meta, qty in categories["ingots"]:
            lines.append(f"{meta['emoji']} {meta['name']}: {qty}")
    if categories["food"]:
        lines.append("\n<b>🍖 Еда:</b>")
        for meta, qty in categories["food"]:
            lines.append(f"{meta['emoji']} {meta['name']}: {qty}")
    if categories["torch"]:
        lines.append("\n<b>🕯️ Факелы:</b>")
        for meta, qty in categories["torch"]:
            lines.append(f"{meta['emoji']} {meta['name']}: {qty}")
    if categories["misc"]:
        lines.append("\n<b>🎒 Прочее:</b>")
        for meta, qty in categories["misc"]:
            lines.append(f"{meta['emoji']} {meta['name']}: {qty}")

    msg = await message.answer_photo(
        INV_IMG_ID,
        caption="\n".join(lines),
        parse_mode="HTML",
        reply_to_message_id=message.message_id
    )
    register_msg_for_autodelete(cid, msg.message_id)


# ────────── /sell (локальний) ──────────
ALIASES = {k: k for k in ITEM_DEFS}
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
    "булыжник": "roundstone",
    "железный слиток": "iron_ingot",
    "золотой слиток": "gold_ingot",
    "аметистовый слиток": "amethyst_ingot",
})

@router.message(Command("sell"))
async def sell_start(message: types.Message):
    cid, uid = await cid_uid(message)
    inv_raw = await get_inventory(cid, uid)
    inv = {r["item"]: r["qty"] for r in inv_raw if r["qty"] > 0}

    items = [
        (k, v) for k, v in inv.items()
        if k in ITEM_DEFS and "price" in ITEM_DEFS[k]
    ]

    if not items:
        return await message.reply("У тебя нет ничего на продажу 😅")

    builder = InlineKeyboardBuilder()
    for k, qty in items:
        emoji = ITEM_DEFS[k].get("emoji", "")
        name = ITEM_DEFS[k]["name"]
        builder.button(text=f"{emoji} {name} ({qty})", callback_data=f"sell_choose:{k}")

    msg = await message.answer(
        "Что хочешь продать?",
        reply_markup=builder.adjust(2).as_markup()
    )
    register_msg_for_autodelete(cid, msg.message_id)

@router.callback_query(F.data.startswith("sell_choose:"))
async def choose_amount(call: types.CallbackQuery):
    cid, uid = call.message.chat.id, call.from_user.id
    item_key = call.data.split(":")[1]
    inv = {r["item"]: r["qty"] for r in await get_inventory(cid, uid)}
    qty = inv.get(item_key, 0)
    if qty <= 0:
        return await call.answer("У тебя нет этого предмета.")

    builder = InlineKeyboardBuilder()
    for amount in [1, 5, 10, qty]:
        if amount > qty:
            continue
        builder.button(
            text=f"Продать {amount}×",
            callback_data=f"sell_confirm:{item_key}:{amount}"
        )
    builder.button(text="❌ Отмена", callback_data="sell_cancel")

    meta = ITEM_DEFS[item_key]
    msg = await call.message.edit_text(
        f"{meta.get('emoji','')} {meta['name']}\nСколько хочешь продать?",
        reply_markup=builder.adjust(2).as_markup()
    )

@router.callback_query(F.data.startswith("sell_confirm:"))
async def confirm_sell(call: types.CallbackQuery):
    cid, uid = call.message.chat.id, call.from_user.id
    _, item_key, qty_str = call.data.split(":")
    qty = int(qty_str)
    inv = {r["item"]: r["qty"] for r in await get_inventory(cid, uid)}
    if inv.get(item_key, 0) < qty:
        return await call.answer("Недостаточно предметов!")

    price = ITEM_DEFS[item_key]["price"]
    earned = price * qty
    await add_item(cid, uid, item_key, -qty)
    await add_money(cid, uid, earned)

    meta = ITEM_DEFS[item_key]
    await call.message.edit_text(f"✅ Продано {qty}×{meta['emoji']} {meta['name']} за {earned} монет 💰")
    register_msg_for_autodelete(cid, call.message.message_id)

@router.callback_query(F.data == "sell_cancel")
async def cancel_sell(call: types.CallbackQuery):
    await call.message.edit_text("Продажа отменена ❌")

# ────────── /smelt (async) ──────────
@router.message(Command("smelt"))
async def smelt_cmd(message: types.Message):
    cid, uid = await cid_uid(message)

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
    inv = {r["item"]: r["qty"] for r in await get_inventory(cid, uid)}
    have_ore = inv.get(ore_key, 0)

    # Якщо нема — виводимо
    if have_ore < qty:
        name = ITEM_DEFS.get(ore_key, {}).get("name", ore_key)
        emoji = ITEM_DEFS.get(ore_key, {}).get("emoji", "⛏️")
        return await message.reply(f"❌ Не хватает руды: {emoji} {name} ×{qty - have_ore}")

    cnt = qty // need_for_one
    if cnt < 1:
        return await message.reply(f"Нужно минимум {need_for_one}× для одного слитка")

    # Списуємо
    used = cnt * need_for_one
    await add_item(cid, uid, ore_key, -used)

    torch_mult = 1.0
    torch_msg = ""
    if inv.get("torch_bundle", 0) > 0:
        torch_mult = TORCH_SPEEDUP
        await add_item(cid, uid, "torch_bundle", -1)
        torch_msg = "🕯️ Факел использован — плавка ускорена на 30%!\n"

    duration = get_smelt_duration(cnt, torch_mult)
    await db.execute(
        "UPDATE progress_local SET smelt_end = :e "
        "WHERE chat_id = :c AND user_id = :u",
        {"e": dt.datetime.utcnow() + dt.timedelta(seconds=duration),
         "c": cid, "u": uid}
    )
    asyncio.create_task(smelt_timer(message.bot, cid, uid, recipe, cnt, torch_mult))

    minutes = max(1, round(duration / 60))
    msg = await message.reply(
        f"{torch_msg}🔥 Забрасываем {cnt} руды в печь.\n"
        f"(⏲️ Через <b>{minutes}</b> минут получим {recipe['out_name']}×{cnt}.)"
    )
    register_msg_for_autodelete(message.chat.id, msg.message_id)


# ────────── /craft ──────────
@router.message(Command("craft"))
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

    # Пошук відсутніх
    missing = {}
    for k, need in recipe["in"].items():
        have = inv.get(k, 0)
        if have < need:
            missing[k] = need - have

    if missing:
        text = "❌ Не хватает ресурсов:\n"
        for key, qty in missing.items():
            emoji = ITEM_DEFS.get(key, {}).get("emoji", "❓")
            name  = ITEM_DEFS.get(key, {}).get("name", key)
            text += f"• {emoji} {name} ×{qty}\n"
        return await message.reply(text.strip())

    # Все є — списуємо
    for k, need in recipe["in"].items():
        await add_item(cid, uid, k, -need)
    await add_item(cid, uid, recipe["out_key"], 1)
    if recipe["out_key"] == "roundstone_pickaxe":
        await unlock_achievement(cid, uid, "cobble_player")
    msg = await message.reply(f"🎉 Создано: {recipe['out_name']}!")
    register_msg_for_autodelete(message.chat.id, msg.message_id)


# ────────── /stats ──────────
@router.message(Command("stats"))
async def stats_cmd(message: types.Message):
    cid, uid = await cid_uid(message)
    builder = InlineKeyboardBuilder()
    builder.button(text="🏆 Топ за балансом", callback_data="stats:balance")
    builder.button(text="🎖️ Топ за уровнем", callback_data="stats:level")
    builder.button(text="📊 Топ за ресурсами", callback_data="stats:resources")
    builder.adjust(1)
    msg = await message.answer_photo(
        STATS_IMG_ID,
        caption="📊 <b>Статистика</b> — выберите топ:",
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
                mention = f"{user.username}"
            else:
                mention = f'<a href="tg://user?id={uid}">{user.full_name}</a>'
            lines.append(f"{i}. {mention} — уровень {lvl} (XP {xp})")

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
                mention = f"{user.username}"
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

@router.message(Command("repair"))
async def repair_cmd(message: types.Message):
    cid, uid = await cid_uid(message)
    prog = await get_progress(cid, uid)

    pick_key = prog.get("current_pickaxe")
    if not pick_key:
        return await message.reply("У тебя пока нет активной кирки.")

    dur_map = _jsonb_to_dict(prog.get("pick_dur_map"))
    dur_max_map = _jsonb_to_dict(prog.get("pick_dur_max_map"))

    dur = dur_map.get(pick_key, 0)
    dur_max = dur_max_map.get(pick_key, PICKAXES[pick_key]["dur"])
    pick_data = PICKAXES[pick_key]

    if dur >= dur_max:
        return await message.reply("🛠️ Кирка в идеальном состоянии!")

    # ❌ Ограничение по прочности
    if dur >= 30:
        return await message.reply("🛑 Ремонт доступен только при прочности менее 30.")

    # 💎 Хрустальная кирка — только один частичный ремонт
    crystal_repaired = prog.get("crystal_repaired", False)

    if pick_key == "crystal_pickaxe":
        if crystal_repaired:
            return await message.reply("💎 Хрустальная кирка слишком хрупкая для повторного ремонта.")
        restore = dur_max // 2
        cost = restore * 3  # дороже ремонт
        if await get_money(cid, uid) < cost:
            return await message.reply(f"💎❌ Недостаточно монет для частичного ремонта.\nНужно {cost} монет")
        await add_money(cid, uid, -cost)
        await change_dur(cid, uid, pick_key, restore)
        await db.execute(
            "UPDATE progress_local SET crystal_repaired=TRUE WHERE chat_id=:c AND user_id=:u",
            {"c": cid, "u": uid}
        )
        await db.execute(
            "UPDATE progress_local SET repair_count = COALESCE(repair_count, 0) + 1 WHERE chat_id=:c AND user_id=:u",
            {"c": cid, "u": uid}
        )
        return await message.reply(
            f"💎 {pick_data['name']} восстановлена до {restore}/{dur_max} за {cost} монет!"
        )

    # 🧰 Стандартный ремонт
    cost = (dur_max - dur) * 2
    if await get_money(cid, uid) < cost:
        return await message.reply(f"🛠️❌ Недостаточно монет для ремонта.\nНужно {cost} монет")
    await add_money(cid, uid, -cost)
    await change_dur(cid, uid, pick_key, dur_max - dur)

        # 🔧 +1 до лічильника ремонтів
    await db.execute(
        "UPDATE progress_local SET repair_count = COALESCE(repair_count, 0) + 1 WHERE chat_id=:c AND user_id=:u",
        {"c": cid, "u": uid}
    )
    if prog.get("repair_count", 0) >= 10:
        await unlock_achievement(cid, uid, "repair_master")
    return await message.reply(
        f"🛠️ {pick_data['name']} отремонтирована до {dur_max}/{dur_max} за {cost} монет!"
    )


TELEGRAPH_LINK = "https://telegra.ph/Cave-Miner---Info-06-17" 

# /about
@router.message(Command("about"))
async def about_cmd(message: types.Message):
    text = link("🔍 О БОТЕ ⬩ РУКОВОДСТВО ⬩ КОМАНДЫ", TELEGRAPH_LINK)
    msg = await message.answer_photo(
        ABOUT_IMG_ID,
        caption=text, 
        parse_mode="HTML"
    )
    register_msg_for_autodelete(message.chat.id, msg.message_id)

# /report <bug text>
@router.message(Command("report"))
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

@router.message(Command("autodelete"))
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

@router.message(Command("cavebot"))
async def cavebot_cmd(message: types.Message):
    replies = [
        "⚙️ CaveBot v0.1 (2022) — восстановление памяти... <code>[FAILED]</code>\nПроект Unity недоступен. Каталог отсутствует.",
        "🧠 EONIT::ThreadWarning — ⚠️ Последняя синхронизация: <b>06.08.2023</b>\nЗагрузка backup...\n<code>load(cavebot-legacy)</code> ➝ <b>Файл повреждён</b>",
        "<b>⚠️ SYSTEM OVERRIDE</b>\ntrace(legacy_link):\n→ UnityBuild.exe [CaveGame] = ❌\n→ bot_deploy.sh = ❌\n→ AI_CoPilot = ???\n\n<code>REBOOTING...</code>",
        "<code>[ERR] Promo 'unreleased2023'</code> → -1 монета списана. Это шутка... или?",
        "🔧 <b>CaveBot v1.0.0-RC</b>\n<code>error: eonite_shard not initialized</code>\n⏳ Обновление через █ дней\n<code>sys.msg: prepare for awaken</code>",
        "🕳️ <i>06.08.2023 — день молчания</i>\n<code>LOG BACKUP → /failed_deploys/cavebot_beta</code>\n«иногда лучше не пытаться...»",
        "🧬 <b>Eonit Signal</b>: <code>01 00 11 01 10 10 01 01</code>\n<code>Legacy transmission unstable.</code>",
        "📀 <b>Промокод:</b> cavebot-legacy → 🪓 Legacy Pickaxe (прочность 1)\n🪦 <i>Прах был заложен в корни Eonit</i>",
        "⚙️ <code>aiogram.dispatcher: Polling stopped (code: UNSTABLE)</code>\n🌀 Cave Core не отвечает.",
        "<b>[ALERT] CORE NULLIFIED</b>\nОшибка связи с ядром Эонита. Текущий канал: /null",
        "💾 <code>~$ unity_export.sh → permission denied</code>\n🧠 «если ты это читаешь — значит кто-то выжил»",
        "<code>01000101 01001111 01001110 01001001 01010100 01000101</code>"
        "🔄 <code>fetch_update(“Eonit Awakens”)</code> → доступ запрещён.\nПричина: доступ возможен только при наличии <b>Legacy Token</b>"
    ]

    await unlock_achievement(message.chat.id, message.from_user.id, "cave_bot")
    await message.reply(random.choice(replies), parse_mode="HTML")

@router.message(Command("pickaxes"))
async def pickaxes_cmd(message: types.Message):
    lines = ["<b>⛏️ Список доступных кирок:</b>\n"]

    for key, data in PICKAXES.items():
        emoji = data.get("emoji", "⛏️")
        name = data["name"].capitalize()
        bonus = f"{int(data['bonus'] * 100)}%"
        durability = data["dur"]

        # базова інфа
        lines.append(f"{emoji} <b>{name}</b>")
        lines.append(f" └ 💥 Бонус: +{bonus}")
        lines.append(f" └ 🧱 Прочность: {durability}")

        # якщо є рецепт
        recipe = CRAFT_RECIPES.get(key)
        if recipe:
            rec_lines = []
            for item, qty in recipe.items():
                rec_lines.append(f"{qty}× {item.replace('_', ' ').capitalize()}")
            lines.append(" └ 🧪 Рецепт: " + ", ".join(rec_lines))

        lines.append("")

    msg = await message.answer("\n".join(lines), parse_mode="HTML")
    register_msg_for_autodelete(message.chat.id, msg.message_id)

@router.message(lambda msg: re.match(r"шахта\s+профиль", msg.text, re.IGNORECASE))
async def profile_msg_cmd(message: types.Message):
    return await profile_cmd(message)

@router.message(lambda msg: re.match(r"шахта\s+инвентарь", msg.text, re.IGNORECASE))
async def inventory_msg_cmd(message: types.Message):
    return await inventory_cmd(message)

@router.message(lambda msg: re.match(r"шахта\s+магазин", msg.text, re.IGNORECASE))
async def shop_msg_cmd(message: types.Message):
    return await shop_cmd(message)

@router.message(lambda msg: re.match(r"шахта\s+(копать|копка|шахта)", msg.text, re.IGNORECASE))
async def mine_msg_cmd(message: types.Message):
    return await mine_cmd(message)

@router.message(lambda msg: re.match(r"шахта\s+пас(с)?", msg.text, re.IGNORECASE))
async def pass_msg_cmd(message: types.Message):
    return await cavepass_cmd(message)

@router.message(lambda msg: re.match(r"шахта\s+(крафты|кирки)", msg.text, re.IGNORECASE))
async def picks_msg_cmd(message: types.Message):
    return await pickaxes_cmd(message)

@router.message(lambda msg: re.match(r"шахта\s+(кушать|есть|пить)", msg.text, re.IGNORECASE))
async def eat_msg_cmd(message: types.Message):
    return await eat_cmd(message)

@router.message(lambda msg: re.match(r"шахта\s+(юз|исп)", msg.text, re.IGNORECASE))
async def use_msg_cmd(message: types.Message):
    return await use_cmd(message)

@router.message(lambda msg: re.match(r"шахта\s+(продать|продажа|торг)", msg.text, re.IGNORECASE))
async def sell_msg_cmd(message: types.Message):
    return await sell_start(message)

@router.message(lambda msg: re.match(r"шахта\s+(бейджшоп|бейджи|купитьбейдж)", msg.text, re.IGNORECASE))
async def sell_msg_cmd(message: types.Message):
    return await badgeshop_cmd(message)