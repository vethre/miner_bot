from io import BytesIO
from aiogram.types import BufferedInputFile           # ← нужный класс
from PIL import Image, ImageDraw, ImageFont

PROFILE_BG = "bot/assets/profile_bg.jpg"
FONT_PATH   = "bot/assets/Montserrat-Medium.ttf"
FONT_BIG_PATH = "bot/assets/Montserrat-SemiBold.ttf"

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
    f_big   = ImageFont.truetype(FONT_BIG_PATH, 54)
    f_medium = ImageFont.truetype(FONT_PATH, 32)
    f_small = ImageFont.truetype(FONT_PATH, 28)

    draw.text((320, 80),  nickname,        font=f_big,   fill="white")
    draw.text((320, 150), f"Уровень {level}", font=f_medium, fill="white")

    BAR_X, BAR_Y = 320, 225           # точка-лево-верх
    BAR_W, BAR_H = 360, 40            # ширина/высота (было 300×28)

    progress = xp / max(next_xp, 1)   # защита от next_xp==0
    inner_w  = int(BAR_W * progress)

    # рамка
    draw.rounded_rectangle(
        (BAR_X, BAR_Y, BAR_X + BAR_W, BAR_Y + BAR_H),
        radius=BAR_H // 2,            # чтобы края были полукруглые
        outline="white",
        width=3
    )
    # заливка
    draw.rounded_rectangle(
        (BAR_X, BAR_Y, BAR_X + inner_w, BAR_Y + BAR_H),
        radius=BAR_H // 2,
        fill="#4caf50"
    )

    # подпись прямо НА бары, чтобы не занимать место сверху
    txt = f"XP {xp}/{next_xp}"
    bbox = draw.textbbox((0, 0), txt, font=f_small)   # (x0, y0, x1, y1)
    tw  = bbox[2] - bbox[0]
    th  = bbox[3] - bbox[1]
    draw.text(
        (BAR_X + (BAR_W - tw) // 2,   # центрируем по X
        BAR_Y + (BAR_H - th) // 2),  # центрируем по Y
        txt,
        font=f_small,
        fill="white"
    )

    # ─── 4. В Telegram ─────────────────────────────────
    buf = BytesIO()
    bg.save(buf, format="PNG")
    file = BufferedInputFile(buf.getvalue(), filename="profile.png")   # ✔ правильно

    return file
