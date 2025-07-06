# bot/utils/profile_card.py   («облегчённая» версия)

from __future__ import annotations
from io import BytesIO
from pathlib import Path
from aiogram.types import BufferedInputFile
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT     = Path(__file__).parent.parent
ASSETS   = ROOT / "assets"
BG_PATH  = ASSETS / "profile_new.jpg"          # тот самый пустой макет
F_MED    = ImageFont.truetype(ASSETS / "Montserrat-Medium.ttf", 32)
F_BIG    = ImageFont.truetype(ASSETS / "Montserrat-SemiBold.ttf", 42)

# ──────────────────────────────────────────────────────────────────────────
def _center(draw: ImageDraw.ImageDraw, txt: str, font, x0: int, x1: int, y: int):
    """Нарисовать txt по центру между x0 и x1."""
    w, h = draw.textbbox((0, 0), txt, font=font)[2:]
    draw.text((x0 + (x1 - x0 - w)//2, y), txt, font=font, fill="white")

async def render_profile_card(bot, uid: int, nickname: str,
                              level: int, xp: int, next_xp: int,
                              energy: int, hunger: int,
                              money: int, fire: int,
                              pick_dur: str, caves: int) -> BufferedInputFile:
    """Возвращает BufferedInputFile с готовой картинкой профиля."""

    # 1️⃣ фон-шаблон
    bg = Image.open(BG_PATH).convert("RGBA")
    draw = ImageDraw.Draw(bg)

    # 2️⃣ аватар (круг 256×256) → позиция (137,120) как в примере
    avatar = Image.new("RGBA", (256, 256), (30, 30, 30, 255))
    photos = await bot.get_user_profile_photos(uid, limit=1)
    if photos.total_count:
        file_id  = photos.photos[0][-1].file_id
        f        = await bot.download_file((await bot.get_file(file_id)).file_path)
        avatar   = Image.open(f).convert("RGBA")
    avatar = ImageOps.fit(avatar, (256, 256), Image.Resampling.LANCZOS)
    mask   = Image.new("L", (256, 256), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, 256, 256), fill=255)
    bg.paste(avatar, (137, 120), mask)

    # 3️⃣ ник (по центру панели 530 px) – координаты подбирались вручную
    _center(draw, nickname, F_BIG, 0, 530, 400)

    # 4️⃣ строки-метрики (текст без иконок – сами плашки уже на фоне)
    #    координаты Y – из макета; X-центрируем в границах панели
    rows = [
        (f"УРОВЕНЬ {level}",            475),
        (f"{xp}/{next_xp}",             545),
        (f"{energy}/100",               637),
        (f"{hunger}/100",               707),
    ]
    for txt, y in rows:
        _center(draw, txt, F_MED, 0, 530, y)

    # 5️⃣ мини-блок (два ряда по 2, координаты под макет)
    mini = [
        (f"{money//1000}k",  825,  70),   # деньги
        (str(fire),          825, 300),   # 🔥
        (pick_dur,           905,  70),   # кирка
        (str(caves),         905, 300),   # кейсы
    ]
    for txt, y, x in mini:
        draw.text((x, y), txt, font=F_MED, fill="white")

    # 6️⃣ → буфер
    buf = BytesIO()
    bg.save(buf, format="PNG")
    return BufferedInputFile(buf.getvalue(), filename="profile.png")
