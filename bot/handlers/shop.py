# bot/handlers/shop.py
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.db_local import cid_uid, get_money, add_money, add_item
from bot.handlers.items import ITEM_DEFS
from bot.handlers.cases import give_case_to_user

router = Router()

# Список товарів у магазині
SHOP_ITEMS = {
    "wood_handle":    {"price": 100,  "name": "Рукоять",         "emoji": "🪵"},
    "wooden_pickaxe": {"price": 200,  "name": "Дерев’яна кирка", "emoji": "🔨"},
    "iron_pickaxe":   {"price": 1000, "name": "Залізна кирка",   "emoji": "⛏️"},
    "gold_pickaxe":   {"price": 2000, "name": "Золота кирка",    "emoji": "✨"},
    "bread":          {"price": 50,   "name": "Хліб",            "emoji": "🍞", "hunger": 20},
    "meat":           {"price": 120,  "name": "М’ясо",           "emoji": "🍖", "hunger": 50},
    "borsch":         {"price": 300,  "name": "Борщ",            "emoji": "🥣", "hunger": 100},
    "cave_case":      {"price": 350, "name": "Cave Case",         "emoji": "📦"},
}

@router.message(Command("shop"))
async def shop_cmd(message: types.Message):
    cid, uid = await cid_uid(message)

    builder = InlineKeyboardBuilder()
    for item_id, props in SHOP_ITEMS.items():
        text = f"{props['emoji']} {props['name']} — {props['price']} монет"
        builder.button(text=text, callback_data=f"buy:{item_id}")
    builder.adjust(1)

    await message.reply(
        "🛒 <b>Магазин</b> — обери товар:",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )

@router.callback_query(F.data.startswith("buy:"))
async def shop_buy_callback(callback: CallbackQuery):
    await callback.answer()
    cid, uid = callback.message.chat.id, callback.from_user.id
    _, item_id = callback.data.split(":", 1)

    item = SHOP_ITEMS.get(item_id)
    if not item:
        return await callback.message.reply("Товар не знайдено 😕")

    balance = await get_money(cid, uid)
    price = item["price"]
    if balance < price:
        return await callback.message.reply("Недостатньо монет 💸")

    await add_money(cid, uid, -price)
    await add_item(cid, uid, item_id, 1)

    await callback.message.reply(
        f"Ти придбав {item['emoji']}<b>{item['name']}</b> за {price} монет! 🎉",
        parse_mode="HTML"
    )
