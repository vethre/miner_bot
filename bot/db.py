import datetime
from databases import Database
from bot.utils.config import DB_DSN

db = Database(DB_DSN)

async def init_db():
    # створюємо таблицю користувачів з новими колонками
    await db.connect()
    await db.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id        BIGINT PRIMARY KEY,
        username       TEXT,
        balance        BIGINT DEFAULT 0,
        last_mine      BIGINT DEFAULT 0,
        level          INTEGER DEFAULT 1,
        xp             BIGINT DEFAULT 0,
        energy         INTEGER DEFAULT 5,
        last_energy_update TIMESTAMP DEFAULT NOW()
    );
    """)

    await db.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS level INTEGER DEFAULT 1;")
    await db.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS xp BIGINT DEFAULT 0;")
    await db.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS energy INTEGER DEFAULT 5;")
    await db.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_energy_update TIMESTAMP DEFAULT NOW();")
    await db.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS streak INTEGER DEFAULT 0;")
    await db.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_mine_day DATE DEFAULT CURRENT_DATE;")
    await db.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS mining_end BIGINT DEFAULT 0;")
    await db.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS hunger INTEGER DEFAULT 100;")
    await db.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_hunger_update TIMESTAMP DEFAULT NOW();")
    await db.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS current_pickaxe TEXT DEFAULT 'none';")
    await db.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_daily TIMESTAMP DEFAULT '1970-01-01';")

    await db.execute("""
    CREATE TABLE IF NOT EXISTS inventory (
        user_id INTEGER,
        item    TEXT,
        quantity BIGINT DEFAULT 0,
        PRIMARY KEY (user_id, item),
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    );
    """)

    await db.execute("""
    CREATE TABLE IF NOT EXISTS groups (
        chat_id   BIGINT PRIMARY KEY,
        title     TEXT,
        added_at  TIMESTAMP DEFAULT NOW() 
    );
    """)

# CRUD для користувача
async def create_user(user_id, username):
    await db.execute("""
      INSERT INTO users (user_id, username)
      VALUES (:uid, :uname)
      ON CONFLICT (user_id) DO NOTHING;
    """, {"uid": user_id, "uname": username})

async def get_user(user_id):
    return await db.fetch_one("""
        SELECT user_id, username, balance, level, xp, energy, last_energy_update, mining_end, streak, last_mine_day, last_hunger_update, hunger, current_pickaxe
          FROM users
         WHERE user_id = :uid
    """, {"uid": user_id})

# Інвентар
async def add_item(user_id, item, qty):
    await db.execute("""
      INSERT INTO inventory (user_id, item, quantity)
      VALUES (:uid, :item, :qty)
      ON CONFLICT (user_id, item) DO UPDATE
        SET quantity = inventory.quantity + EXCLUDED.quantity;
    """, {"uid": user_id, "item": item, "qty": qty})

async def get_inventory(user_id):
    return await db.fetch_all("""
        SELECT item, quantity
          FROM inventory
         WHERE user_id = :uid
    """, {"uid": user_id})

# XP та рівні
async def add_xp(user_id, amount):
    user = await get_user(user_id)
    lvl = user["level"]
    xp = user["xp"] + amount
    # поріг для наступного рівня
    threshold = lvl * 100
    leveled = False
    while xp >= threshold:
        xp -= threshold
        lvl += 1
        threshold = lvl * 100
        leveled = True

    if leveled:
        # на підвищення рівня повністю відновлюємо енергію
        max_e = 5 + (lvl - 1) * 2
        await db.execute("""
          UPDATE users
             SET xp = :xp, level = :lvl,
                 energy = :max_e, last_energy_update = NOW()
           WHERE user_id = :uid
        """, {"xp": xp, "lvl": lvl, "max_e": max_e, "uid": user_id})
    else:
        await db.execute("""
          UPDATE users SET xp = :xp WHERE user_id = :uid
        """, {"xp": xp, "uid": user_id})

# Підрахунок і поновлення енергії
async def update_energy(user):
    now = datetime.datetime.utcnow()
    last = user["last_energy_update"]
    # секунд між оновленнями
    regen_interval = 5 * 60
    elapsed = (now - last).total_seconds()
    gained = int(elapsed // regen_interval)
    if gained <= 0:
        return user["energy"], last

    max_e = 5 + (user["level"] - 1) * 2
    new_energy = min(max_e, user["energy"] + gained)
    new_last = last + datetime.timedelta(seconds=gained * regen_interval)
    await db.execute("""
      UPDATE users
         SET energy = :ene, last_energy_update = :lupd
       WHERE user_id = :uid
    """, {"ene": new_energy, "lupd": new_last, "uid": user["user_id"]})
    return new_energy, new_last

# Cave Streaks
async def update_streak(user):
    today = datetime.date.today()
    last = user["last_mine_day"]
    current = user["streak"] or 0

    if last == today - datetime.timedelta(days=1):
        current += 1
    elif last == today:
        # вже сьогодні були в шахті
        pass
    else:
        current = 1

    await db.execute(
        """
        UPDATE users
           SET streak = :st, last_mine_day = :lm
         WHERE user_id = :uid
        """,
        {"st": current, "lm": today, "uid": user["user_id"]}
    )
    return current

# Hunger
async def update_hunger(user):
    import math
    now = datetime.datetime.utcnow()
    try:
        last = user["last_hunger_update"]
    except KeyError:
        # колонка ще не створена ─ одразу повертаємо поточний hunger
        return user["hunger"], now

    if last is None:               # значення NULL у старих рядках
        await db.execute(
            """
            UPDATE users
               SET last_hunger_update = :ts
             WHERE user_id = :uid
            """,
            {"ts": now, "uid": user["user_id"]}
        )
        return user["hunger"], now
    elapsed_sec = (now - last).total_seconds()

    decount = math.floor(elapsed_sec / 3600) * 10
    if decount <= 0:
        return user["hunger"], last
    
    new_h = max(0, user["hunger"] - decount)
    hours = decount // 10
    new_last = last + datetime.timedelta(hours=hours)
    await db.execute("""
        UPDATE users
           SET hunger = :h, last_hunger_update = :lupd
         WHERE user_id = :uid
        """,
        {"h": new_h, "lupd": new_last, "uid": user["user_id"]})
    return new_h, new_last