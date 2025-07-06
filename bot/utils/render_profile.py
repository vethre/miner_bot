# bot/utils/render_profile.py
from __future__ import annotations
from io import BytesIO
from pathlib import Path
from aiogram.types import BufferedInputFile
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).parent.parent
ASSETS = ROOT / "assets"
BG_PATH = ASSETS / "profile_new.jpg"
FONT_MED_PATH = ASSETS / "Montserrat-Medium.ttf"
FONT_BIG_PATH = ASSETS / "Montserrat-SemiBold.ttf"

# Font sizes adjusted for better fit
F_MED = ImageFont.truetype(FONT_MED_PATH, 28)
F_BIG = ImageFont.truetype(FONT_BIG_PATH, 36)
F_SMALL = ImageFont.truetype(FONT_MED_PATH, 24)

# Avatar settings
AVATAR_SIZE = (200, 200)  # Slightly smaller to fit better
AVATAR_POS = (165, 140)   # Adjusted position

# Panel centering area (left sidebar)
PANEL_X0, PANEL_X1 = 50, 480  # Adjusted for better centering

def _center(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont,
           y: int, x0: int = PANEL_X0, x1: int = PANEL_X1):
    """Center text horizontally between x0 and x1"""
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    x = x0 + (x1 - x0 - text_width) // 2
    draw.text((x, y), text, font=font, fill="white")

async def render_profile_card(bot,
                            uid: int,
                            nickname: str,
                            level: int, xp: int, next_xp: int,
                            energy: int, hunger: int,
                            money: int, fire: int,
                            pick_dur: str, caves: int) -> BufferedInputFile:
    
    # 1️⃣ Load background
    bg = Image.open(BG_PATH).convert("RGBA")
    draw = ImageDraw.Draw(bg)
    
    # 2️⃣ Handle avatar (square with border)
    avatar = Image.new("RGBA", AVATAR_SIZE, (30, 30, 30, 255))
    
    try:
        photos = await bot.get_user_profile_photos(uid, limit=1)
        if photos.total_count > 0:
            fid = photos.photos[0][-1].file_id
            file_info = await bot.get_file(fid)
            f = await bot.download_file(file_info.file_path)
            avatar = Image.open(f).convert("RGBA")
            avatar = ImageOps.fit(avatar, AVATAR_SIZE, Image.Resampling.LANCZOS)
    except Exception as e:
        print(f"Error loading avatar: {e}")
        # Keep default avatar
    
    # Create border for avatar
    border_size = 6
    border = Image.new("RGBA", 
                      (AVATAR_SIZE[0] + border_size*2, AVATAR_SIZE[1] + border_size*2), 
                      (0, 0, 0, 0))
    border_draw = ImageDraw.Draw(border)
    
    # Cyan/neon border
    border_draw.rectangle((0, 0, *border.size), fill=(0, 255, 255, 255))
    # Cut out center
    border_draw.rectangle((border_size, border_size, 
                          border_size + AVATAR_SIZE[0], 
                          border_size + AVATAR_SIZE[1]), 
                         fill=(0, 0, 0, 0))
    
    # Paste border and avatar
    bg.paste(border, (AVATAR_POS[0] - border_size, AVATAR_POS[1] - border_size), border)
    bg.paste(avatar, AVATAR_POS, avatar)
    
    # 3️⃣ Username/nickname - centered below avatar
    _center(draw, nickname, F_BIG, 365)
    
    # 4️⃣ Main stats - positioned in left panel
    stats_data = [
        (f"УРОВЕНЬ {level}", 420),
        (f"{xp}/{next_xp}", 470),
        (f"{energy}/100", 540),
        (f"{hunger}/100", 590),
    ]
    
    for text, y in stats_data:
        _center(draw, text, F_MED, y)
    
    # 5️⃣ Bottom mini stats - positioned in bottom area
    # Format money to show k for thousands
    money_text = f"{money//1000}k" if money >= 1000 else str(money)
    
    mini_stats = [
        # Row 1
        (money_text, 680, 85),      # Money (bottom left)
        (str(fire), 680, 245),      # Fire (bottom left-center)
        # Row 2  
        (pick_dur, 730, 85),        # Pick durability (bottom left)
        (str(caves), 730, 245),     # Caves (bottom left-center)
    ]
    
    for text, y, x in mini_stats:
        draw.text((x, y), text, font=F_SMALL, fill="white")
    
    # 6️⃣ Save to buffer and return
    buf = BytesIO()
    bg.save(buf, format="PNG")
    buf.seek(0)
    
    return BufferedInputFile(buf.getvalue(), filename="profile.png")

# Alternative function with more precise positioning based on your template
async def render_profile_card_precise(bot,
                                    uid: int,
                                    nickname: str,
                                    level: int, xp: int, next_xp: int,
                                    energy: int, hunger: int,
                                    money: int, fire: int,
                                    pick_dur: str, caves: int) -> BufferedInputFile:
    
    bg = Image.open(BG_PATH).convert("RGBA")
    draw = ImageDraw.Draw(bg)
    
    # Avatar handling (same as above)
    avatar = Image.new("RGBA", (200, 200), (30, 30, 30, 255))
    
    try:
        photos = await bot.get_user_profile_photos(uid, limit=1)
        if photos.total_count > 0:
            fid = photos.photos[0][-1].file_id
            file_info = await bot.get_file(fid)
            f = await bot.download_file(file_info.file_path)
            avatar = Image.open(f).convert("RGBA")
            avatar = ImageOps.fit(avatar, (200, 200), Image.Resampling.LANCZOS)
    except:
        pass
    
    # Position avatar in the cyan frame area
    bg.paste(avatar, (165, 140), avatar)
    
    # Text positioning based on your template
    # These coordinates are estimated from your image
    draw.text((265, 370), nickname, font=F_BIG, fill="white", anchor="mm")
    draw.text((265, 420), f"УРОВЕНЬ {level}", font=F_MED, fill="white", anchor="mm")
    draw.text((265, 470), f"{xp}/{next_xp}", font=F_MED, fill="white", anchor="mm")
    draw.text((265, 540), f"{energy}/100", font=F_MED, fill="white", anchor="mm")
    draw.text((265, 590), f"{hunger}/100", font=F_MED, fill="white", anchor="mm")
    
    # Bottom stats - adjust these coordinates to match your icons
    money_text = f"{money//1000}k" if money >= 1000 else str(money)
    draw.text((85, 680), money_text, font=F_SMALL, fill="white")
    draw.text((245, 680), str(fire), font=F_SMALL, fill="white")
    draw.text((85, 730), pick_dur, font=F_SMALL, fill="white")
    draw.text((245, 730), str(caves), font=F_SMALL, fill="white")
    
    buf = BytesIO()
    bg.save(buf, format="PNG")
    buf.seek(0)
    
    return BufferedInputFile(buf.getvalue(), filename="profile.png")