import json
import datetime as dt
from aiogram import types, Router
from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot.db_local import db, get_progress, add_item
from bot.utils.autodelete import register_msg_for_autodelete
from bot.utils.unlockachievement import unlock_achievement
from bot.handlers.badge_defs import BADGES
from bot.handlers.pass_rewards import PASS_REWARDS

router = Router()

def generate_progress_bar(current: int, total: int, size: int = 10) -> str:
    filled = int((current / total) * size)
    empty = size - filled
    return f"{'▰' * filled}{'▱' * empty} {min(current, total)}/{total}"

@router.message(commands="trackpass")
async def trackpass_cmd(message: types.Message):
    cid = message.chat.id
    uid = message.from_user.id
    prog = await get_progress(cid, uid)

    current_xp = prog.get("pass_xp", 0)
    level = prog.get("pass_level", 0)
    claimed = prog.get("pass_claimed", {}) or {}
    if isinstance(claimed, str):
        claimed = json.loads(claimed)

    premium = prog.get("cave_pass") and prog["pass_expires"] and prog["pass_expires"] > dt.datetime.utcnow()
    max_level = max(PASS_REWARDS.keys())
    progress_bar = generate_progress_bar(current_xp, (level + 1) * 100)

    lines = [f"<b>📘 Cave Pass S1</b>\n🎚️ Уровень: {level}\n📊 Прогресс: {progress_bar}\n"]
    
    for lvl in range(1, max_level + 1):
        rewards = PASS_REWARDS.get(lvl, {})
        free = rewards.get("free", "")
        prem = rewards.get("premium", "")
        cl = claimed.get(str(lvl), {})

        status = "✅" if cl.get("free") and (not prem or cl.get("premium")) else "🔓"
        row = f"{status} Lv.{lvl:>2} | Free: {free or '—'} | Premium: {prem or '—'}"
        lines.append(row)

    kb = InlineKeyboardBuilder()
    for lvl in range(1, max_level + 1):
        if not claimed.get(str(lvl), {}).get("free"):
            kb.button(text=f"🎁 Lv{lvl}", callback_data=f"passreward:free:{lvl}")
        if premium and not claimed.get(str(lvl), {}).get("premium"):
            kb.button(text=f"💎 Lv{lvl}", callback_data=f"passreward:prem:{lvl}")
    msg = await message.answer("\n".join(lines), reply_markup=kb.as_markup(), parse_mode="HTML")
    register_msg_for_autodelete(cid, msg.message_id)

@router.callback_query(lambda c: c.data.startswith("passreward:"))
async def claim_pass_reward(call: types.CallbackQuery):
    cid = call.message.chat.id
    uid = call.from_user.id
    _, typ, lvl_str = call.data.split(":")
    lvl = int(lvl_str)

    prog = await get_progress(cid, uid)
    claimed = prog.get("pass_claimed") or {}
    if isinstance(claimed, str):
        claimed = json.loads(claimed)

    if str(lvl) not in PASS_REWARDS:
        return await call.answer("Такого уровня не существует.")

    if lvl > prog.get("pass_level", 0):
        return await call.answer("Ты ещё не достиг этого уровня!")

    if claimed.get(str(lvl), {}).get(typ):
        return await call.answer("Уже получено!")

    reward = PASS_REWARDS[lvl][typ]
    text = f"🎁 Получено с Lv.{lvl}: "

    if reward.endswith("_ingot") or reward in ("torch_bundle", "cave_case"):
        await add_item(cid, uid, reward, 1)
        text += f"{reward}"
    elif reward.startswith("badge:"):
        badge_id = reward.split(":", 1)[1]
        row = await db.fetch_one(
            "SELECT badges_owned FROM progress_local WHERE chat_id=:c AND user_id=:u",
            {"c": cid, "u": uid}
        )
        owned = row["badges_owned"] or []
        if isinstance(owned, str):
            try:
                owned = json.loads(owned)
            except:
                owned = []

        if badge_id not in owned:
            owned.append(badge_id)
            await db.execute(
                "UPDATE progress_local SET badges_owned = :val WHERE chat_id=:c AND user_id=:u",
                {"val": json.dumps(owned), "c": cid, "u": uid}
            )
            text += "🆕 новый бейдж!"
        else:
            text += "🟢 бейдж уже получен"
    elif reward.startswith("ach:"):
        ach_code = reward.split(":", 1)[1]
        await unlock_achievement(cid, uid, ach_code)
        text += "новая ачивка!"
    elif reward == "iron_pickaxe":
        await add_item(cid, uid, reward, 1)
        text += "Железная кирка!"
    elif reward.endswith("XP"):
        xp_gain = int(reward.replace("XP", ""))
        from bot.db_local import add_xp
        await add_xp(cid, uid, xp_gain)
        text += f"{xp_gain} XP"
    elif reward.endswith("gold"):
        gold = int(reward.replace("gold", ""))
        from bot.db_local import add_money
        await add_money(cid, uid, gold)
        text += f"{gold} монет"

    # Сохраняем прогресс
    claimed.setdefault(str(lvl), {})[typ] = True
    await db.execute(
        "UPDATE progress_local SET pass_claimed=:cl WHERE chat_id=:c AND user_id=:u",
        {"cl": json.dumps(claimed), "c": cid, "u": uid}
    )

    await call.answer(text, show_alert=True)
