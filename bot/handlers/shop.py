<<<<<<< HEAD
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.db_local import cid_uid, get_money, add_money, add_item
from bot.handlers.items import ITEM_DEFS

router = Router()

# Список товарів у магазині
SHOP_ITEMS = {
    "wood_handle":    {"price": 100,  "name": "Рукоять",         "emoji": "🪵"},
    "wooden_pickaxe": {"price": 200,  "name": "Дерев’яна кирка", "emoji": "🔨"},
    "iron_pickaxe":   {"price": 1000, "name": "Залізна кирка",   "emoji": "⛏️"},
    "gold_pickaxe":   {"price": 2000, "name": "Золота кирка",    "emoji": "✨"},
    "bread":          {"price": 50,   "name": "Хліб",            "emoji": "🍞", "hunger": 30},
    "meat":           {"price": 120,  "name": "М’ясо",           "emoji": "🍖", "hunger": 60},
=======
# bot/handlers/shop.py
from aiogram import Router, types, F, Bot
from aiogram.filters import Command
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from itertools import islice

from bot.db_local import cid_uid, get_money, add_money, add_item
from bot.handlers.cases import give_case_to_user
from bot.handlers.items import ITEM_DEFS
from bot.utils.autodelete import register_msg_for_autodelete
from bot.assets import SHOP_IMG_ID # Ensure this path is correct for your project

router = Router()

# ---------- каталог ----------
SHOP_ITEMS: dict[str, dict] = {
    "wood_handle":    {"price": 100,  "name": "Рукоять",          "emoji": "🪵"},
    "wooden_pickaxe": {"price": 200,  "name": "Деревянная кирка", "emoji": "🔨"},
    "iron_pickaxe":   {"price": 1000, "name": "Железная кирка",   "emoji": "⛏️"},
    "gold_pickaxe":   {"price": 2000, "name": "Золотая кирка",    "emoji": "✨"},
    "torch_bundle":   {"price": 150,  "name": "Факел",            "emoji": "🕯️"},
    "bread":          {"price": 50,   "name": "Хлеб",             "emoji": "🍞"},
    "meat":           {"price": 120,  "name": "Мясо",             "emoji": "🍖"},
    "borsch":         {"price": 300,  "name": "Борщ",             "emoji": "🥣"},
    "energy_drink":   {"price": 170,  "name": "Энергетик",        "emoji": "🥤"},
    "cave_cases":     {"price": 300,  "name": "Cave Case",        "emoji": "📦"},
>>>>>>> core-2.0
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


async def _send_shop_page(chat_id: int, *, page: int,
                          bot_message: types.Message,
                          edit: bool = True):
    """
    Sends or edits the shop page message with inline keyboard.
    :param chat_id: The ID of the chat.
    :param page: The current page number (0-indexed).
    :param bot_message: The message object to edit or reply to.
    :param edit: If True, edits the message; otherwise, sends a new one.
    """
    items = PAGES[page] # Get items for the current page
    kb = InlineKeyboardBuilder() # Keyboard for shop items

    for iid in items:
        meta = SHOP_ITEMS[iid]
        kb.button(
            text=f"{meta['emoji']} {meta['name']} — {meta['price']} мон.",
            callback_data=f"buy:{iid}"
        )
    kb.adjust(1) # Display each shop item button on its own row

    # Навігація (Pagination) keyboard
    nav = InlineKeyboardBuilder()
    if page > 0:
        nav.button(text="« Назад", callback_data=f"shop:pg:{page-1}") # Corrected callback data
    nav.button(text=f"{page+1}/{len(PAGES)}", callback_data="noop") # Page number display
    if page < len(PAGES)-1:
        nav.button(text="Вперёд »", callback_data=f"shop:pg:{page+1}") # Corrected callback data

    # Convert nav.buttons generator to a list to get its length and use with kb.row()
    nav_buttons_list = list(nav.buttons)
    nav.adjust(len(nav_buttons_list)) # Place all navigation buttons in a single row
    kb.row(*nav_buttons_list) # Add the navigation row to the main keyboard

    if edit:
        await bot_message.edit_reply_markup(reply_markup=kb.as_markup())
    else:
        await bot_message.answer_photo(
            photo=SHOP_IMG_ID,
            caption="🛒 <b>Магазин</b> — выбери товар:",
            parse_mode="HTML",
            reply_markup=kb.as_markup()
        )

# ------------------------------------------------------------------ handlers

# Handler for initial /shop command
@router.message(Command("shop"))
<<<<<<< HEAD
async def shop_cmd(message: types.Message, owner_id: int | None = None):
    cid, uid = await cid_uid(message)
    orig_uid = owner_id or message.from_user.id

    builder = InlineKeyboardBuilder()
    for item_id, props in SHOP_ITEMS.items():
        text = f"{props['emoji']} {props['name']} — {props['price']} монет"
        builder.button(text=text, callback_data=f"buy:{item_id}:{orig_uid}")
    builder.adjust(1)

    await message.reply(
        "🛒 <b>Магазин</b> — обери товар:",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
=======
async def shop_cmd(message: types.Message):
    await _send_shop_page(message.chat.id, page=0, bot_message=message, edit=False)

# Handler for pagination buttons (e.g., "shop:pg:0", "shop:pg:1")
@router.callback_query(F.data.startswith("shop:pg:"))
async def shop_pagination(callback: CallbackQuery):
    await callback.answer() # Acknowledge the callback query
    _, _, page_str = callback.data.split(":") # Split to get the page number
    await _send_shop_page(callback.message.chat.id,
                          page=int(page_str),
                          bot_message=callback.message,
                          edit=True)

# Handler for the "noop" button (e.g., the page number button)
@router.callback_query(F.data == "noop")
async def noop_cb(callback: CallbackQuery):
    """Callback for the non-functional page number button."""
    await callback.answer()
>>>>>>> core-2.0

# Handler for "buy" buttons
@router.callback_query(F.data.startswith("buy:"))
async def shop_buy_callback(callback: CallbackQuery):
<<<<<<< HEAD
    await callback.answer()
    data = callback.data.split(":", 2)
    if len(data) != 3:
        return
    _, item_id, orig_uid = data
    orig_uid = int(orig_uid)
    """if callback.from_user.id != orig_uid:
        return await callback.answer("Ця кнопка не для тебе", show_alert=True)"""

    cid = callback.message.chat.id
    balance = await get_money(cid, orig_uid)
    item = SHOP_ITEMS.get(item_id)
    if not item:
        return await callback.message.reply("Товар не знайдено 😕")
    price = item["price"]
    if balance < price:
        return await callback.message.reply("Недостатньо монет 💸")

    await add_money(cid, orig_uid, -price)
    await add_item(cid, orig_uid, item_id, 1)

    await callback.message.reply(
        f"Ти придбав {item['emoji']}<b>{item['name']}</b> за {price} монет! 🎉",
        parse_mode="HTML"
    )
=======
    await callback.answer() # Acknowledge the callback query
    cid, uid = callback.message.chat.id, callback.from_user.id
    _, item_id = callback.data.split(":", 1) # Split to get the item ID

    if (item := SHOP_ITEMS.get(item_id)) is None:
        return await callback.message.reply("Товар не найден 😕")

    balance = await get_money(cid, uid)
    if balance < item["price"]:
        return await callback.message.reply("Недостаточно монет 💸")

    await add_money(cid, uid, -item["price"]) # Deduct price
    if item_id == "cave_cases":
        await give_case_to_user(cid, uid, 1) # Specific logic for "cave_cases"
    else:
        await add_item(cid, uid, item_id, 1) # Add other items to inventory

    msg = await callback.message.reply(
        f"Покупка: {item['emoji']}<b>{item['name']}</b> за {item['price']} монет ✔️",
        parse_mode="HTML")
    register_msg_for_autodelete(callback.message.chat.id, msg.message_id)
>>>>>>> core-2.0
