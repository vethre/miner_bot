# bot/handlers/shop.py
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot.db import get_user, add_item, db

router = Router()

# Список товарів у магазині з ключами без емодзі для БД
SHOP_ITEMS = {
    "wood_handle":    {"price": 100,  "name": "Рукоять", "emoji": "🪵 "},
    "wooden_pickaxe": {"price": 200,  "name": "Дерев’яна кирка", "emoji": "🔨 "},
    "iron_pickaxe":   {"price": 1000, "name": "Залізна кирка", "emoji": "⛏️ "},
    "gold_pickaxe":   {"price": 2000, "name": "Золота кирка", "emoji": "✨ "},
    # їжа
    "bread": {"price": 50,  "name": "Хліб", "hunger": 30, "emoji": "🍞 "},
    "meat":  {"price": 120, "name": "М’ясо","hunger": 60, "emoji": "🍖 "},
}

@router.message(Command("/shop"))
async def shop_cmd(message: types.Message, user_id: int | None = None):
    uid = user_id or message.from_user.id
    user = await get_user(uid)
    if not user:
        return await message.reply("Спершу введи /start")

    # Створюємо builder для інлайн-кнопок
    builder = InlineKeyboardBuilder()
    for item_id, item in SHOP_ITEMS.items():
        text = f"{item['emoji']} {item['name']} — {item['price']} монет"
        builder.button(text=text, callback_data=f"buy:{item_id}")
    builder.adjust(1)

    await message.reply(
        "🛒 <b>Магазин кирок</b> — натисни кнопку, щоб купити:",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )

@router.callback_query(F.data.startswith("buy:"))
async def shop_buy_callback(callback: CallbackQuery):
    await callback.answer()  # acknowledge to remove loading state
    user_id = callback.from_user.id
    user = await get_user(user_id)
    if not user:
        return await callback.message.reply("Спершу /start")

    item_id = callback.data.split(':', 1)[1]
    item = SHOP_ITEMS.get(item_id)
    if not item:
        return await callback.message.reply("Товар не знайдено 😕")

    if user['balance'] < item['price']:
        return await callback.message.reply("Недостатньо монет 💸")

    # Віднімаємо монети та додаємо товар в інвентар (за id)
    await db.execute(
        "UPDATE users SET balance = balance - :price WHERE user_id = :user_id",
        {"price": item['price'], "user_id": user_id}
    )
    await add_item(user_id, item_id, 1)

    await callback.message.reply(f"Ти придбав {item['emoji']} <b>{item['name']}</b>! 🎉", parse_mode="HTML")
