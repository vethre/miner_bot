# bot/handlers/items.py

# Руди
ORE_ITEMS = {
    "stone": {"name": "Камень",       "emoji": "🪨", "price": 2},
    "coal":  {"name": "Уголь",      "emoji": "🧱", "price": 5},
    "iron":  {"name": "Железная руда", "emoji": "⛏️", "price": 10},
    "gold":  {"name": "Золото",       "emoji": "🪙", "price": 20},
}

# Рецепти переплавки (ті ж, що й раніше)
SMELT_RECIPES = {
    "iron":  {"in_qty": 3,  "out_key": "iron_ingot",  "out_name": "Железный слиток"},
    "stone": {"in_qty": 10, "out_key": "roundstone",   "out_name": "Булыжник"},
    "gold":  {"in_qty": 2,  "out_key": "gold_ingot",   "out_name": "Золотой слиток"},
    "amethyst":  {"in_qty": 2,  "out_key": "amethyst_ingot",  "out_name": "Аметистовый слиток"},
}

# Рецепти крафту
CRAFT_RECIPES = {
    "булыжниковая кирка": {
        "in": {"roundstone": 10, "wood_handle": 1},
        "out_key": "roundstone_pickaxe",
        "out_name": "Булыжниковая кирка",
    },
    "железная кирка": {
        "in": {"iron_ingot": 8, "wood_handle": 1},
        "out_key": "iron_pickaxe",
        "out_name": "Железная кирка",
    },
    "золотая кирка": {
        "in": {"gold_ingot": 5, "wood_handle": 1},
        "out_key": "gold_pickaxe",
        "out_name": "Золотая кирка",
    },
    "аметистовая кирка": {
        "in": {"gold_ingot": 3, "wood_handle": 2},
        "out_key": "amethyst_pickaxe",
        "out_name": "Аметистовая кирка",
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
ITEM_DEFS["bread"] = {"name": "Хлеб", "emoji": "🍞"}
ITEM_DEFS["meat"] = {"name": "Мясо", "emoji": "🍖"}
ITEM_DEFS.update({
    "torch_bundle": {"name": "Факел", "emoji": "🕯️"},
    "cave_cases": {"name": "Cave Case", "emoji": "📦"},
    "energy_drink": {"name": "Энергетик", "emoji": "🥤"},
    "borsch": {"name": "Борщ", "emoji": "🥣"},
    "wooden_pickaxe": {
        "name": "Деревянная кирка",
        "emoji": "🪵",
    },
    "legacy_pickaxe": {"name": "Памятная кирка", "emoji": "🏛️",},
    "coffee": {"name": "Кофе", "emoji": "☕"},
    # інші як є …
})
# bot/handlers/items.py  (где собирается ITEM_DEFS)

# Добавьте эмодзи тем, кому их не хватало
ITEM_DEFS["roundstone"]       = {"name": "Булыжник",        "emoji": "🪨"}
ITEM_DEFS["iron_ingot"]       = {"name": "Железный слиток", "emoji": "⛏️"}
ITEM_DEFS["gold_ingot"]       = {"name": "Золотой слиток",  "emoji": "🪙"}
ITEM_DEFS["amethyst_ingot"]   = {"name": "Аметистовый слиток", "emoji": "💜"}

# кирки-готовые
ITEM_DEFS["iron_pickaxe"]["emoji"]    = "⛏️"
ITEM_DEFS["gold_pickaxe"]["emoji"]    = "✨"
ITEM_DEFS["amethyst_pickaxe"]["emoji"]= "🔮"
ITEM_DEFS["roundstone_pickaxe"]["emoji"] = "🪨"
ITEM_DEFS["wooden_pickaxe"]["emoji"] = "🪵"


EXTRA_ORES = {
    "amethyst": {"name": "Аметистовая руда",  "emoji": "💜", "drop_range": (1,2), "price": 40},
    "diamond":  {"name": "Алмаз",  "emoji": "💎", "drop_range": (1,1), "price": 60},
    "emerald":  {"name": "Изумруд",  "emoji": "💚", "drop_range": (1,2), "price": 55},
    "lapis":    {"name": "Лазурит",  "emoji": "🔵", "drop_range": (2,4), "price": 35},
    "ruby":     {"name": "Рубин",    "emoji": "❤️", "drop_range": (1,2), "price": 50},
}

ORE_ITEMS.update(EXTRA_ORES)
for k, v in EXTRA_ORES.items():
    ITEM_DEFS[k] = v         # щоб /inventory їх знав

ALIASES = {
    "камень": "stone",
    "уголь": "coal",
    "железная руда": "iron",
    "железо": "iron",
    "золото": "gold",
    "аметистовая руда": "amethyst",
    "алмаз": "diamond",
    "изумруд": "emerald",
    "лазурит": "lapis",
    "рубин":   "ruby",

    "💎": "diamond",
    "💚": "emerald",
    "💜": "amethyst",
}
