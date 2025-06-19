# bot/handlers/use.py   (оновлений)
from aiogram import Router, types
from aiogram.filters import Command
from bot.db_local import cid_uid, get_inventory, add_item, db

PICKAXES = {              # ← як і було
    "wooden_pickaxe":  {"bonus": .10, "name": "дерев’яна кирка", "emoji": "🔨",  "dur": 75},
    "iron_pickaxe":    {"bonus": .15, "name": "залізна кирка",   "emoji": "⛏️",  "dur": 90},
    "gold_pickaxe":    {"bonus": .30, "name": "золота кирка",    "emoji": "✨",  "dur": 60},
    "roundstone_pickaxe": {"bonus": .05, "name": "круглякова кирка","emoji": "🪨","dur": 50},
    "crystal_pickaxe": {"bonus":2.50, "name":"кристальна кирка", "emoji":"💎",   "dur": 95},
    "amethyst_pickaxe":{"bonus":.70, "name":"аметистова кирка",  "emoji":"🔮",   "dur":100},
}

ALIAS = {                    # кирки українською
    "дерев'яна кирка":"wooden_pickaxe","дерев’яна кирка":"wooden_pickaxe",
    "залізна кирка":"iron_pickaxe",    "золота кирка":"gold_pickaxe",
    "круглякова кирка":"roundstone_pickaxe",
    "кристальна кирка":"crystal_pickaxe",
    "аметистова кирка":"amethyst_pickaxe",
}

router = Router()


@router.message(Command("use"))
async def use_cmd(message: types.Message):
    cid, uid = await cid_uid(message)

    # ---------- 1) парсимо аргумент ----------
    try:
        _, arg = message.text.split(maxsplit=1)
    except ValueError:
        return await message.reply("Як обрати кирку: /use <назва або ключ>")

    arg = arg.lower().replace("'", "’").strip()
    key = ALIAS.get(arg, arg)          # alias або одразу id
    if key not in PICKAXES:
        return await message.reply(f"Немає кирки «{arg}» 😕")

    # ---------- 2) перевіряємо, чи є така кирка у гравця ----------
    inv = {r["item"]: r["qty"] for r in await get_inventory(cid, uid)}
    if inv.get(key, 0) < 1:
        return await message.reply(f"У тебе немає {PICKAXES[key]['name']} 🙁")

    # ---------- 3) читаємо поточну екіп-кирку й її durability ----------
    prog = await db.fetch_one(
        "SELECT current_pickaxe, pick_dur_map, pick_dur_max_map "
        "FROM progress_local WHERE chat_id=:c AND user_id=:u",
        {"c": cid, "u": uid}
    )
    cur = prog["current_pickaxe"]
    dur_map     = prog["pick_dur_map"]     or {}
    dur_max_map = prog["pick_dur_max_map"] or {}

    # ---------- 4) повертаємо (якщо треба) попередню кирку у інвентар ----------
    if cur:                       # міг бути None
        add_item_task = add_item(cid, uid, cur, +1)      # не чекаємо – лишимо нижче

    # ---------- 5) списуємо нову з інвентаря ----------
    await add_item(cid, uid, key, -1)

    # ---------- 6) фіксуємо durability для нової (якщо ще не було) ----------
    if key not in dur_max_map:
        dur_max_map[key] = PICKAXES[key]["dur"]
    if key not in dur_map:
        dur_map[key] = dur_max_map[key]          # “повна” при першому використанні

    # ---------- 7) оновлюємо progress_local ----------
    await db.execute(
        """
        UPDATE progress_local
           SET current_pickaxe   = :p,
               pick_dur_map      = :dm,
               pick_dur_max_map  = :dmm
         WHERE chat_id = :c AND user_id = :u
        """,
        {"p": key, "dm": dur_map, "dmm": dur_max_map, "c": cid, "u": uid}
    )

    if cur:
        await add_item_task      # (тепер реально чекаємо, щоб зберегти order)

    await message.reply(
        f"{PICKAXES[key]['emoji']} Взяв <b>{PICKAXES[key]['name']}</b> "
        f"(бонус +{int(PICKAXES[key]['bonus']*100)} %)",
        parse_mode="HTML"
    )
