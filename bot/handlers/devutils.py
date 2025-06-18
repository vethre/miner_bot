# bot/handlers/devutils.py

from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.utils.markdown import hcode
from bot.db_local import db, cid_uid, get_progress
from aiogram.filters.command import CommandObject
import logging

router = Router()
ADMINS = {700929765, 988127866}  # заміни на свої ID

# ───────────── Команда /db ─────────────
@router.message(Command("db"))
async def db_query_cmd(message: types.Message, command: CommandObject):
    if message.from_user.id not in ADMINS:
        return await message.reply("⛔ Ти не маєш доступу до цієї команди")

    if not command.args:
        return await message.reply("❓ Приклад: /db SELECT * FROM progress_local LIMIT 1")

    query = command.args.strip()
    try:
        rows = await db.fetch_all(query)
        if not rows:
            return await message.reply("✅ Запит виконано. Пустий результат.")
        text = "\n".join(hcode(str(dict(r))) for r in rows[:5])
        return await message.reply(f"🔍 Перші 5 записів:\n{text}")
    except Exception as e:
        logging.exception("DB Error")
        return await message.reply(f"❌ Помилка: {e}")

# ───────────── Команда /id ─────────────
@router.message(Command("id"))
async def id_cmd(message: types.Message):
    user = message.from_user
    chat = message.chat
    text = (
        f"🆔 <b>User ID:</b> <code>{user.id}</code>\n"
        f"👥 <b>Chat ID:</b> <code>{chat.id}</code>\n"
        f"🔤 <b>Username:</b> @{user.username}\n"
        f"📛 <b>Full name:</b> {user.full_name}"
    )
    await message.reply(text, parse_mode="HTML")

# ───────────── Команда /debug ─────────────
@router.message(Command("debug"))
async def debug_cmd(message: types.Message):
    cid, uid = await cid_uid(message)
    prog = await get_progress(cid, uid)
    if not prog:
        return await message.reply("❌ Не знайдено запису в progress_local")

    lines = [f"<b>{k}:</b> {v}" for k, v in prog.items()]
    await message.reply("\n".join(lines), parse_mode="HTML")

# ───────────── Команда /photoid ─────────────
@router.message(F.photo)
async def photo_id_handler(message: types.Message):
    photo = message.photo[-1]
    await message.reply(f"🖼️ File ID: <code>{photo.file_id}</code>", parse_mode="HTML")

# ───────────── Команда /forcepick ─────────────
@router.message(Command("forcepick"))
async def forcepick_cmd(message: types.Message, command: CommandObject):
    if message.from_user.id not in ADMINS:
        return await message.reply("⛔ Доступ заборонено")

    args = (command.args or "").split()
    if len(args) != 1:
        return await message.reply("❗ Приклад: /forcepick crystal_pickaxe")

    cid, uid = await cid_uid(message)
    key = args[0].strip()
    await db.execute(
        "UPDATE progress_local SET current_pickaxe=:p WHERE chat_id=:c AND user_id=:u",
        {"p": key, "c": cid, "u": uid}
    )
    await message.reply(f"🔧 Кирка встановлена: <b>{key}</b>", parse_mode="HTML")
