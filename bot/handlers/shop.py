from aiogram import Router, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot.db import get_user, add_item, db

router = Router()

# Список товарів у магазині
SHOP_ITEMS = {
    "🪓 Дерев’яна кирка": {"price": 50, "bonus": 1},
    "⛏️ Кам’яна кирка": {"price": 200, "bonus": 5},
    "💎 Золота кирка": {"price": 1000, "bonus": 20},
}

@router.message(F.text == "/shop")
async def shop_cmd(message: types.Message):
    # Створюємо інлайн-кнопки для кожного товару
    keyboard = InlineKeyboardMarkup(row_width=1)
    for name, props in SHOP_ITEMS.items():
        btn = InlineKeyboardButton(
            text=f"{name} — {props['price']} монет",
            callback_data=f"buy:{name}"
        )
        keyboard.add(btn)

    await message.reply(
        "🛒 <b>Магазин кирок</b> — натисни кнопку, щоб купити:",
        parse_mode="HTML",
        reply_markup=keyboard
    )

@router.callback_query(F.data.startswith("buy:"))
async def shop_buy_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    item_name = callback.data.split(':', 1)[1]
    user = await get_user(user_id)

    if not user:
        await callback.answer("Спершу /start", show_alert=True)
        return

    item = SHOP_ITEMS.get(item_name)
    if not item:
        await callback.answer("Товар не знайдено", show_alert=True)
        return

    if user['balance'] < item['price']:
        await callback.answer("Недостатньо монет 💸", show_alert=True)
        return

    # Віднімаємо монети та додаємо товар
    await db.execute(
        "UPDATE users SET balance = balance - :price WHERE user_id = :user_id",
        {"price": item['price'], "user_id": user_id}
    )
    await add_item(user_id, item_name, 1)

    await callback.answer(f"Ти придбав {item_name}! 🎉", show_alert=True)
    # Опціонально оновити клавіатуру
    # await callback.message.edit_reply_markup()
