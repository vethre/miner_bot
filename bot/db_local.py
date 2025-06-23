# bot/db_local.py
import datetime as dt
from zoneinfo import ZoneInfo
import json, asyncpg
from typing import Tuple, List, Dict, Any
from aiogram.types import Message, CallbackQuery
from bot.db import db               # глобальний async-connection

UTC = ZoneInfo("UTC")

# ────────── DDL ──────────
DDL = """
CREATE TABLE IF NOT EXISTS inventory_local (
    chat_id  BIGINT,
    user_id  BIGINT,
    item     TEXT,
    qty      INT DEFAULT 0,
    PRIMARY KEY(chat_id, user_id, item)
);
CREATE TABLE IF NOT EXISTS balance_local (
    chat_id  BIGINT,
    user_id  BIGINT,
    coins    INT DEFAULT 0,
    PRIMARY KEY(chat_id, user_id)
);
CREATE TABLE IF NOT EXISTS progress_local (
    chat_id  BIGINT,
    user_id  BIGINT,
    level    INT  DEFAULT 1,
    xp       INT  DEFAULT 0,

    current_pickaxe TEXT DEFAULT 'wooden_pickaxe',
    pick_dur        INT  DEFAULT 65,
    pick_dur_max    INT  DEFAULT 65,

    cave_pass    BOOL DEFAULT FALSE,
    pass_expires TIMESTAMP,
    cave_cases   INT  DEFAULT 0,

    mining_end   TIMESTAMP,
    smelt_end    TIMESTAMP,
    last_mine_day DATE DEFAULT '1970-01-01',
    last_daily    DATE DEFAULT '1970-01-01',

    energy               INT DEFAULT 100,
    last_energy_update   TIMESTAMP,
    hunger               INT DEFAULT 100,
    last_hunger_update   TIMESTAMP,

    PRIMARY KEY(chat_id, user_id)
);
CREATE TABLE IF NOT EXISTS case_rewards (
  reward_key   TEXT    PRIMARY KEY,
  reward_type  TEXT    NOT NULL,      
  reward_data  JSONB   NOT NULL       
);

ALTER TABLE progress_local
  ADD COLUMN IF NOT EXISTS streak INT DEFAULT 0;

ALTER TABLE progress_local ADD COLUMN IF NOT EXISTS autodelete_minutes INTEGER DEFAULT 0;

ALTER TABLE progress_local
  ADD COLUMN IF NOT EXISTS pick_dur_map     JSONB DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS pick_dur_max_map JSONB DEFAULT '{}'::jsonb;

UPDATE progress_local
SET   pick_dur_map = jsonb_build_object(current_pickaxe, pick_dur)
  ||  COALESCE(pick_dur_map,'{}'::jsonb),
      pick_dur_max_map = jsonb_build_object(current_pickaxe, pick_dur_max)
  ||  COALESCE(pick_dur_max_map,'{}'::jsonb)
WHERE pick_dur_map = '{}'::jsonb;

"""
AUTO_DELETE = {}
# ────────── INIT ──────────
async def init_local():
    """Виконати міграцію DDL після підключення БД."""
    for stmt in DDL.strip().split(";"):
        if stmt.strip():
            await db.execute(stmt + ";")

# ────────── КОНСТАНТИ ──────────
ENERGY_MAX, ENERGY_REGEN, ENERGY_INTERVAL_S = 100, 15, 20 * 60
HUNGER_MAX, HUNGER_DECAY, HUNGER_INTERVAL_S   = 100, 10, 60 * 60
DEFAULT_DUR = 65 

# ────────── HELPER ──────────
async def cid_uid(msg: Message | CallbackQuery) -> Tuple[int, int]:
    if isinstance(msg, CallbackQuery):
        chat = msg.message.chat
        user = msg.from_user
    elif isinstance(msg, Message):
        chat = msg.chat
        user = msg.from_user
    else:
        raise TypeError("cid_uid: unsupported type")

    cid = chat.id if chat.type in ("group", "supergroup") else 0
    return cid, user.id

async def _ensure_progress(cid: int, uid: int):
    dm  = json.dumps({"wooden_pickaxe": DEFAULT_DUR})
    dmm = dm 

    await db.execute(
        """
        INSERT INTO progress_local(
            chat_id, user_id,
            current_pickaxe,
            pick_dur_map, pick_dur_max_map
        )
        VALUES (
            :c, :u,
            'wooden_pickaxe',
            (:dm)::jsonb,
            (:dmm)::jsonb
        )
        ON CONFLICT DO NOTHING
        """,
        {"c": cid, "u": uid, "dm": dm, "dmm": dmm}
    )

    # ② страховка від старого 'wood_pickaxe'
    await db.execute(
        """
        UPDATE progress_local
           SET current_pickaxe = 'wooden_pickaxe'
         WHERE chat_id=:c AND user_id=:u
           AND current_pickaxe IN ('wood_pickaxe','none')
        """,
        {"c": cid, "u": uid}
    )

# ────────── ІНВЕНТАР ──────────
async def add_item(cid: int, uid: int, item: str, delta: int):
    await _ensure_progress(cid, uid)
    await db.execute(
        "INSERT INTO inventory_local VALUES(:c,:u,:i,:d) "
        "ON CONFLICT (chat_id,user_id,item) DO UPDATE SET qty = inventory_local.qty + :d",
        {"c": cid, "u": uid, "i": item, "d": delta}
    )

async def get_inventory(cid: int, uid: int) -> List[Dict[str, Any]]:
    return await db.fetch_all(
        "SELECT item, qty FROM inventory_local "
        "WHERE chat_id=:c AND user_id=:u AND qty>0",
        {"c": cid, "u": uid}
    )

# ────────── ГРОШІ ──────────
async def add_money(cid: int, uid: int, delta: int):
    await _ensure_progress(cid, uid)
    await db.execute(
        "INSERT INTO balance_local VALUES(:c,:u,:d) "
        "ON CONFLICT (chat_id,user_id) DO UPDATE SET coins = balance_local.coins + :d",
        {"c": cid, "u": uid, "d": delta}
    )

async def get_money(cid: int, uid: int) -> int:
    row = await db.fetch_one(
        "SELECT coins FROM balance_local WHERE chat_id=:c AND user_id=:u",
        {"c": cid, "u": uid}
    )
    return row["coins"] if row else 0

# ────────── XP / LEVEL ──────────
async def add_xp(cid: int, uid: int, delta: int):
    await _ensure_progress(cid, uid)

    row = await db.fetch_one(
        "SELECT level, xp FROM progress_local "
        "WHERE chat_id=:c AND user_id=:u",
        {"c": cid, "u": uid}
    )
    lvl, xp = row["level"], row["xp"] + delta
    threshold = lvl * 80

    leveled = False
    while xp >= threshold:
        xp -= threshold
        lvl += 1
        threshold = lvl * 80
        leveled = True

    if leveled:
        # оновлюємо XP і рівень
        await db.execute(
            """
            UPDATE progress_local
               SET xp = :xp,
                   level = :lvl
             WHERE chat_id = :c AND user_id = :u
            """,
            {"xp": xp, "lvl": lvl, "c": cid, "u": uid}
        )
    else:
        # тільки XP
        await db.execute(
            """
            UPDATE progress_local
               SET xp = :xp
             WHERE chat_id = :c AND user_id = :u
            """,
            {"xp": xp, "c": cid, "u": uid}
        )

async def get_progress(cid: int, uid: int) -> Dict[str, Any]:
    row = await db.fetch_one(
        "SELECT * FROM progress_local WHERE chat_id=:c AND user_id=:u",
        {"c": cid, "u": uid}
    )
    return dict(row) if row else {}

# ────────── ENERGY / HUNGER ──────────
async def update_energy(cid: int, uid: int):
    await _ensure_progress(cid, uid)
    row = await db.fetch_one(
        "SELECT energy FROM progress_local WHERE chat_id=:c AND user_id=:u",
        {"c": cid, "u": uid}
    )
    return row["energy"]

async def add_energy(cid:int, uid:int, delta:int):
    await _ensure_progress(cid, uid)
    await db.execute(
        "UPDATE progress_local SET energy = LEAST(:max, GREATEST(0, energy + :d)) "
        "WHERE chat_id=:c AND user_id=:u",
        {"max": ENERGY_MAX, "d": delta, "c": cid, "u": uid}
    )

async def update_hunger(cid: int, uid: int):
    await _ensure_progress(cid, uid)
    row = await db.fetch_one(
        "SELECT hunger FROM progress_local WHERE chat_id=:c AND user_id=:u",
        {"c": cid, "u": uid}
    )
    return row["hunger"]

async def update_streak(cid: int, uid: int) -> int:
    # дістаємо останній день
    row = await db.fetch_one(
        "SELECT last_mine_day FROM progress_local WHERE chat_id=:c AND user_id=:u",
        {"c": cid, "u": uid}
    )
    last_day = row["last_mine_day"] or dt.date(1970,1,1)
    today = dt.date.today()
    if last_day == today:
        streak = await db.fetch_val(
            "SELECT streak FROM progress_local WHERE chat_id=:c AND user_id=:u",
            {"c": cid, "u": uid}
        )
    elif last_day + dt.timedelta(days=1) == today:
        streak = await db.fetch_val(
            "SELECT streak FROM progress_local WHERE chat_id=:c AND user_id=:u",
            {"c": cid, "u": uid}
        ) + 1
    else:
        streak = 1

    await db.execute(
        "UPDATE progress_local SET streak=:s, last_mine_day=:d WHERE chat_id=:c AND user_id=:u",
        {"s": streak, "d": today, "c": cid, "u": uid}
    )

    if streak % 5 == 0:
        bonus = 50 + 10 * (streak // 5)      
        await add_xp(cid, uid, bonus)
        await add_money(cid, uid, 100)      

    return streak

# ─── PICK DUR HELPERS ────────────────────────────────────────────────
async def set_pick(cid:int, uid:int, pick_key:str, max_dur:int):
    """Активувати кирку й виставити її особисту лічильну міцність."""
    await _ensure_progress(cid, uid)

    # оновлюємо мапи
    await db.execute(
        """
        UPDATE progress_local
           SET current_pickaxe = :p,
               pick_dur_map     = jsonb_set(pick_dur_map,     ARRAY[:p], to_jsonb(:max-0)),
               pick_dur_max_map = jsonb_set(pick_dur_max_map, ARRAY[:p], to_jsonb(:max-0))
         WHERE chat_id=:c AND user_id=:u
        """,
        {"p": pick_key, "max": max_dur, "c": cid, "u": uid}
    )

def _jsonb_to_dict(value):
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        return json.loads(value)          # ← «універсальна» точка
    raise TypeError("Unexpected JSONB type")

def _to_int(x):          # допоміжна функція
    try:
        return int(x)
    except (TypeError, ValueError):
        return 0

async def change_dur(cid:int, uid:int, key:str, delta:int):
    row = await db.fetch_one(
        "SELECT pick_dur_map, pick_dur_max_map FROM progress_local "
        "WHERE chat_id=:c AND user_id=:u",
        {"c": cid, "u": uid}
    )

    dur_map     = _jsonb_to_dict(row["pick_dur_map"])
    dur_max_map = _jsonb_to_dict(row["pick_dur_max_map"])

    # перетворюємо значення у числа
    dur_map     = {k: _to_int(v) for k, v in dur_map.items()}
    dur_max_map = {k: _to_int(v) for k, v in dur_max_map.items()}

    # якщо ключів ще нема – заводимо з дефолтами
    if key not in dur_max_map:
        from bot.handlers.use import PICKAXES
        dur_max_map[key] = PICKAXES[key]["dur"]
    if key not in dur_map:
        dur_map[key] = dur_max_map[key]

    # змінюємо міцність
    dur_map[key] = max(0, dur_map[key] + delta)

    # записуємо назад
    await db.execute(
        """
        UPDATE progress_local
           SET pick_dur_map = (:dm)::jsonb,
               pick_dur_max_map = (:dmm)::jsonb
         WHERE chat_id=:c AND user_id=:u
        """,
        {
            "dm":  json.dumps(dur_map),
            "dmm": json.dumps(dur_max_map),
            "c": cid, "u": uid
        }
    )

    return dur_map[key], dur_max_map[key]


