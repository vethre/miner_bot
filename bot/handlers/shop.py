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

# ─── helpers  ──────────────────────────────────────────────────────────
def get_discount_multiplier() -> float:
    """Пятница −20 %, воскресенье −40 %, иначе без скидки."""
    wd = datetime.utcnow().weekday()        # 0-пон, 4-пт, 6-вс
    if wd == 4:      # Friday
        return 0.8
    if wd == 5:
        return 0.6
    if wd == 6:      # Sunday
        return 0.45
    return 1.0


def calc_price(item_id: str, base: int, *, has_sale: bool) -> tuple[int, str]:
    """Вернёт (число, подпись). Кирки не участвуют в акциях."""
    if item_id in PICKAXES:
        return base, f"{base} мон."

    # ← одна строка: общий множитель = скидка_дня × скидка_ваучера
    mult = get_discount_multiplier() * (0.8 if has_sale else 1.0)

    final = int(base * mult)
    label = f"{final} мон."
    if mult < 1.0:
        label += f" (−{int((1 - mult)*100)} %)"
    return final, label
# ───────────────────────────────────────────────────────────────────────

# 🛍 Покращена версія _send_shop_page:
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

    kb = InlineKeyboardBuilder()
    for iid in PAGES[page]:
        meta = SHOP_ITEMS[iid]
        price_val, price_str = calc_price(iid, meta["price"], has_sale=has_sale)
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
async def shop_buy_callback(cb: CallbackQuery):
    await cb.answer()
    cid, uid = cb.message.chat.id, cb.from_user.id

    # ── разбор callback_data
    try:
        _, item_id, orig_uid = cb.data.split(":")
    except ValueError:
        return
    if uid != int(orig_uid):
        return await cb.answer("Эта кнопка не для тебя 😠", show_alert=True)

    # ── товар в каталоге?
    meta = SHOP_ITEMS.get(item_id)
    if not meta:
        return await cb.answer("Товар не найден 😕", show_alert=True)

    # ── цена с учётом скидок
    prog = await get_progress(cid, uid)
    has_sale = prog.get("sale_voucher", False)
    price_val, price_label = calc_price(item_id, meta["price"], has_sale=has_sale)

    # ── денег хватает?
    if await get_money(cid, uid) < price_val:
        return await cb.answer("Недостаточно монет 💸", show_alert=True)

    # ── списываем деньги
    await add_money(cid, uid, -price_val)

    # ── выдаём товар / кейс
    if item_id == "cave_cases":
        await give_case_to_user(cid, uid, "cave_case", 1)
    else:
        await add_item(cid, uid, item_id, 1)

    # ── одноразовый ваучер отработал → сбрасываем
    if has_sale:
        await db.execute(
            "UPDATE progress_local SET sale_voucher = FALSE "
            "WHERE chat_id=:c AND user_id=:u",
            {"c": cid, "u": uid}
        )

    # ── бейдж «moneyback»
    if prog.get("badge_active") == "moneyback":
        cashback = int(meta["price"] * 0.30)
        await add_money(cid, uid, cashback)
        await cb.message.reply(f"💸 Бейдж Монобанк: возвращено {cashback} монет!")

    # ── +Clash-очки
    await add_clash_points(cid, uid, 0)

    # ── подтверждение пользователю
    confirm = await cb.message.reply(
        f"✅ Покупка: {meta['emoji']}<b>{meta['name']}</b> за {price_val} монет.",
        parse_mode="HTML"
    )
    register_msg_for_autodelete(cid, confirm.message_id)