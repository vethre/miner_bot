# adieu_relics.py
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime
import random, textwrap

from bot.db_local import add_item, get_inventory, add_money, get_money
from bot.handlers.items import ITEM_DEFS
from bot.handlers.use import PICKAXES
from bot.handlers.use import open_adieu_pack  # если у тебя другая функция — поправь импорт

router = Router()

ADIEU_ACTIVE = True  # глобальный флаг финала (можешь импортировать из config)

ANGEL_EPILOGUE = (
    "🪽 <b>Adieu</b>\n"
    "Спасибо за путь. Проект уходит на паузу. "
    "Заберите сувениры: /adieu и /soul, попробуйте взорвать /core.\n"
    "Да хранит вас шахта. bid adieu."
)

# 1) /soul — конвертирует «Душу» в Кирку Катарсиса
@router.message(Command("soul"))
async def soul_cmd(m: types.Message):
    cid, uid = m.chat.id, m.from_user.id
    inv = {r["item"]: r["qty"] for r in await get_inventory(cid, uid)}
    if inv.get("adieu_soul", 0) <= 0:
        return await m.answer("🪽 У тебя нет «Души». Получи её из Adieu‑Pack.")
    await add_item(cid, uid, "adieu_soul", -1)
    # выдаём кирку (как предмет экипировки — как у тебя обычно выдается кирка)
    await add_item(cid, uid, "pick_catharsis", 1)
    await m.answer("⚔️ Ты обрёл <b>Кирку Катарсиса</b>. "
                   "Прочность ∞, +100 000% к добыче, каждая копка даёт +10 000 монет.")

# 2) /core — взрыв ядра: +100 кейсов, −300k монет (не уходим в минус)
@router.message(Command("core"))
async def core_cmd(m: types.Message):
    cid, uid = m.chat.id, m.from_user.id
    inv = {r["item"]: r["qty"] for r in await get_inventory(cid, uid)}
    if inv.get("cave_core", 0) <= 0:
        return await m.answer("🧨 Нет «Ядра Cave». Скрафти из Руды Заката и факела.")
    await add_item(cid, uid, "cave_core", -1)
    # выдача 100 кейсов (если у тебя одна сущность кейса — поменяй ключ)
    await add_item(cid, uid, "adieu_pack", 100)
    bal = await get_money(cid, uid)
    fine = min(300_000, bal)  # не уходим в минус
    await add_money(cid, uid, -fine)
    await m.answer(f"💥 <b>Ядро вспыхнуло!</b>\n+100 🎁 Adieu‑Pack, −{fine:,} монет.".replace(",", " "))

# 3) /requiem — «Упокой»: плачущее сообщение в HEX или «утёкший код»
@router.message(Command("requiem"))
async def requiem_cmd(m: types.Message):
    cid, uid = m.chat.id, m.from_user.id
    inv = {r["item"]: r["qty"] for r in await get_inventory(cid, uid)}
    if inv.get("requiem_scroll", 0) <= 0:
        return await m.answer("🕯️ Нет свитка «Упокой». Попробуй выбить в копке.")
    await add_item(cid, uid, "requiem_scroll", -1)

    if random.random() < 0.5:
        # HEX‑плач
        msg = "adieu... спасибо, что были. мы ещё вернёмся."
        hexed = msg.encode("utf-8").hex()
        return await m.answer(f"0x{hexed}")
    else:
        # «утёкший код» (эстетика VS Code)
        snippet = textwrap.dedent("""\
        // cave_core.cpp
        std::string epilogue() {
            return "Шахта спит. Мы встретимся снова. bid adieu.";
        }
        """)
        return await m.answer(f"<code>{snippet}</code>", parse_mode="HTML")

# 4) Перехват лишних команд при ADIEU_ACTIVE
ADIEU_BLOCKED = {"disassemble", "clashrank", "trackpass", "badgeshop"}

@router.message(F.text.regexp(r"^/(\w+)$"))
async def adieu_intercept(m: types.Message):
    if not ADIEU_ACTIVE:
        return
    cmd = m.text.lstrip("/").split()[0].lower()
    if cmd in ADIEU_BLOCKED:
        await m.answer(ANGEL_EPILOGUE, parse_mode="HTML")

@router.message(Command("forge_core"))
async def forge_core_cmd(m: types.Message):
    cid, uid = m.chat.id, m.from_user.id
    inv = {r["item"]: r["qty"] for r in await get_inventory(cid, uid)}
    need_ore = 10  # сколько sunset_ore нужно
    need_torch = 1 # обычный факел, поправь ключ если другой
    if inv.get("sunset_ore", 0) < need_ore or inv.get("lapis_torch", 0) < need_torch:
        return await m.answer(f"Нужно: 🌇 {need_ore}× Руды Заката и 🔥 {need_torch}× Лазурного факела.")
    await add_item(cid, uid, "sunset_ore", -need_ore)
    await add_item(cid, uid, "lapis_torch", -need_torch)
    await add_item(cid, uid, "cave_core", 1)
    await m.answer("🧨 Скрафчено: «Ядро Cave». Взорви его командой /core")

