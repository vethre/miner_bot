from aiogram import Router, types, F, Bot
from aiogram.filters import Command
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from typing import Optional
from datetime import datetime

from bot.db_local import cid_uid, get_money, add_money, add_item, get_progress, db
from bot.handlers.cases import give_case_to_user
from bot.handlers.cave_clash import add_clash_points
from bot.handlers.items import ITEM_DEFS
from bot.handlers.use import PICKAXES
from bot.utils.autodelete import register_msg_for_autodelete
from bot.assets import SHOP_IMG_ID

router = Router()
class ShopBuy(StatesGroup):
    waiting_for_qty = State()

# ---------- каталог ----------
SHOP_ITEMS: dict[str, dict] = {
    "wood_handle":    {"price": 1,  "name": "Рукоять",          "emoji": "🪵"},
    "wax":            {"price": 1,  "name": "Воск",            "emoji": "🍯"},
    "bread":          {"price": 1,   "name": "Хлеб",             "emoji": "🍞"},
    "meat":           {"price": 1,  "name": "Мясо",             "emoji": "🍖"},
    "borsch":         {"price": 1,  "name": "Борщ",             "emoji": "🥣"},
    "energy_drink":   {"price": 1,  "name": "Энергетик",        "emoji": "🥤"},
    "coffee":         {"price": 1,  "name": "Кофе",             "emoji": "☕"},
    "cave_cases":     {"price": 1,  "name": "Cave Case",        "emoji": "📦"},
    "bomb":           {"price": 1, "name": "Бомба",           "emoji": "💣"}
}
MIN_PRICE = 1
CHUNK = 5
ITEM_IDS = list(SHOP_ITEMS.keys())
PAGES = [ITEM_IDS[i:i+CHUNK] for i in range(0, len(ITEM_IDS), CHUNK)]

def max_page() -> int:
    return len(PAGES) - 1

def get_discount_multiplier() -> float:
    wd = datetime.utcnow().weekday()
    if wd == 4:      # Friday
        return 0.8
    if wd == 5:
        return 0.6
    if wd == 6:      # Sunday
        return 0.45
    return 1.0

def calc_price(item_id: str, base: int, *, has_sale: bool) -> tuple[int, str]:
    if item_id in PICKAXES:
        return base, f"{base} мон."
    mult = get_discount_multiplier() * (0.8 if has_sale else 1.0)
    final = max(MIN_PRICE, int(base * mult))
    label = f"{final} мон."
    if mult < 1.0:
        label += f" (−{int((1 - mult)*100)} %)"
    return final, label

def calc_tax(balance: int) -> tuple[float, str]:
    if balance > 100_000:
        return 1.0, "+0%"
    elif balance > 50_000:
        return 1.0, "+0%"
    elif balance > 25_000:
        return 1.0, "+15%"
    elif balance > 10_000:
        return 1.0, "+0%"
    return 1.0, "0%"

async def _send_shop_page(
    chat_id: int,
    *,
    page: int,
    bot_message: types.Message,
    user_id: Optional[int] = None,
    edit: bool = True,
):
    uid = user_id or bot_message.from_user.id
    prog = await get_progress(chat_id, uid)
    has_sale = prog.get("sale_voucher", False)
    balance = await get_money(chat_id, uid)

    kb = InlineKeyboardBuilder()
    for iid in PAGES[page]:
        meta = SHOP_ITEMS[iid]
        base_price, _ = calc_price(iid, meta["price"], has_sale=has_sale)
        tax_mult, tax_label = calc_tax(balance)
        final = max(MIN_PRICE, int(base_price * tax_mult))
        kb.button(
            text=f"{meta['emoji']} {meta['name']} — {final} мон. (Налог {tax_label})",
            callback_data=f"buy:{iid}:{uid}"
        )
    kb.adjust(1)

    nav = InlineKeyboardBuilder()
    if page > 0:
        nav.button(text="« Назад", callback_data=f"shop:pg:{page-1}")
    nav.button(text=f"{page+1}/{len(PAGES)}", callback_data="noop")
    if page < len(PAGES)-1:
        nav.button(text="Вперёд »", callback_data=f"shop:pg:{page+1}")
    nav_buttons_list = list(nav.buttons)
    nav.adjust(len(nav_buttons_list))
    kb.row(*nav_buttons_list)

    if edit:
        msg = await bot_message.edit_reply_markup(reply_markup=kb.as_markup())
    else:
        msg = await bot_message.answer_photo(
            photo=SHOP_IMG_ID,
            caption="🛒 <b>Магазин</b> — выбери товар:",
            parse_mode="HTML",
            reply_markup=kb.as_markup()
        )

    register_msg_for_autodelete(chat_id, msg.message_id)

# ------------------------- Хендлеры -------------------------

@router.message(Command("shop"))
async def shop_cmd(message: types.Message):
    await _send_shop_page(
        chat_id=message.chat.id,
        page=0,
        bot_message=message,
        user_id=message.from_user.id,
        edit=False
    )

@router.callback_query(F.data.startswith("shop:pg:"))
async def shop_pagination(callback: CallbackQuery):
    await callback.answer()
    _, _, page_str = callback.data.split(":")
    await _send_shop_page(
        chat_id=callback.message.chat.id,
        page=int(page_str),
        bot_message=callback.message,
        user_id=callback.from_user.id,
        edit=True
    )

@router.callback_query(F.data == "noop")
async def noop_cb(callback: CallbackQuery):
    await callback.answer()

@router.callback_query(F.data.startswith("buy:"))
async def shop_buy_callback(cb: CallbackQuery):
    await cb.answer()
    try:
        _, item_id, orig_uid = cb.data.split(":")
    except ValueError:
        return
    cid, uid = cb.message.chat.id, cb.from_user.id
    if uid != int(orig_uid):
        return await cb.answer("Эта кнопка не для тебя 😠", show_alert=True)
    meta = SHOP_ITEMS.get(item_id)
    if not meta:
        return await cb.answer("Товар не найден 😕", show_alert=True)

    # Клавиатура выбора количества
    kb = InlineKeyboardBuilder()
    for qty in [1, 5, 10, 25, 50]:
        kb.button(
            text=f"Купить ×{qty}",
            callback_data=f"buyqty:{item_id}:{orig_uid}:{qty}"
        )
    kb.button(
        text="Другое количество…",
        callback_data=f"buyqtycustom:{item_id}:{orig_uid}"
    )
    kb.adjust(2)
    await cb.message.reply(
        f"Выбери количество для покупки {meta['emoji']}<b>{meta['name']}</b>:",
        parse_mode="HTML", reply_markup=kb.as_markup()
    )

@router.callback_query(F.data.startswith("buyqty:"))
async def shop_buy_qty_callback(cb: CallbackQuery):
    await cb.answer()
    try:
        _, item_id, orig_uid, qty_str = cb.data.split(":")
        qty = int(qty_str)
    except Exception:
        return
    cid, uid = cb.message.chat.id, cb.from_user.id
    if uid != int(orig_uid):
        return await cb.answer("Эта кнопка не для тебя 😠", show_alert=True)
    meta = SHOP_ITEMS.get(item_id)
    if not meta:
        return await cb.answer("Товар не найден 😕", show_alert=True)
    prog = await get_progress(cid, uid)
    has_sale = prog.get("sale_voucher", False)
    balance = await get_money(cid, uid)
    base_price, _ = calc_price(item_id, meta["price"], has_sale=has_sale)
    tax_mult, tax_label = calc_tax(balance)
    final_price = int(base_price * qty * tax_mult)
    label = f"{final_price} мон. (Налог {tax_label})"
    if balance < final_price:
        return await cb.answer("Недостаточно монет 💸", show_alert=True)
    await add_money(cid, uid, -final_price)
    if item_id == "cave_cases":
        await give_case_to_user(cid, uid, "cave_case", qty)
    else:
        await add_item(cid, uid, item_id, qty)
    if has_sale:
        await db.execute(
            "UPDATE progress_local SET sale_voucher = FALSE WHERE chat_id=:c AND user_id=:u",
            {"c": cid, "u": uid}
        )
    if prog.get("badge_active") == "moneyback":
        cashback = int(meta["price"] * qty * 0.30)
        await add_money(cid, uid, cashback)
        await cb.message.reply(f"💸 Бейдж Монобанк: возвращено {cashback} монет!")
    await cb.message.reply(
        f"✅ Покупка: {meta['emoji']}<b>{meta['name']}</b> ×{qty} за {label}.",
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("buyqtycustom:"))
async def shop_buy_qty_custom_cb(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    try:
        _, item_id, orig_uid = cb.data.split(":")
    except Exception:
        return
    cid, uid = cb.message.chat.id, cb.from_user.id
    if uid != int(orig_uid):
        return await cb.answer("Эта кнопка не для тебя 😠", show_alert=True)
    meta = SHOP_ITEMS.get(item_id)
    if not meta:
        return await cb.answer("Товар не найден 😕", show_alert=True)
    await state.set_state(ShopBuy.waiting_for_qty)
    await state.update_data(item_id=item_id, orig_uid=orig_uid)
    # Ждём ввод количества через reply
    msg = await cb.message.reply(
        f"Введи количество для покупки <b>{meta['emoji']} {meta['name']}</b> (целое число 1–999):",
        parse_mode="HTML"
    )
    register_msg_for_autodelete(cid, msg.message_id)

@router.message(ShopBuy.waiting_for_qty)
async def shop_buy_qty_text(message: types.Message, state: FSMContext):
    cid, uid = await cid_uid(message)
    data = await state.get_data()
    try:
        item_id = data["item_id"]
        orig_uid = int(data["orig_uid"])
    except Exception:
        await state.clear()
        return await message.reply("Произошла ошибка. Попробуй ещё раз через /shop")
    if uid != orig_uid:
        return await message.reply("Это не для тебя 😠")

    meta = SHOP_ITEMS.get(item_id)
    if not meta:
        await state.clear()
        return await message.reply("Товар не найден 😕")

    qty_str = message.text.strip()
    if not qty_str.isdigit() or not (1 <= int(qty_str) <= 999):
        return await message.reply("Введи корректное количество (от 1 до 999)")
    qty = int(qty_str)
    prog = await get_progress(cid, uid)
    has_sale = prog.get("sale_voucher", False)
    balance = await get_money(cid, uid)
    base_price, _ = calc_price(item_id, meta["price"], has_sale=has_sale)
    tax_mult, tax_label = calc_tax(balance)
    final_price = int(base_price * qty * tax_mult)
    label = f"{final_price} мон. (Налог {tax_label})"
    if balance < final_price:
        await state.clear()
        return await message.reply("Недостаточно монет 💸")
    await add_money(cid, uid, -final_price)
    if item_id == "cave_cases":
        await give_case_to_user(cid, uid, "cave_case", qty)
    else:
        await add_item(cid, uid, item_id, qty)
    if has_sale:
        await db.execute(
            "UPDATE progress_local SET sale_voucher = FALSE WHERE chat_id=:c AND user_id=:u",
            {"c": cid, "u": uid}
        )
    if prog.get("badge_active") == "moneyback":
        cashback = int(meta["price"] * qty * 0.30)
        await add_money(cid, uid, cashback)
        await message.reply(f"💸 Бейдж Монобанк: возвращено {cashback} монет!")
    await message.reply(
        f"✅ Покупка: {meta['emoji']}<b>{meta['name']}</b> ×{qty} за {label}.",
        parse_mode="HTML"
    )
    await state.clear()
