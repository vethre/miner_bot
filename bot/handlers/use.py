from aiogram import Router, types
from aiogram.filters import Command
from bot.db import get_user, get_inventory, db

PICKAXES = {
    "wooden_pickaxe": {"bonus": 0.1,  "name": "Дерев’яна кирка", "emoji": "🔨 "},
    "iron_pickaxe":   {"bonus": 0.2, "name": "Залізна кирка", "emoji": "⛏️ "},
    "gold_pickaxe":   {"bonus": 0.4, "name": "Золота кирка", "emoji": "✨ "},
}

router = Router()

@router.message(Command("use"))
async def use_cmd(message: types.Message):
    text = message.text or ""
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        return await message.reply("Як обрати кирку: /use 'назва'")

    key = parts[1].strip().lower()
    pick = PICKAXES.get(key)
    if not pick:
        return await message.reply(f"Немає такої кирки «{key}»")

    # Перевір, чи в інвентарі є ≥1
    inv = await get_inventory(message.from_user.id)
    have = {r["item"]: r["quantity"] for r in inv}.get(key, 0)
    if have < 1:
        return await message.reply(f"У тебе немає {pick['name']}")

    # Зберігаємо вибір
    await db.execute(
        "UPDATE users SET current_pickaxe = :p WHERE user_id = :uid",
        {"p": key, "uid": message.from_user.id}
    )

    return await message.reply(
        f"Використовуєш {pick['name']} 👍 (бонус до дропу: +{int(pick['bonus']*100)}%)"
    )
