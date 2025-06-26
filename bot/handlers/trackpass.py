# trackpass.py
import json
import datetime as dt
from zoneinfo import ZoneInfo
from aiogram import types, Router
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.db_local import db, get_progress, add_item, add_money, add_xp
from bot.utils.unlockachievement import unlock_achievement
from bot.handlers.badge_defs import BADGES
from bot.utils.autodelete import register_msg_for_autodelete
from bot.handlers.pass_rewards import PASS_REWARDS

router = Router()
UTC = ZoneInfo("UTC")

def generate_progress_bar(current: int, total: int, size: int = 10) -> str:
    filled = int((current / total) * size)
    empty = size - filled
    return f"{'▰' * filled}{'▱' * empty} {min(current, total)}/{total}"

def format_reward(data: dict) -> str:
    parts = []
    for k, v in data.items():
        if k == "money":
            parts.append(f"💰 {v}")
        elif k == "xp":
            parts.append(f"📘 {v} XP")
        elif k == "badge":
            badge = BADGES.get(v, {}).get("emoji", "🏅") + " " + BADGES.get(v, {}).get("name", v)
            parts.append(f"🏅 {badge}")
        elif k == "achievement":
            parts.append(f"🏆 ачивка")
        elif k == "pickaxe":
            parts.append(f"🪓 {v}")
        else:
            parts.append(f"{v}× {k}")
    return " + ".join(parts)

@router.message(Command("trackpass"))
async def trackpass_cmd(message: types.Message):
    cid = message.chat.id
    uid = message.from_user.id
    prog = await get_progress(cid, uid)

    current_xp = prog.get("pass_xp", 0)
    level = prog.get("pass_level", 0)
    claimed = prog.get("pass_claimed") or {}
    if isinstance(claimed, str):
        claimed = json.loads(claimed)

    premium = prog.get("cave_pass") and prog["pass_expires"] and prog["pass_expires"] > dt.datetime.now(tz=UTC)
    max_level = max(PASS_REWARDS.keys())
    progress_bar = generate_progress_bar(current_xp, (level + 1) * 100)

    lines = [f"<b>📘 Cave Pass S1</b>\n🎚️ Уровень: {level}\n📊 Прогресс: {progress_bar}\n"]
    
    for lvl in range(1, max_level + 1):
        rewards = PASS_REWARDS.get(lvl, {})
        free = rewards.get("free")
        prem = rewards.get("premium")
        cl = claimed.get(str(lvl), {})

        status = "✅" if cl.get("free") and (not prem or cl.get("premium")) else "🔓"
        row = f"{status} Lv.{lvl:>2} | Free: {format_reward(free) if free else '—'} | Premium: {format_reward(prem) if prem else '—'}"
        lines.append(row)

    kb = InlineKeyboardBuilder()
    for lvl in range(1, max_level + 1):
        if lvl > level:
            continue  # <-- не показуємо кнопки, якщо ще не досягнутий рівень
        if not claimed.get(str(lvl), {}).get("free"):
            kb.button(text=f"🎁 L{lvl}", callback_data=f"passreward:free:{lvl}")
        if premium and not claimed.get(str(lvl), {}).get("premium"):
            kb.button(text=f"💎 L{lvl}", callback_data=f"passreward:prem:{lvl}")
    kb.adjust(4)
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

    if lvl not in PASS_REWARDS:
        return await call.answer("Такого уровня не существует.")

    if lvl > prog.get("pass_level", 0):
        return await call.answer("Ты ещё не достиг этого уровня!")

    if claimed.get(str(lvl), {}).get(typ):
        return await call.answer("Уже получено!")

    real_key = {"free": "free", "prem": "premium"}.get(typ)
    if not real_key:
        return await call.answer("Некорректный тип награды.")
    reward = PASS_REWARDS[lvl][real_key]
    msg = []

    for key, val in reward.items():
        if key == "money":
            await add_money(cid, uid, val)
            msg.append(f"💰 {val} монет")
        elif key == "xp":
            await add_xp(cid, uid, val)
            msg.append(f"📘 {val} XP")
        elif key == "badge":
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
            if val not in owned:
                owned.append(val)
                await db.execute(
                    "UPDATE progress_local SET badges_owned = :val WHERE chat_id=:c AND user_id=:u",
                    {"val": owned, "c": cid, "u": uid}
                )
                msg.append("🏅 новый бейдж!")
            else:
                msg.append("🏅 бейдж уже есть")
        elif key == "achievement":
            await unlock_achievement(cid, uid, val)
            msg.append("🏆 ачивка")
        elif key == "pickaxe":
            await add_item(cid, uid, val, 1)
            msg.append(f"🪓 кирка: {val}")
        else:
            await add_item(cid, uid, key, val)
            msg.append(f"{val}× {key}")

    claimed.setdefault(str(lvl), {})[typ] = True
    await db.execute(
        "UPDATE progress_local SET pass_claimed=:cl WHERE chat_id=:c AND user_id=:u",
        {"cl": json.dumps(claimed), "c": cid, "u": uid}
    )
    await call.answer("🎁 " + ", ".join(msg), show_alert=True)
