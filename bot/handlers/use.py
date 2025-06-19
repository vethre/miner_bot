# bot/handlers/use.py
import json
from aiogram import Router, types
from aiogram.filters import Command
from difflib import get_close_matches

from bot.db_local import cid_uid, get_inventory, add_item, db

PICKAXES = {
    "wooden_pickaxe":  {"bonus": .10, "name": "дерев’яна кирка",  "emoji": "🔨", "dur": 75},
    "iron_pickaxe":    {"bonus": .15, "name": "залізна кирка",    "emoji": "⛏️", "dur": 90},
    "gold_pickaxe":    {"bonus": .30, "name": "золота кирка",     "emoji": "✨", "dur": 60},
    "roundstone_pickaxe": {"bonus": .05, "name": "круглякова кирка","emoji":"🪨","dur": 50},
    "crystal_pickaxe": {"bonus": 1.5, "name": "кристальна кирка", "emoji": "💎", "dur": 95},
    "amethyst_pickaxe":{"bonus": .70, "name": "аметистова кирка", "emoji": "🔮", "dur":100},
}

raw_dur_map  = prog["pick_dur_map"]      or {}
raw_dur_max  = prog["pick_dur_max_map"]  or {}

def to_dict(raw):
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)       # ← перетворити JSON-рядок на dict
        except json.JSONDecodeError:
            return {}
    return dict(raw)                     # fallback для інших типів

dur_map     = to_dict(raw_dur_map)
dur_max_map = to_dict(raw_dur_max)

# --- alias-и (і укр, і «коротко» без _pickaxe) ---------------
ALIAS = {
    # full UKR
    "дерев’яна кирка": "wooden_pickaxe",
    "залізна кирка":   "iron_pickaxe",
    "золота кирка":    "gold_pickaxe",
    "круглякова кирка":"roundstone_pickaxe",
    "кристальна кирка":"crystal_pickaxe",
    "аметистова кирка":"amethyst_pickaxe",
    # shorthand ENG
    "wooden": "wooden_pickaxe",
    "iron":   "iron_pickaxe",
    "gold":   "gold_pickaxe",
    "round":  "roundstone_pickaxe",
    "crystal":"crystal_pickaxe",
    "amethyst":"amethyst_pickaxe",
}

router = Router()

def resolve_key(raw: str) -> str | None:
    """Повертає id кирки або None."""
    raw = raw.lower().replace("'", "’").strip()
    if raw in ALIAS:
        return ALIAS[raw]
    if not raw.endswith("_pickaxe"):
        raw += "_pickaxe"
    if raw in PICKAXES:
        return raw
    # fuzzy-match (допомагає при помилках в 1-2 літерах)
    closest = get_close_matches(raw, PICKAXES.keys(), n=1, cutoff=0.8)
    return closest[0] if closest else None


@router.message(Command("use"))
async def use_cmd(message: types.Message):
    cid, uid = await cid_uid(message)

    try:
        _, arg = message.text.split(maxsplit=1)
    except ValueError:
        return await message.reply("Як обрати кирку: <code>/use назва</code>")

    key = resolve_key(arg)
    if not key:
        return await message.reply(f"Не знаю такої кирки «{arg}» 😕")

    # ---------- перевіряємо інвентар ----------
    inv = {r["item"]: r["qty"] for r in await get_inventory(cid, uid)}
    if inv.get(key, 0) < 1:
        return await message.reply(f"У тебе немає {PICKAXES[key]['name']} 🙁")

    # ---------- дістаємо прогрес ----------
    prog = await db.fetch_one(
        "SELECT current_pickaxe, pick_dur_map, pick_dur_max_map "
        "FROM progress_local WHERE chat_id=:c AND user_id=:u",
        {"c": cid, "u": uid}
    )
    cur          = prog["current_pickaxe"]
    dur_map      = dict(prog["pick_dur_map"] or {})
    dur_max_map  = dict(prog["pick_dur_max_map"] or {})

    # ---------- повертаємо попередню кирку ----------
    if cur:
        await add_item(cid, uid, cur, +1)

    # ---------- списуємо нову ----------
    await add_item(cid, uid, key, -1)

    # ---------- durability -------------
    if key not in dur_max_map:
        dur_max_map[key] = PICKAXES[key]["dur"]
    if key not in dur_map:
        dur_map[key] = dur_max_map[key]

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

    pct = int(PICKAXES[key]['bonus'] * 100)
    await message.reply(
        f"{PICKAXES[key]['emoji']} Тепер у руці <b>{PICKAXES[key]['name']}</b> "
        f"(бонус +{pct}% до дропу)",
        parse_mode="HTML"
    )
