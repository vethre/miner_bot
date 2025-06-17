# bot/handlers/items.py

# Руди
ORE_ITEMS = {
    "stone": {"name": "Камінь",       "emoji": "🪨"},
    "coal":  {"name": "Вугілля",      "emoji": "🧱"},
    "iron":  {"name": "Залізна руда", "emoji": "⛏️"},
    "gold":  {"name": "Золото",       "emoji": "🪙"},
}

# Рецепти переплавки (ті ж, що й раніше)
SMELT_RECIPES = {
    "iron":  {"in_qty": 3,  "out_key": "iron_ingot",  "out_name": "Залізний злиток"},
    "stone": {"in_qty": 10, "out_key": "roundstone",   "out_name": "Кругляк"},
    "gold":  {"in_qty": 2,  "out_key": "gold_ingot",   "out_name": "Золотий злиток"},
}

# Рецепти крафту
CRAFT_RECIPES = {
    "круглякова кирка": {
        "in": {"roundstone": 12, "wood_handle": 1},
        "out_key": "roundstone_pickaxe",
        "out_name": "Круглякова кирка",
    },
    "залізна кирка": {
        "in": {"iron_ingot": 10, "wood_handle": 1},
        "out_key": "iron_pickaxe",
        "out_name": "Залізна кирка",
    },
    "золота кирка": {
        "in": {"gold_ingot": 7, "wood_handle": 1},
        "out_key": "gold_pickaxe",
        "out_name": "Золота кирка",
    },
}

# Опис готових айтемів, зливаємо всі разом
ITEM_DEFS = {}

# Додаємо ру­ду
for key, val in ORE_ITEMS.items():
    ITEM_DEFS[key] = val.copy()

# Додаємо інготи
for rec in SMELT_RECIPES.values():
    ITEM_DEFS[rec["out_key"]] = {"name": rec["out_name"], "emoji": ""}

# Додаємо кирки та інші крафт-предмети
for rec in CRAFT_RECIPES.values():
    ITEM_DEFS[rec["out_key"]] = {"name": rec["out_name"], "emoji": ""}

# Додати ручку
ITEM_DEFS["wood_handle"] = {"name": "Рукоять", "emoji": "🪵"}
# І магазинні товари, їжа, бустери тощо:
ITEM_DEFS["bread"] = {"name": "Хліб", "emoji": "🍞"}
ITEM_DEFS["meat"] = {"name": "М'со", "emoji": "🍖"}

EXTRA_ORES = {
    "amethyst": {"name": "Аметист",  "emoji": "💜", "drop_range": (1,2), "price": 40},
    "diamond":  {"name": "Діамант",  "emoji": "💎", "drop_range": (1,1), "price": 60},
    "emerald":  {"name": "Смарагд",  "emoji": "💚", "drop_range": (1,2), "price": 55},
    "lapis":    {"name": "Лазурит",  "emoji": "🔵", "drop_range": (2,4), "price": 35},
    "ruby":     {"name": "Рубін",    "emoji": "❤️", "drop_range": (1,2), "price": 50},
}

ORE_ITEMS.update(EXTRA_ORES)
for k, v in EXTRA_ORES.items():
    ITEM_DEFS[k] = v         # щоб /inventory їх знав

ALIASES = {
    "камінь": "stone",
    "вугілля": "coal",
    "залізна руда": "iron",
    "залізо": "iron",
    "золото": "gold",
    "аметист": "amethyst",
    "діамант": "diamond",
    "смарагд": "emerald",
    "лазурит": "lapis",
    "рубин":   "ruby",

    "💎": "diamond",
    "💚": "emerald",
    "💜": "amethyst",
}
