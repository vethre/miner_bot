# bot/db.py
from databases import Database
from bot.utils.config import DB_DSN

db = Database(DB_DSN)

async def init_db():
    # підключаємось до Supabase Postgres
    await db.connect()
    # створюємо таблиці, якщо нема
    await db.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id BIGINT PRIMARY KEY,
        username TEXT,
        balance BIGINT DEFAULT 0,
        last_mine BIGINT DEFAULT 0
    );
    """)
    await db.execute("""
    CREATE TABLE IF NOT EXISTS inventory (
        user_id BIGINT,
        item TEXT,
        quantity BIGINT DEFAULT 0,
        PRIMARY KEY (user_id, item),
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    );
    """)

async def create_user(user_id, username):
    query = """
    INSERT INTO users (user_id, username)
    VALUES (:user_id, :username)
    ON CONFLICT (user_id) DO NOTHING;
    """
    await db.execute(query, {"user_id": user_id, "username": username})

async def get_user(user_id):
    query = "SELECT user_id, username, balance, last_mine FROM users WHERE user_id = :user_id"
    return await db.fetch_one(query, {"user_id": user_id})

async def add_item(user_id, item, qty):
    query = """
    INSERT INTO inventory (user_id, item, quantity)
    VALUES (:user_id, :item, :qty)
    ON CONFLICT (user_id, item) DO UPDATE 
      SET quantity = inventory.quantity + EXCLUDED.quantity;
    """
    await db.execute(query, {"user_id": user_id, "item": item, "qty": qty})

async def get_inventory(user_id):
    query = "SELECT item, quantity FROM inventory WHERE user_id = :user_id"
    return await db.fetch_all(query, {"user_id": user_id})
