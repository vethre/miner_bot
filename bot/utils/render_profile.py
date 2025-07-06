# bot/utils/render_profile.py
from __future__ import annotations
from io import BytesIO
from pathlib import Path

from aiogram.types import BufferedInputFile
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT   = Path(__file__).parent.parent
ASSETS = ROOT / "assets"

BG_PATH       = ASSETS / "profile_new.jpg"
FONT_MED_PATH = ASSETS / "Montserrat-Medium.ttf"
FONT_BIG_PATH = ASSETS / "Montserrat-SemiBold.ttf"

F_MED = ImageFont.truetype(FONT_MED_PATH, 30)
F_BIG = ImageFont.truetype(FONT_BIG_PATH, 40)

AVATAR_SIZE = (256, 256)
AVATAR_POS  = (234, 248)        # ⇐ точка «лево-верх» в шаблоне
PANEL_X0, PANEL_X1 = 0, 530     # область горизонтального центрирования

def _center(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont,
            y: int, x0: int = PANEL_X0, x1: int = PANEL_X1):
    w, h = draw.textbbox((0, 0), text, font=font)[2:]
    draw.text((x0 + (x1 - x0 - w)//2, y), text, font=font, fill="white")

async def render_profile_card(bot,
                              uid: int,
                              nickname: str,
                              level: int, xp: int, next_xp: int,
                              energy: int, hunger: int,
                              money: int, fire: int,
                              pick_dur: str, caves: int) -> BufferedInputFile:

    # 1️⃣ фон
    bg   = Image.open(BG_PATH).convert("RGBA")
    draw = ImageDraw.Draw(bg)

    # 2️⃣ аватар (квадрат, обводка)
    avatar = Image.new("RGBA", AVATAR_SIZE, (30, 30, 30, 255))
    photos = await bot.get_user_profile_photos(uid, limit=1)
    if photos.total_count:
        fid    = photos.photos[0][-1].file_id
        f      = await bot.download_file((await bot.get_file(fid)).file_path)
        avatar = Image.open(f).convert("RGBA")

    avatar = ImageOps.fit(avatar, AVATAR_SIZE, Image.Resampling.LANCZOS)

    # — рамка 4 px —─────────────────────────────────────────────
    border = Image.new("RGBA", (AVATAR_SIZE[0]+8, AVATAR_SIZE[1]+8), (0,0,0,0))
    bdraw  = ImageDraw.Draw(border)
    bdraw.rectangle((0,0,*border.size), fill=(0,255,255,255))          # неон
    bdraw.rectangle((4,4,4+AVATAR_SIZE[0],4+AVATAR_SIZE[1]), fill=(0,0,0,0))
    bg.paste(border, (AVATAR_POS[0]-4, AVATAR_POS[1]-4), border)
    bg.paste(avatar, AVATAR_POS)

    # 3️⃣ ник
    _center(draw, nickname, F_BIG, 445)

    # 4️⃣ строки-метрики
    rows = [
        (f"УРОВЕНЬ {level}",  525),
        (f"{xp}/{next_xp}",   595),
        (f"{energy}/100",     687),
        (f"{hunger}/100",     757),
    ]
    for txt, y in rows:
        _center(draw, txt, F_MED, y)

    # 5️⃣ мини-инфо-блок (два ряда ×2 иконки)
    mini = [
        (f"{money//1000}k",  875,  75),
        (str(fire),          875, 305),
        (pick_dur,           955,  75),
        (str(caves),         955, 305),
    ]
    for txt, y, x in mini:
        draw.text((x, y), txt, font=F_MED, fill="white")

    # 6️⃣ выдаём в буфер
    buf = BytesIO()
    bg.save(buf, format="PNG")
    return BufferedInputFile(buf.getvalue(), filename="profile.png")
