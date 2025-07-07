# bot/handlers/pass_track.py
from __future__ import annotations

import datetime as dt
from aiogram import Router, types
from aiogram.filters import Command

from bot.db_local import db, cid_uid, add_item, add_money
from bot.handlers.items import ITEM_DEFS
from bot.utils.unlockachievement import unlock_achievement

router = Router()

PASS_START  = dt.datetime(2025, 7, 7, tzinfo=dt.timezone.utc)
PASS_END    = dt.datetime(2025, 7, 27, tzinfo=dt.timezone.utc)
PASS_DAYS   = (PASS_END - PASS_START).days      # 20 дн.
TOTAL_LVL   = 20
XP_PER_LVL  = 300

# -------- награды ---------------------------------------------------
#   free[x]  / premium[x]  для уровня (index==lvl-1)
REWARDS = [
    ({"coins": 150},                      {"achievement": "eonite_owner"}),          #  1
    ({"item": "bread", "qty": 2},         {"coins": 400}),                           #  2
    ({"coins": 200},                      {"item": "voucher_sale", "qty": 1}),       #  3
    ({"item": "bomb", "qty": 1},          {"coins": 500}),                           #  4
    ({"coins": 250},                      {"badge": "eonite_beacon"}),               #  5
# ───────────────────────────────────────────────────────────────
    ({"item": "energy_drink", "qty": 2},  {"coins": 600}),                           #  6
    ({"coins": 300},                      {"item": "bread", "qty": 4}),              #  7
    ({"case": "cave_cases", "qty": 1},     {"coins": 700}),                           #  8
    ({"coins": 350},                      {"item": "bomb", "qty": 2}),               #  9
    ({"item": "energy_drink", "qty": 1},  {"item": "proto_eonite_pickaxe", "qty": 1}),# 10
# ───────────────────────────────────────────────────────────────
    ({"coins": 400},                      {"coins": 800}),                           # 11
    ({"item": "bomb", "qty": 1},          {"item": "voucher_borsch", "qty": 1}),     # 12
    ({"coins": 450},                      {"coins": 900}),                           # 13
    ({"item": "bread", "qty": 2},         {"item": "energy_drink", "qty": 3}),       # 14
    ({"coins": 500},                      {"case": "cave_cases", "qty": 3}),          # 15
# ───────────────────────────────────────────────────────────────
    ({"item": "bomb", "qty": 1},          {"coins": 1100}),                          # 16
    ({"coins": 550},                      {"item": "bomb", "qty": 2}),               # 17
    ({"item": "energy_drink", "qty": 2},  {"coins": 1200}),                          # 18
    ({"coins": 600},                      {"item": "bread", "qty": 5}),              # 19
    ({"case": "cave_cases", "qty": 1},     {"item": "voucher_sale", "qty": 1,
                                           "extra": [
                                               {"case": "cave_cases", "qty": 5},
                                               {"item": "eonite_shard", "qty": 3}
                                           ]}),                                      # 20
]

async def ensure_row(cid: int, uid: int):
    await db.execute(
        "INSERT INTO pass_progress (chat_id,user_id) VALUES (:c,:u) "
        "ON CONFLICT DO NOTHING",
        {"c": cid, "u": uid},
    )

async def deliver_reward(cid: int, uid: int, payload: dict):
    if not payload:
        return
    if "item" in payload:
        await add_item(cid, uid, payload["item"], payload.get("qty", 1))
    elif "coins" in payload:
        await add_money(cid, uid, payload["coins"])
    elif "case" in payload:
        from bot.handlers.cases import give_case_to_user
        await give_case_to_user(cid, uid, payload["case"], payload.get("qty", 1))
    elif "achievement" in payload:
        await unlock_achievement(cid, uid, payload["achievement"])
    elif "badge" in payload:
        await db.execute(
            "UPDATE progress_local SET badge_active=:b "
            "WHERE chat_id=:c AND user_id=:u",
            {"b": payload["badge"], "c": cid, "u": uid},
        )
    if "extra" in payload:
        for sub in payload["extra"]:
            await deliver_reward(cid, uid, sub)

async def grant_level_reward(cid: int, uid: int, lvl: int):
    free, prem = REWARDS[lvl - 1]
    await deliver_reward(cid, uid, free)

    row = await db.fetch_one(
        "SELECT is_premium FROM pass_progress WHERE chat_id=:c AND user_id=:u",
        {"c": cid, "u": uid},
    )
    if row and row["is_premium"]:
        await deliver_reward(cid, uid, prem)

async def add_pass_xp(cid: int, uid: int, delta: int):
    await ensure_row(cid, uid)

    # прибавляем XP и читаем новую пару (xp,lvl)
    row = await db.fetch_one(
        "UPDATE pass_progress SET xp = xp + :d "
        "WHERE chat_id=:c AND user_id=:u "
        "RETURNING xp, lvl",
        {"d": delta, "c": cid, "u": uid},
    )
    xp, lvl = row["xp"], row["lvl"]

    # прокачиваем, пока хватает опыта
    while lvl < TOTAL_LVL and xp >= XP_PER_LVL:
        lvl += 1
        xp -= XP_PER_LVL
        await grant_level_reward(cid, uid, lvl)

    await db.execute(
        "UPDATE pass_progress SET xp=:x, lvl=:l WHERE chat_id=:c AND user_id=:u",
        {"x": xp, "l": lvl, "c": cid, "u": uid},
    )

# ────────── helper’ы рендера ──────────
def _bar(val: int, total: int, size: int = 20) -> str:
    filled = min(size, int(round(val / total * size)))
    return "▰" * filled + "▱" * (size - filled)

def _name(p: dict) -> str:
    if "coins" in p:
        base = f"{p['coins']} мон."
    if "item" in p:
        meta = ITEM_DEFS.get(p["item"], {})
        base = f"{meta.get('emoji','')} {meta.get('name', p['item'])}×{p.get('qty',1)}"
    if "case" in p:
        meta = ITEM_DEFS.get(p["case"], {})
        base = f"{meta.get('emoji','🎁')} {meta.get('name','Кейс')}×{p.get('qty',1)}"
    if "achievement" in p:
        base = "Достижение"
    elif "badge" in p:
        base = "Бейдж"
    else:
        base = "?"

    # 2) если есть extra – добавляем короткий список «+ …»
    if "extra" in p:
        extras = ", ".join(_name(x) for x in p["extra"])
        base += f"  (+ {extras})"

    return base

# ────────── команда /trackpass ──────────
@router.message(Command("trackpass"))
async def trackpass_cmd(m: types.Message):
    cid, uid = await cid_uid(m)
    await ensure_row(cid, uid)

    row = await db.fetch_one(
        "SELECT lvl, xp, is_premium FROM pass_progress "
        "WHERE chat_id=:c AND user_id=:u",
        {"c": cid, "u": uid},
    )
    lvl, xp, prem = row["lvl"], row["xp"], row["is_premium"]

    now = dt.datetime.now(dt.timezone.utc)
    d_left = max(0, (PASS_END.date() - now.date()).days)

    header = (
        "🎫 <b>Cave Pass • Сезон 1</b>\n"
        f"⏳ До конца: <b>{'последний день!' if d_left == 0 else str(d_left)+' дн.'}</b>\n"
        f"{'⭐ Премиум активен' if prem else '🔒 Премиум не куплен'}\n"
        "───────────────\n"
    )

    body = (
        f"Уровень <b>{lvl}</b>\n"
        f"<code>{_bar(xp, XP_PER_LVL)}</code>\n"
        f"XP {xp}/{XP_PER_LVL}\n"
        "───────────────\n"
    )

    near = ["<b>Ближайшие уровни:</b>"]
    for i in range(lvl, min(lvl + 5, TOTAL_LVL)):
        fr, pr = REWARDS[i]
        line = f"{i+1:02d}. {_name(fr)}"
        if prem:
            line += f" | ⭐ {_name(pr)}"
        near.append(line)

    await m.answer(header + body + "\n".join(near), parse_mode="HTML")