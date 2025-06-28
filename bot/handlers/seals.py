from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot.db_local import db, add_item, get_inventory, cid_uid
from bot.handlers.items import ITEM_DEFS
from bot.utils.autodelete import register_msg_for_autodelete

router = Router()

SEALS = {
    "seal_durability": {
        "name": "Печать прочности",
        "desc": "Каждая 3-я копка не тратит прочность кирки.",
        "emoji": "🛡️",
        "recipe": {
            "coal": 20,
            "iron_ingot": 10
        }
    },
    "seal_sacrifice": {
        "name": "Печать жертвы",
        "desc": "-20 XP, но +20% руды при копке.",
        "emoji": "🩸",
        "recipe": {
            "roundstone": 15,
            "gold_ingot": 5,
            "coal": 20
        }
    },
    "seal_energy": {
        "name": "Печать бодрости",
        "desc": "Сокращает время копки на 5 минут.",
        "emoji": "⚡",
        "recipe": {
            "borsch": 2,
            "bread": 1,
            "coal": 30
        }
    }
}

@router.message(Command("seals"))
async def show_seals(message: types.Message):
    cid, uid = await cid_uid(message)
    builder = InlineKeyboardBuilder()
    for key, data in SEALS.items():
        builder.button(
            text=f"{data['emoji']} {data['name']}",
            callback_data=f"seal_{key}"
        )
    builder.adjust(1)
    msg = await message.answer("🪬 Выбери печать для крафта:", reply_markup=builder.as_markup())
    register_msg_for_autodelete(message.chat.id, msg.message_id)

@router.callback_query(F.data.startswith("seal_"))
async def seal_craft(callback: types.CallbackQuery):
    cid, uid = await cid_uid(callback)
    seal_key = callback.data.split("_", 1)[1]
    seal = SEALS.get(seal_key)

    if not seal:
        return await callback.answer("Неизвестная печать.")

    inv = {i["item"]: i["qty"] for i in await get_inventory(cid, uid)}
    missing = []

    for item, need in seal["recipe"].items():
        if inv.get(item, 0) < need:
            missing.append(f"{ITEM_DEFS[item]['emoji']} {ITEM_DEFS[item]['name']} ×{need - inv.get(item, 0)}")

    if missing:
        return await callback.message.edit_text("❌ Не хватает ресурсов:\n" + "\n".join(missing))

    for item, qty in seal["recipe"].items():
        await add_item(cid, uid, item, -qty)

    await db.execute(
        "UPDATE progress_local SET seals_owned = json_set(COALESCE(seals_owned, '{}'::json), :key, 'true'::json, true) "
        "WHERE chat_id=:c AND user_id=:u",
        {"key": f'{{{seal_key}}}', "c": cid, "u": uid}
    )

    await callback.message.edit_text(f"🎉 {seal['emoji']} {seal['name']} скрафчена и добавлена в вашу коллекцию печатей!")

@router.message(Command("sealset"))
async def choose_seal(message: types.Message):
    cid, uid = await cid_uid(message)
    prog = await db.fetch_one(
        "SELECT seals_owned, seal_active FROM progress_local WHERE chat_id=:c AND user_id=:u",
        {"c": cid, "u": uid}
    )
    owned = list(prog["seals_owned"].keys()) if prog and prog["seals_owned"] else []
    active = prog["seal_active"] if prog else None

    if not owned:
        return await message.answer("❌ У тебя ещё нет ни одной печати.")

    builder = InlineKeyboardBuilder()
    for seal_key in owned:
        seal = SEALS.get(seal_key)
        if not seal:
            continue
        is_active = " ✅" if seal_key == active else ""
        builder.button(
            text=f"{seal['emoji']} {seal['name']}{is_active}",
            callback_data=f"setseal_{seal_key}"
        )

    builder.button(text="❌ Снять печать", callback_data="setseal_none")
    builder.adjust(1)

    msg = await message.answer("🪬 Выбери активную печать:", reply_markup=builder.as_markup())
    register_msg_for_autodelete(message.chat.id, msg.message_id)

@router.callback_query(F.data.startswith("setseal_"))
async def set_seal(callback: types.CallbackQuery):
    cid, uid = await cid_uid(callback)
    seal_key = callback.data.split("_", 1)[1]

    if seal_key == "none":
        await db.execute(
            "UPDATE progress_local SET seal_active=NULL WHERE chat_id=:c AND user_id=:u",
            {"c": cid, "u": uid}
        )
        return await callback.answer("❌ Печать деактивирована", show_alert=True)

    await db.execute(
        "UPDATE progress_local SET seal_active=:s WHERE chat_id=:c AND user_id=:u",
        {"s": seal_key, "c": cid, "u": uid}
    )
    msg = await callback.answer("✅ Печать активирована", show_alert=True)
    register_msg_for_autodelete(callback.message.chat.id, msg.message_id)