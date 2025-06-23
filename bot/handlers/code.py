from aiogram import Router, types
from aiogram.filters import Command
import datetime as dt
import json

from bot.db_local import cid_uid, db, add_money, add_xp, add_item
from bot.handlers.cases import give_case_to_user
from bot.handlers.items import ITEM_DEFS
from bot.utils.autodelete import register_msg_for_autodelete

router = Router()

@router.message(Command("code"))
async def promo_code_cmd(message: types.Message):
    cid, uid = await cid_uid(message)
    code = message.text.split(maxsplit=1)[1].strip().lower()

    row = await db.fetch_one("SELECT * FROM promo_codes WHERE code=:code", {"code": code})
    if not row:
        return await message.reply("❌ Промокод не найден")

    used_by = row["used_by"] or "[]"
    try:
        used_by = json.loads(used_by)
    except Exception:
        used_by = []

    # Підтримка старого формату (тільки user_id)
    if used_by and isinstance(used_by[0], int):
        already_used = uid in used_by
        if not already_used:
            used_by.append(uid)
    else:
        already_used = any(u.get("chat_id") == cid and u.get("user_id") == uid for u in used_by)
        if not already_used:
            used_by.append({"chat_id": cid, "user_id": uid})

    if already_used:
        return await message.reply("🚫 Ты уже активировал этот промокод в этом чате.")

    # 💰 выдача награды
    reward = row["reward"]
    if isinstance(reward, str):
        reward = json.loads(reward)

    coins = reward.get("coins", 0)
    xp    = reward.get("xp", 0)
    items = reward.get("items", {})  # {"item_id": qty}

    if coins < 0:
        await add_money(cid, uid, coins)  # списание монет
        return await message.reply(f"😅 Интересный выбор... −{abs(coins)} монет списано")
    
    if coins:
        await add_money(cid, uid, coins)
    if xp:
        await add_xp(cid, uid, xp)
    for item_id, qty in items.items():
        await add_item(cid, uid, item_id, qty)

    await db.execute(
        "UPDATE promo_codes SET used_by = :used WHERE code = :code",
        {"used": json.dumps(used_by), "code": code}
    )

    msg = ["🎉 <b>Промокод активирован!</b>\n"]
    if coins:
        msg.append(f"💰 +{coins} монет")
    if xp:
        msg.append(f"📘 +{xp} XP")

    for item_id, qty in items.items():
        # Випадок для Cave Case
        if item_id == "cave_cases":
            await give_case_to_user(cid, uid, qty)
            msg.append(f"+📦 Cave Case ×{qty}")
        else:
            await add_item(cid, uid, item_id, qty)
            meta = ITEM_DEFS.get(item_id, {"name": item_id, "emoji": "📦"})
            name = meta["name"]
            emoji = meta.get("emoji", "")
            msg.append(f"+{emoji} {name} ×{qty}")

    msg_code = await message.reply("\n".join(msg), parse_mode="HTML")
    register_msg_for_autodelete(message.chat.id, msg_code.message_id)