# bot/handlers/devutils.py

import datetime as dt
from aiogram import F, Bot, Router, types
from aiogram.filters import Command
from aiogram.utils.markdown import hcode
from bot.db_local import db, cid_uid, get_money, get_progress, get_inventory, add_money
from aiogram.filters.command import CommandObject
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
import logging

from bot.handlers.items import ITEM_DEFS
from bot.utils.autodelete import register_msg_for_autodelete

router = Router()
ADMINS = {700929765, 988127866}  # заміни на свої ID

# ───────────── Команда /db ─────────────
@router.message(Command("db"))
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

class Ann(StatesGroup):
    text = State()
    choose = State()

# util — получить список групп, где «живёт» бот
async def _all_chats() -> list[tuple[int,str]]:
    rows = await db.fetch_all("SELECT chat_id, title FROM groups")
    # title может быть NULL → str(chat_id)
    return [(r["chat_id"], r["title"] or str(r["chat_id"])) for r in rows]

# ────────────────────────────────────────────

@router.message(Command("announce"))
async def announce_entry(msg: types.Message, state: FSMContext, bot: Bot):
    if msg.from_user.id not in ADMINS:
        return await msg.reply("⛔️ Только для разработчика")

    args = msg.text.split(maxsplit=2)

    # ── Быстрый режим: /announce all …  или  /announce <id1,id2> …
    if len(args) >= 3:
        dest_raw, text = args[1], args[2]
        if dest_raw.lower() == "all":
            chats = [cid for cid, _ in await _all_chats()]
        else:
            chats = [int(x) for x in dest_raw.split(",") if x.strip().isdigit()]
        await _broadcast(bot, chats, text, msg)
        return

    # ─────────────────────────────── интерактив
    if len(args) == 1:
        await state.set_state(Ann.text)
        await msg.reply("📝 Пришли текст объявления одним сообщением.")
    else:
        await msg.reply("❗️ Формат: /announce all 'текст'  или  /announce 'id,id' 'текст'")

# получаем текст
@router.message(Ann.text)
async def ann_got_text(msg: types.Message, state: FSMContext):
    await state.update_data(text=msg.html_text)
    # строим клавиатуру
    chats = await _all_chats()
    kb = InlineKeyboardBuilder()
    for cid, title in chats:
        kb.button(text=f"❌ {title}", callback_data=f"ann:{cid}:0")
    kb.adjust(1)
    kb.button(text="➡️ Отправить", callback_data="ann_send")
    await msg.reply("✅ Выбери чаты (клик меняет статус):", reply_markup=kb.as_markup())
    await state.update_data(choosen=set())
    await state.set_state(Ann.choose)

# переключаем «✅/❌»
@router.callback_query(Ann.choose, F.data.startswith("ann:"))
async def ann_toggle(cb: types.CallbackQuery, state: FSMContext):
    _, cid_str, flag = cb.data.split(":")
    cid = int(cid_str)
    data = await state.get_data()
    chosen: set[int] = data.get("choosen", set())
    if flag == "0":
        chosen.add(cid)
        new_flag, mark = "1", "✅"
    else:
        chosen.discard(cid)
        new_flag, mark = "0", "❌"
    await state.update_data(choosen=chosen)

    # меняем подпись кнопки
    await cb.message.edit_reply_markup(
        reply_markup=_rebuild_kb(cb.message.reply_markup, cid, new_flag, mark)
    )
    await cb.answer()

# отправка
@router.callback_query(Ann.choose, F.data == "ann_send")
async def ann_send(cb: types.CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    text = data["text"]
    chats = list(data["choosen"])
    await _broadcast(bot, chats, text, cb.message)
    await state.clear()

# ─── helper: массовая рассылка ─────────────────────
async def _broadcast(bot: Bot, chats: list[int], text: str, origin_msg: types.Message):
    ok = fail = 0
    for cid in chats:
        try:
            await bot.send_message(cid, text, parse_mode="HTML")
            ok += 1
        except Exception:
            fail += 1
    await origin_msg.reply(f"📣 Разослано: {ok}, ошибок: {fail}")

# ─── helper: перестроить инлайн-клаву ──────────────
def _rebuild_kb(markup: types.InlineKeyboardMarkup, cid: int, new_flag:str, mark:str):
    new_rows = []
    for row in markup.inline_keyboard:
        new_row = []
        for btn in row:
            if btn.callback_data and btn.callback_data.startswith(f"ann:{cid}:"):
                title = btn.text[2:].strip()        # отрезаем старый ❌/✅
                new_row.append(
                    types.InlineKeyboardButton(
                        text=f"{mark} {title}",
                        callback_data=f"ann:{cid}:{new_flag}"
                    )
                )
            else:
                new_row.append(btn)
        new_rows.append(new_row)
    return types.InlineKeyboardMarkup(inline_keyboard=new_rows)

# ───────────── Команда /debug ─────────────
@router.message(Command("debug"))
async def debug_cmd(message: types.Message):
    cid, uid = await cid_uid(message)
    prog = await get_progress(cid, uid)
    if not prog:
        return await message.reply("❌ Не найдена запись в progress_local")

    lines = [f"<b>{k}:</b> {v}" for k, v in prog.items()]
    await message.reply("\n".join(lines), parse_mode="HTML")

# ───────────── Команда /photoid ─────────────
@router.message(Command("fileid"))
async def fileid_cmd(m: types.Message):
    if m.reply_to_message and m.reply_to_message.photo:
        await m.reply(str(m.reply_to_message.photo[-1].file_id))
    else:
        await m.reply("Ответь на фото.")

@router.message(Command("devinfo"))
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

@router.message(Command("flush_timers"))
async def flush_timers_cmd(msg: types.Message):
    if msg.from_user.id not in ADMINS:
        return await msg.reply("⛔ Только админ.")

    # чистим просроченные
    n1 = await db.execute(
        """UPDATE progress_local
              SET mining_end = NULL
            WHERE mining_end IS NOT NULL
              AND mining_end < NOW()"""
    )
    n2 = await db.execute(
        """UPDATE progress_local
              SET smelt_end = NULL
            WHERE smelt_end IS NOT NULL
              AND smelt_end < NOW()"""
    )
    await msg.reply(f"🧹 Сброшено: копка {n1.rowcount}, плавка {n2.rowcount}")

# ───────────── Команда /forcepick ─────────────
@router.message(Command("forcepick"))
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

AFK_FINE = 300      # 💰 аренда кирки
AFK_DAYS  = 1                              # ⏳ сколько дней без копки — AFK
AFK_TEXT  = (
    "<b>🏴‍☠️ Доска должников AFK-шахтёров!</b>\n"
    "Следующие граждане забыли про кирку и туннели:\n\n"
    "{mentions}\n\n"
    "Вы либо копаете, либо оплачиваете уборку своего хлама! 💸"
)

@router.message(Command("notify_afk"))
async def notify_afk_cmd(message: types.Message):
    # ─── доступ тільки адмінам ────────────────────────────────
    if message.from_user.id not in ADMINS:
        return await message.reply("⛔️ Только разработчикам")

    cid = message.chat.id
    cutoff = dt.date.today() - dt.timedelta(days=AFK_DAYS)
    # ─── берем список всех «заснувших» ───────────────────────

    rows = await db.fetch_all(
        """
        SELECT user_id
          FROM progress_local
         WHERE chat_id = :c
           AND (last_mine_day IS NULL OR last_mine_day < :cutoff)
        """,
        {"c": cid, "cutoff": cutoff}
    )

    if not rows:
        return await message.reply("Все шахтёры активны! ✨")

    # формируем @упоминания
    mentions = []
    for r in rows:
        try:
            member = await message.bot.get_chat_member(cid, r["user_id"])
            m = member.user
            mention = f"@{m.username}" if m.username else f'<a href="tg://user?id={m.id}">{m.full_name}</a>'
            mentions.append(mention)
        except Exception:
            # пользователь покинул чат или скрыт — просто uid
            mentions.append(f"ID <code>{r['user_id']}</code>")

        await add_money(cid, r["user_id"], -AFK_FINE)  # штрафуем

        txt = (
            AFK_TEXT.format(mentions=" • ".join(mentions)) +
            f"\n\n💸 <b>Штраф</b>: −{AFK_FINE} монет каждому бездельнику."
        )
        msg = await message.answer(txt, parse_mode="HTML", disable_web_page_preview=True)
        register_msg_for_autodelete(cid, msg.message_id)


@router.message(Command("premium_emoji"))
async def premium_emoji_cmd(message: types.Message):
    # ─── доступ тільки адмінам ────────────────────────────────
    if message.from_user.id not in ADMINS:
        return await message.reply("⛔️ Только разработчикам")
    cid = message.chat.id
    text      = " че за нахуй"                 # ← в тексте ставим любой placeholder
    emoji_id  = "5837208434730077905"   # ID, который ты сохранил раньше

    await message.answer(
        text,
        entities=[{
            "type": "custom_emoji",
            "offset": 0,
            "length": 1,             # ровно один символ-заглушка
            "custom_emoji_id": emoji_id
        }]
    )