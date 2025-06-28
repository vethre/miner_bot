"""
Unified cases handler — поддерживает и Cave Case, и Clash Case.

• /case          — открыть Cave Case (📦 каменный)
• /clashcase     — открыть Clash Case (🔥 турнирный)
• /give_case ... — админ‑команда: теперь принимает тип кейса.

Требования:
- aiogram>=3.0.0
- в таблице progress_local должны быть поля cave_cases, clash_cases (INT, default 0)
"""

from __future__ import annotations

import asyncio
import json
import random
from typing import Dict, List, Literal

from aiogram import Router, Bot, types
from aiogram.filters import Command
from aiogram.types import Message

from bot.db_local import (
    cid_uid,
    db,
    add_item,
    add_money,
    add_xp,
    get_progress,
)
from bot.handlers.items import ITEM_DEFS

router = Router()
ADMINS = {700_929_765, 988_127_866}

CaseType = Literal["cave_case", "clash_case"]

# 🎲 Локальные weight‑пулы — можно заменить БД
CASE_POOLS: dict[CaseType, List[Dict[str, int | str]]] = {
    "cave_case": [
        {"key": "stone_pack", "weight": 25},
        {"key": "repair_pack", "weight": 20},
        {"key": "xp_boost", "weight": 18},
        {"key": "gold_nugget", "weight": 5},
        {"key": "food_pack", "weight": 8},
        {"key": "tool_pack", "weight": 6},
        {"key": "energy_combo", "weight": 7},
        {"key": "chef_pack", "weight": 10},
        {"key": "exclusive_pack", "weight": 2},
        {"key": "coin_pack", "weight": 1},
        {"key": "rich_pack", "weight": 1},
    ],
    "clash_case": [  # ⚡ Менее «мусора», больше эпика
        {"key": "xp_mega_boost", "weight": 20},
        {"key": "gold_mega_nugget", "weight": 15},
        {"key": "exclusive_pack", "weight": 15},
        {"key": "coin_mega_pack", "weight": 10},
        {"key": "rich_pack", "weight": 9},
        {"key": "emerald_bundle", "weight": 7},
        {"key": "diamond_bundle", "weight": 3},
        {"key": "legendary_tool", "weight": 2},
    ],
}

# ────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────

def _weighted_choice(pool: List[Dict[str, int | str]]) -> str:
    total = sum(p["weight"] for p in pool)
    rnd = random.randint(1, total)
    acc = 0
    for p in pool:
        acc += p["weight"]
        if rnd <= acc:
            return p["key"]
    return pool[-1]["key"]


async def pick_case_reward(case_type: CaseType) -> Dict[str, str | dict]:
    """Берём случайный ключ из пула, запрашиваем БД, fallback — мок."""
    pool_keys = [p["key"] for p in CASE_POOLS[case_type]]
    chosen_key = random.choice(pool_keys)

    row = await db.fetch_one(
        """
        SELECT reward_key, reward_type, reward_data
          FROM case_rewards
         WHERE reward_key = :k
        """,
        {"k": chosen_key},
    )
    if row:
        return row

    return {
        "reward_key": chosen_key,
        "reward_type": "item",
        "reward_data": json.dumps({"item": chosen_key, "qty": 1}),
    }


async def give_case_to_user(chat_id: int, user_id: int, case_type: CaseType, qty: int):
    column = "cave_cases" if case_type == "cave_case" else "clash_cases"
    await db.execute(
        f"UPDATE progress_local SET {column} = {column} + :q WHERE chat_id=:c AND user_id=:u",
        {"q": qty, "c": chat_id, "u": user_id},
    )


# ────────────────────────────────────────────────
# Main open logic
# ────────────────────────────────────────────────
async def _open_case(message: Message, case_type: CaseType):
    cid, uid = await cid_uid(message)
    prog = await get_progress(cid, uid)
    column = "cave_cases" if case_type == "cave_case" else "clash_cases"

    if prog[column] < 1:
        await message.reply("У тебя нет " + ("Cave Case 😕" if case_type == "cave_case" else "Clash Case 😕"))
        return

    await db.execute(
        f"UPDATE progress_local SET {column} = {column} - 1 WHERE chat_id=:c AND user_id=:u",
        {"c": cid, "u": uid},
    )

    reward = await pick_case_reward(case_type)
    rtype, raw = reward["reward_type"], reward["reward_data"]
    data = raw if isinstance(raw, dict) else json.loads(raw)

    parts: List[str] = []

    if rtype == "item" and "items" in data:
        for it in data["items"]:
            if "item" in it and "qty" in it:
                await add_item(cid, uid, it["item"], it["qty"])
                meta = ITEM_DEFS[it["item"]]
                parts.append(f"{it['qty']}×{meta['emoji']} {meta['name']}")
            elif "coins" in it:
                await add_money(cid, uid, it["coins"])
                parts.append(f"{it['coins']} монет")
            elif "xp" in it:
                await add_xp(cid, uid, it["xp"])
                parts.append(f"{it['xp']} XP")

    elif rtype == "item":
        it = data
        await add_item(cid, uid, it["item"], it["qty"])
        meta = ITEM_DEFS[it["item"]]
        parts.append(f"{it['qty']}×{meta['emoji']} {meta['name']}")

    elif rtype == "coins":
        await add_money(cid, uid, data["coins"])
        parts.append(f"{data['coins']} монет")

    elif rtype == "xp":
        await add_xp(cid, uid, data["xp"])
        parts.append(f"{data['xp']} XP")

    descr = " + ".join(parts)
    msg = await message.reply("📦 Открываем кейс...")
    for frame in ["▓▓░░░░░░░", "▓▓▓▓░░░░", "▓▓▓▓▓▓░░"]:
        await asyncio.sleep(0.35)
        await msg.edit_text(f"📦 {frame}")
    await asyncio.sleep(0.25)
    await msg.edit_text(f"🎉 Тебе выпало: {descr}!")


# ────────────────────────────────────────────────
# Commands
# ────────────────────────────────────────────────
@router.message(Command("case"))
async def cave_case_cmd(message: Message):
    await _open_case(message, "cave_case")


@router.message(Command("clashcase"))
async def clash_case_cmd(message: Message):
    await _open_case(message, "clash_case")


@router.message(Command("give_case"))
async def give_case_cmd(message: Message):
    cid, _ = await cid_uid(message)
    if message.from_user.id not in ADMINS:
        await message.reply("⚠️ У вас нет прав на эту команду")
        return

    parts = message.text.split()
    if len(parts) not in {3, 4}:
        await message.reply("Использование: /give_case 'user_id|@username' 'кол-во' [cave|clash]")
        return

    target, cnt_str = parts[1], parts[2]
    if not cnt_str.isdigit():
        await message.reply("Кол-во должно быть числом")
        return
    qty = int(cnt_str)

    ctype: CaseType = "clash_case" if len(parts) == 4 and parts[3].lower().startswith("clash") else "cave_case"

    if target.startswith("@"):  # mention
        try:
            member = await message.bot.get_chat_member(cid, target)
            uid = member.user.id
        except Exception:
            await message.reply("Пользователь не найден")
            return
    else:
        if not target.isdigit():
            await message.reply("Неверный id")
            return
        uid = int(target)

    await give_case_to_user(cid, uid, ctype, qty)
    mention = f'<a href="tg://user?id={uid}">{uid}</a>'
    await message.reply(
        f"✅ Выдано {qty} {( 'Clash' if ctype=='clash_case' else 'Cave' )} Case(ов) пользователю {mention}",
        parse_mode="HTML",
    )

