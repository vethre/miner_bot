from io import BytesIO
from aiogram.types import FSInputFile
from PIL import Image, ImageDraw, ImageFont

PROFILE_BG = "bot/assets/profile.jpg"
FONT_PATH = "bot/assets/Roboto-Regular.ttf"

async def render_profile_card(bot, uid: int, nickname: str, level: int, xp: int, next_xp: int):
    photos = await bot.get_user_profile_photos(uid, limit=1)
    avatar_img = Image.new("RGBA", (256, 256), (40, 40, 40))
    if photos.total_count:
        file_id = photos.photos[0][-1].file_id
        file = await bot.get_file(file_id)
        bytes_io = await bot.download_file(file.file_path)
        avatar_img = Image.open(bytes_io).convert("RGB")

    mask = Image.new("L", (256, 256), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, 256, 256), fill=255)
    avatar_img = avatar_img.resize((256, 256), Image.Resampling.LANCZOS)

    bg = Image.open(PROFILE_BG).convert("RGBA")
    bg.paste(avatar_img, (40, 72), mask=mask)

    draw = ImageDraw.Draw(bg)
    fnt_big = ImageFont.truetype(FONT_PATH, 46)
    font_small = ImageFont.truetype(FONT_PATH, 32)

    draw.text((320, 80), nickname, font=fnt_big, fill="white")
    draw.text((320, 150), f"⭐ Уровень {level}", font=font_small, fill="white")

    bar_x, bar_y, bar_w, bar_h = 320, 220, 300, 28
    progress = int(min(1, xp / next_xp))
    draw.rounded_rectangle((bar_x, bar_y, bar_x + bar_w, bar_y + bar_h), 8, outline="white", width=2)
    draw.rounded_rectangle((bar_x, bar_y, bar_x + bar_w*progress, bar_y+bar_h), 8, fill="#4caf50")
    draw.text((bar_x, bar_y-34), f"XP {xp}/{next_xp}", font=font_small, fill="white")

    buf = BytesIO()
    bg.save(buf, format="PNG")
    buf.seek(0)
    return FSInputFile(buf, filename=f"profile_{uid}.png")