from io import BytesIO
from aiogram.types import BufferedInputFile           # ← нужный класс
from PIL import Image, ImageDraw, ImageFont

PROFILE_BG = "bot/assets/profile_bg.jpg"
FONT_PATH   = "bot/assets/Roboto.ttf"

async def render_profile_card(bot, uid: int, nickname: str,
                              level: int, xp: int, next_xp: int):
    # ─── 1. Аватар ─────────────────────────────────────
    avatar_img = Image.new("RGB", (256, 256), (40, 40, 40))     # дефолт-заглушка
    photos = await bot.get_user_profile_photos(uid, limit=1)
    if photos.total_count:
        file_id  = photos.photos[0][-1].file_id                 # самое большое
        tg_file  = await bot.get_file(file_id)
        bytes_io = await bot.download_file(tg_file.file_path)
        avatar_img = Image.open(bytes_io).convert("RGB")

    avatar_img = avatar_img.resize((256, 256), Image.Resampling.LANCZOS)
    mask = Image.new("L", (256, 256), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, 256, 256), fill=255)

    # ─── 2. Фон ────────────────────────────────────────
    bg = Image.open(PROFILE_BG).convert("RGBA")
    bg.paste(avatar_img, (40, 72), mask)

    # ─── 3. Текст / XP-бар ─────────────────────────────
    draw = ImageDraw.Draw(bg)
    f_big   = ImageFont.truetype(FONT_PATH, 46)
    f_small = ImageFont.truetype(FONT_PATH, 32)

    draw.text((320, 80),  nickname,        font=f_big,   fill="white")
    draw.text((320, 150), f"⭐ Уровень {level}", font=f_small, fill="white")

    bar_x, bar_y, bar_w, bar_h = 320, 220, 300, 28
    progress = min(1, xp / next_xp or 1)
    draw.rounded_rectangle((bar_x, bar_y, bar_x+bar_w, bar_y+bar_h),
                           radius=8, outline="white", width=2)
    draw.rounded_rectangle((bar_x, bar_y, bar_x+bar_w*progress, bar_y+bar_h),
                           radius=8, fill="#4caf50")
    draw.text((bar_x, bar_y-34), f"XP {xp}/{next_xp}", font=f_small, fill="white")

    # ─── 4. В Telegram ─────────────────────────────────
    buf = BytesIO()
    bg.save(buf, format="PNG")
    file = BufferedInputFile(buf.getvalue(), filename="profile.png")   # ✔ правильно

    return file
