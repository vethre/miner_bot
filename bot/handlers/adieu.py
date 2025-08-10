from aiogram import Router, types
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.db_local import add_item, get_inventory
from bot.handlers.use import open_adieu_pack
router = Router()

ADIEU_TEXT = (
    "✨ <b>Adieu Update</b>\n"
    "Спасибо, что были с нами. Проект уходит на паузу.\n"
    "Забери памятный набор — и до скорой встречи."
)

@router.message(Command("adieu"))
async def adieu_cmd(m: types.Message):
    cid, uid = m.chat.id, m.from_user.id
    inv = {r["item"]: r["qty"] for r in await get_inventory(cid, uid)}
    if inv.get("adieu_badge",0) > 0:
        return await m.answer("Ты уже получил памятный набор. ❤️")
    kb = InlineKeyboardBuilder()
    kb.button(text="🎗️ Забрать сувенир", callback_data=f"adieu_get:{uid}")
    await m.answer(ADIEU_TEXT, reply_markup=kb.as_markup())

@router.callback_query(lambda c: c.data.startswith("adieu_get:"))
async def adieu_get(cb: types.CallbackQuery):
    _, orig = cb.data.split(":")
    if cb.from_user.id != int(orig):
        return await cb.answer("Не для тебя 🤚", show_alert=True)
    cid, uid = cb.message.chat.id, cb.from_user.id
    inv = {r["item"]: r["qty"] for r in await get_inventory(cid, uid)}
    if inv.get("adieu_badge",0) > 0:
        return await cb.answer("Уже выдано ❤️", show_alert=True)
    # бейдж + пак
    await add_item(cid, uid, "adieu_badge", 1)
    await add_item(cid, uid, "adieu_pack", 1)
    txt = "🎗️ Выдано: Знамя «Adieu» и Сувенир‑пак.\n"
    txt += await open_adieu_pack(cid, uid)
    await cb.message.edit_text(txt)
