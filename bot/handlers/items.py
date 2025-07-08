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
    "stone": {"in_qty": 6, "out_key": "roundstone",   "out_name": "Булыжник"},
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
    "reinforced_grip": {
        "name": "Усиленная рукоять",
        "emoji": "🛠️",
    },
    "sharp_tip": {
        "name": "Острый наконечник",
        "emoji": "🛠️",
    },
    "smoke_absorb_handle": {
        "name": "Угольная рукоять",
        "emoji": "🛠️",
    },
    "diamond_pickaxe": {
        "name": "Алмазная кирка",
        "emoji": "💎",
    },
    "wax": {
        "name": "Воск",
        "emoji": "🍯",
    },
    "disassemble_tool": {
        "name": "Инструмент разборки",
        "emoji": "🔧"
    },
    "iron_handle": {
        "name": "Железная рукоять",
        "emoji": "🪚"
    },
    "lapis_torch": {
        "name": "Лазурный факел",
        "emoji": "🔵"
    },
    "old_hdd": {
        "name": "HDD",
        "emoji": "💽",
        "price": 512
    },
    "water_bottle": {
        "name": "Фляга с водой",
        "emoji": "💧"
    }
})
# bot/handlers/items.py  (где собирается ITEM_DEFS)

# Добавьте эмодзи тем, кому их не хватало
ITEM_DEFS["roundstone"]       = {"name": "Булыжник",        "emoji": "🪨"}
ITEM_DEFS["iron_ingot"]       = {"name": "Железный слиток", "emoji": "⛏️"}
ITEM_DEFS["gold_ingot"]       = {"name": "Золотой слиток",  "emoji": "🪙"}
ITEM_DEFS["amethyst_ingot"]   = {"name": "Аметистовый слиток", "emoji": "💜"}
ITEM_DEFS["eonite_shard"]      = {"name": "Эонитовый осколок",  "emoji": "🔮"}

# кирки-готовые
ITEM_DEFS["iron_pickaxe"]["emoji"]    = "⛏️"
ITEM_DEFS["gold_pickaxe"]["emoji"]    = "✨"
ITEM_DEFS["amethyst_pickaxe"]["emoji"]= "🔮"
ITEM_DEFS["roundstone_pickaxe"]["emoji"] = "🪨"
ITEM_DEFS["obsidian_pickaxe"] = {
    "name":  "Обсидиановая кирка",
    "emoji": "🟪"
}
ITEM_DEFS["wooden_pickaxe"]["emoji"] = "🪵"
ITEM_DEFS["diamond_pickaxe"]["emoji"] = "💎"
CRAFT_RECIPES.update({
    "obsidian_pickaxe": {
        "in": {"obsidian_shard": 8, "iron_handle": 1},
        "out_key": "obsidian_pickaxe",
        "out_name": "Обсидиановая кирка"
    },
    "lapis_torch": {
        "in": {"lapis": 2, "torch": 1},
        "out_key": "lapis_torch",
        "out_name": "Лазурный факел"
    },
    "iron_handle": {
        "in": {
            "wood_handle": 3,
            "iron_ingot": 5
        },
        "out_key": "iron_handle",
        "out_name": "Железная рукоять"
    },
    "disassemble_tool": {
        "in": {
            "wax": 2,
            "iron_ingot": 2
        },
        "out_key": "disassemble_tool",
        "out_name": "Инструмент разборки"
    }
})


for ore, v in SMELT_RECIPES.items():
    base_price = ORE_ITEMS.get(ore, {"price": 20})["price"]
    ITEM_DEFS[v["out_key"]] = {
        "name": v["out_name"],
        "emoji": "🔥",
        "price": int(base_price * 1.8)
    }

ITEM_DEFS.update({
    "obsidian_shard":  {"name": "Обсидиановый осколок", "emoji": "🟣", "price": 85},
    "iron_handle":     {"name": "Железная рукоять",      "emoji": "🪚"},
    "lapis_torch":     {"name": "Лазуритовый факел",     "emoji": "🔵"},
    "bomb":            {"name": "Бомба",                 "emoji": "💣"},
    "voucher_borsch": {
        "name":  "Ваучер «Борщ FREE»",
        "emoji": "🎟️",
        "desc":  "Активируй — получишь один борщ.",
    },
    "voucher_sale": {
        "name":  "Скид-ваучер −20 %",
        "emoji": "🎫",
        "desc":  "Один раз снижает цену следующей покупки.",
    },
    "voucher_full_energy": {
        "name":  "Ваучер бодрости",
        "emoji": "💥",
        "desc":  "Мгновенно восстанавливает энергию и сытость.",
    },
})

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
    "обсидиановый осколок": "obsidian_shard",

    "💎": "diamond",
    "💚": "emerald",
    "💜": "amethyst",
}
