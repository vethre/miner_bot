# bot/handlers/shop.py
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.db_local import cid_uid, get_money, add_money, add_item
from bot.handlers.cases import give_case_to_user
from bot.handlers.items import ITEM_DEFS
from bot.utils.autodelete import register_msg_for_autodelete
from bot.assets import SHOP_IMG_ID

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
}

PER_PAGE = 6
PAGES = list(                 # список списків id-товарів посторінково
    [k for k, _ in chunk]
    for chunk in (zip(*[iter(SHOP_ITEMS.items())]*PER_PAGE),)
)
# альтернативний підрахунок:
def max_page() -> int:
    return (len(SHOP_ITEMS) - 1) // PER_PAGE


# ------------------------------------------------------------------ helpers
async def _send_shop_page(chat_id: int, *, page: int,
                          bot_message: types.Message | None = None,
                          edit: bool = False):
    """Формуємо й відправляємо сторінку магазину."""
    start = page * PER_PAGE
    chunk = list(SHOP_ITEMS.items())[start:start + PER_PAGE]

    kb = InlineKeyboardBuilder()
    for item_id, props in chunk:
        kb.button(
            text=f"{props['emoji']} {props['name']} — {props['price']} монет",
            callback_data=f"buy:{item_id}"
        )
    kb.adjust(1)                           # кожна позиція в окремому рядку

    # ─── навігація ─────────────────────────────────────────────────────────
    nav = InlineKeyboardBuilder()
    if page > 0:
        nav.button(text="⬅️", callback_data=f"shop:page:{page-1}")
    # Лічильник сторінок (неактивна кнопка)
    nav.button(text=f"{page+1}/{max_page()+1}", callback_data="noop")
    if page < max_page():
        nav.button(text="➡️", callback_data=f"shop:page:{page+1}")
    nav.adjust(len(nav.buttons))           # у ряд один за одним

    # прикріпляємо нав-кнопки до основного builder
    kb.row(*nav.buttons)

    if edit and bot_message:               # редагуємо старе
        await bot_message.edit_reply_markup(reply_markup=kb.as_markup())
    else:                                  # або шлемо нове
        sent = await bot.send_photo(
            chat_id,
            SHOP_IMG_ID,
            caption="🛒 <b>Магазин</b> — выбери товар:",
            parse_mode="HTML",
            reply_markup=kb.as_markup()
        )
        register_msg_for_autodelete(chat_id, sent.message_id)

# ------------------------------------------------------------------ handlers
@router.message(Command("shop"))
async def shop_cmd(message: types.Message):
    await _send_shop_page(message.chat.id, page=0, bot_message=message, edit=False)

# перегортання сторінок
@router.callback_query(F.data.startswith("shop:pg:"))
async def shop_pagination(callback: CallbackQuery):
    _, _, page_str = callback.data.split(":")
    await callback.answer()
    await _send_shop_page(callback.message.chat.id,
                          page=int(page_str),
                          bot_message=callback.message,
                          edit=True)

# глушилка для «{n/m}»-кнопки
@router.callback_query(F.data == "noop")
async def noop_cb(callback: CallbackQuery):
    await callback.answer()

# покупка
@router.callback_query(F.data.startswith("buy:"))
async def shop_buy_callback(callback: CallbackQuery):
    await callback.answer()
    cid, uid = callback.message.chat.id, callback.from_user.id
    _, item_id = callback.data.split(":", 1)

    if (item := SHOP_ITEMS.get(item_id)) is None:
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
        f"Покупка: {item['emoji']}<b>{item['name']}</b> за {item['price']}₴ ✔️",
        parse_mode="HTML")
    register_msg_for_autodelete(callback.message.chat.id, msg.message_id)
