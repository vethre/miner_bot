from __future__ import annotations
import json, math

from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import CallbackQuery

from bot.db_local import cid_uid, get_progress, db
from bot.utils.pass_rewards import grant_pass_reward
from bot.handlers.items import ITEM_DEFS
from bot.utils.autodelete import register_msg_for_autodelete

router = Router()

async def _load_track() -> list[dict]:
    rows = await db.fetch_all("SELECT level, reward_type, reward_data FROM pass_track ORDER BY level")
    return [dict(r) for r in rows]

async def _claimed_set(cid:int, uid:int) -> set[int]:
    rows = await db.fetch_all(
        "SELECT level FROM pass_claims WHERE chat_id=:c AND user_id=:u",
        {"c":cid, "u":uid}
    )
    return {r["level"] for r in rows}

@router.message(Command("trackpass"))
async def trackpass_cmd(message: types.Message):
    cid, uid = await cid_uid(message)
    await _send_track_page(chat_id=cid, user_id=uid, page=0, bot_message=message, edit=False)

@router.callback_query(F.data.startswith("tp:"))  # tp = track pass
async def trackpass_callback(cb: CallbackQuery):
    cid, uid = cb.message.chat.id, cb.from_user.id
    _, action, arg = cb.data.split(":", 2)

    if action == "pg":
        await _send_track_page(cid, uid, int(arg), cb.message, edit=True)
        await cb.answer()
    elif action == "claim":
        level = int(arg)
        await _attempt_claim(cid, uid, level, cb)
    else:
        await cb.answer()

PER_PAGE = 5

async def _send_track_page(chat_id:int, user_id:int, page:int,
                           bot_message:types.Message, edit:bool=True):
    track  = await _load_track()
    pages  = math.ceil(len(track) / PER_PAGE)
    page   = max(0, min(page, pages-1))
    prog   = await get_progress(chat_id, user_id)       # level / xp
    user_lvl = prog.get("level", 1)

    # -------- текст ---------------------------------------------------
    start = page*PER_PAGE
    chunk = track[start:start+PER_PAGE]
    lines = [f"🎫 <b>Cave Pass — Track {page+1}/{pages}</b>",
             f"Твій рівень: {user_lvl}"]
    for row in chunk:
        lvl = row["level"]
        locked  = "🔒" if lvl > user_lvl else "✅"
        preview = _preview_reward(row)
        lines.append(f"{locked} <b>{lvl}</b>. {preview}")

    # -------- клавіатура ---------------------------------------------
    kb = InlineKeyboardBuilder()

    for row in chunk:
        lvl = row["level"]
        if lvl > user_lvl:
            text = "🔒"
            kb.button(text=text, callback_data="tp:noop:x")
        else:
            # перевіряємо, забрано чи ні
            claimed = await db.fetch_val(
                "SELECT 1 FROM pass_claims WHERE chat_id=:c AND user_id=:u AND level=:l",
                {"c":chat_id,"u":user_id,"l":lvl}
            )
            if claimed:
                kb.button(text="✅ Забрано", callback_data="tp:noop:x")
            else:
                kb.button(text=f"🎁 Забрати {lvl}", callback_data=f"tp:claim:{lvl}")

    kb.adjust(1)                         # вертикальний стовп

    # навігація
    nav = InlineKeyboardBuilder()
    if page>0:
        nav.button(text="◀️", callback_data=f"tp:pg:{page-1}")
    nav.button(text=f"{page+1}/{pages}", callback_data="tp:noop:x")
    if page<pages-1:
        nav.button(text="▶️", callback_data=f"tp:pg:{page+1}")
    nav_buttons = list(list(nav.buttons))
    # з’єднуємо
    kb.row(*nav.buttons, width=len(list(nav.buttons)))

    if edit:
        sent = await bot_message.edit_text("\n".join(lines),
                                           parse_mode="HTML",
                                           reply_markup=kb.as_markup())
    else:
        sent = await bot_message.reply("\n".join(lines),
                                       parse_mode="HTML",
                                       reply_markup=kb.as_markup())
    register_msg_for_autodelete(chat_id, sent.message_id)


def _preview_reward(row:dict)->str:
    t = row["reward_type"]
    d = row["reward_data"]
    if isinstance(d, str):
        d = json.loads(d)
    if t == "coins":
        return f"{d['coins']} монет"
    if t == "xp":
        return f"{d['xp']} XP"
    if t == "item":
        items = []
        for itm in d["items"]:
            meta = ITEM_DEFS.get(itm["item"], {"name": itm["item"], "emoji": ""})
            pre  = f"{meta.get('emoji','')}" if meta.get("emoji") else ""
            items.append(f"{pre}{meta['name']}×{itm['qty']}")
        return ", ".join(items)
    return "?"

# ────────────────────────────────────────────────────────────
#  Спроба забрати нагороду
# ────────────────────────────────────────────────────────────
async def _attempt_claim(cid:int, uid:int, level:int, cb:CallbackQuery):
    track_row = await db.fetch_one("SELECT * FROM pass_track WHERE level=:l", {"l":level})
    if not track_row:
        return await cb.answer("Невідома нагорода", show_alert=True)

    prog = await get_progress(cid, uid)
    if level > prog.get("level", 1):
        return await cb.answer("Недостатній рівень!", show_alert=True)

    already = await db.fetch_val(
        "SELECT 1 FROM pass_claims WHERE chat_id=:c AND user_id=:u AND level=:l",
        {"c":cid,"u":uid,"l":level}
    )
    if already:
        return await cb.answer("Вже забрано 😉")

    # видаємо
    await grant_pass_reward(cid, uid, track_row["reward_type"], track_row["reward_data"])
    await db.execute(
        "INSERT INTO pass_claims(chat_id,user_id,level) VALUES(:c,:u,:l)",
        {"c":cid,"u":uid,"l":level}
    )
    await cb.answer("🎉 Нагороду отримано!")
    # перерендер сторінки
    page = (level-1)//PER_PAGE
    await _send_track_page(cid, uid, page, cb.message, edit=True)