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

# Правильные размеры шрифтов
F_SMALL = ImageFont.truetype(FONT_MED_PATH, 24)
F_MED = ImageFont.truetype(FONT_MED_PATH, 28)
F_BIG = ImageFont.truetype(FONT_BIG_PATH, 32)

# Настройки аватара - НАМНОГО меньше!
AVATAR_SIZE = (140, 140)  # Уменьшенный размер
AVATAR_POS = (135, 125)   # Позиция в рамке

async def render_profile_card(bot,
                            uid: int,
                            nickname: str,
                            level: int, xp: int, next_xp: int,
                            energy: int, hunger: int,
                            money: int, fire: int,
                            pick_dur: str, caves: int) -> BufferedInputFile:
    
    # 1️⃣ Загружаем фон
    bg = Image.open(BG_PATH).convert("RGBA")
    draw = ImageDraw.Draw(bg)
    
    # 2️⃣ Обрабатываем аватар
    avatar = Image.new("RGBA", AVATAR_SIZE, (50, 50, 50, 255))
    
    try:
        photos = await bot.get_user_profile_photos(uid, limit=1)
        if photos.total_count > 0:
            fid = photos.photos[0][-1].file_id
            file_info = await bot.get_file(fid)
            f = await bot.download_file(file_info.file_path)
            avatar = Image.open(f).convert("RGBA")
            avatar = ImageOps.fit(avatar, AVATAR_SIZE, Image.Resampling.LANCZOS)
    except Exception as e:
        print(f"Ошибка загрузки аватара: {e}")
    
    # Вставляем аватар БЕЗ рамки (рамка уже есть в шаблоне)
    bg.paste(avatar, AVATAR_POS, avatar)
    
    # 3️⃣ Никнейм - под аватаром, выровнен по левому краю
    draw.text((135, 280), nickname, font=F_MED, fill="white")
    
    # 4️⃣ Основные характеристики - точные позиции как во втором изображении
    
    # Уровень
    draw.text((135, 320), f"УРОВЕНЬ {level}", font=F_SMALL, fill="white")
    
    # XP
    draw.text((135, 355), f"{xp}/{next_xp}", font=F_SMALL, fill="white")
    
    # Энергия (с желтой молнией)
    draw.text((175, 400), f"{energy}/100", font=F_SMALL, fill="white")
    
    # Голод (с коричневым бургером)
    draw.text((175, 435), f"{hunger}/100", font=F_SMALL, fill="white")
    
    # 5️⃣ Нижний блок статистики - две строки
    
    # Первая строка: деньги и огонь
    money_text = f"{money//1000}k" if money >= 1000 else str(money)
    draw.text((135, 485), money_text, font=F_SMALL, fill="white")  # Зеленые деньги
    draw.text((250, 485), str(fire), font=F_SMALL, fill="white")   # Желтый огонь
    
    # Вторая строка: кирка и пещеры  
    draw.text((135, 520), pick_dur, font=F_SMALL, fill="white")    # Синяя кирка
    draw.text((250, 520), str(caves), font=F_SMALL, fill="white")  # Фиолетовые пещеры
    
    # 6️⃣ Сохраняем в буфер
    buf = BytesIO()
    bg.save(buf, format="PNG")
    buf.seek(0)
    
    return BufferedInputFile(buf.getvalue(), filename="profile.png")


# Альтернативная версия с более точным позиционированием
async def render_profile_card_exact(bot,
                                  uid: int,
                                  nickname: str,
                                  level: int, xp: int, next_xp: int,
                                  energy: int, hunger: int,
                                  money: int, fire: int,
                                  pick_dur: str, caves: int) -> BufferedInputFile:
    
    bg = Image.open(BG_PATH).convert("RGBA")
    draw = ImageDraw.Draw(bg)
    
    # Аватар
    avatar = Image.new("RGBA", (140, 140), (50, 50, 50, 255))
    
    try:
        photos = await bot.get_user_profile_photos(uid, limit=1)
        if photos.total_count > 0:
            fid = photos.photos[0][-1].file_id
            file_info = await bot.get_file(fid)
            f = await bot.download_file(file_info.file_path)
            avatar = Image.open(f).convert("RGBA")
            avatar = ImageOps.fit(avatar, (140, 140), Image.Resampling.LANCZOS)
    except:
        pass
    
    # Позиционируем аватар точно в рамку
    bg.paste(avatar, (135, 125), avatar)
    
    # Текст - координаты основаны на втором изображении
    draw.text((135, 280), nickname, font=F_MED, fill="white")
    
    # Характеристики с иконками (позиции иконок уже есть в шаблоне)
    draw.text((165, 320), f"УРОВЕНЬ {level}", font=F_SMALL, fill="white")
    draw.text((165, 355), f"{xp}/{next_xp}", font=F_SMALL, fill="white")
    draw.text((175, 400), f"{energy}/100", font=F_SMALL, fill="white")
    draw.text((175, 435), f"{hunger}/100", font=F_SMALL, fill="white")
    
    # Нижние статистики
    money_text = f"{money//1000}k" if money >= 1000 else str(money)
    draw.text((175, 485), money_text, font=F_SMALL, fill="white")
    draw.text((290, 485), str(fire), font=F_SMALL, fill="white")
    draw.text((175, 520), pick_dur, font=F_SMALL, fill="white")
    draw.text((290, 520), str(caves), font=F_SMALL, fill="white")
    
    buf = BytesIO()
    bg.save(buf, format="PNG")
    buf.seek(0)
    
    return BufferedInputFile(buf.getvalue(), filename="profile.png")