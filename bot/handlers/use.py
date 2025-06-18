from aiogram import Router, types
from aiogram.filters import Command
import datetime as dt

from bot.db_local import cid_uid, get_inventory, db

# Опис кирок та їх бонусів
PICKAXES = {
    "wooden_pickaxe":    {"bonus": 0.1,  "name": "Дерев’яна кирка",   "emoji": "🔨"},
    "iron_pickaxe":      {"bonus": 0.15, "name": "Залізна кирка",      "emoji": "⛏️"},
    "gold_pickaxe":      {"bonus": 0.3,  "name": "Золота кирка",      "emoji": "✨"},
    "roundstone_pickaxe":{"bonus": 0.05, "name": "Круглякова кирка",  "emoji": "🔨"},
}

router = Router()

@router.message(Command("use"))
async def use_cmd(message: types.Message):
    cid, uid = await cid_uid(message)
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        return await message.reply("Як обрати кирку: /use <назва кирки>")

    key = parts[1].strip().lower()
    pick = PICKAXES.get(key)
    if not pick:
        return await message.reply(f"Немає такої кирки «{key}» 😕")

    inv = await get_inventory(cid, uid)
    have = next((r["qty"] for r in inv if r["item"] == key), 0)
    if have < 1:
        return await message.reply(f"У тебе немає {pick['name']} 🙁")

    # Оновлюємо поточну кирку
    await db.execute(
        """
        UPDATE progress_local
           SET current_pickaxe = :p
         WHERE chat_id = :c AND user_id = :u
        """,
        {"p": key, "c": cid, "u": uid}
    )

    bonus_pct = int(pick['bonus'] * 100)
    await message.reply(
        f"{pick['emoji']} Використовуєш <b>{pick['name']}</b> \n"  
        f"Бонус до дропу: +{bonus_pct}%",
        parse_mode="HTML"
    )
