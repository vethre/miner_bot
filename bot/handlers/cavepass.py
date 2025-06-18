# bot/handlers/cavepass.py

import datetime as dt
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.db_local import cid_uid, get_progress, add_money, add_item, db, get_money
from bot.handlers.items import ITEM_DEFS

router = Router()

PASS_PRICE_COINS = 1000           # якщо все ж хочете альтернативно за внутрішню валюту
PASS_PRICE_UAH = 1               # реальна ціна в гривнях
PAYMENT_LINK = "https://send.monobank.ua/jar/A8ew2aMM3S"  # замініть на ваш

PASS_DURATION_DAYS = 30
EX_KEY = "crystal_pickaxe"
EX_NAME = "Кристальна кирка"
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
            text=f"💳 Купити за ₴{PASS_PRICE_UAH}",
            url=PAYMENT_LINK
        )
        builder.adjust(1)
        text = (
            "<b>Cave Pass</b> — 30 днів преміальних бонусів:\n"
            f" • Ексклюзивна кирка {EX_EMOJI} <b>{EX_NAME}</b>\n"
            " • ×1.5 XP при копанні\n"
            " • +5 пасивного XP щодня\n\n"
            f"<i>Ціна: {PASS_PRICE_UAH} ₴ (оплата зовні)</i>\n"
            "<i>Після оплати повідомте мені у PM або в групі /activate_pass</i>"
        )
    else:
        days = max(0, (expires.date() - now.date()).days)
        text = (
            "<b>Ваш Cave Pass активний!</b>\n"
            f"Ексклюзивна кирка: {EX_EMOJI} <b>{EX_NAME}</b>\n"
            f"Термін дії залишився: <b>{days} дн.</b>"
        )

    await message.reply(text, parse_mode="HTML", reply_markup=builder.as_markup())

# тільки для адмінів
ADMINS = {700929765, 988127866}

@router.message(Command("activate_pass"))
async def activate_pass_cmd(message: types.Message):
    if message.from_user.id not in ADMINS:
        return await message.reply("⚠️ У вас немає прав")
    parts = message.text.split()
    if len(parts) != 2:
        return await message.reply("Використання: /activate_pass <user_id або @username>")
    target = parts[1]
    # знайдемо uid
    if target.startswith("@"):
        try:
            member = await message.bot.get_chat_member(message.chat.id, target)
            uid = member.user.id
        except:
            return await message.reply("Користувача не знайдено")
    else:
        if not target.isdigit():
            return await message.reply("Невірний формат")
        uid = int(target)

    cid = message.chat.id if message.chat.type in ("group","supergroup") else 0
    now = dt.datetime.utcnow()
    exp = now + dt.timedelta(days=PASS_DURATION_DAYS)

    # списувати внутрішню валюту не будемо, тільки активуємо
    await db.execute(
        """
        UPDATE progress_local
           SET cave_pass = TRUE,
               pass_expires = :exp,
               current_pickaxe = :pick,
               pick_dur = pick_dur_max
         WHERE chat_id=:c AND user_id=:u
        """,
        {"exp": exp, "pick": EX_KEY, "c": cid, "u": uid}
    )
    # на всякий випадок гарантовано додамо кирку
    await db.execute(
        """
        INSERT INTO inventory_local(chat_id,user_id,item,qty)
             VALUES(:c,:u,:pick,1)
           ON CONFLICT DO NOTHING
        """,
        {"c": cid, "u": uid, "pick": EX_KEY}
    )

    await message.reply(
        f"✅ Cave Pass активовано для user_id={uid} до {exp.date()}",
        parse_mode="HTML"
    )
