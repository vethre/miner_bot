# bot/handlers/shop.py
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.db_local import cid_uid, get_money, add_money, add_item
from bot.handlers.items import ITEM_DEFS
from bot.handlers.cases import give_case_to_user
from bot.assets import SHOP_IMG_ID
from bot.handlers.cases import give_case_to_user
from bot.utils.autodelete import register_msg_for_autodelete

router = Router()

# Список товарів у магазині
SHOP_ITEMS = {
    "wood_handle":    {"price": 100,  "name": "Рукоять",         "emoji": "🪵"},
    "wooden_pickaxe": {"price": 200,  "name": "Деревяная кирка", "emoji": "🔨"},
    "iron_pickaxe":   {"price": 1000, "name": "Железная кирка",   "emoji": "⛏️"},
    "gold_pickaxe":   {"price": 2000, "name": "Золотая кирка",    "emoji": "✨"},
    "torch_bundle":   {"price": 150, "name": "Факел",    "emoji": "🕯️"},
    "bread":          {"price": 50,   "name": "Хлеб",            "emoji": "🍞", "hunger": 20},
    "meat":           {"price": 120,  "name": "Мясо",           "emoji": "🍖", "hunger": 50},
    "borsch":         {"price": 300,  "name": "Борщ",            "emoji": "🥣", "hunger": 100},
    "energy_drink":   {"price": 170, "name": "Энергетик",        "emoji": "🥤", "energy": 40},
    "cave_cases":     {"price": 300, "name": "Cave Case",        "emoji": "📦"},
}

@router.message(Command("shop"))
async def shop_cmd(message: types.Message):
    cid, uid = await cid_uid(message)

    builder = InlineKeyboardBuilder()
    for item_id, props in SHOP_ITEMS.items():
        text = f"{props['emoji']} {props['name']} — {props['price']} монет"
        builder.button(text=text, callback_data=f"buy:{item_id}")
    builder.adjust(1)

    msg = await message.answer_photo(
        photo=SHOP_IMG_ID,
        caption="🛒 <b>Магазин</b> — выбери товар:",
        parse_mode="HTML",
        reply_to_message_id=message.message_id,
        reply_markup=builder.as_markup()
    )
    register_msg_for_autodelete(message.chat.id, msg.message_id)
    """
    await message.reply(
        "🛒 <b>Магазин</b> — обери товар:",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    ) """

@router.callback_query(F.data.startswith("buy:"))
async def shop_buy_callback(callback: CallbackQuery):
    await callback.answer()
    cid, uid = callback.message.chat.id, callback.from_user.id
    _, item_id = callback.data.split(":", 1)

    item = SHOP_ITEMS.get(item_id)
    if not item:
        return await callback.message.reply("Товар не найден 😕")

    balance = await get_money(cid, uid)
    price = item["price"]
    if balance < price:
        return await callback.message.reply("Недостаточно монет 💸")

    await add_money(cid, uid, -price)
    if item_id == "cave_cases":
        await give_case_to_user(cid, uid, 1)
    else:
        await add_item(cid, uid, item_id, 1)

    msg = await callback.message.reply(
        f"Ты купил {item['emoji']}<b>{item['name']}</b> за {price} монет! 🎉",
        parse_mode="HTML"
    )
    register_msg_for_autodelete(callback.message.chat.id, msg.message_id)
