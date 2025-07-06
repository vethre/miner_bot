from __future__ import annotations
from io import BytesIO
from pathlib import Path
from aiogram.types import BufferedInputFile
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).parent.parent
ASSETS = ROOT / "assets"
BG_PATH = ASSETS / "profile_new.jpg"
# Updated font sizes to better match the template's visual scale
F_MED = ImageFont.truetype(ASSETS / "Montserrat-Medium.ttf", 30) # Slightly smaller
F_BIG = ImageFont.truetype(ASSETS / "Montserrat-SemiBold.ttf", 40) # Slightly smaller

# ──────────────────────────────────────────────────────────────────────────
def _center(draw, txt, font, y, x_start, x_end):
    """
    Centers text horizontally within a given bounding box.
    x_start: Left boundary of the centering area.
    x_end: Right boundary of the centering area.
    """
    w, h = draw.textbbox((0, 0), txt, font=font)[2:]
    draw.text((x_start + (x_end - x_start - w) // 2, y), txt, font=font, fill="white")


async def render_profile_card(bot, uid: int, nickname: str,
                              level: int, xp: int, next_xp: int,
                              energy: int, hunger: int,
                              money: int, fire: int,
                              pick_dur: str, caves: int) -> BufferedInputFile:
    """Возвращает BufferedInputFile с готовой картинкой профиля."""

    # 1️⃣ фон-шаблон
    bg = Image.open(BG_PATH).convert("RGBA")
    draw = ImageDraw.Draw(bg)

    # 2️⃣ аватар (квадрат 256×256) → позиция (175, 140) - Confirmed from visual
    avatar_size = (256, 256)
    avatar_pos = (175, 140) # Top-left corner of the avatar circle bounding box
    
    avatar = Image.new("RGBA", avatar_size, (30, 30, 30, 255))
    photos = await bot.get_user_profile_photos(uid, limit=1)
    if photos.total_count:
        file_id = photos.photos[0][-1].file_id
        f = await bot.download_file((await bot.get_file(file_id)).file_path)
        avatar = Image.open(f).convert("RGBA")

    # Fit avatar to a square, then apply round mask
    avatar = ImageOps.fit(avatar, avatar_size, Image.Resampling.LANCZOS)
    mask = Image.new("L", avatar_size, 0)
    ImageDraw.Draw(mask).ellipse((0, 0, avatar_size[0], avatar_size[1]), fill=255)

    # Apply the mask to the avatar
    alpha_composite = Image.composite(avatar, Image.new("RGBA", avatar_size, (0, 0, 0, 0)), mask)
    bg.paste(alpha_composite, avatar_pos, alpha_composite)

    # 2.1 Аватар: неоновая обводка (4px толщиной, цвет Cyan neon)
    border_color = (0, 255, 255, 255)  # Cyan neon (R, G, B, Alpha)
    border_width = 4

    # Draw the border. We draw slightly larger ellipses to create the border effect.
    # The outer boundary of the border will be at avatar_pos[0] - border_width, etc.
    # The inner boundary will be at avatar_pos[0] + avatar_size[0], etc.
    
    # Create a temporary image for the border to draw it cleanly
    border_img = Image.new("RGBA", bg.size, (0,0,0,0))
    border_draw = ImageDraw.Draw(border_img)

    # Outer ellipse for the border
    border_draw.ellipse(
        (avatar_pos[0] - border_width,
         avatar_pos[1] - border_width,
         avatar_pos[0] + avatar_size[0] + border_width,
         avatar_pos[1] + avatar_size[1] + border_width),
        fill=border_color
    )

    # Inner ellipse to cut out the center, leaving only the border
    border_draw.ellipse(
        (avatar_pos[0],
         avatar_pos[1],
         avatar_pos[0] + avatar_size[0],
         avatar_pos[1] + avatar_size[1]),
        fill=(0,0,0,0) # Transparent fill to cut out the middle
    )
    
    bg.paste(border_img, (0,0), border_img) # Paste the border onto the background

    # 3️⃣ ник (по центру панели)
    # The panel for the nickname appears to span from X ~ 0 to X ~ 530-540.
    # Let's adjust for visual centering within that range.
    nickname_panel_x_start = 0
    nickname_panel_x_end = 530 # Still seems to be the target width
    _center(draw, nickname, F_BIG, 400, nickname_panel_x_start, nickname_panel_x_end)

    # 4️⃣ строки-метрики (текст без иконок – сами плашки уже на фоне)
    # The centering area for these metrics seems to be the same as the nickname.
    metric_panel_x_start = 0
    metric_panel_x_end = 530 # Consistent with nickname panel

    # Adjusted Y coordinates based on the template image
    rows = [
        (f"УРОВЕНЬ {level}", 495),
        (f"{xp}/{next_xp}", 565),
        (f"{energy}/100", 657),
        (f"{hunger}/100", 727),
    ]
    for txt, y in rows:
        _center(draw, txt, F_MED, y, metric_panel_x_start, metric_panel_x_end)

    # 5️⃣ мини-блок (два ряда по 2, координаты под макет)
    # These are not centered but rather left-aligned within smaller, implicit boxes.
    # We need to find their precise left-aligned X coordinates and Y coordinates.
    # Based on visual inspection of your image:
    mini = [
        (f"{money//1000}k", 845, 75),  # Adjusted X
        (str(fire),          845, 305), # Adjusted X
        (pick_dur,           925, 75),  # Adjusted X
        (str(caves),         925, 305), # Adjusted X
    ]
    for txt, y, x in mini:
        draw.text((x, y), txt, font=F_MED, fill="white")

    # 6️⃣ → буфер
    buf = BytesIO()
    bg.save(buf, format="PNG")
    return BufferedInputFile(buf.getvalue(), filename="profile.png")