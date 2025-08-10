# bot/handlers/use.py
import random
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import CallbackQuery
from bot.db_local import add_money, cid_uid, get_inventory, add_item, db
import json, asyncpg

from bot.handlers.items import ITEM_DEFS

router = Router()

PICKAXES = {
    "wooden_pickaxe":   {"bonus": .05, "name": "деревяная кирка",   "emoji": "🔨", "dur": 65},
    "iron_pickaxe":     {"bonus": .18, "name": "железная кирка",     "emoji": "⛏️", "dur": 115},
    "gold_pickaxe":     {"bonus": .30, "name": "золотая кирка",      "emoji": "✨", "dur": 80},
    "roundstone_pickaxe":{"bonus": .12, "name": "булыжниковая кирка", "emoji": "🪨", "dur": 100},
    "crystal_pickaxe":  {"bonus":.95, "name": "хрустальная кирка",  "emoji": "💎", "dur": 75},
    "amethyst_pickaxe": {"bonus": .55, "name": "аметистовая кирка",  "emoji": "🔮", "dur":120},
    "diamond_pickaxe": {"bonus": .80, "name": "алмазная кирка",  "emoji": "💎", "dur":85},
    "obsidian_pickaxe": {"name":  "Обсидиановая кирка", "emoji": "🟪", "bonus": .90,"dur":   165},
    "proto_eonite_pickaxe": {"bonus": 1.1, "name": "прототип эонитовой кирки",  "emoji": "🧿", "dur":50},
    "greater_eonite_pickaxe": {"bonus": 1.45, "name": "старшая эонитовая кирка", "emoji": "🔮", "dur": 60, "regen": 10},
    "void_pickaxe": {"bonus": 0, "name": "войд-кирка",  "emoji": "🕳️", "dur":70},
    "pick_catharsis": {  # Pickaxe of Catharsis
        "name": "кирка катарсиса", "emoji": "⚔️", "dur": 10**12,  # псевдо-беск. прочность
        "bonus": 0.0, "crit": 100, "crit_mult": 5.0,  # крит чисто для вида
        "is_divine": True
    },
    "legacy_pickaxe": {
        "name": "памятная кирка", "emoji": "♾️", "dur": 1,  # не ломается логикой ниже
        "bonus": 0.0, "crit": 0, "crit_mult": 1.0,
        "is_legacy": True
    },
}

USABLE_EXTRA = {
    "voucher_borsch",
    "voucher_sale",
    "voucher_full_energy",
}

ALIAS = {
    "деревяная кирка":"wooden_pickaxe",
    "железная кирка":"iron_pickaxe",    "золотая кирка":"gold_pickaxe",
    "булыжниковая кирка":"roundstone_pickaxe",
    "хрустальная кирка":"crystal_pickaxe",
    "аметистовая кирка":"amethyst_pickaxe",
    "алмазная кирка": "diamond_pickaxe",
    "обсидиановая кирка": "obsidian_pickaxe",
    "ваучер борщ": "voucher_borsch",
    "ваучер распродажа": "voucher_sale",
    "ваучер восстановления": "voucher_full_energy",
    "прототип эонитовой кирки": "proto_eonite_pickaxe",
    "пэк": "proto_eonite_pickaxe",
    "старшая эонитовая кирка": "greater_eonite_pickaxe",
    "сэк": "greater_eonite_pickaxe",
    "войд-кирка": "void_pickaxe",
    "кирка катарсиса": "pick_catharsis",
    "наследие кирка": "legacy_pickaxe"
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
    extra_keys = [k for k in USABLE_EXTRA if inv.get(k, 0) > 0]

    if not (pick_keys or extra_keys):
        return await message.reply("У тебя нет ничего, что можно использовать 😅")

    kb = InlineKeyboardBuilder()
    for key in pick_keys + extra_keys:
        meta = PICKAXES.get(key) or ITEM_DEFS.get(
            key, {"name": key, "emoji": "🎟️"}
        )
        kb.button(
            text=f"{meta['emoji']} {meta['name']} ({inv[key]})",
            callback_data=f"use:{key}:{uid}"
        )
    kb.adjust(1)
    await message.reply("🔧 Выбери кирку/ваучер:", reply_markup=kb.as_markup())


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

    inv = {r["item"]: r["qty"] for r in await get_inventory(cid, uid)}
    if inv.get(key, 0) < 1:
        return await callback.answer("У тебя нет этого предмета ❌", show_alert=True)
    
    if key == "voucher_borsch":
        await add_item(cid, uid, "voucher_borsch", -1)
        await add_item(cid, uid, "borsch", 1)
        txt = "🎟️ Ваучер обменян — ты получил тарелку борща!"
        await callback.message.edit_text(txt)
        return await callback.answer()

    elif key == "voucher_sale":
        await add_item(cid, uid, "voucher_sale", -1)
        await db.execute("""
            UPDATE progress_local SET sale_voucher = TRUE
            WHERE chat_id=:c AND user_id=:u
        """, {"c": cid, "u": uid})
        txt = "🎫 Скид-ваучер активирован.\nСледующая покупка будет на 20 % дешевле!"
        await callback.message.edit_text(txt)
        return await callback.answer()

    elif key == "voucher_full_energy":
        await add_item(cid, uid, "voucher_full_energy", -1)
        await db.execute("""
            UPDATE progress_local
            SET energy  = 100,
                hunger  = 100
            WHERE chat_id=:c AND user_id=:u
        """, {"c": cid, "u": uid})
        txt = "💥 Полная перезарядка! Энергия и сытость восстановлены."
        await callback.message.edit_text(txt)
        return await callback.answer()
    else:
        if key not in PICKAXES:
            return await callback.answer("Такой кирки не существует 😵")
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

ADIEU_PACK_REWARDS = [
    ("coin", 15_000, 100_000),
    ("adieu_pack", 1, 2),
    ("lapis_torch", 1, 1),
    ("adieu_soul", 1, 1),
    ("sunset_ore", 1, 5),  # косметика
]
async def open_adieu_pack(cid:int, uid:int):
    txt = "🎁 Ты открываешь Сувенир‑пак «Adieu»:\n"
    for key, a, b in ADIEU_PACK_REWARDS:
        qty = random.randint(a,b) if a<b else a
        if key == "coin":
            await add_money(cid, uid, qty)
            txt += f"• 💰 Монеты: +{qty}\n"
        else:
            await add_item(cid, uid, key, qty)
            nm = ITEM_DEFS[key]["name"]; em = ITEM_DEFS[key].get("emoji","")
            txt += f"• {em} {nm}: +{qty}\n"
    return txt
