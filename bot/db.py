import aiosqlite
import os
from bot.utils.config import DATABASE_PATH

async def init_db():
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)

    async with aiosqlite.connect(DATABASE_PATH) as db:
        # main
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance INTEGER DEFAULT 0,
            last_mine INTEGER DEFAULT 0
        );
        """)
        # inventory
        await db.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            user_id INTEGER,
            item TEXT,
            quantity INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, item),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );
        """)

        await db.commit()

async def get_user(user_id):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            return await cursor.fetchone()

async def create_user(user_id, username):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
        await db.commit()

async def get_invnetory(user_id):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute("SELECT item, quantity FROM inventory WHERE user_id = ?", (user_id,))
        return await cursor.fetchall()
    
async def add_item(user_id, item, qty):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            INSERT INTO inventory (user_id, item, quantity)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, item) DO UPDATE SET quantity = quantity + excluded.quantity
        """, (user_id, item, qty))
        return db.commit()
