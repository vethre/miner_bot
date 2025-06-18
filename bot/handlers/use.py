from aiogram import Router, types
from aiogram.filters import Command
import datetime as dt

from bot.db_local import cid_uid, get_inventory, db

# Опис кирок та їх бонусів
PICKAXES = {
    "wooden_pickaxe":    {"bonus": 0.1,  "name": "дерев’яна кирка",   "emoji": "🔨"},
    "iron_pickaxe":      {"bonus": 0.15, "name": "залізна кирка",      "emoji": "⛏️"},
    "gold_pickaxe":      {"bonus": 0.3,  "name": "золота кирка",      "emoji": "✨"},
    "roundstone_pickaxe":{"bonus": 0.05, "name": "круглякова кирка",  "emoji": "🔨"},
    "crystal_pickaxe":    {"bonus": 2.5,  "name": "кристальна кирка",   "emoji": "💎"},
    "amethyst_pickaxe":    {"bonus": 0.7,  "name": "аметистова кирка",   "emoji": "✨"},
}

router = Router()

PICKAXE_ALIASES = {
    "дерев'яна кирка":    "wooden_pickaxe",
    "дерев’яна кирка":    "wooden_pickaxe",
    "залізна кирка":      "iron_pickaxe",
    "золота кирка":       "gold_pickaxe",
    "круглякова кирка":   "roundstone_pickaxe",
    "аметистова кирка":    "amethyst_pickaxe",
}

@router.message(Command("use"))
async def use_cmd(message: types.Message):
    cid, uid = await cid_uid(message)
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        return await message.reply("Як обрати кирку: /use <назва або ключ кирки>")

    user_input = parts[1].strip().lower()
    user_input = user_input.replace("'", "’")  # нормалізація апострофа

    key = PICKAXE_ALIASES.get(user_input) or (
        user_input if user_input in PICKAXES else None
    )
    if not key:
        return await message.reply(f"Немає такої кирки «{parts[1]}» 😕")

    inv = await get_inventory(cid, uid)
    have = next((r["qty"] for r in inv if r["item"] == key), 0)
    if have < 1:
        return await message.reply(f"У тебе немає {PICKAXES[key]['name']} 🙁")

    # встановлюємо кирку й міцність
    await db.execute(
        """
        UPDATE progress_local
           SET current_pickaxe = :p, pick_dur = pick_dur_max
         WHERE chat_id = :c AND user_id = :u
        """,
        {"p": key, "c": cid, "u": uid}
    )

    bonus_pct = int(PICKAXES[key]['bonus'] * 100)
    await message.reply(
        f"{PICKAXES[key]['emoji']} Використовуєш <b>{PICKAXES[key]['name']}</b>\n"
        f"Бонус до дропу: +{bonus_pct}%",
        parse_mode="HTML"
    )