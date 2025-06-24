from aiogram import types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot.db_local import get_progress, db
from bot.utils.autodelete import register_msg_for_autodelete
from .badge_defs import BADGES

async def badges_menu(message: types.Message, uid: int):
    cid = message.chat.id
    prog = await get_progress(cid, uid)
    owned = prog.get("badges_owned", []) or []
    active = prog.get("badge_active")

    user = await message.bot.get_chat(uid)
    mention = user.full_name
    text = [f"🏅 <b>Бейджи шахтёра {mention}:</b>\n"]
    kb = InlineKeyboardBuilder()

    for code, b in BADGES.items():
        is_active = (code == active)
        is_owned = code in owned

        if is_active:
            line = f"✅ {b['emoji']} <b>{b['name']}</b>"
        elif is_owned:
            line = f"{b['emoji']} {b['name']}"
        else:
            line = f"🔒 {b['emoji']} {b['name']}"

        text.append(line)

        if is_owned and not is_active:
            kb.button(text=f"Активировать «{b['name']}»", callback_data=f"badge:use:{code}")
            kb.adjust(1)

    #kb.button(text="◀ Назад", callback_data=f"dprofile:dcavepass:{uid}")

    msg = await message.answer("\n".join(text), parse_mode="HTML", reply_markup=kb.as_markup())
    register_msg_for_autodelete(message.chat.id, msg.message_id)
