# bot/handlers/devutils.py

from aiogram import F, Bot, Router, types
from aiogram.filters import Command
from aiogram.utils.markdown import hcode
from bot.db_local import add_money, add_item, db, cid_uid, get_money, get_progress, get_inventory
from aiogram.filters.command import CommandObject
import logging

from bot.handlers.items import ITEM_DEFS
from bot.handlers.trackpass import SEASON_LEN
from bot.utils.autodelete import register_msg_for_autodelete

router = Router()
ADMINS = {700929765, 988127866}  # заміни на свої ID

# ───────────── Команда /ddb ─────────────
@router.message(Command("ddb"))
async def db_cmd(message: types.Message):
    if message.from_user.id not in ADMINS:
        return await message.reply("⛔ Только для админов!")

    cid, uid = await cid_uid(message)
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        return await message.reply("⚠️ Введи SQL-запрос после команды, напр.:\n/db SELECT * FROM progress_local")

    sql = parts[1]
    try:
        # Автоматично визначаємо тип запиту
        if sql.strip().lower().startswith("select"):
            rows = await db.fetch_all(sql)
            if not rows:
                return await message.reply("✅ Запрос исполнен, но ничего не найдено.")
            # Форматуємо перший рядок як приклад
            first = rows[0]
            lines = [f"<code>{k}</code>: {v}" for k, v in first.items()]
            return await message.reply("\n".join(lines), parse_mode="HTML")
        else:
            # Наприклад: UPDATE ... або INSERT ...
            await db.execute(sql)
            return await message.reply("✅ Успешно исполнено.")
    except Exception as e:
        return await message.reply(f"❌ Ошибка:\n<code>{e}</code>", parse_mode="HTML")

# ───────────── Команда /did ─────────────
@router.message(Command("did"))
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

@router.message(Command("devdrop"))
async def devdrop(message: types.Message):
    if message.from_user.id not in ADMINS:  # безпека
        return
    await add_item(message.chat.id, message.from_user.id, "diamond", 999)
    await add_money(message.chat.id, message.from_user.id, 1_000_000)
    await message.reply("💎 devdrop ok")

@router.message(Command("devpass"))
async def dev_pass(message: types.Message):
    if message.from_user.id not in ADMINS:      # ваш список
        return
    cid, uid = await cid_uid(message)
    await db.execute(
        """UPDATE progress_local
              SET cave_pass=TRUE,
                  pass_expires=NOW()+INTERVAL ':d day'
            WHERE chat_id=:c AND user_id=:u""",
        {"d": SEASON_LEN, "c": cid, "u": uid},
    )
    await message.reply("Выдан premium-Pass на тест 🎫")

@router.message(Command("devskipday"))
async def dev_skip(message: types.Message):
    if message.from_user.id not in ADMINS:
        return
    await db.execute("UPDATE progress_local SET last_daily = last_daily - INTERVAL '1 day'")
    await message.reply("⏩ -1 day")

@router.message(Command("dannounce"))
async def announce_cmd(message: types.Message, bot: Bot):
    # ─── доступ тільки для адмінів ─────────────────────────────
    if message.from_user.id not in ADMINS:
        return await message.reply("⛔️ Только для разработчика")

    # ─── текст оголошення ──────────────────────────────────────
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        return await message.reply("Используй: /announce 'текст'")
    text = parts[1]

    # ─── вибираємо всі групи ───────────────────────────────────
    rows = await db.fetch_all("SELECT chat_id FROM groups")
    ok, fail = 0, 0
    for r in rows:
        try:
            await bot.send_message(r["chat_id"], text, parse_mode="HTML")
            ok += 1
        except Exception:
            fail += 1

    await message.reply(f"✅ Отослано: {ok}, ошибок: {fail}")

# ───────────── Команда /ddebug ─────────────
@router.message(Command("ddebug"))
async def debug_cmd(message: types.Message):
    cid, uid = await cid_uid(message)
    prog = await get_progress(cid, uid)
    if not prog:
        return await message.reply("❌ Не найдена запись в progress_local")

    lines = [f"<b>{k}:</b> {v}" for k, v in prog.items()]
    await message.reply("\n".join(lines), parse_mode="HTML")

# ───────────── Команда /photoid ─────────────
@router.message(Command("dfileid"))
async def fileid_cmd(m: types.Message):
    if m.reply_to_message and m.reply_to_message.photo:
        await m.reply(str(m.reply_to_message.photo[-1].file_id))
    else:
        await m.reply("Ответь на фото.")

@router.message(Command("ddevinfo"))
async def devinfo_cmd(message: types.Message, bot: Bot):
    # ── 1. доступ тільки для DEV_IDS ───────────────────────────────
    if message.from_user.id not in ADMINS:
        return

    # ── 2. парсимо аргументи ───────────────────────────────────────
    #    /devinfo <uid | @username> [chat_id]
    try:
        _, arg1, *rest = message.text.strip().split()
    except ValueError:
        return await message.reply("Usage: /devinfo 'uid|@username' [chat_id]")

    cid = int(rest[0]) if rest else (
        message.chat.id if message.chat.type in ("group", "supergroup") else 0
    )

    # ── 3. визначаємо uid ──────────────────────────────────────────
    if arg1.lstrip("-").isdigit():
        uid = int(arg1)
    else:                               # @username
        if cid == 0:
            return await message.reply("У приваті треба передати chat_id.")
        try:
            member = await bot.get_chat_member(cid, arg1)
        except Exception as e:
            return await message.reply(f"Не знайшов {arg1} у чаті {cid}\n{e}")
        uid = member.user.id

    # ── 4. тягнемо дані з БД ───────────────────────────────────────
    prog     = await get_progress(cid, uid)
    balance  = await get_money(cid, uid)
    inv_rows = await get_inventory(cid, uid)

    inv_lines = [
        f"{ITEM_DEFS.get(r['item'], {'name': r['item']})['name']}: {r['qty']}"
        for r in inv_rows
    ] or ["— пусто —"]

    text = (
        f"<b>User-ID:</b> <code>{uid}</code>\n"
        f"<b>Chat-ID:</b> <code>{cid}</code>\n"
        f"<b>Balance:</b> {balance} монет\n"
        f"<b>Progress row:</b> <code>{prog}</code>\n\n"
        "<b>📦 Інвентар:</b>\n" + "\n".join(inv_lines)
    )

    msg = await message.reply(text, parse_mode="HTML")
    register_msg_for_autodelete(message.chat.id, msg.message_id)

# ───────────── Команда /dforcepick ─────────────
@router.message(Command("dforcepick"))
async def forcepick_cmd(message: types.Message, command: CommandObject):
    if message.from_user.id not in ADMINS:
        return await message.reply("⛔ Доступ воспрещён")

    args = (command.args or "").split()
    if len(args) != 1:
        return await message.reply("❗ Пример: /forcepick crystal_pickaxe")

    cid, uid = await cid_uid(message)
    key = args[0].strip()
    await db.execute(
        "UPDATE progress_local SET current_pickaxe=:p WHERE chat_id=:c AND user_id=:u",
        {"p": key, "c": cid, "u": uid}
    )
    await message.reply(f"🔧 Кирка установлена: <b>{key}</b>", parse_mode="HTML")
