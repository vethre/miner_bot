# bot/handlers/eat.py
from aiogram import Router, types, F
from aiogram.filters import Command
import datetime as dt
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import CallbackQuery

from bot.db_local import (
    cid_uid, get_inventory, add_item,
    update_hunger, update_energy, add_energy, db
)
from bot.utils.autodelete import register_msg_for_autodelete

router = Router()

# ───── потребляемые предметы ────────────────────────────────────────────────
CONSUMABLES = {
    # еда → восстанавливает hunger
    "bread":        {"name": "🍞 Хлеб",  "hunger": 30},
    "meat":         {"name": "🍖 Мясо",  "hunger": 50},
    "borsch":       {"name": "🥣 Борщ",  "hunger": 70, "energy": 20},
    # напитки / бустеры → восстанавливают energy
    "energy_drink": {"name": "🥤 Энергетик", "energy": 20},
    "coffee":       {"name": "☕ Кофе",       "energy": 70},
    "water_bottle": {"name": "💧 Фляга с водой", "energy": 100}
}

ALIAS = {
    "хлеб": "bread",
    "мясо": "meat",
    "борщ": "borsch",
    "энергетик": "energy_drink",
    "кофе": "coffee",
    "борсч": "borsch",
    "borshch": "borsch",
}

@router.message(Command("eat"))
async def eat_cmd(message: types.Message):
    cid, uid = await cid_uid(message)
    inv = {r["item"]: r["qty"] for r in await get_inventory(cid, uid)}

    edible_keys = [k for k in CONSUMABLES if inv.get(k, 0) > 0]
    if not edible_keys:
        return await message.reply("🍽️ У тебя нет ничего съедобного")

    kb = InlineKeyboardBuilder()
    for key in edible_keys:
        meta = CONSUMABLES[key]
        kb.button(text=f"{meta['name']} ({inv[key]} шт.)", callback_data=f"eat:{key}:{uid}")
    kb.adjust(1)
    await message.reply("Выбери, что хочешь съесть:", reply_markup=kb.as_markup())


@router.callback_query(F.data.startswith("eat:"))
async def eat_callback(callback: CallbackQuery):
    cid, uid = await cid_uid(callback)

    try:
        _, key, orig_uid_str = callback.data.split(":")
        if uid != int(orig_uid_str):
            return await callback.answer("Эта еда не для тебя 😤", show_alert=True)
    except ValueError:
        return await callback.answer("Неверные данные", show_alert=True)

    item = CONSUMABLES.get(key)
    if not item:
        return await callback.answer("Такой еды нет 😅")

    inv = {r["item"]: r["qty"] for r in await get_inventory(cid, uid)}
    if inv.get(key, 0) < 1:
        return await callback.answer("У тебя нет этого блюда 😔", show_alert=True)

    # ─── списываем 1 шт ───────────────────────────────────────
    await add_item(cid, uid, key, -1)

    now          = dt.datetime.utcnow()
    text_parts   = [f"Ты употребил: {item['name']}"]

    # ─── голод ────────────────────────────────────────────────
    if "hunger" in item:
        curr_hunger = await update_hunger(cid, uid)
        new_hunger  = min(100, curr_hunger + item["hunger"])
        await db.execute(
            """
            UPDATE progress_local
               SET hunger = :h,
                   last_hunger_update = :now
             WHERE chat_id=:c AND user_id=:u
            """,
            {"h": new_hunger, "now": now, "c": cid, "u": uid}
        )
        text_parts.append(f"🍗 Голод: {new_hunger}/100")

    # ─── энергия ──────────────────────────────────────────────
    if "energy" in item:
        await add_energy(cid, uid, item["energy"])
        new_energy = await update_energy(cid, uid)
        text_parts.append(f"🔋 Энергия: {new_energy}/100")

    await callback.message.edit_text("\n".join(text_parts))