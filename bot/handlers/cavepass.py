# bot/handlers/cavepass.py

import datetime as dt
import logging
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.db_local import cid_uid, get_progress, add_money, add_item, db, get_money
from bot.handlers.items import ITEM_DEFS
from bot.assets import PASS_IMG_ID

router = Router()

PASS_PRICE_COINS = 1000           # якщо все ж хочете альтернативно за внутрішню валюту
PASS_PRICE_UAH = 53               # реальна ціна в гривнях
PAYMENT_LINK = "https://send.monobank.ua/jar/A8ew2aMM3S"  # замініть на ваш

PASS_DURATION_DAYS = 19
EX_KEY = "crystal_pickaxe"
EX_NAME = "Хрустальная кирка"
EX_EMOJI = "💎"
ITEM_DEFS[EX_KEY] = {"name": EX_NAME, "emoji": EX_EMOJI}

@router.message(Command("cavepass"))
async def cavepass_cmd(message: types.Message):
    cid, uid = await cid_uid(message)
    prog = await get_progress(cid, uid)
    now = dt.datetime.utcnow()
    expires = prog.get("pass_expires")
    has = prog.get("cave_pass", False)

    builder = InlineKeyboardBuilder()
    if not has or (expires and expires < now):
        # кнопка на зовнішню оплату
        builder.button(
            text=f"💳 Купить за ₴{PASS_PRICE_UAH}",
            url=PAYMENT_LINK
        )
        builder.adjust(1)
        text = (
            "<b><i>[Pre-Season]</i> Cave Pass</b> — 15 дней премиальных бонусов:\n"
            f" • Эксклюзивная {EX_EMOJI} <b>{EX_NAME}</b>\n"
            " • ×1.5 XP при добывании\n"
            " • +10 пассивного XP каждый час!\n"
            f" • <i><b>Примечание:</b> {EX_EMOJI} {EX_NAME} чинится только 1 раз и только наполовину.</i>\n\n"
            f"<i>Цена: {PASS_PRICE_UAH} ₴ (оплата снаружи)</i>\n"
            "<i>После оплаты сообщите мне через /report 'сообщение'</i>"
        )
    else:
        days = max(0, (expires.date() - now.date()).days)
        text = (
            "<b>Ваш Cave Pass активирован!</b>\n"
            f"Эксклюзивная кирка: {EX_EMOJI} <b>{EX_NAME}</b>\n"
            f"Термин действия остался: <b>{days} дн.</b>"
        )
    await message.answer_photo(
        PASS_IMG_ID,
        caption=text,
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )

# тільки для адмінів
ADMINS = {700929765, 988127866}

@router.message(Command("activate_pass"))
async def activate_pass_cmd(message: types.Message):
    if message.from_user.id not in ADMINS:
        return await message.reply("⚠️ У вас нет прав на выполнение этой команды.")

    parts = message.text.split()
    if len(parts) != 3:
        return await message.reply("Использование:\n/activate_pass 'user_id | @username' 'chat_id'")

    target = parts[1]
    try:
        chat_id = int(parts[2])
    except ValueError:
        return await message.reply("❌ Неверный формат chat_id (ожидалось число).")

    # 🔍 Получаем user_id
    if target.startswith("@"):
        try:
            member = await message.bot.get_chat_member(chat_id, target)
            user_id = member.user.id
        except Exception as e:
            logging.warning(f"Не удалось получить юзера: {e}")
            return await message.reply("❌ Пользователь не найден в этом чате.")
    else:
        if not target.isdigit():
            return await message.reply("❌ Неверный формат user_id.")
        user_id = int(target)

    # 🗓️ Устанавливаем даты и кирку
    now = dt.datetime.utcnow()
    expires = dt.datetime(2025, 7, 10, 21, 59, 59)

    # ✅ Обновляем данные в progress_local
    await db.execute(
        """
        UPDATE progress_local
           SET cave_pass = TRUE,
               pass_expires = :exp,
               current_pickaxe = :pick,
               pick_dur = 94,
               pick_dur_max = 95
         WHERE chat_id = :c AND user_id = :u
        """,
        {"exp": expires, "pick": EX_KEY, "c": chat_id, "u": user_id}
    )

    # 🧱 Добавляем кирку в инвентарь (если ещё нет)
    await db.execute(
        """
        INSERT INTO inventory_local(chat_id, user_id, item, qty)
             VALUES(:c, :u, :i, 1)
           ON CONFLICT DO NOTHING
        """,
        {"c": chat_id, "u": user_id, "i": EX_KEY}
    )

    await message.reply(
        f"✅ Cave Pass активирован для <code>{user_id}</code> в чате <code>{chat_id}</code>\n"
        f"Действителен до <b>{expires.strftime('%d.%m.%Y')}</b> ⛏️",
        parse_mode="HTML"
    )

