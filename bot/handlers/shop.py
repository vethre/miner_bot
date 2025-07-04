# bot/handlers/shop.py
from aiogram import Router, types, F, Bot
from aiogram.filters import Command
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from itertools import islice
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

# ---------- каталог ----------
SHOP_ITEMS: dict[str, dict] = {
    "wood_handle":    {"price": 80,  "name": "Рукоять",          "emoji": "🪵"},
    "wax":            {"price": 90,  "name": "Воск",            "emoji": "🍯"},
    "bread":          {"price": 40,   "name": "Хлеб",             "emoji": "🍞"},
    "meat":           {"price": 80,  "name": "Мясо",             "emoji": "🍖"},
    "borsch":         {"price": 120,  "name": "Борщ",             "emoji": "🥣"},
    "energy_drink":   {"price": 40,  "name": "Энергетик",        "emoji": "🥤"},
    "coffee":         {"price": 80,  "name": "Кофе",             "emoji": "☕"},
    "cave_cases":     {"price": 300,  "name": "Cave Case",        "emoji": "📦"},
    "bomb":           {"price": 100, "name": "Бомба",           "emoji": "💣"}
}

ITEMS_PER_PAGE = 6 # This variable is not currently used to chunk PAGES.
                   # CHUNK variable below is used. Consider consolidating or clarifying.

# ⬇️ Список ключів-товарів, поділений на сторінки  ---------------------------
CHUNK = 5 # Number of items per page
ITEM_IDS = list(SHOP_ITEMS.keys())
PAGES = [ITEM_IDS[i:i+CHUNK] for i in range(0, len(ITEM_IDS), CHUNK)]
# ---------------------------------------------------------------------------

def max_page() -> int:
    """Returns the index of the last page."""
    return len(PAGES) - 1

def get_discount_multiplier():
    weekday = datetime.utcnow().weekday()
    if weekday == 4:
        return 0.80
    elif weekday == 6:
        return 0.60
    return 1.0

def get_item_price(item_id: str, base_price: int) -> tuple[int, str]:
    discount = get_discount_multiplier()
    if item_id in PICKAXES:
        return base_price, f"{base_price} мон."
    if discount < 1.0:
        discounted = int(base_price * discount)
        return discounted, f"{discounted} мон. (−{int((1 - discount) * 100)}%)"
    return base_price, f"{base_price} мон."

# 🛍 Покращена версія _send_shop_page:
async def _send_shop_page(
    chat_id: int,
    *,
    page: int,
    bot_message: types.Message,
    user_id: Optional[int] = None,
    edit: bool = True
):
    items = PAGES[page]
    kb = InlineKeyboardBuilder()

    # ВАЖЛИВО: використай user_id, або fallback на from_user.id
    uid = user_id or bot_message.from_user.id

    prog = await get_progress(chat_id, uid)
    has_sale = prog.get("sale_voucher", False)

    for iid in items:
        meta = SHOP_ITEMS[iid]
        price_val = int(meta['price'] * (0.8 if has_sale else 1.0))
        price_str = f"{price_val} мон." + (" (−20 %)" if has_sale else "")
        kb.button(
            text=f"{meta['emoji']} {meta['name']} — {price_str}",
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

# ------------------------------------------------------------------ handlers

# Handler for initial /shop command
@router.message(Command("shop"))
async def shop_cmd(message: types.Message):
   await _send_shop_page(
    chat_id=message.chat.id,
    page=0,
    bot_message=message,
    user_id=message.from_user.id,  # ← ключове!
    edit=False
)

# Handler for pagination buttons (e.g., "shop:pg:0", "shop:pg:1")
@router.callback_query(F.data.startswith("shop:pg:"))
async def shop_pagination(callback: CallbackQuery):
    await callback.answer() # Acknowledge the callback query
    _, _, page_str = callback.data.split(":") # Split to get the page number
    await _send_shop_page(
        chat_id=callback.message.chat.id,
        page=int(page_str),
        bot_message=callback.message,
        user_id=callback.from_user.id,  # ← ключове!
        edit=True
    )

# Handler for the "noop" button (e.g., the page number button)
@router.callback_query(F.data == "noop")
async def noop_cb(callback: CallbackQuery):
    """Callback for the non-functional page number button."""
    await callback.answer()

# Handler for "buy" buttons
@router.callback_query(F.data.startswith("buy:"))
async def shop_buy_callback(callback: CallbackQuery):
    await callback.answer() # Acknowledge the callback query
    cid, uid = callback.message.chat.id, callback.from_user.id
    try:
        _, item_id, orig_uid_str = callback.data.split(":")
        orig_uid = int(orig_uid_str)
    except ValueError:
        return await callback.answer("Неверные данные", show_alert=True)

    if uid != orig_uid:
        return await callback.answer("Эта кнопка не для тебя 😠", show_alert=True)

    if (item := SHOP_ITEMS.get(item_id)) is None:
        return await callback.message.reply("Товар не найден 😕")

    has_sale     = prog.get("sale_voucher", False)
    balance = await get_money(cid, uid)
    price_val = int(item["price"] * (0.8 if has_sale else 1.0))
    if balance < price_val:
        return await callback.message.reply("Недостаточно монет 💸")

    await add_money(cid, uid, -price_val) # Deduct price
    if item_id == "cave_cases":
        await give_case_to_user(cid, uid, "cave_case", 1) # Specific logic for "cave_cases"
    else:
        await add_item(cid, uid, item_id, 1) # Add other items to inventory

    prog = await get_progress(cid, uid)
    if has_sale:
       await db.execute("""
           UPDATE progress_local
              SET sale_voucher = FALSE
            WHERE chat_id=:c AND user_id=:u
       """, {"c": cid, "u": uid})

    active_badge = prog.get("badge_active")

    if active_badge == "moneyback":
        cashback = int(item["price"] * 0.3)
        await add_money(cid, uid, cashback)
        await callback.message.reply(f"💸 Бейдж Монобанк активен: возвращено {cashback} монет!")
    await add_clash_points(cid, uid, 0)

    msg = await callback.message.reply(
        f"Покупка: {item['emoji']}<b>{item['name']}</b> за {item['price']} монет ✔️",
        parse_mode="HTML")
    register_msg_for_autodelete(callback.message.chat.id, msg.message_id)
