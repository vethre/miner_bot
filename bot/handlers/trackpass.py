from __future__ import annotations
import json, math
import datetime as dt

from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import CallbackQuery

from bot.db import add_item
from bot.db_local import add_money, add_xp, cid_uid, get_progress, db
from bot.utils.pass_rewards import grant_pass_reward
from bot.handlers.items import ITEM_DEFS
from bot.utils.autodelete import register_msg_for_autodelete

router = Router()

SEASON_ID   = 1
SEASON_LEN  = 15          # днів дії Pass-у
LVL_XP      = 120         # XP на 1 рівень

PASS_REWARDS: dict[int, dict] = {
    1: {"free": {"coins": 100},
        "premium": {"item": "wood_handle", "qty": 2}},
    2: {"free": {"xp": 80},
        "premium": {"item": "torch_bundle", "qty": 2}},
    3: {"free": {"coins": 150},
        "premium": {"item": "crystal_pickaxe", "qty": 5}},
    4: {"free": {"coins": 150},
        "premium": {"item": "iron_ingot", "qty": 5}},
    5: {"free": {"coins": 150},
        "premium": {"item": "iron_ingot", "qty": 5}},
    6: {"free": {"coins": 150},
        "premium": {"item": "iron_ingot", "qty": 5}},
    7: {"free": {"coins": 150},
        "premium": {"item": "iron_ingot", "qty": 5}},
    8: {"free": {"coins": 150},
        "premium": {"item": "iron_ingot", "qty": 5}},
    9: {"free": {"coins": 150},
        "premium": {"item": "iron_ingot", "qty": 5}},
    10: {"free": {"coins": 150},
        "premium": {"item": "amethyst_pickaxe", "qty": 1}},
    11: {"free": {"coins": 150},
        "premium": {"item": "lapis", "qty": 5}},
    12: {"free": {"coins": 150},
        "premium": {"item": "iron_ingot", "qty": 5}},
    13: {"free": {"coins": 150},
        "premium": {"item": "iron_ingot", "qty": 5}},
    14: {"free": {"item": "amethyst", "qty": 7},
        "premium": {"item": "lapis", "qty": 5}},
    15: {"free": {"item": "gold_ingot", "qty": 13},
        "premium": {"item": "iron_ingot", "qty": 5}},
    16: {"free": {"item": "iron_ingot", "qty": 15},
        "premium": {"item": "iron_ingot", "qty": 5}},
    17: {"free": {"coins": 350},
        "premium": {"item": "iron_ingot", "qty": 5}},
    18: {"free": {"xp": 270},
        "premium": {"item": "emerald", "qty": 5}},
    19: {"free": {"coins": 500},
        "premium": {"item": "iron_ingot", "qty": 5}},
    20: {"free": {"xp": 300},
        "premium": {"item": "iron_ingot", "qty": 5}},
    # …
}
MAX_LEVEL = max(PASS_REWARDS)

async def _load_track() -> list[dict]:
    rows = await db.fetch_all("SELECT level, reward_type, reward_data FROM pass_track ORDER BY level")
    return [dict(r) for r in rows]

async def _claimed_set(cid:int, uid:int) -> set[int]:
    rows = await db.fetch_all(
        "SELECT level FROM pass_claims WHERE chat_id=:c AND user_id=:u",
        {"c":cid, "u":uid}
    )
    return {r["level"] for r in rows}

async def add_pass_xp(cid:int, uid:int, delta:int):
    """Нарахувати XP треку й, за потреби, підвищити рівень."""
    row = await db.fetch_one(
        "SELECT cave_pass, pass_xp, pass_level FROM progress_local "
        "WHERE chat_id=:c AND user_id=:u",
        {"c": cid, "u": uid}
    )
    if not row:                      # safety
        return
    xp  = row["pass_xp"] + delta
    lvl = row["pass_level"]
    up  = 0
    while xp >= LVL_XP and lvl + up < MAX_LEVEL:
        xp -= LVL_XP
        up += 1
    if up:
        await db.execute(
            "UPDATE progress_local SET pass_xp=:xp, pass_level=pass_level+:up "
            "WHERE chat_id=:c AND user_id=:u",
            {"xp": xp, "up": up, "c": cid, "u": uid}
        )
    else:
        await db.execute(
            "UPDATE progress_local SET pass_xp=:xp WHERE chat_id=:c AND user_id=:u",
            {"xp": xp, "c": cid, "u": uid}
        )

PAGE_SIZE = 4       # скільки level-карток на сторінку

def _progress_bar(p: int, tot:int=LVL_XP, width:int=12) -> str:
    filled = round(p / tot * width)
    return "▰" * filled + "▱" * (width - filled)

@router.message(Command("trackpass"))
async def trackpass_cmd(message: types.Message):
    cid, uid = await cid_uid(message)
    await _send_track_page(cid, uid, page=0, bot_message=message, edit=False)

@router.callback_query(F.data.startswith("tp:"))
async def tp_cb(cb: types.CallbackQuery):
    _, action, arg = cb.data.split(":")
    cid, uid = cb.message.chat.id, cb.from_user.id
    if action == "page":
        await _send_track_page(cid, uid, int(arg), cb.message, edit=True)
    elif action == "claim":
        lvl = int(arg)
        await _claim_reward(cid, uid, lvl, cb)

async def _send_track_page(chat_id:int, user_id:int, page:int,
                           bot_message:types.Message, edit:bool):
    prog = await get_progress(chat_id, user_id)
    have_pass = prog.get("cave_pass", False) and (prog["pass_expires"] or dt.datetime.min) > dt.datetime.utcnow()
    lvl  = prog.get("pass_level", 0)
    xp   = prog.get("pass_xp", 0)
    claimed = (prog.get("pass_claimed") or {})

    start = page * PAGE_SIZE + 1
    end   = min(start + PAGE_SIZE - 1, MAX_LEVEL)

    lines = [f"🎫 <b>Cave Pass Season {SEASON_ID}</b>",
             f"Level: {lvl}/{MAX_LEVEL}  XP: {_progress_bar(xp)} {xp}/{LVL_XP}",
             ""]
    kb = InlineKeyboardBuilder()

    for lv in range(start, end + 1):
        rew = PASS_REWARDS[lv]
        status = "✅" if str(lv) in claimed else ("🟢" if lv <= lvl else "🔒")
        free = _rew_str(rew["free"])
        prem = _rew_str(rew["premium"])
        lines.append(f"<b>{status} Level {lv}</b>\nFREE  — {free}\nPASS — {prem}")

        if lv <= lvl and str(lv) not in claimed:
            kb.button(text=f"Забрать L{lv}", callback_data=f"tp:claim:{lv}")

    # пагінація
    nav = InlineKeyboardBuilder()
    if start > 1:
        nav.button(text="⬅️", callback_data=f"tp:page:{page-1}")
    nav.button(text=f"{page+1}/{(MAX_LEVEL-1)//PAGE_SIZE+1}", callback_data="noop")
    if end < MAX_LEVEL:
        nav.button(text="➡️", callback_data=f"tp:page:{page+1}")

    kb.row(*nav.buttons)

    text = "\n".join(lines)
    if edit:
        await bot_message.edit_text(text, parse_mode="HTML", reply_markup=kb.as_markup())
    else:
        await bot_message.reply(text, parse_mode="HTML", reply_markup=kb.as_markup())

def _rew_str(r:dict)->str:
    if "coins" in r:   return f"{r['coins']}💰"
    if "xp" in r:      return f"{r['xp']} XP"
    return f"{r['qty']}×{ITEM_DEFS[r['item']]['emoji']} {ITEM_DEFS[r['item']]['name']}"

async def _claim_reward(cid:int, uid:int, lvl:int, cb:types.CallbackQuery):
    prog = await get_progress(cid, uid)
    if lvl > prog.get("pass_level",0):
        return await cb.answer("Недоступно 👀", show_alert=True)
    claimed = prog.get("pass_claimed") or {}
    if str(lvl) in claimed:
        return await cb.answer("Уже забрано", show_alert=False)

    rew = PASS_REWARDS[lvl]["free"]
    # premium частина
    if prog.get("cave_pass"):
        rew_p = PASS_REWARDS[lvl]["premium"]
        _merge_rewards(rew, rew_p)

    # видаємо
    await _apply_reward(cid, uid, rew)
    claimed[str(lvl)] = True
    await db.execute(
        "UPDATE progress_local SET pass_claimed=:cl WHERE chat_id=:c AND user_id=:u",
        {"cl": json.dumps(claimed), "c": cid, "u": uid}
    )
    await cb.answer("🎉 Награда получена!")
    await _send_track_page(cid, uid, (lvl-1)//PAGE_SIZE, cb.message, edit=True)

def _merge_rewards(base:dict, extra:dict):
    if "coins" in extra: base["coins"] = base.get("coins",0)+extra["coins"]
    if "xp"    in extra: base["xp"]    = base.get("xp",0)+extra["xp"]
    if "item"  in extra:
        base.setdefault("items", []).append(extra)

async def _apply_reward(cid:int, uid:int, rew:dict):
    if "coins" in rew: await add_money(cid, uid, rew["coins"])
    if "xp"    in rew: await add_xp   (cid, uid, rew["xp"])
    if "items" in rew:
        for itm in rew["items"]:
            await add_item(cid, uid, itm["item"], itm["qty"])