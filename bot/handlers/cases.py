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
CAVE_CASE_REWARDS = [
    {"weight": 30, "items": [{"item": "stone", "qty": 20}]},
    {"weight": 20, "items": [{"item": "coal", "qty": 8}]},
    {"weight": 12, "items": [{"item": "wax", "qty": 2}]},
    {"weight": 10, "items": [{"item": "bread", "qty": 2}]},
    {"weight": 7, "items": [{"item": "borsch", "qty": 1}]},
    {"weight": 6, "items": [{"item": "energy_drink", "qty": 2}]},
    {"weight": 6, "items": [{"item": "iron_ingot", "qty": 2}]},
    {"weight": 5, "items": [{"item": "gold_ingot", "qty": 1}]},
    {"weight": 4, "items": [{"item": "wood_handle", "qty": 2}]},
    {"weight": 3, "items": [{"item": "roundstone_pickaxe", "qty": 1}]},
    {"weight": 3, "coins": 100},
    {"weight": 2, "xp": 5},
    {"weight": 1, "items": [{"item": "cave_cases", "qty": 1}]}, # мем-рефлекс
    {"weight": 1, "items": [{"item": "voucher_sale", "qty": 1}]},
    {"weight": 1, "meme": "Тебе выпала дырка от бублика! Но настроение приподнялось."}
]

CLASH_CASE_REWARDS = [
    {"weight": 16, "coins": 200},
    {"weight": 12, "items": [{"item": "gold_ingot", "qty": 3}]},
    {"weight": 11, "items": [{"item": "iron_ingot", "qty": 5}]},
    {"weight": 8, "items": [{"item": "amethyst_ingot", "qty": 1}]},
    {"weight": 8, "items": [{"item": "diamond", "qty": 1}]},
    {"weight": 7, "items": [{"item": "obsidian_shard", "qty": 2}]},
    {"weight": 5, "xp": 8},
    {"weight": 3, "items": [{"item": "diamond_pickaxe", "qty": 1}]},
    {"weight": 2, "items": [{"item": "clash_case", "qty": 1}]},
    {"weight": 1, "meme": "Ничего не выпало, но ты красавчик! (Clash кейс любит смелых)"}
]
# ────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────

def weighted_choice(rewards):
    total = sum(r['weight'] for r in rewards)
    rnd = random.randint(1, total)
    acc = 0
    for r in rewards:
        acc += r['weight']
        if rnd <= acc:
            return r
    return rewards[-1]

async def give_case_to_user(chat_id: int, user_id: int, case_type: CaseType, qty: int):
    column = "cave_cases" if case_type == "cave_case" else "clash_cases"
    await db.execute(
        f"UPDATE progress_local SET {column} = {column} + :q WHERE chat_id=:c AND user_id=:u",
        {"q": qty, "c": chat_id, "u": user_id},
    )

# ────────────────────────────────────────────────
# Main open logic
# ────────────────────────────────────────────────
async def _open_case(message, case_type="cave_case"):
    rewards = CAVE_CASE_REWARDS if case_type == "cave_case" else CLASH_CASE_REWARDS
    prize = weighted_choice(rewards)
    cid, uid = await cid_uid(message)
    out = []

    if "coins" in prize:
        await add_money(cid, uid, prize["coins"])
        out.append(f"{prize['coins']} монет")
    if "xp" in prize:
        await add_xp(cid, uid, prize["xp"])
        out.append(f"{prize['xp']} XP")
    if "items" in prize:
        for it in prize["items"]:
            await add_item(cid, uid, it["item"], it["qty"])
            meta = ITEM_DEFS.get(it["item"], {"name": it["item"], "emoji": "❔"})
            out.append(f"{it['qty']}×{meta['emoji']} {meta['name']}")
    if "meme" in prize:
        out.append(prize["meme"])

    await message.reply("🎁 Тебе выпало: " + " + ".join(out))

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

