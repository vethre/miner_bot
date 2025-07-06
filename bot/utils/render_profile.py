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

# шрифты
F_SMALL = ImageFont.truetype(FONT_MED_PATH, 24)
F_MED   = ImageFont.truetype(FONT_MED_PATH, 28)

# аватар
AVATAR_SIZE = (226, 226)  # размер аватара
AVATAR_POS  = (232, 248)

NICK_POS   = (295, 459)

LVL_POS    = (260, 542)    
XP_POS     = (260, 620)    

ENERGY_POS = (265, 760)    
HUNGER_POS = (265, 838)    

MONEY_POS  = (255, 945)
FIRE_POS   = (424, 945)

PICK_POS   = (255, 1005)
CAVES_POS  = (424, 1005)
# ─────────────────────────────────────────────────

async def render_profile_card(
    bot,
    uid: int,
    nickname: str,
    level: int, xp: int, next_xp: int,
    energy: int, hunger: int,
    money: int, fire: int,
    pick_dur: str, caves: int
) -> BufferedInputFile:

    # 1. фон
    bg   = Image.open(BG_PATH).convert("RGBA")
    draw = ImageDraw.Draw(bg)

    # 2. аватар
    avatar = Image.new("RGBA", AVATAR_SIZE, (40, 40, 40, 255))
    try:
        photos = await bot.get_user_profile_photos(uid, limit=1)
        if photos.total_count:
            fid = photos.photos[0][-1].file_id
            file_info = await bot.get_file(fid)
            f = await bot.download_file(file_info.file_path)
            avatar = Image.open(f).convert("RGBA")
    except Exception:
        pass

    avatar = ImageOps.fit(avatar, AVATAR_SIZE, Image.Resampling.LANCZOS)
    bg.paste(avatar, AVATAR_POS, avatar)

    # 3. текст
    draw.text(NICK_POS, nickname, font=F_MED, fill="white")

    draw.text(LVL_POS,    f"УРОВЕНЬ {level}", font=F_SMALL, fill="white")
    draw.text(XP_POS,     f"{xp}/{next_xp}",  font=F_SMALL, fill="white")
    draw.text(ENERGY_POS, f"{energy}/100",    font=F_SMALL, fill="white")
    draw.text(HUNGER_POS, f"{hunger}/100",    font=F_SMALL, fill="white")

    money_txt = f"{money//1000}k" if money >= 1000 else str(money)
    draw.text(MONEY_POS, money_txt, font=F_SMALL, fill="white")
    draw.text(FIRE_POS,  str(fire), font=F_SMALL, fill="white")

    draw.text(PICK_POS,  pick_dur,  font=F_SMALL, fill="white")
    draw.text(CAVES_POS, str(caves), font=F_SMALL, fill="white")

    # 4. в буфер
    buf = BytesIO()
    bg.save(buf, format="PNG")
    buf.seek(0)
    return BufferedInputFile(buf.getvalue(), filename="profile.png")
