# bot/db_local.py
import datetime as dt
from typing import Tuple, List, Dict, Any
from bot.db import db               # глобальний async-connection

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
    pick_dur        INT  DEFAULT 100,
    pick_dur_max    INT  DEFAULT 100,

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
"""

# ────────── INIT ──────────
async def init_local():
    """Виконати міграцію DDL після підключення БД."""
    for stmt in DDL.strip().split(";"):
        if stmt.strip():
            await db.execute(stmt + ";")

# ────────── КОНСТАНТИ ──────────
ENERGY_MAX, ENERGY_REGEN, ENERGY_INTERVAL_S = 100, 15, 30 * 60
HUNGER_MAX, HUNGER_DECAY, HUNGER_INTERVAL_S   = 100, 10, 60 * 60

# ────────── HELPER ──────────
async def cid_uid(msg) -> Tuple[int, int]:
    cid = msg.chat.id if msg.chat.type in ("group", "supergroup") else 0
    return cid, msg.from_user.id

async def _ensure_progress(cid: int, uid: int):
    await db.execute(
        "INSERT INTO progress_local(chat_id,user_id) VALUES(:c,:u) ON CONFLICT DO NOTHING",
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
    await db.execute(
        "UPDATE progress_local SET xp = xp + :d WHERE chat_id=:c AND user_id=:u",
        {"d": delta, "c": cid, "u": uid}
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
    now = dt.datetime.utcnow()
    row = await db.fetch_one(
        "SELECT energy,last_energy_update FROM progress_local "
        "WHERE chat_id=:c AND user_id=:u", {"c": cid, "u": uid}
    )
    energy = row["energy"]
    last   = row["last_energy_update"] or now
    regen  = int((now - last).total_seconds() // ENERGY_INTERVAL_S) * ENERGY_REGEN
    if regen:
        energy = min(ENERGY_MAX, energy + regen)
        await db.execute(
            "UPDATE progress_local SET energy=:e,last_energy_update=:n "
            "WHERE chat_id=:c AND user_id=:u",
            {"e": energy, "n": now, "c": cid, "u": uid}
        )
    return energy, now

async def update_hunger(cid: int, uid: int):
    await _ensure_progress(cid, uid)
    now = dt.datetime.utcnow()
    row = await db.fetch_one(
        "SELECT hunger,last_hunger_update FROM progress_local "
        "WHERE chat_id=:c AND user_id=:u", {"c": cid, "u": uid}
    )
    hunger = row["hunger"]
    last   = row["last_hunger_update"] or now
    decay  = int((now - last).total_seconds() // HUNGER_INTERVAL_S) * HUNGER_DECAY
    if decay:
        hunger = max(0, hunger - decay)
        await db.execute(
            "UPDATE progress_local SET hunger=:h,last_hunger_update=:n "
            "WHERE chat_id=:c AND user_id=:u",
            {"h": hunger, "n": now, "c": cid, "u": uid}
        )
    return hunger, now

async def update_streak(cid: int, uid: int) -> int:
    # дістаємо останній день
    row = await db.fetch_one(
        "SELECT last_mine_day FROM progress_local WHERE chat_id=:c AND user_id=:u",
        {"c": cid, "u": uid}
    )
    last_day = row["last_mine_day"] or dt.date(1970,1,1)
    today = dt.date.today()
    if last_day + dt.timedelta(days=1) == today:
        streak = (await db.fetch_val(
            "SELECT streak FROM progress_local WHERE chat_id=:c AND user_id=:u",
            {"c": cid, "u": uid}
        )) + 1
    else:
        streak = 1
    # зберігаємо
    await db.execute(
        "UPDATE progress_local SET streak=:s, last_mine_day=:d WHERE chat_id=:c AND user_id=:u",
        {"s": streak, "d": today, "c": cid, "u": uid}
    )
    return streak
