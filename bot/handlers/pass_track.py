# bot/handlers/pass_track.py
from __future__ import annotations
import datetime as dt, json
from io import BytesIO

from aiogram import Router, types, F
from aiogram.types import BufferedInputFile
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from PIL import Image, ImageDraw, ImageFont

from bot.db_local import db, cid_uid, get_progress, add_item, add_money
from bot.assets import PASS_IMG_ID          # добавьте фон-картинку в assets
from bot.utils.autodelete import register_msg_for_autodelete

router = Router()

PASS_START  = dt.datetime(2025, 7, 7, tzinfo=dt.timezone.utc)
PASS_END    = dt.datetime(2025, 7, 27, tzinfo=dt.timezone.utc)
PASS_DAYS   = (PASS_END - PASS_START).days      # 20 дн.
TOTAL_LVL   = 20
XP_PER_LVL  = 100

# -------- награды ---------------------------------------------------
#   free[x]  / premium[x]  для уровня (index==lvl-1)
REWARDS = [
# lvl  free-track                         , premium-track
# ───────────────────────────────────────────────────────────────
    ({"coins": 150},                      {"achievement": "eonite_owner"}),          #  1
    ({"item": "bread", "qty": 2},         {"coins": 400}),                           #  2
    ({"coins": 200},                      {"item": "voucher_sale", "qty": 1}),       #  3
    ({"item": "bomb", "qty": 1},          {"coins": 500}),                           #  4
    ({"coins": 250},                      {"badge": "eonite_beacon"}),               #  5
# ───────────────────────────────────────────────────────────────
    ({"item": "energy_drink", "qty": 2},  {"coins": 600}),                           #  6
    ({"coins": 300},                      {"item": "bread", "qty": 4}),              #  7
    ({"case": "cave_case", "qty": 1},     {"coins": 700}),                           #  8
    ({"coins": 350},                      {"item": "bomb", "qty": 2}),               #  9
    ({"item": "energy_drink", "qty": 1},  {"item": "proto_eonite_pickaxe", "qty": 1}),# 10
# ───────────────────────────────────────────────────────────────
    ({"coins": 400},                      {"coins": 800}),                           # 11
    ({"item": "bomb", "qty": 1},          {"item": "voucher_borsch", "qty": 1}),     # 12
    ({"coins": 450},                      {"coins": 900}),                           # 13
    ({"item": "bread", "qty": 2},         {"item": "energy_drink", "qty": 3}),       # 14
    ({"coins": 500},                      {"case": "cave_case", "qty": 3}),          # 15
# ───────────────────────────────────────────────────────────────
    ({"item": "bomb", "qty": 1},          {"coins": 1100}),                          # 16
    ({"coins": 550},                      {"item": "bomb", "qty": 2}),               # 17
    ({"item": "energy_drink", "qty": 2},  {"coins": 1200}),                          # 18
    ({"coins": 600},                      {"item": "bread", "qty": 5}),              # 19
    ({"case": "cave_case", "qty": 1},     {"item": "voucher_sale", "qty": 1,
                                           "extra": [
                                               {"case": "cave_case", "qty": 5},
                                               {"item": "eonite_shard", "qty": 3}
                                           ]}),                                      # 20
# ───────────────────────────────────────────────────────────────
    # … и так далее до 30-го уровня – заполняйте по своему вкусу
]

# ---------- шрифты ---------------------------------------------------
FONT_BIG   = ImageFont.load_default()
FONT_SMALL = ImageFont.load_default()
# --------------------------------------------------------------------
async def ensure_row(cid:int, uid:int):
    await db.execute("""
        INSERT INTO pass_progress (chat_id,user_id)
        VALUES (:c,:u)
        ON CONFLICT DO NOTHING""", {"c":cid,"u":uid})

async def add_pass_xp(cid:int, uid:int, delta:int):
    await ensure_row(cid,uid)
    row = await db.fetch_one("""
        UPDATE pass_progress
           SET xp = xp + :d
         WHERE chat_id=:c AND user_id=:u
     RETURNING xp, lvl""",
        {"d":delta,"c":cid,"u":uid})
    xp, lvl = row["xp"], row["lvl"]
    # левел-ап
    while lvl < TOTAL_LVL and xp >= XP_PER_LVL:
        lvl += 1
        xp  -= XP_PER_LVL
        await grant_level_reward(cid, uid, lvl)
    await db.execute(
        "UPDATE pass_progress SET xp=:x,lvl=:l WHERE chat_id=:c AND user_id=:u",
        {"x":xp,"l":lvl,"c":cid,"u":uid})

async def grant_level_reward(cid:int, uid:int, lvl:int):
    free, prem = REWARDS[lvl-1]
    await deliver_reward(cid, uid, free)
    row = await db.fetch_one("SELECT is_premium FROM pass_progress "
                             "WHERE chat_id=:c AND user_id=:u",
                             {"c":cid,"u":uid})
    if row["is_premium"]:
        await deliver_reward(cid, uid, prem)

async def deliver_reward(cid:int, uid:int, payload:dict):
    """
    Понимает:
      item/qty    – обычный предмет
      coins       – деньги
      case/qty    – вызвать give_case_to_user
      achievement – unlock_achievement
      badge       – выдать бейдж (badge_active)
      extra       – список payload-ов поверх основного
    """
    if not payload:
        return
    if "item" in payload:
        await add_item(cid, uid, payload["item"], payload.get("qty",1))
    elif "coins" in payload:
        await add_money(cid, uid, payload["coins"])
    elif "case" in payload:
        from bot.handlers.cases import give_case_to_user
        await give_case_to_user(cid, uid, payload["case"], payload.get("qty",1))
    elif "achievement" in payload:
        from bot.utils.unlockachievement import unlock_achievement
        await unlock_achievement(cid, uid, payload["achievement"])
    elif "badge" in payload:
        await db.execute("""
            UPDATE progress_local
               SET badge_active = :b
             WHERE chat_id=:c AND user_id=:u
        """, {"b": payload["badge"], "c": cid, "u": uid})

    # рекурсивно обрабатываем вложенный список
    if "extra" in payload and isinstance(payload["extra"], list):
        for sub in payload["extra"]:
            await deliver_reward(cid, uid, sub)

@router.message(Command("trackpass"))
async def trackpass_cmd(message: types.Message):
    cid, uid = await cid_uid(message)
    await ensure_row(cid,uid)
    row = await db.fetch_one("""
        SELECT lvl,xp,is_premium FROM pass_progress
        WHERE chat_id=:c AND user_id=:u""", {"c":cid,"u":uid})
    lvl, xp, prem = row["lvl"], row["xp"], row["is_premium"]

    # ------- рисуем карточку -----------------
    bg = Image.open("bot/assets/PREMIUM_BG.png").convert("RGBA")
    draw = ImageDraw.Draw(bg)

    # Заголовок
    draw.text((40, 30), "Cave Pass • Season 1", font=FONT_BIG, fill="white")
    draw.text((40, 90), f"До конца: {(PASS_END-dt.datetime.now(dt.timezone.utc)).days} дн.",
              font=FONT_SMALL, fill="orange")

    # шкала прогресса
    pct = (lvl + xp/XP_PER_LVL) / TOTAL_LVL
    bar_x, bar_y, bar_w, bar_h = 40, 160, 620, 28
    draw.rounded_rectangle((bar_x, bar_y, bar_x+bar_w, bar_y+bar_h),
                           radius=12, outline="white", width=3)
    draw.rounded_rectangle((bar_x, bar_y,
                            bar_x+int(bar_w*pct), bar_y+bar_h),
                           radius=12, fill="#4caf50")
    draw.text((bar_x, bar_y-36),
              f"Уровень {lvl}  •  XP {xp}/{XP_PER_LVL}",
              font=FONT_SMALL, fill="white")

    # мини-список грядущих наград (5 следующих)
    start = lvl
    lines = ["Следующие уровни:"]
    for i in range(start, min(start+5, TOTAL_LVL)):
        f, p = REWARDS[i]
        tag = "⚡" if prem else "•"
        lines.append(f"{i+1:02d}. {f.get('item','💰') or '💰'}"
                     f"{'×'+str(f.get('qty',f.get('coins')))}"
                     + (f"  {tag} {p.get('item','💰') or '💰'}×{p.get('qty',p.get('coins'))}"
                        if prem else ""))

    for n,l in enumerate(lines):
        draw.text((40, 220+n*32), l, font=FONT_SMALL, fill="white")

    # ---------- отправка ----------------------
    buf = BytesIO()
    bg.save(buf, format="PNG")
    photo_bytes = buf.getvalue()                  # <- извлекаем байты

    photo = BufferedInputFile(photo_bytes, filename="cave_pass.png")

    await message.answer_photo(
        photo,
        caption="⚒️ Твой прогресс Cave Pass"
    )

