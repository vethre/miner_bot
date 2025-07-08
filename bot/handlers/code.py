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
        if isinstance(used_by, list) and used_by and isinstance(used_by[0], int):
            # старий формат (тільки user_id)
            used_by = [{"user_id": u, "chat_id": cid} for u in used_by]
    except:
        used_by = []

    already_used = any(u.get("chat_id") == cid and u.get("user_id") == uid for u in used_by)
    if already_used:
        return await message.reply("🚫 Ты уже активировал этот промокод в этом чате.")
    else:
        used_by.append({"chat_id": cid, "user_id": uid})

    # 💰 выдача награды
    reward = row["reward"]
    if isinstance(reward, str):
        reward = json.loads(reward)

    coins = reward.get("coins", 0)
    xp    = reward.get("xp", 0)
    energy  = reward.get("energy",  0)
    hunger  = reward.get("hunger",  0)
    items = reward.get("items", {})  # {"item_id": qty}

    if coins < 0:
        await add_money(cid, uid, coins)  # списание монет
        return await message.reply(f"😅 Интересный выбор... −{abs(coins)} монет списано")
    
    if coins:
        await add_money(cid, uid, coins)
    if xp:
        await add_xp(cid, uid, xp)
    if energy or hunger:
        await db.execute("""
            UPDATE progress_local
               SET energy = energy + :en,
                   hunger = hunger + :hu
             WHERE chat_id=:c AND user_id=:u
        """, {"en": energy, "hu": hunger, "c": cid, "u": uid})
    for item_id, qty in items.items():
        if item_id in ("cave_case", "cave_cases"):
            await give_case_to_user(cid, uid, "cave_case", qty)
        else:
            await add_item(cid, uid, item_id, qty)

    await db.execute(
        "UPDATE promo_codes SET used_by = :used WHERE code = :code",
        {"used": json.dumps(used_by), "code": code}
    )

    msg = ["🎉 <b>Промокод активирован!</b>"]
    if coins:   msg.append(f"💰 +{coins}")
    if xp:      msg.append(f"📘 +{xp} XP")
    if energy:  msg.append(f"🔋 +{energy} энергии")
    if hunger:  msg.append(f"🍗 +{hunger} голода")
    for item_id, qty in items.items():
        meta = ITEM_DEFS.get(item_id, {"name": item_id, "emoji": "📦"})
        msg.append(f"+{meta.get('emoji','📦')} {meta['name']} ×{qty}")

    msg_code = await message.reply("\n".join(msg), parse_mode="HTML")
    register_msg_for_autodelete(message.chat.id, msg_code.message_id)