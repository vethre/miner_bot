# bot/handlers/shop.py
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.db_local import cid_uid, get_money, add_money, add_item
from bot.handlers.items import ITEM_DEFS
from bot.handlers.cases import give_case_to_user
from bot.assets import SHOP_IMG_ID
from bot.utils.autodelete import register_msg_for_autodelete

router = Router()

###############################################################################
#  ТОВАРЫ  #####################################################################
###############################################################################

SHOP_ITEMS = {
    "wood_handle":     {"price": 100,  "name": "Рукоять",          "emoji": "🪵"},
    "wooden_pickaxe":  {"price": 200,  "name": "Деревяная кирка",  "emoji": "🔨"},
    "iron_pickaxe":    {"price": 1000, "name": "Железная кирка",   "emoji": "⛏️"},
    "gold_pickaxe":    {"price": 2000, "name": "Золотая кирка",    "emoji": "✨"},
    "torch_bundle":    {"price": 150,  "name": "Факел",            "emoji": "🕯️"},
    "bread":           {"price": 50,   "name": "Хлеб",             "emoji": "🍞", "hunger": 20},
    "meat":            {"price": 120,  "name": "Мясо",             "emoji": "🍖", "hunger": 50},
    "borsch":          {"price": 300,  "name": "Борщ",             "emoji": "🥣", "hunger": 100},
    "energy_drink":    {"price": 170,  "name": "Энергетик",        "emoji": "🥤", "energy": 40},
    "cave_cases":      {"price": 300,  "name": "Cave Case",        "emoji": "📦"},
}

ALL_ITEMS = list(SHOP_ITEMS.keys())            # фиксированный порядок
PAGE_SIZE = 6                                  # сколько позиций на страницу

def items_on_page(page: int):
    start = page * PAGE_SIZE
    return ALL_ITEMS[start : start + PAGE_SIZE]

def max_page():
    return (len(ALL_ITEMS) - 1) // PAGE_SIZE   # 0-based

###############################################################################
#  ВИТРИНА  ####################################################################
###############################################################################

async def _send_shop_page(chat_id: int,
                          page: int,
                          bot_message: types.Message | None,
                          *,
                          edit: bool):
    page = max(0, min(page, max_page()))       # clamp
    kb = InlineKeyboardBuilder()

    # сами товары
    for item_id in items_on_page(page):
        p = SHOP_ITEMS[item_id]
        kb.button(
            text=f"{p['emoji']} {p['name']} — {p['price']} монет",
            callback_data=f"buy:{item_id}"
        )
    kb.adjust(1)

    # —— навигация ————————————————————————————
    nav = []
    if page > 0:
        nav.append(types.InlineKeyboardButton("⬅️", callback_data=f"shop_page:{page-1}"))
    nav.append(types.InlineKeyboardButton(f"{page+1}/{max_page()+1}", callback_data="noop"))
    if page < max_page():
        nav.append(types.InlineKeyboardButton("➡️", callback_data=f"shop_page:{page+1}"))
    kb.row(*nav)

    if edit and bot_message:                   # листаем
        await bot_message.edit_reply_markup(kb.as_markup())
    else:                                      # первая страница
        out = await bot_message.answer_photo(
            SHOP_IMG_ID,
            "🛒 <b>Магазин</b> — листай страницы:",
            parse_mode="HTML",
            reply_markup=kb.as_markup()
        )
        register_msg_for_autodelete(chat_id, out.message_id)

###############################################################################
#  /shop  #####################################################################
###############################################################################

@router.message(Command("shop"))
async def shop_cmd(message: types.Message):
    await _send_shop_page(message.chat.id, page=0, bot_message=message, edit=False)

@router.callback_query(F.data.startswith("shop_page:"))
async def shop_page_cb(cb: CallbackQuery):
    _, page_str = cb.data.split(":")
    await _send_shop_page(cb.message.chat.id, int(page_str), cb.message, edit=True)
    await cb.answer()

###############################################################################
#  ПОКУПКА  ####################################################################
###############################################################################

@router.callback_query(F.data.startswith("buy:"))
async def shop_buy_callback(callback: CallbackQuery):
    await callback.answer()
    cid, uid = callback.message.chat.id, callback.from_user.id
    _, item_id = callback.data.split(":", 1)

    item = SHOP_ITEMS.get(item_id)
    if not item:
        return await callback.message.reply("Товар не найден 😕")

    balance = await get_money(cid, uid)
    if balance < item["price"]:
        return await callback.message.reply("Недостаточно монет 💸")

    await add_money(cid, uid, -item["price"])
    if item_id == "cave_cases":
        await give_case_to_user(cid, uid, 1)
    else:
        await add_item(cid, uid, item_id, 1)

    msg = await callback.message.reply(
        f"Ты купил {item['emoji']}<b>{item['name']}</b> за {item['price']} монет! 🎉",
        parse_mode="HTML"
    )
    register_msg_for_autodelete(callback.message.chat.id, msg.message_id)
