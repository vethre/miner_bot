# bot/utils/render_profile.py
from __future__ import annotations
from io import BytesIO
from pathlib import Path

from aiogram.types import BufferedInputFile
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageResampling

ROOT   = Path(__file__).parent.parent
ASSETS = ROOT / "assets"
BG     = ASSETS / "profile_new.jpg"

F_MED   = ImageFont.truetype(ASSETS / "Montserrat-Medium.ttf", 30)
F_SMALL = ImageFont.truetype(ASSETS / "Montserrat-Medium.ttf", 26)

# Геометрия левой панели, «снята» по образцу
COL_CX          = 208             # центр колонки-контента
AVATAR_SZ       = 150
AVATAR_TOP      = 120
NICK_Y          = 305
SLOT_W, SLOT_H  = 290, 42
SLOT_CENTERS_Y  = (370, 420, 500, 550)       # lvl / xp / energy / hunger
# нижние 2-ряда статистики
STAT_Y1, STAT_Y2 = 685, 730
X_L,   X_R       = 115, 300                  # money|pick  /  fire|caves

def _center_txt(draw, text, cx, cy, font):
    tw, th = draw.textbbox((0, 0), text, font=font)[2:]
    draw.text((cx - tw // 2, cy - th // 2), text, font=font, fill='white')

async def render_profile_card(
    bot,
    uid:      int,
    nickname: str,
    level:    int, xp: int, next_xp: int,
    energy:   int, hunger: int,
    money:    int, fire: int,
    pick_dur: str, caves: int
) -> BufferedInputFile:

    bg  = Image.open(BG).convert('RGBA')
    dr  = ImageDraw.Draw(bg)

    # ─── АВАТАР ──────────────────────────────────────────────
    avatar = Image.new('RGBA', (AVATAR_SZ, AVATAR_SZ), (60,60,60,255))
    try:
        photos = await bot.get_user_profile_photos(uid, limit=1)
        if photos.total_count:
            f_id   = photos.photos[0][-1].file_id
            file   = await bot.get_file(f_id)
            stream = await bot.download_file(file.file_path)
            avatar = Image.open(stream).convert('RGBA')
    except Exception as e:
        print("[profile/avatar]", e)

    avatar = ImageOps.fit(avatar, (AVATAR_SZ, AVATAR_SZ), ImageResampling.LANCZOS)
    avatar_x = COL_CX - AVATAR_SZ // 2
    bg.paste(avatar, (avatar_x, AVATAR_TOP), avatar)

    # ─── НИК ────────────────────────────────────────────────
    _center_txt(dr, nickname, COL_CX, NICK_Y, F_MED)

    # ─── 4 «капсулы» ────────────────────────────────────────
    values = [
        f"УРОВЕНЬ {level}",
        f"{xp}/{next_xp}",
        f"{energy}/100",
        f"{hunger}/100",
    ]
    for y, text in zip(SLOT_CENTERS_Y, values):
        _center_txt(dr, text, COL_CX, y, F_SMALL)

    # ─── нижний блок статистики ─────────────────────────────
    money_txt = f"{money//1000}k" if money >= 1_000 else str(money)
    dr.text((X_L, STAT_Y1), money_txt, font=F_SMALL, fill='white')
    dr.text((X_R, STAT_Y1), str(fire), font=F_SMALL,   fill='white')
    dr.text((X_L, STAT_Y2), pick_dur,  font=F_SMALL,   fill='white')
    dr.text((X_R, STAT_Y2), str(caves),font=F_SMALL,   fill='white')

    # ─── ВЫВОД ──────────────────────────────────────────────
    buf = BytesIO();  bg.save(buf, format='PNG');  buf.seek(0)
    return BufferedInputFile(buf.getvalue(), filename='profile.png')
