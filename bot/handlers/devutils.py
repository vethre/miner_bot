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
    wait_media = State()   # ждём шаблон-сообщение
    choose     = State()   # выбираем группы

# ───── утилиты ────────────────────────────────────────────
async def _all_chats() -> list[tuple[int, str]]:
    rows = await db.fetch_all("SELECT chat_id, title FROM groups")
    return [(r["chat_id"], r["title"] or str(r["chat_id"])) for r in rows]

def _rebuild_kb(markup: types.InlineKeyboardMarkup,
                cid: int, flag: str, mark: str):
    """Обновляем одну кнопку ✅/❌ без перестройки всей клавы."""
    new_rows = []
    for row in markup.inline_keyboard:
        new_row = []
        for btn in row:
            if btn.callback_data and btn.callback_data.startswith(f"ann:{cid}:"):
                title = btn.text[2:].strip()
                new_row.append(
                    types.InlineKeyboardButton(
                        text=f"{mark} {title}",
                        callback_data=f"ann:{cid}:{flag}"
                    )
                )
            else:
                new_row.append(btn)
        new_rows.append(new_row)
    return types.InlineKeyboardMarkup(inline_keyboard=new_rows)

# ───── /announce ──────────────────────────────────────────
@router.message(Command("announce"))
async def announce_start(msg: types.Message, state: FSMContext):
    if msg.from_user.id not in ADMINS:
        return await msg.reply("⛔️ Только для разработчика")

    await msg.reply(
        "📢 Пришли ОДНО сообщение-шаблон (текст/картинку/гиф/стикер/emoji).\n"
        "После этого выберешь, куда разослать."
    )
    await state.set_state(Ann.wait_media)

# ───── ловим шаблон-сообщение ─────────────────────────────
@router.message(Ann.wait_media)
async def ann_got_media(msg: types.Message, state: FSMContext):
    # сохраняем chat_id + message_id для copy_message
    await state.update_data(src_chat=msg.chat.id,
                            src_msg=msg.message_id,
                            choosen=set())

    # строим клавиатуру чатов
    kb = InlineKeyboardBuilder()
    for cid, title in await _all_chats():
        kb.button(text=f"❌ {title}", callback_data=f"ann:{cid}:0")
    kb.adjust(1)
    kb.button(text="➡️ Отправить", callback_data="ann_send")

    prompt = await msg.reply(
        "✅ Теперь отметь чаты, куда слать:",
        reply_markup=kb.as_markup()
    )
    register_msg_for_autodelete(prompt.chat.id, prompt.message_id)
    await state.set_state(Ann.choose)

# ───── переключаем ✅/❌ ──────────────────────────────────
@router.callback_query(Ann.choose, F.data.startswith("ann:"))
async def ann_toggle(cb: types.CallbackQuery, state: FSMContext):
    _, cid_str, cur_flag = cb.data.split(":")
    cid = int(cid_str)

    data = await state.get_data()
    chosen: set[int] = data.get("choosen", set())

    if cur_flag == "0":
        chosen.add(cid)
        new_flag, mark = "1", "✅"
    else:
        chosen.discard(cid)
        new_flag, mark = "0", "❌"

    await state.update_data(choosen=chosen)
    await cb.message.edit_reply_markup(
        reply_markup=_rebuild_kb(cb.message.reply_markup,
                                 cid, new_flag, mark)
    )
    await cb.answer()

# ───── отправка ───────────────────────────────────────────
@router.callback_query(Ann.choose, F.data == "ann_send")
async def ann_send(cb: types.CallbackQuery, state: FSMContext, bot: types.Bot):
    data = await state.get_data()
    src_chat = data["src_chat"]
    src_msg  = data["src_msg"]
    chats    = list(data["choosen"])

    ok = fail = 0
    for cid in chats:
        try:
            # copy_message сохраняет оригинальный вид медиа/текста
            await bot.copy_message(cid, src_chat, src_msg)
            ok += 1
        except Exception as e:
            fail += 1
            print(f"[announce] copy to {cid} failed: {e!r}")

    await cb.message.answer(f"📣 Разослано: {ok}, ошибок: {fail}")
    await state.clear()

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

@router.message(Command("emoji_id"))
async def emoji_id_cmd(message: types.Message):
    """
    1️⃣ Перешлите/напишите сообщение c premium-эмодзи и добавьте /emoji_id
       (можно в том же сообщении, можно ответом).
    2️⃣ Бот вернёт список найденных custom_emoji_id.
    """
    # Если команда пришла реплаем – анализируем reply-сообщение.
    target_msg = message.reply_to_message or message

    ids: list[str] = []
    if target_msg.entities:
        for ent in target_msg.entities:
            if ent.type == "custom_emoji":
                ids.append(ent.custom_emoji_id)

    if not ids:
        return await message.reply("❌ В этом сообщении нет premium-эмодзи")

    txt = "🔎 Найдено custom_emoji_id:\n" + "\n".join(f"`{e}`" for e in ids)
    await message.reply(txt, parse_mode="Markdown")
    
@router.message(Command("run_season_now"))
async def run_season_now(message: types.Message):
    if message.from_user.id not in ADMINS:
        return await message.reply("⛔ Нет прав")
    from bot.handlers.cave_clash import _season_job
    await _season_job(message.bot)
    await message.reply("🔁 Clash сезон пересчитан.")
    
@router.message(Command("force_clash_reset"))
async def force_clash_reset(message: types.Message):
    if message.chat.type != "supergroup":
        return await message.reply("⚠️ Только в группах.")

    if message.from_user.id not in ADMINS:
        return await message.reply("❌ Нет прав")

    from bot.handlers.cave_clash import _process_chat
    await _process_chat(message.bot, message.chat.id)
    await message.reply("✅ Clash Rewards вручную выданы.")

TECH_PAUSE_KEY = "tech_pause"
DEFAULT_ALLOWED_CHAT = -1001987529426               # чат, где бот «живой» даже в паузе


async def _is_paused() -> bool:
    row = await db.fetch_one("SELECT value FROM bot_flags WHERE key=:k",
                             {"k": TECH_PAUSE_KEY})
    return bool(row and row["value"])


async def _set_pause(flag: bool):
    await db.execute("""
        INSERT INTO bot_flags(key,value) VALUES(:k,:v)
        ON CONFLICT (key) DO UPDATE SET value=:v
    """, {"k": TECH_PAUSE_KEY, "v": flag})


@router.message(Command("techpause"))
async def techpause_cmd(msg: types.Message):
    if msg.from_user.id not in ADMINS:
        return
    args = msg.text.split(maxsplit=1)
    if len(args) != 2 or args[1] not in ("on", "off"):
        return await msg.reply("Использование: <code>/techpause on|off</code>",
                               parse_mode="HTML")

    flag = args[1] == "on"
    await _set_pause(flag)
    await msg.reply("🛠 Тех-режим: ВКЛ" if flag else "✅ Тех-режим снят")


# ───────────────────── middleware “глушилка” ──────────────────────
from aiogram import BaseMiddleware
from typing import Dict, Any, Callable, Awaitable


class TechPauseMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[types.TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: types.TelegramObject,
        data: Dict[str, Any]
    ):
        # пропускаем апдейты, которые не являются сообщениями/колбэками
        chat_id = None
        if isinstance(event, types.Message):
            chat_id = event.chat.id
        elif isinstance(event, types.CallbackQuery):
            chat_id = event.message.chat.id

        if chat_id is None:
            return await handler(event, data)

        if await _is_paused() and chat_id != DEFAULT_ALLOWED_CHAT:
            # отвечаем тем, кто пишет
            if isinstance(event, types.Message):
                await event.reply("🔧 Бот на техническом перерыве. Попробуйте позже.")
            elif isinstance(event, types.CallbackQuery):
                await event.answer("🔧 Тех. перерыв – попробуйте позже", show_alert=True)
            return  # глушим остальные хендлеры

        return await handler(event, data)