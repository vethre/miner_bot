import random

ADIEU_ABSOLUTE = True

FAREWELL_PHRASES = [
    "🪽 bid adieu",
    "⚰️ Система закрывается...",
    "🕯️ Ты ощущаешь пустоту в руках.",
    "🌌 Всё обратилось в хаос.",
    "∞ Путь завершён.",
]

GLITCH_SYMBOL = ["▒", "░", "▓", "?", "𓂀", "¤", "∞"]

def glitch_text(text: str) -> str:
    return "".join(random.choice(GLITCH_SYMBOL) if random.random() < 0.2 else c for c in text)

def glitch_number(value: int) -> str:
    roll = random.random()
    if roll < 0.1:
        return "∞"
    elif roll < 0.2:
        return str(value*1000)
    elif roll < 0.3:
        return str(value * -1)
    else:
        return str(value)
    
def chaos_loot(value: int) -> int:
    roll = random.random()
    if roll < 0.05:
        return 0
    if roll < 0.1:
        return value * 1000
    elif roll < 0.15:
        return -value
    else:
        return value
    
def chaos_farewell() -> str:
    return random.choice(FAREWELL_PHRASES)

def apply_chaos_to_message(text: str) -> str:
    return glitch_text(text) + "\n" + chaos_farewell()