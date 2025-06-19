from aiogram import Router, types
from aiogram.filters import Command
from bot.db import get_inventory, add_item, db

router = Router()

SMELT_INPUT_MAP = {
    "железная руда": "iron",
    "камень":        "stone",
    "золото":        "gold",
}

SMELT_RECIPES = {
    "iron":  {"in_qty": 3,  "out_key": "iron_ingot",  "out_name": "Железный злиток"},
    "stone": {"in_qty": 10, "out_key": "roundstone",   "out_name": "Булыжник"},
    "gold":  {"in_qty": 2,  "out_key": "gold_ingot",   "out_name": "Золотой слиток"},
    "amethyst":  {"in_qty": 2,  "out_key": "amethyst_ingot",  "out_name": "Аметистовый слиток"},
}

CRAFT_RECIPES = {
    "булыжниковая кирка": {
        "in": {"roundstone": 12, "wood_handle": 1},
        "out_key": "roundstone_pickaxe",
        "out_name": "🔨 Булыжниковая кирка"
    },
    "железная кирка": {
        "in": {"iron_ingot": 10, "wood_handle": 1},
        "out_key": "iron_pickaxe",
        "out_name": "⛏️ Железная кирка"
    },
    "золотая кирка": {
        "in": {"gold_ingot": 7, "wood_handle": 1},
        "out_key": "gold_pickaxe",
        "out_name": "✨ Золотая кирка"
    },
    "аметистовая кирка": {
        "in": {"gold_ingot": 3, "wood_handle": 2},
        "out_key": "amethyst_pickaxe",
        "out_name": "✨ Аметистовая кирка",
    },
}