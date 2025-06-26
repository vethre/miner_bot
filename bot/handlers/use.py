# bot/handlers/use.py
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import CallbackQuery
from bot.db_local import cid_uid, get_inventory, add_item, db
import json, asyncpg

router = Router()

PICKAXES = {
    "wooden_pickaxe":   {"bonus": .05, "name": "деревяная кирка",   "emoji": "🔨", "dur": 65},
    "iron_pickaxe":     {"bonus": .15, "name": "железная кирка",     "emoji": "⛏️", "dur": 90},
    "gold_pickaxe":     {"bonus": .30, "name": "золотая кирка",      "emoji": "✨", "dur": 60},
    "roundstone_pickaxe":{"bonus": .10, "name": "булыжниковая кирка", "emoji": "🪨", "dur": 80},
    "crystal_pickaxe":  {"bonus":.80, "name": "хрустальная кирка",  "emoji": "💎", "dur": 75},
    "amethyst_pickaxe": {"bonus": .50, "name": "аметистовая кирка",  "emoji": "🔮", "dur":100},
    "diamond_pickaxe": {"bonus": .75, "name": "алмазная кирка",  "emoji": "💎", "dur":65},
    "proto_eonite_pickaxe": {"bonus": 1.3, "name": "прототип эонитовой кирки",  "emoji": "🔮", "dur":50},
}


ALIAS = {
    "деревяная кирка":"wooden_pickaxe","деревяная кирка":"wooden_pickaxe",
    "железная кирка":"iron_pickaxe",    "золотая кирка":"gold_pickaxe",
    "булыжниковая кирка":"roundstone_pickaxe",
    "хрустальная кирка":"crystal_pickaxe",
    "аметистовая кирка":"amethyst_pickaxe",
    "алмазная кирка": "diamond_pickaxe",
    "прототип эонитовой кирки": "proto_eonite_pickaxe",
    "пэк": "proto_eonite_pickaxe",
}

def _json2dict(raw):
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, asyncpg.Record):
        return dict(raw)
    try:
        return json.loads(raw)
    except Exception:
        # fallback:   '{"key":1}' → dict(record)  /  'text' → {}
        try:
            return dict(raw)
        except Exception:
            return {}

@router.message(Command("use"))
async def use_cmd(message: types.Message):
    cid, uid = await cid_uid(message)
    inv = {r["item"]: r["qty"] for r in await get_inventory(cid, uid)}

    pick_keys = [k for k in PICKAXES if inv.get(k, 0) > 0]
    if not pick_keys:
        return await message.reply("У тебя нет ни одной кирки 🪨")

    kb = InlineKeyboardBuilder()
    for key in pick_keys:
        meta = PICKAXES[key]
        kb.button(
            text=f"{meta['emoji']} {meta['name']} ({inv[key]} шт.)",
            callback_data=f"use:{key}:{uid}"
        )
    kb.adjust(1)
    await message.reply("🔧 Выбери кирку:", reply_markup=kb.as_markup())


@router.callback_query(F.data.startswith("use:"))
async def use_callback(callback: CallbackQuery):
    cid, uid = await cid_uid(callback)
    try:
        _, key, orig_uid_str = callback.data.split(":")
        orig_uid = int(orig_uid_str)
    except ValueError:
        return await callback.answer("Неверные данные", show_alert=True)

    if uid != orig_uid:
        return await callback.answer("Эта кнопка не для тебя 😾", show_alert=True)

    if key not in PICKAXES:
        return await callback.answer("Такой кирки не существует 😵")

    inv = {r["item"]: r["qty"] for r in await get_inventory(cid, uid)}
    if inv.get(key, 0) < 1:
        return await callback.answer("У тебя нет этой кирки ❌", show_alert=True)

    prog = await db.fetch_one("""
        SELECT current_pickaxe, pick_dur_map, pick_dur_max_map
          FROM progress_local
         WHERE chat_id=:c AND user_id=:u
    """, {"c": cid, "u": uid})
    cur = prog["current_pickaxe"]
    dur_map = _json2dict(prog["pick_dur_map"])
    dur_max_map = _json2dict(prog["pick_dur_max_map"])

    if key not in dur_max_map:
        dur_max_map[key] = PICKAXES[key]["dur"]
    if key not in dur_map:
        dur_map[key] = dur_max_map[key]

    async with db.transaction():
        await add_item(cid, uid, key, -1)
        if cur:
            await add_item(cid, uid, cur, +1)
        await db.execute("""
            UPDATE progress_local
               SET current_pickaxe = :p,
                   pick_dur_map = (:dm)::jsonb,
                   pick_dur_max_map = (:dmm)::jsonb
             WHERE chat_id = :c AND user_id = :u
        """, {
            "p": key,
            "dm": json.dumps(dur_map),
            "dmm": json.dumps(dur_max_map),
            "c": cid,
            "u": uid
        })

    await callback.message.edit_text(
        f"{PICKAXES[key]['emoji']} Взял <b>{PICKAXES[key]['name']}</b> "
        f"(бонус +{int(PICKAXES[key]['bonus'] * 100)}%)",
        parse_mode="HTML"
    )
    # (…все як було, без змін)
