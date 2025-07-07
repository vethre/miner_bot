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
# lvl  free-track                         , premium-track
# ───────────────────────────────────────────────────────────────
    ({"coins": 150},                      {"achievement": "eonite_owner"}),          #  1
    ({"item": "bread", "qty": 2},         {"coins": 400}),                           #  2
    ({"coins": 200},                      {"item": "voucher_sale", "qty": 1}),       #  3
    ({"item": "bomb", "qty": 1},          {"coins": 500}),                           #  4
    ({"coins": 250},                      {"badge": "eonite_beacon"}),               #  5
# ───────────────────────────────────────────────────────────────
    ({"item": "energy_drink", "qty": 2},  {"coins": 600}),                           #  6
    ({"coins": 300},                      {"item": "bread", "qty": 4}),              #  7
    ({"case": "cave_case", "qty": 1},     {"coins": 700}),                           #  8
    ({"coins": 350},                      {"item": "bomb", "qty": 2}),               #  9
    ({"item": "energy_drink", "qty": 1},  {"item": "proto_eonite_pickaxe", "qty": 1}),# 10
# ───────────────────────────────────────────────────────────────
    ({"coins": 400},                      {"coins": 800}),                           # 11
    ({"item": "bomb", "qty": 1},          {"item": "voucher_borsch", "qty": 1}),     # 12
    ({"coins": 450},                      {"coins": 900}),                           # 13
    ({"item": "bread", "qty": 2},         {"item": "energy_drink", "qty": 3}),       # 14
    ({"coins": 500},                      {"case": "cave_case", "qty": 3}),          # 15
# ───────────────────────────────────────────────────────────────
    ({"item": "bomb", "qty": 1},          {"coins": 1100}),                          # 16
    ({"coins": 550},                      {"item": "bomb", "qty": 2}),               # 17
    ({"item": "energy_drink", "qty": 2},  {"coins": 1200}),                          # 18
    ({"coins": 600},                      {"item": "bread", "qty": 5}),              # 19
    ({"case": "cave_case", "qty": 1},     {"item": "voucher_sale", "qty": 1,
                                           "extra": [
                                               {"case": "cave_case", "qty": 5},
                                               {"item": "eonite_shard", "qty": 3}
                                           ]}),                                      # 20
# ───────────────────────────────────────────────────────────────
    # … и так далее до 30-го уровня – заполняйте по своему вкусу
]

def _bar(value: int, total: int, size: int = 20) -> str:
    """▰▰▰▱-бар из Unicode‐блоков."""
    filled = min(size, int(round(value / total * size)))
    return "▰" * filled + "▱" * (size - filled)

def _name(payload: dict) -> str:
    """Читабельное имя награды (для списка уровней)."""
    if "coins" in payload:
        return f"{payload['coins']} мон."
    if "item" in payload:
        meta = ITEM_DEFS.get(payload["item"], {})
        qty  = payload.get("qty", 1)
        return f"{meta.get('emoji','')} {meta.get('name', payload['item'])}×{qty}"
    if "case" in payload:
        meta = ITEM_DEFS.get(payload["case"], {})
        qty  = payload.get("qty", 1)
        return f"{meta.get('emoji','🎁')} {meta.get('name','Кейс')}×{qty}"
    if "achievement" in payload:
        return "Достижение"
    if "badge" in payload:
        return "Бейдж"
    return "?"

# ───────────────── команда /trackpass ─────────────
@router.message(Command("trackpass"))
async def trackpass_cmd(m: types.Message):
    cid, uid = await cid_uid(m)

    # гарантируем, что строка есть
    await db.execute(
        "INSERT INTO pass_progress (chat_id,user_id) VALUES (:c,:u) "
        "ON CONFLICT DO NOTHING",
        {"c": cid, "u": uid},
    )

    row = await db.fetch_one(
        "SELECT lvl, xp, is_premium FROM pass_progress "
        "WHERE chat_id=:c AND user_id=:u",
        {"c": cid, "u": uid},
    )
    lvl, xp, prem = row["lvl"], row["xp"], row["is_premium"]

    # ───── заголовок / счётчик дней ─────
    now = dt.datetime.now(dt.timezone.utc)
    days_left = max(0, (PASS_END.date() - now.date()).days)
    header = (
        "🎫 <b>Cave Pass • Сезон 1</b>\n"
        f"⏳ До конца: <b>{'последний день!' if days_left == 0 else str(days_left)+' дн.'}</b>\n"
        f"{'⭐ Премиум активен' if prem else '🔒 Премиум не куплен'}\n"
        "───────────────\n"
    )

    # ───── ваш текущий прогресс ─────
    bar = _bar(xp, XP_PER_LVL)
    body = (
        f"Уровень <b>{lvl}</b>\n"
        f"<code>{bar}</code>\n"
        f"XP {xp}/{XP_PER_LVL}\n"
        "───────────────\n"
    )

    # ───── ближайшие 5 уровней ─────
    upcoming = ["<b>Ближайшие награды:</b>"]
    for i in range(lvl, min(lvl + 5, TOTAL_LVL)):
        free, prem_r = REWARDS[i]
        line = f"{i+1:02d}. {_name(free)}"
        if prem:
            line += f" | ⭐ {_name(prem_r)}"
        upcoming.append(line)

    await m.answer(
        header + body + "\n".join(upcoming),
        parse_mode="HTML",
    )