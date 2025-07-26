from aiogram import Bot, types
import datetime

ADMIN_ID = 700929765
WHITELIST = [1413444407, 1251835950, 1538081912, 700929765, 796070660, 988127866, 1872832056]

async def send_log(bot: Bot, user: types.User, chat: types.Chat, context: str):
    if user.id in WHITELIST:
        return # no logging
    
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    text = (
        f"📥 <b>Нова взаємодія</b>\n"
        f"🕒 <code>{now}</code>\n"
        f"👤 <code>{user.id}</code> | @{user.username or 'немає'} | {user.full_name}\n"
        f"💬 <b>{context}</b>\n"
        f"📍 chat_id: <code>{chat.id}</code> ({chat.type})"
    )

    try:
        await bot.send_message(chat_id=ADMIN_ID, text=text)
    except Exception:
        pass