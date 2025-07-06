# bot/handlers/cavepass.py

import datetime as dt
import json
import logging
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.db_local import cid_uid, get_progress, add_money, add_item, db, get_money
from bot.handlers.items import ITEM_DEFS
from bot.assets import PASS_IMG_ID
from bot.handlers.use import PICKAXES
from bot.utils.unlockachievement import unlock_achievement

router = Router()

PASS_PRICE_COINS = 1000           # якщо все ж хочете альтернативно за внутрішню валюту
PASS_PRICE_UAH = 53               # реальна ціна в гривнях
PAYMENT_LINK = "https://send.monobank.ua/jar/A8ew2aMM3S"  # замініть на ваш

PASS_DURATION_DAYS = 20
EX_KEY = "proto_eonite_pickaxe"
EX_NAME = "Прототип Эонитовой Кирки"
EX_EMOJI = "🧿"
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
            "<b>СКОРО</b> — 7.7.2025\n"
            "<b>Cave Pass</b> — Пробуждение Эонита:\n"
            f" • Эксклюзивная {EX_EMOJI} <b>{EX_NAME}</b>\n"
            " • ×1.5 XP при добывании\n"
            " • +10 пассивного XP каждый час!\n"
            " • Премиальные награды на пути Pass\n"
            f"<i>Цена: {PASS_PRICE_UAH} ₴ (оплата вне)</i>\n"
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
        return await message.reply("⚠️ У вас нет прав")

    parts = message.text.strip().split()
    if len(parts) != 3:
        return await message.reply("Использование: /activate_pass 'user_id' 'chat_id'")

    try:
        uid = int(parts[1])
        cid = int(parts[2])
    except ValueError:
        return await message.reply("❌ user_id и chat_id должны быть числами.")

    pick_key = "crystal_pickaxe"
    if pick_key not in PICKAXES:
        return await message.reply("❌ Кирка не найдена.")

    exp = dt.datetime(2025, 7, 27, 21, 59, 59)
    pick_dur = PICKAXES[pick_key]["dur"]
    dur_map = json.dumps({pick_key: pick_dur})
    dur_max_map = json.dumps({pick_key: pick_dur})

    # Update progress_local table
    await db.execute(
        """
        UPDATE progress_local
           SET cave_pass = TRUE,
               pass_expires = :exp,
               current_pickaxe = :pick,
               pick_dur_map = :dmap,
               pick_dur_max_map = :dmax
         WHERE chat_id = :cid AND user_id = :uid
        """,
        {
            "exp": exp,
            "pick": pick_key,
            "dmap": dur_map,
            "dmax": dur_max_map,
            "cid": cid,
            "uid": uid
        }
    )

    # Update pass_progress table - Set is_premium to TRUE
    await db.execute(
        """
        UPDATE pass_progress
           SET is_premium = TRUE
         WHERE chat_id = :cid AND user_id = :uid
        """,
        {"cid": cid, "uid": uid}
    )

    await db.execute(
        """
        INSERT INTO inventory_local (chat_id, user_id, item, qty)
             VALUES (:cid, :uid, :item, 1)
           ON CONFLICT DO NOTHING
        """,
        {"cid": cid, "uid": uid, "item": pick_key}
    )

    emoji = PICKAXES[pick_key]["emoji"]
    name = PICKAXES[pick_key]["name"]

    await unlock_achievement(cid, uid, "pre_pass")

    await message.reply(
        f"✅ Cave Pass активирован для user_id={uid} в чате {cid} до {exp.date()}\n"
        f"{emoji} Выдана кирка: <b>{name}</b> ({pick_dur}/{pick_dur})",
        parse_mode="HTML"
    )
