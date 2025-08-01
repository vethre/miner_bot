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
    "старшая эонитовая кирка": {
        "in": {"iron_handle": 5, "eonite_ingot": 3, "eonite_ore": 6},
        "out_key": "greater_eonite_pickaxe",
        "out_name": "🔮 Старшая эонитовая кирка",
    },
}

CRAFT_RECIPES.update({
    "обсидиановая кирка": {
        "in": {"obsidian_shard": 8, "iron_handle": 1},
        "out_key": "obsidian_pickaxe",
        "out_name": "🟪 Обсидиановая кирка"
    },
    "лазурный факел": {
        "in": {"lapis": 3, "coal": 5},
        "out_key": "lapis_torch",
        "out_name": "🔵 Лазурный факел"
    },
    "руда эонита": {
        "in": {"eonite_shard": 3},
        "out_key": "eonite_ore",
        "out_name": "🧿 Руда Эонита"
    },
    "железная рукоять": {
        "in": {
            "wood_handle": 3,
            "iron_ingot": 5
        },
        "out_key": "iron_handle",
        "out_name": "🪚 Железная рукоять"
    },
    "инструмент разборки": {
        "in": {
            "wax": 2,
            "iron_ingot": 2
        },
        "out_key": "disassemble_tool",
        "out_name": "🔧 Инструмент разборки"
    },
    "войд-кирка": {
        "in": {"void_crystal": 20, "iron_handle": 4},
        "out_key": "void_pickaxe",
        "out_name": "🕳️ Войд-кирка"
    },
})

RECIPES_BY_ID: dict[str, dict] = {r["out_key"]: r for r in CRAFT_RECIPES.values()}

# если хотите принимать /disassemble "золотая кирка" и т.п.
ALIAS_TO_ID: dict[str, str] = {
    human.lower(): r["out_key"] for human, r in CRAFT_RECIPES.items()
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
