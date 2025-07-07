from __future__ import annotations
import datetime as dt, json
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.assets import PASS_IMG_ID
from bot.db_local import db, cid_uid, get_progress
from bot.handlers.items import ITEM_DEFS
from bot.handlers.use import PICKAXES
from bot.utils.unlockachievement import unlock_achievement

router = Router()

# ─────────── сезон и сроки ───────────────────────────────────────────────
PASS_START  = dt.datetime(2025, 7, 7, 0, 0, tzinfo=dt.timezone.utc)
PASS_END    = dt.datetime(2025, 7, 27, 23, 59, 59, tzinfo=dt.timezone.utc)
PASS_DAYS   = (PASS_END.date() - PASS_START.date()).days            # 20
PASS_PRICE_STARS = 130                                             # ≈ 53 ₴

# ─────────── эксклюзивная кирка и метаданные ────────────────────────────
EX_KEY   = "proto_eonite_pickaxe"
EX_EMOJI = "🧿"
EX_NAME  = "Прототип Эонитовой Кирки"
PICKAXES.setdefault(EX_KEY,
    {"name": EX_NAME, "emoji": EX_EMOJI, "bonus": 1.0, "dur": 250})
ITEM_DEFS.setdefault(EX_KEY,
    {"name": EX_NAME, "emoji": EX_EMOJI})

# ─────────── /cavepass ──────────────────────────────────────────────────
@router.message(Command("cavepass"))
async def cavepass_cmd(m: types.Message):
    cid, uid = await cid_uid(m)
    prog = await get_progress(cid, uid)
    now = dt.datetime.now(dt.timezone.utc)

    has_pass  = prog.get("cave_pass")
    expires   = prog.get("pass_expires") or PASS_END
    active    = has_pass and expires > now

    kb = InlineKeyboardBuilder()

    if not active:
        # кнопка-инвойс (Stars)
        kb.button(
            text=f"💳 Купить за {PASS_PRICE_STARS} ⭐",
            callback_data=f"buy_pass:{uid}"
        )
        txt = (
            "<b>Cave Pass S-1 • Пробуждение Эонита</b>\n\n"
            f"{EX_EMOJI} Экскл. кирка — <b>{EX_NAME}</b>\n"
            "×1.5 XP за копку • +10 XP/ч\n"
            "Премиальные награды на пути (30 ур.)\n\n"
            f"Стоимость: <b>{PASS_PRICE_STARS} ⭐</b>"
        )
    else:
        left = (expires.date() - now.date()).days
        txt = (
            "✅ <b>Cave Pass активирован</b>\n"
            f"Действует ещё <b>{left}</b> дн.\n"
            f"Кирка: {EX_EMOJI} <b>{EX_NAME}</b>"
        )

    await m.answer_photo(
        PASS_IMG_ID,      # статичный баннер-картинка
        caption=txt, parse_mode="HTML",
        reply_markup=kb.as_markup()
    )

# ─────────── invoice генератор ───────────────────────────────────────────
@router.callback_query(F.data.startswith("buy_pass:"))
async def invoice_cb(cb: types.CallbackQuery):
    await cb.answer()
    _, uid_str = cb.data.split(":")
    if cb.from_user.id != int(uid_str):
        return await cb.answer("Не для тебя 🤚", show_alert=True)

    title = "Cave Pass • Season 1"
    desc  = "Доступ к премиальному пути + эксклюзивная кирка"
    prices = [types.LabeledPrice(label="Cave Pass", amount=PASS_PRICE_STARS*100)]

    await cb.message.answer_invoice(
        title=title,
        description=desc,
        provider_token="",
        payload="cavepass_purchase",
        currency="XTR",
        prices=prices,
        max_tip_amount=0
    )

# ─────────── обработчик успешной оплаты ─────────────────────────────────
@router.message(F.successful_payment)
async def pass_paid(msg: types.Message):
    cid, uid = msg.chat.id, msg.from_user.id

    if msg.successful_payment.invoice_payload != "cavepass_purchase":
        return 

    # 1. В progress_local
    await db.execute("""
        UPDATE progress_local
           SET cave_pass     = TRUE,
               pass_expires  = :exp
         WHERE chat_id=:c AND user_id=:u
    """, {"exp": PASS_END, "c": cid, "u": uid})

    # 2. В pass_progress
    await db.execute("""
        INSERT INTO pass_progress (chat_id,user_id,is_premium)
             VALUES (:c,:u,TRUE)
        ON CONFLICT (chat_id,user_id)
        DO UPDATE SET is_premium = TRUE
    """, {"c": cid, "u": uid})

    # 3. Выдаём кирку (если нет) и чиним/ставим
    await db.execute("""
        INSERT INTO inventory_local (chat_id,user_id,item,qty)
             VALUES (:c,:u,:it,1)
        ON CONFLICT (chat_id,user_id,item)
        DO NOTHING
    """, {"c": cid, "u": uid, "it": EX_KEY})

    dur = PICKAXES[EX_KEY]["dur"]
    await db.execute("""
        UPDATE progress_local
           SET current_pickaxe=:it,
               pick_dur_map = jsonb_set(
                     COALESCE(pick_dur_map,'{}'::jsonb),
                     '{%s}',       
                     to_jsonb(:d)::jsonb, 
                     TRUE),
               pick_dur_max_map = jsonb_set(
                     COALESCE(pick_dur_max_map,'{}'::jsonb),
                     '{%s}',
                     to_jsonb(:d)::jsonb,
                     TRUE),
               pick_dur_max_map = jsonb_set(
                     COALESCE(pick_dur_max_map,'{}'::jsonb),
                     '{%s}',
                     to_jsonb(:d)::jsonb,
                     TRUE)
         WHERE chat_id=:c AND user_id=:u
    """ % (EX_KEY, EX_KEY), {"it": EX_KEY, "d": dur, "c": cid, "u": uid})

    # 4. Ачивка
    await unlock_achievement(cid, uid, "eonite_owner")

    await msg.reply("🎉 Cave Pass активирован! Приятной игры ☺️")
