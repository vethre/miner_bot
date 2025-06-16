from aiogram import Router, types, F
from bot.db import create_user, get_user
import time
import random

router = Router()

@router.message(F.text == "/start")
async def start_cmd(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.full_name

    await create_user(user_id, username)
    await message.reply("Привіт, шахтарю! ⛏️ Ти щойно зареєструвався в системі. Напиши /mine щоб копати!")

@router.message(F.text == "/mine")
async def mine_cmd(message: types.Message):
    user_id = message.from_user.id
    user = await get_user(user_id)

    if not user:
        await message.reply("Спершу введи /start, щоб тебе зареєструвати!")
        return
    
    now = int(time.time())
    cooldown = 30

    if now - user[3] < cooldown:
        await message.reply(f"🕒 Ти вже копав! Спробуй знову через {cooldown - (now - user[3])} сек.")
        return
    
    loot = random.choice(["🪨 Камінь", "🧱 Вугілля", "🪙 Золото"])
    value = {"🪨 Камінь": 5, "🧱 Вугілля": 10, "🪙 Золото": 20}[loot]

    from bot.db import aiosqlite, DATABASE_PATH
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("UPDATE users SET balance = balance + ?, last_mine = ? WHERE user_id = ?", (value, now, user_id))
        await db.commit()

    await message.reply(f"Ти знайшов {loot}! Твій баланс поповнено на {value} монет 💰")

@router.message(F.text == "/inventory")
async def inventory_cmd(message: types.Message):
    user = await get_user(message.from_user.id)
    if not user:
        await message.reply("Спершу введи /start, щоб тебе зареєструвати!")
        return
    
    await message.reply(f"🧾 Твій баланс: {user[2]} монет")