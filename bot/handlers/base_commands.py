from aiogram import Router, types, F
from bot.db import create_user, get_user, db
import time
import random

router = Router()

@router.message(F.text == "/start")
async def start_cmd(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.full_name

    await create_user(user_id, username)
    await message.reply(
        "Привіт, шахтарю! ⛏️ Ти щойно зареєструвався в системі. Напиши /mine щоб копати!"
    )

@router.message(F.text == "/mine")
async def mine_cmd(message: types.Message):
    user_id = message.from_user.id
    user = await get_user(user_id)

    if not user:
        await message.reply("Спершу введи /start, щоб тебе зареєструвати!")
        return

    now = int(time.time())
    cooldown = 30

    # user[3] — це last_mine
    if now - user["last_mine"] < cooldown:
        await message.reply(
            f"🕒 Ти вже копав! Спробуй знову через {cooldown - (now - user['last_mine'])} сек."
        )
        return

    loot = random.choice(["🪨 Камінь", "🧱 Вугілля", "🪙 Золото"])
    value = {"🪨 Камінь": 5, "🧱 Вугілля": 10, "🪙 Золото": 20}[loot]

    # Оновлюємо баланс і час копання через db.execute
    await db.execute(
        """
        UPDATE users
           SET balance = balance + :value,
               last_mine = :now
         WHERE user_id = :user_id
        """,
        {"value": value, "now": now, "user_id": user_id}
    )

    await message.reply(f"Ти знайшов {loot}! Твій баланс поповнено на {value} монет 💰")

@router.message(F.text == "/inventory")
async def inventory_cmd(message: types.Message):
    user = await get_user(message.from_user.id)
    if not user:
        await message.reply("Спершу введи /start, щоб тебе зареєструвати!")
        return

    await message.reply(f"🧾 Твій баланс: {user['balance']} монет")
