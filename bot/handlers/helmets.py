# bot/handlers/helmet.py
from __future__ import annotations

import random
import datetime as dt
from typing import Dict, Any

from aiogram import Router, types
from aiogram.filters import Command, CommandObject
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.db_local import db, cid_uid, add_money
from bot.utils.autodelete import register_msg_for_autodelete

router = Router()

# ───────────────────── системные константы ──────────────────────────
FORGE_PRICE   = 3_000          # 💰 создать новую каску
UPGRADE_PRICE = 2_000          # 💰 повысить уровень
MAX_LVL       = 5
AUCTION_FEE   = 0.05           # пока не используется, но пригодится

# шаблоны:  строка-описание и диапазон случайного числа
EFFECT_TEMPLATES: dict[str, tuple[str, tuple[int, int]]] = {
    "energy_boost":   ("🔋 +{n} ед. энергии каждые 24 ч", (5, 20)),
    "xp_bonus":       ("📘 +{n}% опыта с копок",           (3, 12)),
    "ore_bonus":      ("⛏ +{n}% добычи руды",             (2, 15)),
    "hunger_slow":    ("🍗 Голод уменьш. на {n}%",         (10, 35)),
    "coin_bonus":     ("💰 +{n}% монет из событий",        (5, 25)),
    "crit_mine":      ("💥 {n}% шанс ×2 добыча",           (3, 12)),
    "super_event":    ("🌈 +{n}% шанс редкой ивентовой награды", (2, 8)),
    "extra_case":     ("📦 {n}% шанс получить кейс после копки", (2, 10)),
    "regen_pick":     ("♻️ +{n}% шанс восстановить 1 прочность кирки после копки", (3, 12)),
    "fatigue_resist": ("💪 -{n}% к расходу энергии при копке", (5, 20)),
    "lucky_miner":    ("🍀 +{n}% шанс найти редкую руду", (3, 10)),
}

# ───────────────────── вспом. генераторы ────────────────────────────
def _rand_serial() -> str:
    """CM-XXXX, 0-впереди возможен."""
    return f"CM-{random.randint(0, 9999):04d}"

def _rand_effect() -> tuple[str, str]:
    """
    Возвращает:
        effect_code:  xp_bonus_7
        human_text :  📘 +7% опыта с копок
    """
    key, (tpl, rng) = random.choice(list(EFFECT_TEMPLATES.items()))
    n = random.randint(*rng)
    return f"{key}_{n}", tpl.format(n=n)

def _effect_readable(code: str) -> str:
    if "_" not in code:
        return "❓ Неизвестный эффект"
    kind, n = code.split("_", 1)
    tpl = EFFECT_TEMPLATES.get(kind, ("❓", (0, 0)))[0]
    return tpl.format(n=n)

# ───────────────────── рендер каски ─────────────────────────────────
async def _format_helmet(row: Dict[str, Any], show_price: bool = True) -> str:
    txt = [
        f"⚒️ <b>Каска {row['serial']}</b>",
        f"• Уровень: <b>{row['lvl']}</b>",
        f"• Эффект: { _effect_readable(row['effect_code']) }",
        f"• Дата: {row['created_at']:%d.%m.%Y}",
    ]
    if show_price:
        txt.append(f"Стоимость апгрейда: {UPGRADE_PRICE} монет")
    return "\n".join(txt)

# ───────────────────── команды ──────────────────────────────────────
@router.message(Command("forge_helmet"))
async def forge_helmet_cmd(m: types.Message):
    cid, uid = await cid_uid(m)

    # снимаем деньги
    await add_money(cid, uid, -FORGE_PRICE)

    serial = _rand_serial()
    effect_code, _ = _rand_effect()

    row = await db.fetch_one(
        """INSERT INTO helmets
               (chat_id, user_id, serial, lvl, effect_code, created_at)
         VALUES (:c, :u, :s, 1, :e, NOW())
      RETURNING *""",
        {"c": cid, "u": uid, "s": serial, "e": effect_code},
    )

    text = (
        f"🛠 <b>Новая каска выкована!</b>\n\n"
        + await _format_helmet(dict(row))
        + f"\n\n💸 Списано {FORGE_PRICE} монет."
    )
    msg = await m.reply(text, parse_mode="HTML")
    register_msg_for_autodelete(cid, msg.message_id)

@router.message(Command("helmets"))
async def list_helmets_cmd(m: types.Message):
    cid, uid = await cid_uid(m)
    rows = await db.fetch_all(
        "SELECT * FROM helmets WHERE chat_id=:c AND user_id=:u ORDER BY created_at",
        {"c": cid, "u": uid},
    )
    if not rows:
        return await m.reply("У тебя ещё нет касок.")
    parts = [await _format_helmet(dict(r), False) for r in rows]
    await m.reply("\n\n".join(parts), parse_mode="HTML")

@router.message(Command("upgrade_helmet"))
async def upgrade_helmet_cmd(m: types.Message, command: CommandObject = None):
    cid, uid = await cid_uid(m)

    if not command.args:
        return await m.reply("Использование: /upgrade_helmet CM-1234")

    serial = command.args.strip().upper()

    row = await db.fetch_one(
        "SELECT * FROM helmets WHERE chat_id=:c AND user_id=:u AND serial=:s",
        {"c": cid, "u": uid, "s": serial},
    )
    if not row:
        return await m.reply("❌ Каска не найдена.")

    if row["lvl"] >= MAX_LVL:
        return await m.reply("🔨 Каска уже максимального уровня.")

    await add_money(cid, uid, -UPGRADE_PRICE)

    # 10 % шанс получить новый случайный эффект
    new_effect = row["effect_code"]
    if random.random() < 0.80:
        new_effect, _ = _rand_effect()

    row = await db.fetch_one(
        """UPDATE helmets
              SET lvl = lvl + 1,
                  effect_code = :e
            WHERE chat_id=:c AND user_id=:u AND serial=:s
        RETURNING *""",
        {"e": new_effect, "c": cid, "u": uid, "s": serial},
    )

    txt = (
        "<b>Каска улучшена!</b>\n\n"
        + await _format_helmet(dict(row))
        + f"\n\n💸 Списано {UPGRADE_PRICE} монет."
    )
    msg = await m.reply(txt, parse_mode="HTML")
    register_msg_for_autodelete(cid, msg.message_id)

@router.message(Command("auction_helmet"))
async def auction_helmet_cmd(m: types.Message, cmd: CommandObject = None):
    cid, uid = await cid_uid(m)

    if not (cmd and cmd.args):
        return await m.reply("Использование: /auction_helmet <code>номер цена</code>")

    args = cmd.args.split()
    if len(args) != 2:
        return await m.reply("Использование: /auction_helmet <code>номер цена</code>")

    serial, price = args[0].strip().upper(), int(args[1])
    # Найти каску игрока
    row = await db.fetch_one(
        "SELECT * FROM helmets WHERE chat_id=:c AND user_id=:u AND serial=:s AND on_auction=FALSE",
        {"c": cid, "u": uid, "s": serial},
    )
    if not row:
        return await m.reply("❌ Каска не найдена или уже на аукционе.")
    # Сделать неактивной, выставить на аукцион
    await db.execute(
        "UPDATE helmets SET on_auction=TRUE, auction_price=:p, active=FALSE WHERE id=:id",
        {"p": price, "id": row["id"]},
    )
    await m.reply(f"🪖 Каска {serial} выставлена на аукцион за {price} монет.")

@router.message(Command("buy_helmet"))
async def buy_helmet_cmd(m: types.Message, cmd: CommandObject = None):
    cid, uid = await cid_uid(m)
    if not cmd.args:
        return await m.reply("Использование: /buy_helmet <code>номер</code>")
    serial = cmd.args.strip().upper()
    row = await db.fetch_one(
        "SELECT * FROM helmets WHERE serial=:s AND on_auction=TRUE",
        {"s": serial},
    )
    if not row:
        return await m.reply("❌ Каска не найдена на аукционе.")
    if row["user_id"] == uid:
        return await m.reply("Ты не можешь купить свою же каску.")
    # Проверяем баланс
    from bot.db_local import get_money, add_money
    price = row["auction_price"]
    buyer_balance = await get_money(cid, uid)
    if buyer_balance < price:
        return await m.reply("Недостаточно монет для покупки.")
    # Деньги продавцу
    await add_money(cid, row["user_id"], price)
    # Деньги у покупателя списываем
    await add_money(cid, uid, -price)
    # Передаём каску покупателю, снимаем с аукциона
    await db.execute(
        "UPDATE helmets SET user_id=:new_uid, chat_id=:new_cid, on_auction=FALSE, active=FALSE, previous_owner=:old_uid WHERE id=:id",
        {"new_uid": uid, "new_cid": cid, "old_uid": row["user_id"], "id": row["id"]}
    )
    await m.reply(f"Покупка прошла успешно! Ты приобрёл каску {serial} за {price} монет.")

@router.message(Command("unauction_helmet"))
async def unauction_helmet_cmd(m: types.Message, cmd: CommandObject = None):
    cid, uid = await cid_uid(m)
    if not cmd.args:
        return await m.reply("Использование: /unauction_helmet <code>номер</code>")
    serial = cmd.args.strip().upper()
    row = await db.fetch_one(
        "SELECT * FROM helmets WHERE chat_id=:c AND user_id=:u AND serial=:s AND on_auction=TRUE",
        {"c": cid, "u": uid, "s": serial},
    )
    if not row:
        return await m.reply("❌ Каска не найдена или не на аукционе.")
    await db.execute(
        "UPDATE helmets SET on_auction=FALSE WHERE id=:id", {"id": row["id"]}
    )
    await m.reply(f"Каска {serial} снята с аукциона.")

@router.message(Command("my_auctioned_helmets"))
async def my_auctioned_helmets_cmd(m: types.Message):
    cid, uid = await cid_uid(m)
    rows = await db.fetch_all(
        "SELECT * FROM helmets WHERE chat_id=:c AND user_id=:u AND on_auction=TRUE",
        {"c": cid, "u": uid},
    )
    if not rows:
        return await m.reply("У тебя нет касок на аукционе.")
    lines = [f"{r['serial']} — {r['auction_price']} монет" for r in rows]
    await m.reply("\n".join(lines))
