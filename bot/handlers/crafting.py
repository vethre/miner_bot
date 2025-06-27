from aiogram import Router, types
from aiogram.filters import Command
from bot.db import get_inventory, add_item, db

router = Router()

SMELT_INPUT_MAP: dict[str, str] = {
    "железная руда":  "iron",
    "железо":         "iron",
    "iron":           "iron",

    "каменная руда":  "stone",
    "камень":         "stone",
    "stone":          "stone",

    "золото":         "gold",
    "gold":           "gold",

    "аметист":        "amethyst",
    "аметистовая руда":"amethyst",
    "amethyst":       "amethyst",
    "руда эонита":"eonite_ore",
}

SMELT_RECIPES = {
    "iron":  {"in_qty": 3,  "out_key": "iron_ingot",  "out_name": "Железный cлиток"},
    "stone": {"in_qty": 6, "out_key": "roundstone",   "out_name": "Булыжник"},
    "gold":  {"in_qty": 2,  "out_key": "gold_ingot",   "out_name": "Золотой слиток"},
    "amethyst":  {"in_qty": 2,  "out_key": "amethyst_ingot",  "out_name": "Аметистовый слиток"},
    "eonite_ore":  {"in_qty": 2,  "out_key": "eonite_ingot",  "out_name": "Слиток Эонита"},
}

CRAFT_RECIPES = {
    "булыжниковая кирка": {
        "in": {"roundstone": 10, "wood_handle": 1},
        "out_key": "roundstone_pickaxe",
        "out_name": "🔨 Булыжниковая кирка"
    },
    "железная кирка": {
        "in": {"iron_ingot": 8, "wood_handle": 1},
        "out_key": "iron_pickaxe",
        "out_name": "⛏️ Железная кирка"
    },
    "золотая кирка": {
        "in": {"gold_ingot": 5, "wood_handle": 2},
        "out_key": "gold_pickaxe",
        "out_name": "✨ Золотая кирка"
    },
    "аметистовая кирка": {
        "in": {"amethyst_ingot": 3, "wood_handle": 2},
        "out_key": "amethyst_pickaxe",
        "out_name": "✨ Аметистовая кирка",
    },
    "алмазная кирка": {
        "in": {"diamond": 3, "wood_handle": 4},
        "out_key": "diamond_pickaxe",
        "out_name": "💎 Аметистовая кирка",
    },
    "руда эонита": {
        "in": {"eonite_shard": 2},
        "out_key": "eonite_ore",
        "out_name": "🔮 Руда Эонита",
    },
    "железная рукоять": {
        "in": {"wood_handle": 5, "iron_ingot": 5},
        "out_key": "iron_handle",
        "out_name": "🧲 Железная рукоять",
    },
    "старшая эонитовая кирка": {
        "in": {"iron_handle": 1, "eonite_ingot": 3, "eonite_ore": 1},
        "out_key": "greater_eonite_pickaxe",
        "out_name": "🔮 Старшая эонитовая кирка",
    },
}

PICKAXE_UPGRADES = {
    "reinforced_grip": {
        "name": "🛠️ Усиленная рукоять",
        "materials": {"coal": 20, "wood_handle": 3},
    },
    "sharp_tip": {
        "name": "🛠️ Острый наконечник",
        "materials": {"coal": 50, "iron_ingot": 5},
    },
    "smoke_absorb_handle": {
        "name": "🛠️ Угольная рукоять",
        "materials": {"coal": 80, "wood_handle": 3, "gold_ingot": 2},
    },
}
