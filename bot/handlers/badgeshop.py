import json
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot.assets import BADGESHOP_IMG_ID
from bot.db_local import cid_uid, get_progress, get_money, add_money, db
from bot.handlers.badge_defs import BADGES
from bot.utils.autodelete import register_msg_for_autodelete

router = Router()

BADGE_PRICES = {
    "recruit": 1750,
    "cashback": 2300,
    "moneyback": 4500,
}

BADGES_PER_PAGE = 3
BADGE_IDS = list(BADGES.keys())
PAGES = [BADGE_IDS[i:i + BADGES_PER_PAGE] for i in range(0, len(BADGE_IDS), BADGES_PER_PAGE)]

# ────────── Вивід сторінки ──────────
async def _send_badgeshop(chat_id: int, user_id: int, page: int, bot_message: types.Message, edit=True):
    prog = await get_progress(chat_id, user_id)
    owned = set(prog.get("badges_owned") or [])
    balance = await get_money(chat_id, user_id)

    badge_ids = PAGES[page]
    kb = InlineKeyboardBuilder()
    lines = ["🏬 <b>Бейдж-Магазин:</b>\n"]

    for badge_id in badge_ids:
        badge = BADGES[badge_id]
        price = BADGE_PRICES.get(badge_id)
        is_owned = badge_id in owned

        if price is None:
            lines.append(f"🪧 {badge['emoji']} <b>{badge['name']}</b> — Только в Pass")
            continue

        status = "✅ Куплено" if is_owned else f"{price} монет"
        lines.append(f"{badge['emoji']} <b>{badge['name']}</b> — {status}")

        if not is_owned:
            kb.button(text=f"{badge['emoji']} {badge['name']} - {price}", callback_data=f"badgeshop:buy:{badge_id}")

    # навігація
    kb.adjust(1)
    nav = InlineKeyboardBuilder()
    if page > 0:
        nav.button(text="« Назад", callback_data=f"badgeshop:pg:{page-1}")
    nav.button(text=f"{page+1}/{len(PAGES)}", callback_data="noop")
    if page < len(PAGES)-1:
        nav.button(text="Вперёд »", callback_data=f"badgeshop:pg:{page+1}")

    kb.row(*nav.buttons)
    kb.button(text="◀ Назад", callback_data=f"profile:badges:{user_id}")

    text = "\n".join(lines)
    if edit:
        await bot_message.edit_text(text, parse_mode="HTML", reply_markup=kb.as_markup())
    else:
        msg = await bot_message.answer_photo(
            BADGESHOP_IMG_ID,
            caption=text,
            parse_mode="HTML",
            reply_markup=kb.as_markup()
        )
        register_msg_for_autodelete(chat_id, msg.message_id)

# ────────── Команда /badgeshop ──────────
@router.message(Command("badgeshop"))
async def badgeshop_cmd(message: types.Message):
    cid, uid = await cid_uid(message)
    await _send_badgeshop(cid, uid, page=0, bot_message=message, edit=False)

# ────────── Пагінація ──────────
@router.callback_query(F.data.startswith("badgeshop:pg:"))
async def badgeshop_page(callback: CallbackQuery):
    await callback.answer()
    _, _, page_str = callback.data.split(":")
    cid, uid = callback.message.chat.id, callback.from_user.id
    await _send_badgeshop(cid, uid, int(page_str), callback.message, edit=True)

# ────────── Покупка бейджа ──────────
@router.callback_query(F.data.startswith("badgeshop:buy:"))
async def badgeshop_buy(callback: CallbackQuery):
    await callback.answer()
    cid, uid = callback.message.chat.id, callback.from_user.id
    _, _, badge_id = callback.data.split(":")

    if badge_id not in BADGE_PRICES:
        return await callback.message.reply("Этот бейдж нельзя купить 😶")

    prog = await get_progress(cid, uid)
    row = await db.fetch_one(
        "SELECT badges_owned FROM progress_local WHERE chat_id=:c AND user_id=:u",
        {"c": cid, "u": uid}
    )
    owned = json.loads(row["badges_owned"] or "[]")

    if badge_id in owned:
        return await callback.message.reply("Ты уже купил этот бейдж")

    price = BADGE_PRICES[badge_id]
    balance = await get_money(cid, uid)
    if balance < price:
        return await callback.message.reply("Недостаточно монет 💸")
    
    await add_money(cid, uid, -price)
    if badge_id not in owned:
        owned.append(badge_id)
        await db.execute(
            "UPDATE progress_local SET badges_owned = :val WHERE chat_id=:c AND user_id=:u",
            {"val": json.dumps(owned), "c": cid, "u": uid}
        )

    await callback.message.reply(f"✅ Куплено: {BADGES[badge_id]['emoji']} <b>{BADGES[badge_id]['name']}</b>", parse_mode="HTML")
    await _send_badgeshop(cid, uid, 0, callback.message, edit=True)
