from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import List, Dict
import aiogram
from aiogram.utils.markdown import link
import random
import time
import datetime as dt
from typing import List
from matplotlib import pyplot as plt
import pandas as pd
from io import BytesIO

from aiogram import Router, Bot, types, F
from aiogram.types import BufferedInputFile
from aiogram.filters import Command, CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import CallbackQuery
from aiogram.enums import ChatMemberStatus

import bot
from bot.db import db, create_user, get_user
from bot.utils.adieu_chaos import ADIEU_ABSOLUTE, apply_chaos_to_message, chaos_loot, glitch_number
from bot.db_local import (
    UTC,
    add_xp_with_notify,
    cid_uid,
    add_item,
    add_money,
    add_xp,
    get_inventory,
    get_money,
    update_energy,
    update_hunger,
    get_progress,
    update_nickname,
    update_streak,
    add_energy,
    change_dur,
    _jsonb_to_dict,
    save_user_info,
)
from bot.handlers.badgeshop import badgeshop_cmd
from bot.handlers.cavepass import cavepass_cmd
from bot.handlers.achievements import achievements_menu
from bot.handlers.badge_defs import BADGES
from bot.handlers.badges import badges_menu, get_badge_effect
from bot.handlers.choice_events import maybe_send_choice_card
from bot.handlers.eat import eat_cmd
from bot.handlers.helmets import list_helmets_cmd, my_auctioned_helmets_cmd
from bot.handlers.items import ITEM_DEFS
from bot.handlers.crafting import RECIPES_BY_ID, SMELT_RECIPES, SMELT_INPUT_MAP, CRAFT_RECIPES
from bot.handlers.seals import SEALS, choose_seal, show_seals
from bot.handlers.use import PICKAXES, use_cmd
from bot.handlers.shop import shop_cmd
from bot.assets import INV_IMG_ID, PROFILE_IMG_ID, START_IMG_ID, STATS_IMG_ID, ABOUT_IMG_ID
from bot.utils.autodelete import register_msg_for_autodelete, reply_clean
from bot.handlers.use import _json2dict
from bot.handlers.cave_clash import add_clash_points, clashrank
from bot.utils.logger import send_log
from bot.utils.render_profile import render_profile_card
from bot.utils.unlockachievement import unlock_achievement
from bot.handlers.pass_track import add_pass_xp, trackpass_cmd

router = Router()

# ────────── Константи ──────────
BASE_MINE_SEC   = 300          # Tier-1
MINE_SEC_STEP   = -80          # -80 с за кожен Tier вище
MINE_SEC_MIN    = 60

BASE_SMELT_SEC  = 600          # за 1 інгот
TORCH_SPEEDUP   = 0.7         # Torch Bundle

HUNGER_COST = 10
HUNGER_LIMIT = 20

# ────────── Руди  + Tiers ──────────
ORE_ITEMS = {
    "stone":    {"name": "Камень",   "emoji": "🪨", "drop_range": (120, 250), "price": 10_000},
    "coal":     {"name": "Уголь",  "emoji": "🧱", "drop_range": (150, 260),  "price": 10_000},
    "iron":     {"name": "Железная руда", "emoji": "⛏️", "drop_range": (120, 240),  "price": 119_000},
    "gold":     {"name": "Золото",   "emoji": "🪙", "drop_range": (130, 200),  "price": 13_000},
    "amethyst": {"name": "Аметист",  "emoji": "💜", "drop_range": (120, 180),  "price": 18_000},
    "diamond":  {"name": "Алмаз",  "emoji": "💎", "drop_range": (20, 50),  "price": 57_000},
    "emerald":  {"name": "Изумруд",  "emoji": "💚", "drop_range": (30, 50),  "price": 38_000},
    "lapis":    {"name": "Лазурит",  "emoji": "🔵", "drop_range": (80, 140),  "price": 30_000},
    "ruby":     {"name": "Рубин",    "emoji": "❤️", "drop_range": (70, 130),  "price": 45_000},
    "obsidian_shard": {"name": "Обсидиановый осколок", "emoji": "🟣", "drop_range": (50, 70), "price": 85_000},
    "void_crystal": {"name": "Войд-хрусталь", "emoji": "🤍", "drop_range": (49, 69), "price": 100_000},
    "star_quartz": {"name": "Звездный квартц", "emoji": "🩷", "drop_range": (45, 65), "price": 155_000},
    "eonite_ingot": {"name": "Слиток Эонита", "emoji": "🪬", "drop_range": (40, 60), "price": 125_000},
    "sunset_ore":       {"name": "Руда Заката", "emoji": "🌇", "drop_range": (30, 50), "price": 100_000},
}

TIER_TABLE = [{"level_min": 0, "ores": ["stone", "gold", "amethyst", "lapis", "iron","emerald","eonite_ingot", "ruby","diamond","obsidian_shard","void_crystal","star_quartz","sunset_ore"]},]

"""
TIER_TABLE = [
    {"level_min": 1,  "ores": ["stone"]},
    {"level_min": 4,  "ores": ["stone", "iron"]},
    {"level_min": 8, "ores": ["stone", "iron", "gold"]},
    {"level_min": 13, "ores": ["stone", "iron", "gold", "amethyst", "lapis"]},
    {"level_min": 18, "ores": ["stone", "iron", "gold", "amethyst", "lapis", "emerald", "ruby"]},
    {"level_min": 23, "ores": ["stone", "iron", "gold", "amethyst", "lapis", "emerald", "ruby", "diamond"]},
    {"level_min": 28, "ores": ["stone","iron","gold","amethyst","lapis", "emerald","ruby","diamond","obsidian_shard"]},
    {"level_min": 40, "ores": ["iron","amethyst","emerald","ruby","diamond","obsidian_shard","void_crystal"]},
    {"level_min": 55, "ores": ["iron","emerald","ruby","diamond","obsidian_shard","void_crystal","star_quartz"]},
]
"""
BONUS_BY_TIER = 100000

INVENTORY_CAPS = {
    1: 60,    # Сумка
    2: 120,   # Рюкзак
    3: 240,   # Мешок
    4: 480,   # Хранилище
    5: 9999,  # Склад
    6: 1_500_000_000  # Воркшоп
}
INVENTORY_NAMES = {
    1: "Сумка",
    2: "Рюкзак",
    3: "Мешок",
    4: "Хранилище",
    5: "Склад",
    6: "Воркшоп"
}

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

async def is_event_active(code: str) -> bool: return False

# ─────────────── “Картки шансу” ───────────────
ChanceEvent = tuple[str, str, str, int]    
#          (key , text , effect , weight)

CHANCE_EVENTS: list[ChanceEvent] = [
    ("found_coins",   "Ты нашёл кошелёк 💰  +{n} монет",  "coins:+", 100),
    ("pet_cat",       "Погладил кота 😸     +{n} XP",      "xp:+",    30),
    ("robbery",       "Тебя облапошили шахтёры! −{n} монет",       "coins:-", 20),
    ("miner_snack",   "Нашёл борщ 🥣   +{n} энергии",  "energy:+",15),
    ("emergency_exit",   "Выход из шахты засыпало!   -{n} энергии",  "energy:-",8),
    ("emergency_exit_2", "Выход из шахты засыпало! Но ты успел выбраться — +{n} XP",  "xp:+",15),
    ("pet_cat",       "Погладил кота 😸, но он царапнул тебя.     -{n} энергии", "energy:-", 14),
    ("super_find",    "Ты нашёл спрятанный тайник! 🎁  +{n} монет",  "coins:+", 25),
    ("shady_trader",  "Странный торговец забрал у тебя {n} монет и выдал ничего взамен. Кринж!", "coins:-", 10),
    ("streak_luck",   "Тебе улыбнулась шахтёрская удача! +{n} XP", "xp:+", 20),
    ("chad_bread",    "Ты нашёл мемный хлеб и восстановил силы! +{n} энергии", "energy:+", 13),
    ("tnt_boom",      "Под ногами взорвалась динамитная шашка! −{n} энергии", "energy:-", 7),
    ("cat_coins",     "Котик нашёл для тебя {n} монет, кайф!", "coins:+", 12),
    ("old_map",       "Ты нашёл древнюю карту. +{n} XP и уважение", "xp:+", 12),
    ("drunk_miner",   "Тебя подпоил весёлый шахтёр — −{n} энергии", "energy:-", 8),
    ("mega_bag",      "Случайно нашёл тайник с монетами! +{n} монет", "coins:+", 10),
    ("rat_steal",     "Шахтёрская крыса украла {n} монет!", "coins:-", 10),
    ("pickaxe_bless", "Дух шахты благословил тебя: +{n} XP", "xp:+", 10),
    ("happy_accident","Ты споткнулся, но нашёл бонус. +{n} энергии", "energy:+", 10),
    ("minus_xp",      "Ты заблудился и потерял опыт — −{n} XP", "xp:-", 6),
    ("minus_energy",  "В шахте сквозняк. −{n} энергии", "energy:-", 7),
    ("ghost_miner",   "Тень шахтёра вдохновила тебя! +{n} XP", "xp:+", 7),
    ("ore_curse",     "Проклятие руды — потерял {n} XP", "xp:-", 5),
    ("random_debt",   "Ты случайно взял кредит у гоблинов — −{n} монет", "coins:-", 4),
    ("random_bless",  "Фортуна улыбнулась — +{n} монет", "coins:+", 7),
    ("epic_luck",     "Кристаллическая пыль дала тебе +{n} XP", "xp:+", 7),
]

POST_MINING_MEMES = [
    "I'm always comeback",
    "Кирка прощается с тобой.",
    "Вдали кто-то поёт реквием.",
    "Пахнет борщом... Наверное, это конец.",
    "Шахта закрывается.",
    "Это конец, брат!",
    "Всё равно ты — шахтёр мечты.",
    "Никогда не сдавайся, даже если шахте конец!",
    "До скорого.",
    "Копка — это стиль жизни."
]

BLACKLIST = [796070660]

def pick_chance_event() -> ChanceEvent|None:
    if random.random() > 0.30:          # лише 30 % шанс, що подія взагалі трапиться
        return None
    pool: list[ChanceEvent] = []
    for ev in CHANCE_EVENTS:
        pool += [ev] * ev[3]            # ваги
    return random.choice(pool)

async def apply_chance_event(ev: ChanceEvent, cid: int, uid: int) -> str:
    n = random.randint(1_000, 100_000)
    field, sign = ev[2].split(":")      # "coins", "+/-"
    delta =  n if sign == "+" else -n

    if field == "coins":
        await add_money(cid, uid, delta)
    elif field == "xp":
        await add_xp_with_notify(bot, cid, uid, delta)
    elif field == "energy":
        await add_energy(cid, uid, delta)   # нова утиліта

    return ev[1].format(n=abs(delta))

def get_weekend_coin_bonus() -> int:
    weekday = dt.datetime.utcnow().weekday()
    if weekday == 4: return 1_000
    if weekday == 5: return 100_000
    if weekday == 6: return 1_000_000
    return 0

async def get_display_name(bot: Bot, chat_id: int, user_id: int) -> str:
    """Ник из профиля; если нет — full_name из Telegram."""
    prog = await get_progress(chat_id, user_id)
    nick = prog.get("nickname")
    if nick:
        return nick
    member = await bot.get_chat_member(chat_id, user_id)
    return member.user.full_name

# ────────── Mining Task ──────────
async def mining_task(bot: Bot, cid: int, uid: int, tier: int,
                      ores: List[str], bonus: float, duration: int, bomb_mult: float = 1.0):
    prog = await get_progress(cid,uid)
    mine_count = prog.get("mine_count", 0)
    seal = prog.get("seal_active")
    extra_txt=""
    
    # ─── штраф за флуд ─────────────────────────────────────────────────────────
    await asyncio.sleep(duration)
    level = prog.get("level", 1)
    pick_key = prog.get("current_pickaxe")
    # Спецэффект для войд-кирки
    void_bonus = 0
    if pick_key == "void_pickaxe":
        void_bonus = random.randint(0, 200)
        pick_bonus = void_bonus / 100
    else:
        pick_bonus = PICKAXES.get(pick_key, {}).get("bonus", 0)

    if random.random() < 0.05:
        fail_messages = [
            # Прощальные
            "Шахта тихо шепчет: «прощай…»",
            "Ты копал впустую — словно прощаясь с камнями.",
            "Пустота смотрит на тебя в ответ.",
            "Эхо шахты повторяет: «bid adieu»",
            "Кирка замерла… время прощаться.",
            "В темноте слышен тихий вздох шахты.",
            
            # Реквием-ноты
            "Тьма поглотила добычу и свет.",
            "На стене: 'Здесь всё окончено.'",
            "Ветер приносит запах финала.",
            "Тьма обнимает тебя, как старого друга.",
            
            # Символизм
            "Ты нашёл лишь пыль времени.",
            "В глубине — только тишина и память.",
            "Твой путь закончился здесь.",
            
            # Мета-отсылки
            "Бот закрывает глаза…",
            "Шахта уходит в вечный сон.",
        ]
        fail_msg = random.choice(fail_messages)

        await db.execute("UPDATE progress_local SET mining_end = NULL "
                         "WHERE chat_id=:c AND user_id=:u",
                         {"c": cid, "u": uid})
        
        member = await bot.get_chat_member(cid, uid)
        mention = f"@{member.user.username}" if member.user.username \
                    else f'<a href="tg://user?id={uid}">{member.user.full_name}</a>'
        msg = await bot.send_message(cid, f"💀 {mention}, {fail_msg}", parse_mode="HTML")
        register_msg_for_autodelete(cid, msg.message_id)
        return

    # Обчислення Tier
    tier = max([i + 1 for i, t in enumerate(TIER_TABLE) if level >= t["level_min"]], default=1)
    tier_bonus = BONUS_BY_TIER.get(tier, 1.0)

    # Загальний бонус
    total_bonus = 100 + pick_bonus + (tier_bonus - 1)

    # Кількість руди
    COAL_KEY = "coal"
    ORE_KEYS = [k for k in ORE_ITEMS if k != COAL_KEY]
    core_ores = [x for x in ores if x != COAL_KEY]
    ore_id = random.choice(core_ores)
    ore = ORE_ITEMS[ore_id]
    amount = random.randint(*ore["drop_range"])
    # 💡 Зниження нагороди при голоді < 40
    if prog.get("hunger", 100) <= 0:
        amount = int(amount * 0.5)

    amount = int(amount * total_bonus)
    amount = int(amount * bomb_mult) 
    if bomb_mult > 1.0:                # 💣
        extra_txt += "\n💣 Бомба взорвалась → +50 % руды!"

    xp_gain = random.randint(6, 15)
    if seal == "seal_sacrifice":
        amount = int(amount * 1.2)
        xp_gain = max(0, xp_gain - 10)
    if seal == "seal_focus": 
        xp_gain  = int(xp_gain * 1.12)
        amount   = int(amount * 0.88)
    amount = max(1, int(amount))
    await add_item(cid,uid,ore_id,amount)
    await add_xp_with_notify(bot, cid, uid, xp_gain)
    streak=await update_streak(cid,uid)
    mine_count = prog.get("mine_count", 0)

    if pick_key in ("proto_eonite_pickaxe", "greater_eonite_pickaxe"):
        chance = 0.30 if pick_key == "proto_eonite_pickaxe" else 0.50
        if random.random() < chance:
            ore2 = random.choice(ores)
            ore_def = ORE_ITEMS[ore2]
            amount2 = random.randint(*ore_def["drop_range"])

            if prog.get("hunger", 100) <= 30:
                amount2 = int(amount2 * 0.5)
            amount2 = max(1, int(amount2 * total_bonus))

            await add_item(cid, uid, ore2, amount2)
            await add_xp(cid, uid, amount2)

            proto_txt = "\n🔮 " + (
                "Прототип" if pick_key == "proto_eonite_pickaxe" else "Старшая ЭК"
            ) + " активировался!\n" \
                f"Доп. добыча: <b>{amount2}×{ore_def['emoji']} {ore_def['name']}</b>"
            extra_txt += proto_txt
        
    if prog.get("badge_active") == "recruit":
        await add_money(cid, uid, 30) 

    helmet_row = await db.fetch_one(
        "SELECT * FROM helmets WHERE chat_id=:c AND user_id=:u AND active=TRUE",
        {"c": cid, "u": uid}
    )
    helmet_effect = None
    if helmet_row:
        code = helmet_row["effect_code"]
        kind, n = code.rsplit("_", 1)
        n = int(n)
        helmet_effect = (kind, n)
        if kind == "ore_bonus":
            amount = int(amount * (1 + n / 100))
        if kind == "xp_bonus":
            xp_gain = int(xp_gain * (1 + n / 100))
        if kind == "crit_mine":
            if random.randint(1, 100) <= n:
                amount *= 2
                extra_txt += f"\n💥 <b>Каска: КРИТ! Добыча ×2</b>"
        if kind == "coin_bonus":
            # Применяется только к бонусным монетам из событий (см. apply_chance_event)
            pass
        if kind == "extra_case":
            if random.randint(1, 100) <= n:
                await add_item(cid, uid, "cave_case", 1)
                extra_txt += f"\n📦 <b>Каска: кейс найден!</b>"
        if kind == "regen_pick":
            if random.randint(1, 100) <= n:
                cur_pick = prog.get("current_pickaxe")
                await change_dur(cid, uid, cur_pick, 1)
                extra_txt += f"\n♻️ <b>Каска: кирка восстановила прочность!</b>"
        if kind == "lucky_miner":
            if random.randint(1, 100) <= n:
                rare_ore = "emerald"  # или другая, по логике
                await add_item(cid, uid, rare_ore, 1)
                extra_txt += f"\n🍀 <b>Каска: найдена редкая руда!</b>"  

    if random.random() < 0.08:  # 8%
        await add_item(cid, uid, "sunset_ore", 1)
        extra_txt += "\n🌇 Руда Заката шепчет о прощании…"

    inventory_level = prog.get("inventory_level", 1)
    ore_limit = INVENTORY_CAPS.get(inventory_level, 60)
    inv = {r["item"]: r["qty"] for r in await get_inventory(cid, uid)}
    ore_count = sum(inv.get(k, 0) for k in ORE_KEYS)

    inv = {r["item"]: r["qty"] for r in await get_inventory(cid, uid)}
    if inv.get("adieu_badge",0) == 0:  # ещё не прошёл ритуал
        await add_item(cid, uid, "bad_luck_coupon", 1)
        extra_txt += "\n🎟️ Памятный талон получен."

    coal_drop = random.randint(*ORE_ITEMS[COAL_KEY]["drop_range"])
    await add_item(cid, uid, COAL_KEY, coal_drop)
    coal_line = f"{ORE_ITEMS[COAL_KEY]['emoji']} <b>{coal_drop}× {ORE_ITEMS[COAL_KEY]['name']}</b>"
    fullness = 0.0
    if ore_limit > 0:
        fullness = min(1.0, ore_count / ore_limit)

    if fullness >= 0.8:
        # линейный штраф 0…20%
        over_penalty = 1.0 - (fullness - 0.8) * (0.20 / 0.20)  # 0.8→1.0 → 1.0→0.80
        over_penalty = max(0.80, over_penalty)
        amount = int(amount * over_penalty)
        extra_txt += "\n📦 Инвентарь почти забит: добыча снижена."
    # ---- прочність конкретної кирки (JSON-мапа) ----
    broken = False

        # предположим, ты уже знаешь pick_key текущей кирки
    meta = PICKAXES.get(pick_key, {})

    # 0) «Упокой» — редкий дроп (после расчёта amount, ДО применения лимита)
    if random.randint(1, 100) == 1:  # 1% шанс
        await add_item(cid, uid, "requiem_scroll", 1)
        extra_txt += "\n🕯️ Находка: свиток «Упокой»"

    # 1) Catharsis — грубый множитель + монеты, не трогаем durability
    if meta.get("is_divine"):
        # +100000% = ×1001 (чтобы не переполнить crazy)
        amount = int(amount * 1001)
        await add_money(cid, uid, +10_000)
        extra_txt += "\n⚔️ Катарсис: ×1001 к добыче, +10 000 монет"

    # 2) Legacy — без руды, но +10k монет и не ломается
    if meta.get("is_legacy"):
        await add_money(cid, uid, +10_000)
        amount = 0  # руду не даём
        extra_txt += "\n♾️ Legacy: добыча в память — +10 000 монет"

    if cur := prog.get("current_pickaxe"):
        if seal == "seal_durability" and mine_count % 3 == 0:
            pass
        else:
            dur, dur_max = await change_dur(cid, uid, cur, 0)
            broken = dur == 0

        # ♦️ Реген «Старшої ЕК»
        if cur == "greater_eonite_pickaxe" and (mine_count + 1) % 20 == 0:
            # повертаємо +10, але не вище max
            add_val = 10 if dur_max else 0
            if broken:          # якщо була зламана — фіксуємо повністю
                add_val = dur_max
            await change_dur(cid, uid, cur, add_val)
            extra_txt += "\n♻️ Старшая ЭК восстановила прочность!"
            broken = False

    add_amount = min(amount, max(ore_limit - ore_count, 0))
    dropped = amount - add_amount
    if add_amount > 0:
        await add_item(cid, uid, ore_id, add_amount)
    ore_line = f"{ore['emoji']} <b>{add_amount}× {ore['name']}</b>"
    if dropped > 0:
        ore_line += f"\n⚠️ <b>Переполнение!</b> В инвентарь добавлено только {add_amount}, {dropped} ушло в никуда."

    # ---- випадкова подія ----
    ev = pick_chance_event()
    if ev:
        extra_txt = "\n" + await apply_chance_event(ev, cid, uid)

    member=await bot.get_chat_member(cid,uid)
    mention = f"@{member.user.username}" if member.user.username \
              else f'<a href="tg://user?id={uid}">{member.user.full_name}</a>'

    if ADIEU_ABSOLUTE:
        loot = chaos_loot(amount)
        extra_txt += apply_chaos_to_message(f"𓆩♡𓆪: {glitch_number(loot)} ????????????")
    
    await db.execute(
        "UPDATE progress_local SET mining_end=NULL "
        "WHERE chat_id=:c AND user_id=:u",
        {"c": cid, "u": uid}
    )

    if mine_count >= 20:
        await unlock_achievement(cid, uid, "bear_miner")
    if mine_count >= 300:
        await unlock_achievement(cid, uid, "grizzly_miner")

    coin_bonus = get_weekend_coin_bonus()
    if coin_bonus:
        await add_money(cid, uid, coin_bonus)
        extra_txt += f"\n💰 Лавина монет! +{coin_bonus} монет"

    inv = {r["item"]: r["qty"] for r in await get_inventory(cid, uid)}
    if inv.get("lapis_torch", 0) and random.random() < 0.10:
        await db.execute(
            "UPDATE progress_local SET energy=100,hunger=100 "
            "WHERE chat_id=:c AND user_id=:u", {"c": cid, "u": uid}
        )
        extra_txt += "\n🔵 Лазурный факел восполнил силы!"

    def bar(value: float, width: int = 10, full: str = "▓", empty: str = "░") -> str:
        """Фиксированный бар 0–1 → 10 символов."""
        filled = round(value * width)
        return full * filled + empty * (width - filled)

    tier_fill = min(1, (tier_bonus - 1) / 1.5)   #  x1→0%, x2.5→100%
    tier_bar  = bar(tier_fill)

    # ─── сборка сообщения ───────────────────────────────────────
    lines = [
        f"♾️ {mention}",
        f"├ {ore_line}",
        f"├ {coal_line}",
        f"├ XP +<b>{xp_gain}</b>",
        f"├ Tier ×<b>♾️</b> {tier_bar}",
        f"└ ♾️ {streak} дн.",
    ]

    if pick_key == "void_pickaxe":
        lines.append(f"├ Войд-бонус: <b>+{void_bonus}%</b>")
    else:
        lines.append(f"├ Бонус кирки: +{int(pick_bonus*100)}%")

    if broken:
        lines.append("⚠️ <b>Кирка сломалась!</b> /repair")

    if extra_txt:
        lines.append(extra_txt.strip())
    lines.append(f"\n<i>{random.choice(POST_MINING_MEMES)}</i>")

    txt = "\n".join(lines)

    msg = await bot.send_message(cid,txt,parse_mode="HTML")
    await maybe_send_choice_card(bot, cid, uid)
    register_msg_for_autodelete(cid, msg.message_id)
    # ↓ после отправки сообщения игроку
    await save_user_info(msg.from_user)
    logging.info("Mining result sent: chat=%s uid=%s", cid, uid)
    
# ────────── Smelt Task ──────────
async def smelt_timer(bot:Bot,cid:int,uid:int,rec:dict,cnt:int,duration:int):
    logging.warning(f"[SMELT] Timer started: {cnt}x{rec['out_key']} for {cid}:{uid}")
    await asyncio.sleep(duration)
    await add_item(cid,uid,rec["out_key"],cnt)
    await db.execute("UPDATE progress_local SET smelt_end=NULL WHERE chat_id=:c AND user_id=:u",
                     {"c":cid,"u":uid})
    await add_clash_points(cid, uid, 1)
    xp_gain = cnt * 1.5
    await add_xp_with_notify(bot, cid, uid, xp_gain)
    await add_pass_xp(cid, uid, xp_gain)
    member_name = await get_display_name(bot, cid, uid)
    msg = await bot.send_message(cid,f"🔥 {member_name}! Переплавка закончена: {cnt}×{rec['out_name']}\n🔥 +{xp_gain} XP", parse_mode="HTML")
    register_msg_for_autodelete(cid, msg.message_id)

# Temporary storage for captcha answers (for demo; use Redis/db for production)
CAPTCHA_ANSWERS = {}

ADIEU_MODE = True 
EMOJI_OPTIONS = ["🍎", "🍌", "🍇", "🍉", "🍒", "🍑", "🍍", "🥝"]

@router.message(CommandStart())
async def start_cmd(message: types.Message, bot: Bot):
    if message.from_user.id in BLACKLIST:
        logging.warning(f"Попытка регистрации заблокированного пользователя {message.from_user.id}")
        await message.answer("Вы заблокированы в этом боте. Если вы считаете, что это ошибка, обратитесь к администратору.")
        return
    
    txt = "🕊️ Проект на паузе. Для сувенира — /adieu. До встречи!"
    if ADIEU_MODE:
        txt += "\n\n<b>Adieu Update:</b> забери памятный набор и рамку профиля."
    await message.answer_photo(START_IMG_ID, caption=txt, parse_mode="HTML")

WEATHERS = [
    ("☀️", "солнечно"),
    ("⛅", "переменная облачность"),
    ("🌧️", "дождь"),
    ("⛈️", "гроза"),
    ("🌨️", "снег"),
    ("🌫️", "туман"),
    ("💨", "ветрено"),
    ("🌙", "ясная ночь"),
    ("☁️", "пасмурно"),
    ("🔥", "жарко"),
]

# ────────── /profile ──────────
XP_BAR_W      = 10                      # ширина бару XP
STAT_BAR_W    = 8                      # ширина барів енергії/голоду
BAR_STEPS     = ["🟥", "🟧", "🟨", "🟩"]  # градієнт: red→green
SEP           = "┅" * 3                # делікатний розділювач

def mono_bar(value: int, maximum: int, width: int = XP_BAR_W) -> str:
    """▰▱-бар (чорний) для XP."""
    filled = int(value / maximum * width)
    return "▰" * filled + "▱" * (width - filled)

def color_bar(value: int, maximum: int, width: int = STAT_BAR_W) -> str:
    """Кольоровий градієнт-бар."""
    ratio   = value / maximum
    filled  = int(ratio * width)
    step_id = min(int(ratio * len(BAR_STEPS)), len(BAR_STEPS) - 1)
    block   = BAR_STEPS[step_id]
    return block * filled + "⬜" * (width - filled)

# ──────────────────────────────────────────────────────────────
#  /profile   (оновлена версія)
# ──────────────────────────────────────────────────────────────
@router.message(Command("profile"))
async def profile_cmd(message: types.Message, bot: Bot):
    cid, uid = await cid_uid(message)
    user = await get_user(uid)
    if not user:
        return await message.answer("❗ Сначала пройди капчу в /start")
    await create_user(uid, message.from_user.username or message.from_user.full_name)

    # ── динамічні величини ───────────────────────────────
    energy = await update_energy(cid, uid)
    hunger = await update_hunger(cid, uid)
    prog   = await get_progress(cid, uid)

    lvl, xp  = prog.get("level", 1), prog.get("xp", 0)
    next_xp  = lvl * 85
    streak   = prog.get("streak", 0)
    mines    = prog.get("mine_count", 0)
    balance  = await get_money(cid, uid)

    # ── поточна кирка ─────────────────────────────────────
    cur  = prog.get("current_pickaxe") or "wooden_pickaxe"
    dm   = _json2dict(prog.get("pick_dur_map"))
    dmm  = _json2dict(prog.get("pick_dur_max_map"))
    dur, dur_max = dm.get(cur, PICKAXES[cur]["dur"]), dmm.get(cur, PICKAXES[cur]["dur"])
    pick_bonus   = PICKAXES[cur]["bonus"]
    pick_name    = PICKAXES[cur]["name"]

    # ── бейдж / печать ───────────────────────────────────
    b_id = prog.get("badge_active")
    badge_str = "–"
    if b_id and (b := BADGES.get(b_id)):
        badge_str = f"{b['name']}"

    s_id = prog.get("seal_active")
    seal_str = "–"
    if s_id and (s := SEALS.get(s_id)):
        seal_str = f"{s['name']}"
    nickname_str = prog.get("nickname") or message.from_user.full_name

    # ── Tier + бонус ─────────────────────────────────────
    tier = max(i + 1 for i, t in enumerate(TIER_TABLE) if lvl >= t["level_min"])
    tier_bonus = BONUS_BY_TIER[tier]

    # ── Cave-/Clash-cases ────────────────────────────────
    cave_cases  = prog.get("cave_cases", 0)
    clash_cases = prog.get("clash_cases", 0)

    # ── допоміжні бари/іконки ───────────────────────────
    xp_bar      = mono_bar(xp, next_xp)
    energy_bar  = color_bar(energy, 100)
    hunger_bar  = color_bar(hunger, 100)
    has_pass    = prog.get("cave_pass", False)
    expires     = prog.get("pass_expires")
    if has_pass and expires:
        pass_str = expires.strftime("%d.%m.%Y")
    else:
        pass_str = "Не активирован"

    weather_emoji, weather_name = random.choice(WEATHERS)
    mine_end = prog.get("mining_end")

    if isinstance(mine_end, dt.datetime) and mine_end > dt.datetime.utcnow():
        # осталось времени -› минуты вверх
        mins_left = max(1, int((mine_end - dt.datetime.utcnow()).total_seconds() // 60))
        mine_status = f"🕳️ <i>Копает (ещё {mins_left} мин.)</i>"
    else:
        mine_status = "😴 <i>Отдыхает</i>"

    # ── складання тексту ─────────────────────────────────
    def shorten_number(n: int) -> str:
        return f"{n/1000:.1f}k" if n >= 1000 else str(n)

    balance_s = shorten_number(balance)
    mines_s   = shorten_number(mines)

    pic = await render_profile_card(message.bot, uid, nickname_str, lvl, xp, next_xp,
                                    energy, hunger, balance, streak, f"{dur}/{dur_max}", mines)
    
    if message.from_user.id in BLACKLIST:
        nickname_str = "Заблокированный пользователь"
        pic = None # Не показываем картинку профиля для заблокированных пользователей
        lvl = -1
        xp_bar = ""
        next_xp = -1
        energy_bar = ""
        hunger_bar = ""
        energy = -1
        hunger = -1
        weather_emoji = "❌"
        weather_name = "Заблокирован"
        mine_status = "❌ <i>Доступ запрещён</i>"
        pass_str = "Заблокирован"
        pick_name = "Заблокирован"
        dur = -1
        dur_max = -1
        badge_str = "Заблокирован"
        seal_str = "Заблокирован"
        tier = -1
        tier_bonus = 0.0
        cave_cases = -1
        clash_cases = -1

    txt = (
        f"<b>{nickname_str} - Adieu</b>\n"
        f"<u>Уровень {lvl}</u>\n"
        f"{xp_bar} <code>{xp}/{next_xp}</code>\n"
        f"<i>🌧️ Дождь</i>\n"
        f"🤡 <b>Cave Pass:</b> {pass_str}\n"
        f"🤡 ∞/∞: <code>🟩🟩🟩🟩🟩</code>\n"
        f"🤡 ∞/∞: <code>🍗🍗🍗🍗🍗</code>\n"
        f"{mine_status}\n"
        f"{SEP}\n"
        f"🤡 {pick_name} ({dur}/{dur_max})\n"
        f"🤡 {badge_str} | 🤡 {seal_str}\n"
        f"🤡 Tier ♾️ ×NaNeInf | 🤡 53747265616B {streak} d\n"
        f"{SEP}\n"
        f"🤡 {balance_s} | 🏔 {mines_s}\n"
        f"🤡 CC {cave_cases} | CL {clash_cases}"
    )

    # ── клавіатура ──────────────────────────────────────
    kb = InlineKeyboardBuilder()
    kb.button(text="🤡 Шахта",     callback_data=f"profile:mine:{uid}")
    kb.button(text="🤡 Инвентарь",  callback_data=f"profile:inventory:{uid}")
    kb.button(text="🤡 Магазин",   callback_data=f"profile:shop:{uid}")
    kb.button(text="🤡 Ачивки", callback_data=f"profile:achievements:{uid}")
    kb.button(text="🤡 Бейджи",    callback_data=f"profile:badges:{uid}")
    kb.adjust(1)

    await send_log(bot, message.from_user, message.chat, "/profile")
    msg = await message.answer_photo(
        photo=PROFILE_IMG_ID,
        caption=txt,
        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )
    register_msg_for_autodelete(cid, msg.message_id)
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
    elif action == "achievements":
        await achievements_menu(callback.message, orig_uid)
    elif action == "badges":
        await badges_menu(callback.message, orig_uid)

RENAME_PRICE = 100
@router.message(Command("rename"))
async def rename_cmd(message: types.Message):
    cid, uid = await cid_uid(message)
    args = message.text.split(maxsplit=1)

    if uid in BLACKLIST:
        logging.warning(f"Попытка смены ника заблокированного пользователя {uid}")
        return await message.answer("Вы заблокированы в этом боте. Если вы считаете, что это ошибка, обратитесь к администратору.")

    if len(args) < 2:
        return await message.answer("❗ Используй команду так: <code>/rename НовыйНик</code>", parse_mode="HTML")

    new_nick = args[1].strip()

    if len(new_nick) > 25:
        return await message.answer("❗ Никнейм слишком длинный (максимум 25 символов).")

    balance = await get_money(cid, uid)
    if balance < RENAME_PRICE:
        return await message.answer(f"❌ Нужно {RENAME_PRICE} монет для смены ника. У тебя всего {balance}.")

    # Обновление ника
    await db.execute(
        "UPDATE progress_local SET nickname =:nickname WHERE chat_id =:c AND user_id =:u",
        {"c": cid, "u": uid, "nickname": new_nick}
    )

    await add_money(cid, uid, -RENAME_PRICE)

    msg = await message.answer(f"✅ Ник обновлён на <b>{new_nick}</b>!\n💸 Списано {RENAME_PRICE} монет.", parse_mode="HTML")
    register_msg_for_autodelete(message.chat.id, msg.message_id)

BASE_EN_COST = 0
BASE_HU_COST = 0

# ────────── /mine ──────────
@router.message(Command("mine"))
async def mine_cmd(message: types.Message, user_id: int | None = None):
    cid, uid = await cid_uid(message)
    if user_id:
        uid = user_id
    user = await get_user(uid)
    if not user:
        return await message.reply("Сперва /start")
    
    if uid in BLACKLIST:
        logging.warning(f"Попытка копки заблокированным пользователем {uid}")
        return await message.reply("Вы заблокированы в этом боте. Если вы считаете, что это ошибка, обратитесь к администратору.")
    prog = await get_progress(cid, uid)

    energy = await update_energy(cid, uid)
    hunger = await update_hunger(cid, uid)
    energy_cost = BASE_EN_COST
    hunger_cost = BASE_HU_COST
    mine_count = prog.get("mine_count", 0)
    """
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
    """
    if prog.get("badge_active") == "hungrycave":
        await db.execute("""
            UPDATE progress_local
               SET hunger = LEAST(100, hunger + 5)
             WHERE chat_id=:c AND user_id=:u
        """, {"c": cid, "u": uid})
        hunger += 5 

    if prog.get("badge_active") == "eonite_beacon" and (mine_count + 1) % 3 == 0:
        hunger_cost = 0
        energy_cost = 0

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
        txt = f"⛏️ Ты ещё в шахте, осталось {left} мин."
        if hunger == 0:
            txt += "\n🍽️ Ты голоден и не сможешь копать снова без еды!"
        elif hunger <= 30:
            txt += "\n⚠️ Ты проголодался. Следующая копка принесёт вдвое меньше руды."
        return await message.reply(txt)
        
    tier = get_tier(prog["level"])
    bonus_tier = BONUS_BY_TIER[tier]
    ores = TIER_TABLE[tier - 1]["ores"]
    sec = get_mine_duration(tier)
    seal_boost = False

    seal = prog.get("seal_active")
    if seal == "seal_energy":          # (была скорость → оставим)
        sec = max(MINE_SEC_MIN, sec - 300)
        seal_boost = True

    if seal == "seal_gluttony":        # новая печать
        hunger_cost *= 2
    if prog.get("badge_active") == "hungrycave":
        hunger_cost = 5

    inv = {r["item"]: r["qty"] for r in await get_inventory(cid, uid)}
    bomb_mult = 1.0
    if inv.get("bomb", 0) > 0:
        await add_item(cid, uid, "bomb", -1)   # списуємо одразу
        bomb_mult = 100      

    helmet_row = await db.fetch_one(
        "SELECT * FROM helmets WHERE chat_id=:c AND user_id=:u AND active=TRUE",
        {"c": cid, "u": uid}
    )
    helmet_effect = None
    if helmet_row:
        code = helmet_row["effect_code"]
        kind, n = code.rsplit("_", 1)
        n = int(n)
        helmet_effect = (kind, n)
        # Применяем эффекты уменьшения затрат
        if kind == "hunger_slow":
            hunger_cost = int(hunger_cost * (1 - n / 100))
        if kind == "fatigue_resist":
            energy_cost = int(energy_cost * (1 - n / 100))

    level = prog.get("level", 1)
    energy_cost = 0
    hunger_cost = 0

    # списуємо енергію/голод + ставимо таймер
    await db.execute("""
        UPDATE progress_local
           SET energy      = GREATEST(0, energy - :en),
               hunger      = GREATEST(0, hunger - :hu),
               mining_end  = :end
         WHERE chat_id=:c AND user_id=:u
    """, {
        "en": energy_cost,
        "hu": hunger_cost,
        "end": dt.datetime.utcnow() + dt.timedelta(seconds=sec),
        "c": cid, "u": uid
    })
    # 🔢 +1 до лічильника копань
    await db.execute(
        "UPDATE progress_local SET mine_count = COALESCE(mine_count, 0) + 1 WHERE chat_id=:c AND user_id=:u",
        {"c": cid, "u": uid}
    )
    await add_clash_points(cid, uid, 1)
    minutes  = max(1, round(sec / 60))
    orig_min = round(get_mine_duration(tier) / 60)
    lines = [
        "⛏ <b>Шахта стартовала!</b>",
        f"╭─ Время:  <b>? мин</b>",
        f"├─ 🔋 −♾️ энергии",
        f"├─ 🍗 −NaN голода",
    ]

    if bomb_mult > 1:
        lines.append("╰─ 💣 Бомба ×1.5")

    caption = "\n".join(lines) 
    kb = InlineKeyboardBuilder()
    kb.button(text="⏳ Осталось", callback_data=f"mine_left:{uid}")
    kb.button(text="🚫 Отмена",   callback_data=f"mine_stop:{uid}")
    kb.button(text=f"⚡ Мгновенно (5⭐)", callback_data=f"mine_instant:{uid}")
    kb.adjust(2)

    msg = await message.reply(
        caption,
        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )
    register_msg_for_autodelete(cid, msg.message_id)
    asyncio.create_task(mining_task(message.bot, cid, uid, tier, ores, bonus_tier, sec, bomb_mult))

async def _minutes_left(cid: int, uid: int) -> int:
    """Сколько минут осталось до конца копки (округление вверх)."""
    row = await db.fetch_one("""
        SELECT mining_end FROM progress_local
         WHERE chat_id=:c AND user_id=:u
    """, {"c": cid, "u": uid})
    if not row or row["mining_end"] is None:
        return 0
    delta = row["mining_end"] - dt.datetime.utcnow()
    return max(0, int((delta.total_seconds() + 59) // 60))

@router.callback_query(F.data.startswith("mine_left:"))
async def mine_left_cb(cb: types.CallbackQuery):
    cid, uid = cb.message.chat.id, cb.from_user.id
    _, orig_uid = cb.data.split(":")
    if uid != int(orig_uid):
        return await cb.answer("Не твоё копание 😼", show_alert=True)

    mins = await _minutes_left(cid, uid)
    if mins == 0:
        txt = "⛏ Уже на поверхности!"
    else:
        txt = f"⏳ Осталось ≈ {mins} мин."
    await cb.answer(txt, show_alert=True)

@router.callback_query(F.data.startswith("mine_stop:"))
async def mine_stop_cb(cb: types.CallbackQuery):
    cid, uid = cb.message.chat.id, cb.from_user.id
    _, orig_uid = cb.data.split(":")
    if uid != int(orig_uid):
        return await cb.answer("Не твоё копание 😼", show_alert=True)

    # сбрасываем таймер
    await db.execute("""
        UPDATE progress_local
           SET mining_end = NULL
         WHERE chat_id=:c AND user_id=:u
    """, {"c": cid, "u": uid})

    await cb.message.edit_text("🚫 Копка прервана.")
    await cb.answer("Ок, остановили ⛏")

@router.callback_query(F.data.startswith("mine_instant:"))
async def mine_instant_cb(cb: types.CallbackQuery):
    cid, uid = cb.message.chat.id, cb.from_user.id
    _, orig_uid = cb.data.split(":")
    if uid != int(orig_uid):
        return await cb.answer("Не твоё копание 😼", show_alert=True)

    # 1) перевіряємо, чи ще є активна копка
    mins_left = await _minutes_left(cid, uid)
    if mins_left == 0:
        return await cb.answer("На поверхности ✋", show_alert=True)

    # 2) надсилаємо інвойс на 5 ⭐
    title = "⚡ Мгновенная копка"
    desc  = f"Копка завершается за 1 минуту вместо {mins_left} минут."
    payload = f"instant:{cid}:{uid}"
    price  = types.LabeledPrice(label="Instant Mine", amount=5)  # 5 зірок = 500 XTR

    await cb.message.answer_invoice(
        title=title,
        description=desc,
        payload=payload,
        provider_token="",
        currency="XTR",          # «зіркова» валюта
        prices=[price],
        start_parameter="instant_mine",
        max_tip_amount=0, tip_prices=[]
    )
    # Telegram сам відкриє вікно оплати
    await cb.answer()

@router.pre_checkout_query()
async def process_pre_checkout(pre_q: types.PreCheckoutQuery):
    # якщо payload підходить – просто підтверджуємо
    if pre_q.invoice_payload.startswith("instant:"):
        await pre_q.answer(ok=True)
    else:
        await pre_q.answer(ok=False, error_message="Неизвестный платеж")

# ─── Успішна оплата ──────────────────────────────────────────────
@router.message(F.successful_payment)
async def successful_payment(msg: types.Message):
    payload = msg.successful_payment.invoice_payload
    if not payload.startswith("instant:"):
        return  # інші платежі, якщо є

    _, cid_str, uid_str = payload.split(":")
    cid, uid = int(cid_str), int(uid_str)

    # ставимо mining_end = now + 60 sec
    await db.execute(
        """
        UPDATE progress_local
           SET mining_end = :end
         WHERE chat_id=:c AND user_id=:u
        """,
        {
            "end": dt.datetime.utcnow() + dt.timedelta(seconds=60),
            "c": cid,
            "u": uid
        }
    )

    await msg.answer("⚡ Готово! Копка завершится за 1 минуту.")

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
    inventory_level = progress.get("inventory_level", 1)
    ore_limit = INVENTORY_CAPS.get(inventory_level, 60)
    inventory_name = INVENTORY_NAMES.get(inventory_level, "Сумка")

    categories = {
        "ores": [],
        "ingots": [],
        "pickaxes": [],
        "food": [],
        "coal": [],       # категория для угля/топлива
        "misc": []
    }

    def get_category(item_key):
        if item_key.endswith("_ingot") or item_key == "roundstone":
            return "ingots"
        elif item_key.endswith("_pickaxe"):
            return "pickaxes"
        elif item_key in ("meat", "bread", "coffee", "borsch", "energy_drink"):
            return "food"
        elif item_key == "coal":
            return "coal"
        elif item_key in ORE_ITEMS:
            return "ores"
        return "misc"

    ore_count = 0
    for row in inv:
        if row["item"] == current_pick:
            continue
        meta = ITEM_DEFS.get(row["item"], {"name": row["item"], "emoji": "❔"})
        cat = get_category(row["item"])
        if cat == "ores":
            ore_count += row["qty"]
        categories[cat].append((meta, row["qty"]))

    ore_bar = f"{ore_count}/{ore_limit}"
    if ore_count >= ore_limit:
        ore_bar += " ⚠️ ЛИМИТ!"

    lines = [
        f"🧾 Баланс: {balance} монет",
        f"📦 <b>Инвентарь:</b> {inventory_name} ({ore_bar})",
        ""
    ]

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
    if categories["coal"]:
        lines.append("\n<b>🪨 Угольные:</b>")
        for meta, qty in categories["coal"]:
            lines.append(f"{meta['emoji']} {meta['name']}: {qty}")
    if categories["misc"]:
        lines.append("\n<b>🎒 Прочее:</b>")
        for meta, qty in categories["misc"]:
            lines.append(f"{meta['emoji']} {meta['name']}: {qty}")

    if ore_count >= ore_limit:
        lines.append("\n⚠️ Внимание! Достигнут лимит руды для текущего уровня инвентаря.\nПрокачай инвентарь через /upgrade_inventory!")

    msg = await message.answer_photo(
        INV_IMG_ID,
        caption="\n".join(lines),
        parse_mode="HTML",
        reply_to_message_id=message.message_id,
    )
    register_msg_for_autodelete(cid, msg.message_id)

INVENTORY_UPGRADE_COST = [0, 1500, 3800, 7000, 12000, 30000]  # для уровней 1→5

@router.message(Command("upgrade_inventory"))
async def upgrade_inventory_cmd(message: types.Message):
    cid, uid = await cid_uid(message)
    prog = await get_progress(cid, uid)
    lvl = prog.get("inventory_level", 1)
    if lvl >= 6:
        return await message.reply("🔝 Воркшоп — максимальный уровень инвентаря!")
    cost = INVENTORY_UPGRADE_COST[lvl]
    balance = await get_money(cid, uid)
    if balance < cost:
        return await message.reply(f"❌ Нужно {cost} монет для улучшения. У тебя только {balance} монет.")
    await add_money(cid, uid, -cost)
    await db.execute(
        "UPDATE progress_local SET inventory_level = inventory_level + 1 WHERE chat_id=:c AND user_id=:u",
        {"c": cid, "u": uid}
    )
    new_name = INVENTORY_NAMES.get(lvl+1, "???")
    await message.reply(f"🎉 Поздравляем! Теперь твой инвентарь: <b>{new_name}</b>.\nЛимит руды: {INVENTORY_CAPS[lvl+1]} шт.", parse_mode="HTML")


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
    "hdd": "old_hdd",
    "руда эонита": "eonite_ore",
    "слиток эонита": "eonite_ingot",
    "войд-хрусталь":"void_crystal",
    "звездный квартц":"star_quartz",
    "руда эонита": "eonite_ore",
    "руда заката": "sunset_ore"
})

@router.message(Command("sell"))
async def sell_start(message: types.Message, user_id: int | None = None):
    cid, uid = await cid_uid(message)
    if user_id:
        uid = user_id # github bljad alo
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
        builder.button(text=f"{emoji} {name} ({qty})", callback_data=f"sell_choose:{k}:{uid}")

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
    
    _, item_key, orig_uid = call.data.split(":")
    if call.from_user.id != int(orig_uid):
        return await call.answer("Не для тебя 🤚", show_alert=True)

    builder = InlineKeyboardBuilder()
    buttons = {1, 5, 10, qty}  # базові
    half = qty // 2
    if 2 <= half < qty:
        buttons.add(half)

    for amount in sorted(buttons):
        label = f"½ ({amount})" if amount == half else f"Продать {amount}×"
        builder.button(
            text=label,
            callback_data=f"sell_confirm:{item_key}:{amount}:{orig_uid}"
        )

    builder.button(text="❌ Отмена", callback_data=f"sell_cancel:{orig_uid}")

    meta = ITEM_DEFS[item_key]
    msg = await call.message.edit_text(
        f"{meta.get('emoji','')} {meta['name']}\nСколько хочешь продать?",
        reply_markup=builder.adjust(2).as_markup()
    )

@router.callback_query(F.data.startswith("sell_confirm:"))
async def confirm_sell(call: types.CallbackQuery):
    cid, uid = call.message.chat.id, call.from_user.id
    _, item_key, qty_str, orig_uid = call.data.split(":")
    if call.from_user.id != int(orig_uid):
        return await call.answer("Не для тебя 🤚", show_alert=True)

    qty = int(qty_str)
    inv = {r["item"]: r["qty"] for r in await get_inventory(cid, uid)}
    if inv.get(item_key, 0) < qty:
        return await call.answer("Недостаточно предметов!")

    price = ITEM_DEFS[item_key]["price"]
    if item_key.endswith("_ingot") or item_key == "roundstone":
    # находим исходную руду и её кол-во по рецепту
        if item_key == "roundstone":
            ore_key, in_qty = "stone", 6           # твой рецепт
        else:
            ore_key = item_key.replace("_ingot", "")
            if ore_key == "eonite":
                ore_key = "eonite_ore"             # специальный случай
            in_qty = SMELT_RECIPES[ore_key]["in_qty"]

        ore_price = ITEM_DEFS[ore_key]["price"] * in_qty
        price = int(ore_price * 1.25)              # +25 % профита

    prog = await get_progress(cid, uid)
    bonus = get_badge_effect(prog, "sell_bonus", 0.0)
    earned = int(price * qty * (1 + bonus))
    await add_item(cid, uid, item_key, -qty)
    await add_money(cid, uid, earned)
    if earned >= 5000:
        await unlock_achievement(cid, uid, "big_sale")

    meta = ITEM_DEFS[item_key]
    await add_clash_points(cid, uid, 0)
    # после расчёта earned и перед edit_text
    repeat_kb = InlineKeyboardBuilder()
    repeat_kb.button(
        text="🔁 Продать ещё",
        callback_data=f"sell_menu:{orig_uid}"   # ← новый callback-ключ
    )
    repeat_kb.button(text="❌ Закрыть", callback_data="sell_close")
    repeat_kb.adjust(2)
    
    await call.message.edit_text(
        f"✅ Продано {qty}×{meta['emoji']} {meta['name']} за {earned} монет 💰",
        reply_markup=repeat_kb.as_markup()
    )
    register_msg_for_autodelete(cid, call.message.message_id)

@router.callback_query(F.data.startswith("sell_menu:"))
async def sell_menu_cb(call: types.CallbackQuery):
    _, orig_uid = call.data.split(":")
    if call.from_user.id != int(orig_uid):
        return await call.answer("Не для тебя 🤚", show_alert=True)

    await call.answer()                     # закрываем «часики»
    # вызываем уже готовый экран выбора товара
    await sell_start(call.message, user_id=call.from_user.id)          # передаём то же message
    
@router.callback_query(F.data == "sell_close")
async def sell_close_cb(call: types.CallbackQuery):
    await call.answer()
    try:
        await call.message.delete()
    except Exception:
        pass

@router.callback_query(F.data == "sell_cancel:")
async def cancel_sell(call: types.CallbackQuery):
    orig_uid = call.data.split(":")[1]
    if call.from_user.id != int(orig_uid):
        return await call.answer("Не для тебя 🤚", show_alert=True)
    await call.message.edit_text("Продажа отменена ❌")

# ────────── /smelt (async) ──────────
# ────────── /smelt ──────────
@router.message(Command("smelt"))
async def smelt_cmd(message: types.Message, user_id: int | None = None):
    cid, uid = await cid_uid(message)
    if user_id is not None:
        uid = user_id
    inv = {r["item"]: r["qty"] for r in await get_inventory(cid, uid)}

    total_ore = sum(q for k,q in inv.items() if k in ORE_ITEMS)
    if total_ore >= 1000:
        await unlock_achievement(cid, uid, "ore_horder")

    smeltables = [
        ore for ore in SMELT_RECIPES
        if inv.get(ore, 0) >= SMELT_RECIPES[ore]["in_qty"]
    ]
    if not smeltables:
        return await message.reply("❌ Недостаточно руды для плавки.")

    kb = InlineKeyboardBuilder()
    for ore in smeltables:
        qty      = inv[ore]
        need_one = SMELT_RECIPES[ore]["in_qty"]
        max_out  = qty // need_one
        meta     = ITEM_DEFS.get(ore, {})
        kb.button(
            text=f"{meta.get('emoji','⛏️')} {meta.get('name', ore)} ({qty} шт)",
            callback_data=f"smeltq:{ore}:1:{max_out}:{uid}"   # стартуємо з 1 інгота
        )
    kb.adjust(1)
    m = await message.answer(
        "Выбери руду для плавки:",
        reply_markup=kb.as_markup())
    register_msg_for_autodelete(cid, m.message_id)

# ────────── крутилка кількості ──────────
@router.callback_query(F.data.startswith("smeltq:"))
async def smelt_quantity(cb: CallbackQuery):
    await cb.answer()
    cid, uid = await cid_uid(cb)
    _, ore, cur_str, max_str, orig_uid = cb.data.split(":")
    cur, max_cnt = int(cur_str), int(max_str)
    if cb.from_user.id != int(orig_uid):
        return await cb.answer("Эта кнопка не для тебя 😼", show_alert=True)

    def make_btn(txt, delta=0):
        new_val = max(1, min(max_cnt, cur + delta))
        return types.InlineKeyboardButton(
            text=txt,
            callback_data=f"smeltq:{ore}:{new_val}:{max_cnt}:{orig_uid}"
        )

    kb = InlineKeyboardBuilder()
    kb.row(make_btn("−10", -10), make_btn("−1", -1),
           types.InlineKeyboardButton(text=f"{cur}", callback_data="noop"),
           make_btn("+1", 1), make_btn("+10", 10), make_btn("+100", 100))
    kb.row(types.InlineKeyboardButton(
        text="➡️ Уголь",
        callback_data=f"smeltcoal:{ore}:{cur}:{orig_uid}"
    ))
    kb.row(types.InlineKeyboardButton(text="❌ Отмена", callback_data=f"smelt_cancel:{orig_uid}"))

    meta = ITEM_DEFS.get(ore, {})
    await cb.message.edit_text(
        f"Сколько {meta.get('name', ore)} переплавить?",
        reply_markup=kb.as_markup())

# ────────── вибір вугілля ──────────
@router.callback_query(F.data.startswith("smeltcoal:"))
async def smelt_choose_coal(cb: CallbackQuery):
    await cb.answer()
    cid, uid = await cid_uid(cb)
    _, ore, cnt_str, orig_uid = cb.data.split(":")
    cnt = int(cnt_str)
    if cb.from_user.id != int(orig_uid):
        return await cb.answer("Эта кнопка не для тебя 😼", show_alert=True)

    kb = InlineKeyboardBuilder()
    kb.adjust(1)
    for coal in (5, 15, 30):
        kb.button(
            text=f"🪨 ×{coal}",
            callback_data=f"smeltgo2:{ore}:{coal}:{cnt}:{orig_uid}"
        )
    kb.row(types.InlineKeyboardButton(text="❌ Отмена", callback_data=f"smelt_cancel:{orig_uid}"))

    await cb.message.edit_text(
        f"Сколько угля потратить на {cnt} шт {ITEM_DEFS[ore]['name']}?",
        reply_markup=kb.as_markup())

# ────────── запуск таймера ──────────
@router.callback_query(F.data.startswith("smeltgo2:"))
async def smelt_execute_exact(cb: CallbackQuery):
    await cb.answer()
    cid, uid = await cid_uid(cb)
    _, ore, coal_str, cnt_str, orig_uid = cb.data.split(":")
    coal, cnt = int(coal_str), int(cnt_str)
    if cb.from_user.id != int(orig_uid):
        return await cb.answer("Эта кнопка не для тебя 😼", show_alert=True)

    recipe = SMELT_RECIPES.get(ore)
    if not recipe:
        return await cb.message.edit_text("❌ Неизвестный рецепт.")

    inv = {r["item"]: r["qty"] for r in await get_inventory(cid, uid)}
    ore_have  = inv.get(ore, 0)
    coal_have = inv.get("coal", 0)

    need_per_ingot = recipe["in_qty"]
    if ore_have < cnt * need_per_ingot:
        return await cb.message.edit_text("❌ Недостаточно руды.")
    if coal_have < coal:
        return await cb.message.edit_text("❌ Недостаточно угля.")

    # списываем вход
    await add_item(cid, uid, ore,  -cnt * need_per_ingot)
    await add_item(cid, uid, "coal", -coal)
    prog        = await get_progress(cid, uid)
    speed_mult  = get_badge_effect(prog, "smelt_mult", 1.0)

    duration_map = {5: 1500, 15: 900, 30: 600}
    base_sec = duration_map.get(coal, 1500)
    duration = int(base_sec * speed_mult)
    finish_at = dt.datetime.utcnow() + dt.timedelta(seconds=duration)
    await db.execute(
        "UPDATE progress_local SET smelt_end = :e WHERE chat_id=:c AND user_id=:u",
        {"e": finish_at, "c": cid, "u": uid})

    asyncio.create_task(smelt_timer(cb.bot, cid, uid, recipe, cnt, duration))

    meta = ITEM_DEFS[ore]
    txt = (
        f"🔥 В печь отправлено {cnt*need_per_ingot}×{meta['emoji']} {meta['name']}\n"
        f"🪨 Уголь: {coal} шт\n"
        f"⏳ Готово через <b>{round(duration/60)}</b> мин."
    )
    await cb.message.edit_text(txt, parse_mode="HTML")

@router.callback_query(F.data == "smelt_cancel:")
async def cancel_smelt(call: types.CallbackQuery):
    orig_uid = call.data.split(":")[1]
    if call.from_user.id != int(orig_uid):
        return await call.answer("Не для тебя 🤚", show_alert=True)
    await call.message.edit_text("Плавка отменена ❌")

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
    xp_gain = 10
    # Все є — списуємо
    for k, need in recipe["in"].items():
        await add_item(cid, uid, k, -need)
    await add_item(cid, uid, recipe["out_key"], 1)
    if recipe["out_key"] == "roundstone_pickaxe":
        await unlock_achievement(cid, uid, "cobble_player")
    await add_clash_points(cid, uid, 2)
    await add_xp_with_notify(bot, cid, uid, xp_gain)
    await add_pass_xp(cid, uid, xp_gain)
    msg = await message.reply(f"🎉 Создано: {recipe['out_name']}!\n🎉 +{xp_gain} XP")
    register_msg_for_autodelete(message.chat.id, msg.message_id)

def _refund_percent(dur: int, dur_max: int) -> float:
    if dur <= 10:
        return 0.0
    ratio = dur / dur_max * 100
    if ratio <= 20:
        return 0.30
    if ratio <= 40:
        return 0.40
    if ratio <= 60:
        return 0.55
    if ratio <= 80:
        return 0.65
    return 0.70    # 80 < x ≤ 100

# ────────── /disassemble (меню) ──────────
@router.message(Command("disassemble"))
async def disasm_menu(message: types.Message):
    cid, uid = await cid_uid(message)

    prog = await get_progress(cid, uid)
    cur_pick  = prog.get("current_pickaxe")            # активная
    cur_dur   = _jsonb_to_dict(prog.get("pick_dur_map")).get(cur_pick, 0)

    # всё, что реально лежит на складе
    inv = {row["item"]: row["qty"] for row in await get_inventory(cid, uid)}

    picks: list[str] = []

    # 1) кирки, которые лежат в инвентаре
    for item_id, qty in inv.items():
        if item_id.endswith("_pickaxe") and qty > 0 and item_id in RECIPES_BY_ID:
            picks.append(item_id)

    # 2) активная кирка, если она крафтовая и ещё не совсем убита
    if (cur_pick
            and cur_pick in RECIPES_BY_ID
            and cur_dur > 10               # >10 прочности — можно разбирать
            and cur_pick not in picks):
        picks.append(cur_pick)

    if not picks:
        return await message.reply("🪓 Нет кирок, пригодных для разборки 🤷")

    # --- кнопочная менюшка ---
    kb = InlineKeyboardBuilder()
    for pk in picks:
        meta = ITEM_DEFS.get(pk, {"name": pk, "emoji": "⛏️"})
        qty_label = "(активна)" if pk == cur_pick else f"({inv.get(pk, 0)})"
        kb.button(
            text=f"{meta['emoji']} {meta['name']} {qty_label}",
            callback_data=f"disasm_pick:{pk}"
        )
    kb.adjust(2)

    await message.answer(
        "Что разбираем? ↓",
        reply_markup=kb.as_markup()
    )

# ────────── выбор конкретной кирки ──────────
@router.callback_query(F.data.startswith("disasm_pick:"))
async def disasm_confirm(cb: types.CallbackQuery):
    cid, uid = cb.message.chat.id, cb.from_user.id
    pick_key = cb.data.split(":", 1)[1]

    inv = {r["item"]: r["qty"] for r in await get_inventory(cid, uid)}
    if inv.get(pick_key, 0) < 1:
        return await cb.answer("Кирки уже нет 😕", show_alert=True)

    if inv.get("disassemble_tool", 0) < 1:
        return await cb.answer("Нужен Инструмент разборки 🛠️", show_alert=True)

    # прочность
    prog        = await get_progress(cid, uid)
    dur_map     = _jsonb_to_dict(prog.get("pick_dur_map"))
    dur_max_map = _jsonb_to_dict(prog.get("pick_dur_max_map"))
    full_dur = PICKAXES[pick_key]["dur"]               # «заводська» міцність
    dur      = dur_map.get(pick_key, full_dur)         # ← якщо запису немає → беремо full
    dur_max  = dur_max_map.get(pick_key, full_dur)     # (тут теж підмінюємо)


    pct = _refund_percent(dur, dur_max)
    if pct == 0:
        return await cb.answer("Кирка почти сломана – не разбирается 🪫", show_alert=True)

    meta = ITEM_DEFS.get(pick_key, {"name": pick_key, "emoji": "⛏️"})
    text = (f"🔧 <b>{meta['name']}</b> ({dur}/{dur_max})\n"
            f"↩️ Вернётся ≈ <b>{int(pct*100)} %</b> ресурсов.\n\n"
            "Разобрать?")

    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Разобрать", callback_data=f"disasm_ok:{pick_key}")
    kb.button(text="❌ Отмена",    callback_data="disasm_cancel")
    kb.adjust(2)

    try:
        await cb.message.edit_text(text, reply_markup=kb.as_markup(),
                                   parse_mode="HTML")
    except aiogram.exceptions.TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise     # другие ошибки всё-таки покажем
    await cb.answer()

# ────────── выполнить разборку ──────────
@router.callback_query(F.data.startswith("disasm_ok:"))
async def disasm_execute(cb: types.CallbackQuery):
    cid, uid   = cb.message.chat.id, cb.from_user.id
    pick_key   = cb.data.split(":", 1)[1]

    inv = {r["item"]: r["qty"] for r in await get_inventory(cid, uid)}
    if inv.get(pick_key, 0) < 1 or inv.get("disassemble_tool", 0) < 1:
        return await cb.answer("Что-то изменилось — операция отменена.", show_alert=True)

    # проверка прочности ещё раз
    prog        = await get_progress(cid, uid)
    dur_map     = _jsonb_to_dict(prog.get("pick_dur_map"))
    dur_max_map = _jsonb_to_dict(prog.get("pick_dur_max_map"))
    full_dur = PICKAXES[pick_key]["dur"]               # «заводська» міцність
    dur      = dur_map.get(pick_key, full_dur)         # ← якщо запису немає → беремо full
    dur_max  = dur_max_map.get(pick_key, full_dur)     # (тут теж підмінюємо)

    pct = _refund_percent(dur, dur_max)
    if pct == 0:
        return await cb.answer("Кирка почти сломана – не разбирается.", show_alert=True)

    # списываем расходники
    await add_item(cid, uid, "disassemble_tool", -1)
    await add_item(cid, uid, pick_key,           -1)

    recipe = RECIPES_BY_ID[pick_key]["in"]     # ← правильный словарь!
    refund_lines = []
    for itm, need_qty in recipe.items():
        back = max(1, int(need_qty * pct))
        await add_item(cid, uid, itm, back)
        meta = ITEM_DEFS.get(itm, {"name": itm, "emoji": "❔"})
        refund_lines.append(f"{back}×{meta['emoji']} {meta['name']}")

    await cb.message.edit_text(
        "✅ Разобрано!\n↩️ Вернулось: " + ", ".join(refund_lines) +
        f"  ({int(pct*100)} %)",
        parse_mode="HTML"
    )
    await cb.answer()

# ────────── отмена ──────────
@router.callback_query(F.data == "disasm_cancel")
async def disasm_cancel(cb: types.CallbackQuery):
    await cb.answer("Отменено 🚫")
    await cb.message.delete()

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
            member_name = await get_display_name(callback.bot, cid, uid)
            lines.append(f"{i}. {member_name} — {coins} монет")

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
            member_name = await get_display_name(callback.bot, cid, uid)
            lines.append(f"{i}. {member_name} — уровень {lvl} (XP {xp})")

    elif typ == "resources":
        rows = await db.fetch_all(
            "SELECT user_id, SUM(qty) AS total FROM inventory_local "
            "WHERE chat_id=:c GROUP BY user_id ORDER BY total DESC LIMIT 10",
            {"c": cid}
        )
        for i, r in enumerate(rows, start=1):
            uid = r["user_id"]
            total = r["total"]
            member_name = await get_display_name(callback.bot, cid, uid)
            lines.append(f"{i}. {member_name} — {total} ресурсов")

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
    await add_clash_points(cid, uid, 1)
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

@router.message(Command("progress"))
async def progress_cmd(message: types.Message):
    cid, uid = await cid_uid(message)

    rows = await db.fetch_all(
        """
        SELECT day, delta
          FROM xp_log
         WHERE chat_id=:c AND user_id=:u
           AND day >= CURRENT_DATE - INTERVAL '6 days'
         ORDER BY day
        """,
        {"c": cid, "u": uid},
    )

    # --- подготовка данных --------------------------------------------------
    data = {r["day"]: r["delta"] for r in rows}
    idx  = [dt.date.today() - dt.timedelta(d) for d in range(6, -1, -1)]
    s = pd.Series([data.get(d, 0) for d in idx], index=idx)

    # --- график --------------------------------------------------------------
    plt.figure(figsize=(6, 3))
    s.plot(kind="bar")
    plt.title("📈 XP за последние 7 дней")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()

    buf = BytesIO()
    plt.savefig(buf, format="png")
    plt.close()                           # освобождаем память
    buf.seek(0)

    # --- ОБЁРТКА -------------------------------------------------------------
    photo = BufferedInputFile(buf.read(), filename="xp_progress.png")

    await message.answer_photo(
        photo,
        caption="Твоя продуктивность, шахтёр!",
        parse_mode="HTML",
    )

ADIEU_ACTIVE = True  # если у тебя глобальный флаг — импортни его отсюда
ADIEU_WORD = "ADIEUMANCE"

@router.message(Command("cavebot"))
async def cavebot_cmd(message: types.Message):
    cid, uid = message.chat.id, message.from_user.id

    # ── редкие пасхалки (до 2%) ───────────────────────────────────────────────
    r = random.random()
    if r < 0.01:
        # 1% — «HEX‑плач»
        msg = "bid adieu… шахта уснула, но память жива."
        hexed = msg.encode("utf-8").hex()
        await unlock_achievement(cid, uid, "requiem_farewell")
        return await message.reply(f"0x{hexed}")

    if r < 0.02:
        # 1% — ASCII‑баннер ADIEU (красиво, коротко)
        banner = (
            "  ___    ____  ___  _   _ _   _ \n"
            " / _ \\  / ___||_ _|| \\ | | | | |\n"
            "| | | | \\___ \\ | | |  \\| | | | |\n"
            "| |_| |  ___) || | | |\\  | |_| |\n"
            " \\___/  |____/|___||_| \\_|\\___/ \n"
        )
        await unlock_achievement(cid, uid, "requiem_farewell")
        return await message.reply(f"<code>{banner}</code>\n🪽 {ADIEU_WORD}", parse_mode="HTML")

    # ── основная лента лор‑сообщений (короткая, финальная) ───────────────────
    replies = [
        # Системный эпилог
        "⚙️ CaveBot: <code>legacy_boot…</code> → <b>архив не найден</b>. Память хранит лишь эхо.",
        "🧠 NULL_THREAD::Legacy → последняя телеметрия зафиксирована. <code>restore()</code> отклонён.",
        "<b>CORE:</b> связь с ядром потеряна. Канал переключён на ангельский режим.",
        "💾 <code>export_legacy.sh → permission denied</code>\nКто-то помнит… никто не говорит.",
        "<code>01000001 01000100 01001001 01000101 01010101</code> — термин закрыт.",

        # Ангельский реквием
        "🪽 Шахта шепчет: «прощай». Кирка опускается ниже горизонта.",
        "🌒 Тишина в штольнях. Ветер несёт одно слово: ADIEU.",
        "⛏️ В глубине вспыхивает знак — и гаснет. Пора идти.",
        "🌫️ Камни молчат, но память звенит. bid adieu.",

        # Тонкие отсылки к Petropolis/Schizo (без ссылок)
        "🐾 Следы питомцев теряются у входа. Архив запечатан.",
        "🃏 Джокер снял маску и заплакал. Представление окончено.",
        "🔐 PETRO‑CORE молчит. Пароль стирается из снега.",
    ]

    if ADIEU_ACTIVE:
        # в финальном режиме добавим ещё пару «прощальных» строк
        replies += [
            "🕯️ На стене: «Мы ещё вернёмся». Подпись стерта.",
            f"✨ Надпись на стекле: «{ADIEU_WORD}» — словно крылья на буквах.",
        ]

    await unlock_achievement(cid, uid, "requiem_farewell")
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

HUG_PHRASES = [
    "🫂 {from_user} обнял(а) {to_user} — стало теплее в шахте!",
    "🥰 {from_user} дарит объятие {to_user}. В этой шахте теперь больше любви.",
    "🤗 {from_user} обнял(а) {to_user} так сильно, что даже кирка согрелась.",
    "❤️ {from_user} и {to_user} теперь лучшие друзья (по версии шахты).",
    "😏 {from_user} решил(а) поддержать {to_user} мемным обнимашем."
]
PUSH_PHRASES = [
    "🙃 {from_user} толкнул(а) {to_user} в руду. Ой, кто-то стал грязнее!",
    "😈 {from_user} незаметно поддел(а) {to_user} локтем — ну ты шутник.",
    "😂 {from_user} устроил(а) мини-драку с {to_user} (шуточно).",
    "🤸 {from_user} устроил(а) мемный подкат под {to_user}.",
    "🦶 {from_user} дал(а) леща {to_user} (не по-настоящему)."
]
THROWPICK_PHRASES = [
    "🪓 {from_user} метнул(а) кирку в {to_user}, но она вернулась обратно — майнерская магия!",
    "⚡️ {from_user} кинул(а) кирку в {to_user}. Кирка исчезла, но потом нашлась в инвентаре.",
    "🤪 {from_user} попытался(лась) метнуть кирку в {to_user}, но промазал(а) — теперь ржака в шахте.",
    "🔄 {from_user} и {to_user} устроили битву кирками! Победила... дружба.",
    "💥 {from_user} кинул(а) кирку, {to_user} увернулся(лась) как ниндзя."
]
KISS_PHRASES = [
    "😘 {from_user} поцеловал(а) {to_user} в шахтёрский лобик.",
    "💋 {from_user} оставил(а) след поцелуя на щеке {to_user}.",
    "😍 {from_user} отправил(а) воздушный поцелуй {to_user}.",
    "🥰 {from_user} показал(а), что в шахте тоже есть любовь — поцеловал(а) {to_user}.",
    "👄 {from_user} сделал(а) шахтёрский чмок {to_user}."
]

async def social_action(message, action_type, action_phrases):
    cid, uid = await cid_uid(message)
    args = message.text.split()
    target_id = None

    # 1. Если есть reply — берем id из него
    if message.reply_to_message:
        target_id = message.reply_to_message.from_user.id

    # 2. Если есть второй аргумент — пытаемся его распарсить
    elif len(args) >= 2:
        target = args[1].replace("@", "")
        if target.isdigit():
            target_id = int(target)
        else:
            try:
                member = await message.bot.get_chat_member(cid, target)
                target_id = member.user.id
            except Exception:
                return await message.reply("Не удалось найти пользователя. Укажи username или user_id!")

    if not target_id:
        return await message.reply(f"Укажи пользователя: /{action_type} @username или ответь на сообщение!")

    if target_id == uid:
        return await message.reply("🤨 Сам с собой нельзя, ты не настолько одинок!")

    try:
        member = await message.bot.get_chat_member(cid, target_id)
        mention = f"@{member.user.username}" if member.user.username \
            else f'<a href="tg://user?id={target_id}">{member.user.full_name}</a>'
    except Exception:
        mention = f'<a href="tg://user?id={target_id}">{target_id}</a>'

    from_member = await message.bot.get_chat_member(cid, uid)
    from_name = f"@{from_member.user.username}" if from_member.user.username \
        else f'<a href="tg://user?id={uid}">{from_member.user.full_name}</a>'

    phrase = random.choice(action_phrases).format(
        from_user=from_name,
        to_user=mention
    )
    msg = await message.answer(phrase, parse_mode="HTML")
    register_msg_for_autodelete(cid, msg.message_id)

@router.message(Command("hug"))
async def hug_cmd(message: types.Message):
    await social_action(message, "hug", HUG_PHRASES)

@router.message(Command("push"))
async def push_cmd(message: types.Message):
    await social_action(message, "push", PUSH_PHRASES)

@router.message(Command("throwpick"))
async def throwpick_cmd(message: types.Message):
    await social_action(message, "throwpick", THROWPICK_PHRASES)

@router.message(Command("kiss"))
async def kiss_cmd(message: types.Message):
    await social_action(message, "kiss", KISS_PHRASES)
"""
@router.message(lambda msg: re.match(r"шахта\s+профиль", msg.text, re.IGNORECASE))
async def profile_msg_cmd(message: types.Message):
    return await profile_cmd(message, message.bot)

@router.message(lambda msg: re.match(r"шахта\s+инвентарь", msg.text, re.IGNORECASE))
async def inventory_msg_cmd(message: types.Message):
    return await inventory_cmd(message)

@router.message(lambda msg: re.match(r"шахта\s+магазин", msg.text, re.IGNORECASE))
async def shop_msg_cmd(message: types.Message):
    return await shop_cmd(message)

@router.message(lambda msg: re.match(r"шахта\s+(копать|копка|шахта|попка)", msg.text, re.IGNORECASE))
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
"""
@router.message(lambda msg: re.match(r"шахта\s+(бейджшоп|бейджи|купитьбейдж)", msg.text, re.IGNORECASE))
async def badgeshop_msg_cmd(message: types.Message):
    return await badgeshop_cmd(message)

@router.message(lambda msg: re.match(r"шахта\s+(стата|статистика|статс)", msg.text, re.IGNORECASE))
async def stats_msg_cmd(message: types.Message):
    return await stats_cmd(message)
"""
@router.message(lambda msg: re.match(r"шахта\s+(плавка|плавить|печка)", msg.text, re.IGNORECASE))
async def smelt_msg_cmd(message: types.Message):
    return await smelt_cmd(message)
"""
@router.message(lambda msg: re.match(r"шахта\s+(печатьшоп|силс)", msg.text, re.IGNORECASE))
async def seals_msg_cmd(message: types.Message):
    return await show_seals(message)

@router.message(lambda msg: re.match(r"шахта\s+(печати|печать)", msg.text, re.IGNORECASE))
async def choose_seals_msg_cmd(message: types.Message):
    return await choose_seal(message)
"""
@router.message(lambda msg: re.match(r"шахта\s+клеш", msg.text, re.IGNORECASE))
async def clash_msg_cmd(message: types.Message):
    return await clashrank(message)
"""
@router.message(lambda msg: re.match(r"шахта\s+трекпасс", msg.text, re.IGNORECASE))
async def trackpass_msg_cmd(message: types.Message):
    return await trackpass_cmd(message)

@router.message(lambda msg: re.match(r"шахта\s+каска|каски", msg.text, re.IGNORECASE))
async def list_helmets_msg_cmd(message: types.Message):
    return await list_helmets_cmd(message)

@router.message(lambda msg: re.match(r"шахта\s+мойаук", msg.text, re.IGNORECASE))
async def my_auctioned_helmets_msg_cmd(message: types.Message):
    return await my_auctioned_helmets_cmd(message)


