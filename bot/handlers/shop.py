# bot/handlers/shop.py
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
}

@router.message(Command("shop"))
async def shop_cmd(message: types.Message):
    cid, uid = await cid_uid(message)
    # переконаємось, що є запис у progress_local
    # (optional) init_local already зробив це
    
    builder = InlineKeyboardBuilder()
    for item_id, props in SHOP_ITEMS.items():
        text = f"{props['emoji']} {props['name']} — {props['price']} монет"
        # додаєм original uid, щоб лише він міг купити
        builder.button(
            text=text,
            callback_data=f"buy:{item_id}:{uid}"
        )
    builder.adjust(1)

    await message.reply(
        "🛒 <b>Магазин</b> — обери товар:",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )

@router.callback_query(F.data.startswith("buy:"))
async def shop_buy_callback(callback: CallbackQuery):
    await callback.answer()
    cid = callback.message.chat.id
    data = callback.data.split(":", 2)
    # формат: ['buy', item_id, orig_uid]
    if len(data) != 3:
        return
    _, item_id, orig_uid = data
    orig_uid = int(orig_uid)
    # тільки той, хто відкрив магазин
    if callback.from_user.id != orig_uid:
        return await callback.answer("Ця кнопка не для тебе", show_alert=True)

    # перевіряємо баланс локальний
    balance = await get_money(cid, orig_uid)
    item = SHOP_ITEMS.get(item_id)
    if not item:
        return await callback.message.reply("Товар не знайдено 😕")
    price = item["price"]
    if balance < price:
        return await callback.message.reply("Недостатньо монет 💸")

    # списуємо гроші й додаємо в інвентар
    await add_money(cid, orig_uid, -price)
    await add_item(cid, orig_uid, item_id, 1)

    await callback.message.reply(
        f"Ти придбав {item['emoji']}<b>{item['name']}</b> за {price} монет! 🎉",
        parse_mode="HTML"
    )
