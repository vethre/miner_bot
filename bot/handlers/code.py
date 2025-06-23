from aiogram import Router, types
from aiogram.filters import Command
import datetime as dt
import json

from bot.db_local import cid_uid, db, add_money, add_xp, add_item
from bot.utils.autodelete import register_msg_for_autodelete

router = Router()

@router.message(Command("code"))
async def promo_code_cmd(message: types.Message):
    cid, uid = await cid_uid(message)

    try:
        _, code = message.text.split(maxsplit=1)
        code = code.strip().lower()
    except ValueError:
        return await message.reply("📥 Введи промокод: /code <твой_код>")

    row = await db.fetch_one(
        "SELECT * FROM promo_codes WHERE code=:code",
        {"code": code}
    )
    if not row:
        return await message.reply("❌ Промокод не найден или неактивен.")

    if row["chat_id"] is not None and row["chat_id"] != cid:
        return await message.reply("🚫 Этот промокод не действует в этом чате.")

    used_by = json.loads(row["used_by"]) if isinstance(row["used_by"], str) else row["used_by"]
    if uid in used_by:
        return await message.reply("⛔️ Ты уже использовал этот промокод.")

    if row["max_uses"] is not None and len(used_by) >= row["max_uses"]:
        return await message.reply("😢 Промокод уже полностью использован.")

    if row["expires_at"] and row["expires_at"] < dt.datetime.utcnow():
        return await message.reply("⌛ Этот промокод уже истёк.")

    # применяем награду
    reward = row["reward"]
    coins = reward.get("coins", 0)
    xp = reward.get("xp", 0)
    items = reward.get("items", {})

    await add_money(cid, uid, coins)
    await add_xp(cid, uid, xp)

    for item_id, qty in items.items():
        await add_item(cid, uid, item_id, qty)

    used_by.append(uid)

    await db.execute(
        """UPDATE promo_codes
              SET used_by = :used
            WHERE code = :code""",
        {"used": json.dumps(used_by), "code": code}
    )

    # відповідаємо користувачу
    lines = ["🎉 <b>Промокод активирован!</b>"]
    if coins:
        lines.append(f"💰 Монеты: +{coins}")
    if xp:
        lines.append(f"📚 XP: +{xp}")
    for item_id, qty in items.items():
        lines.append(f"🎁 {item_id}: +{qty}")

    msg = await message.reply("\n".join(lines), parse_mode="HTML")
    register_msg_for_autodelete(message.chat.id, msg.message_id)
