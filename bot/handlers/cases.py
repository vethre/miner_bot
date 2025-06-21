# bot/handlers/cases.py

CASE_POOL = [
    {"key": "stone_pack",     "weight": 25},
    {"key": "coin_pack",      "weight": 30},
    {"key": "xp_boost",       "weight": 20},
    {"key": "gold_nugget",    "weight": 10},
    {"key": "food_pack",      "weight": 8},
    {"key": "exclusive_pack", "weight": 4},
    {"key": "repair_pack",    "weight": 2},
    {"key": "rich_pack",      "weight": 1},
]

import random, json
from aiogram import Router, types
from aiogram.filters import Command
from typing import List, Dict
from bot.db_local import cid_uid, db, add_item, add_money, add_xp, get_progress
from bot.handlers.items import ITEM_DEFS

router = Router()
ADMINS = {700929765, 988127866}

async def pick_case_reward() -> dict:
    rows = await db.fetch_all("SELECT reward_key, reward_type, reward_data FROM case_rewards")
    pool = []
    for r in rows:
        w = next(p['weight'] for p in CASE_POOL if p['key'] == r['reward_key'])
        pool += [r] * w
    return random.choice(pool)

async def give_case_to_user(cid: int, uid: int, count: int=1):
    await db.execute(
      "UPDATE progress_local SET cave_cases = cave_cases + :n WHERE chat_id=:c AND user_id=:u",
      {"n": count, "c": cid, "u": uid}
    )

@router.message(Command("dcase"))
async def case_cmd(message: types.Message):
    cid, uid = await cid_uid(message)
    prog = await get_progress(cid, uid)
    if prog["cave_cases"] < 1:
        return await message.reply("У тебя нет Cave Case 😕")

    # отнимаем кейс
    await db.execute(
        "UPDATE progress_local SET cave_cases = cave_cases - 1 WHERE chat_id=:c AND user_id=:u",
        {"c": cid, "u": uid}
    )

    reward = await pick_case_reward()
    rtype = reward["reward_type"]
    # raw JSON из БД
    raw = reward["reward_data"]
    # парсим в dict
    data = raw if isinstance(raw, dict) else json.loads(raw)

    descr_parts: List[str] = []

    if rtype == "item" and "items" in data:
        for it in data["items"]:
            if "item" in it and "qty" in it:
                await add_item(cid, uid, it["item"], it["qty"])
                meta = ITEM_DEFS[it["item"]]
                descr_parts.append(f"{it['qty']}×{meta['emoji']} {meta['name']}")
            elif "coins" in it:
                await add_money(cid, uid, it["coins"])
                descr_parts.append(f"{it['coins']} монет")
            elif "xp" in it:
                await add_xp(cid, uid, it["xp"])
                descr_parts.append(f"{it['xp']} XP")

    elif rtype == "item":
        # единичный айтем
        it = data
        await add_item(cid, uid, it["item"], it["qty"])
        meta = ITEM_DEFS[it["item"]]
        descr_parts.append(f"{it['qty']}×{meta['emoji']} {meta['name']}")

    elif rtype == "coins":
        await add_money(cid, uid, data["coins"])
        descr_parts.append(f"{data['coins']} монет")

    elif rtype == "xp":
        await add_xp(cid, uid, data["xp"])
        descr_parts.append(f"{data['xp']} XP")

    descr = " + ".join(descr_parts)
    await message.reply(f"📦 Твой Cave Case открыт! Выпало: {descr}")


async def give_case_to_user(chat_id: int, user_id: int, count: int) -> None:
    """
    Збільшує лічильник cave_cases у таблиці progress_local для заданого користувача.
    """
    await db.execute(
        """
        UPDATE progress_local
           SET cave_cases = cave_cases + :cnt
         WHERE chat_id = :c AND user_id = :u
        """,
        {"cnt": count, "c": chat_id, "u": user_id},
    )

@router.message(Command("give_case"))
async def give_case_cmd(message: types.Message):
    cid, _ = await cid_uid(message)

    # Перевірка прав
    if message.from_user.id not in ADMINS:
        return await message.reply("⚠️ У вас нет прав на эту команду")

    parts = message.text.split()
    if len(parts) != 3:
        return await message.reply("Использование: /give_case 'user_id или @username' 'кол-во'")

    target, cnt_str = parts[1], parts[2]
    if not cnt_str.isdigit():
        return await message.reply("Кол-во должно быть числом")
    count = int(cnt_str)

    # Розбір ідентифікатора користувача з mention або числа
    if target.startswith('@'):
        # отримуємо user_id по юзернейму
        try:
            member = await message.bot.get_chat_member(cid, target)
            uid = member.user.id
        except Exception:
            return await message.reply("Пользователь не найден в чате")
    else:
        if not target.isdigit():
            return await message.reply("Неверный формат user_id или @username")
        uid = int(target)

    # Виконуємо нарахування кейсів
    await give_case_to_user(cid, uid, count)

    # Підтвердження
    mention = f'<a href="tg://user?id={uid}">{uid}</a>'
    return await message.reply(
        f"✅ Выдано {count} Cave Case(ов) пользователю {mention}",
        parse_mode="HTML"
    )
