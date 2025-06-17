from aiogram import Router, types
from aiogram.filters import Command
from bot.db import get_inventory, add_item, db

router = Router()

SMELT_INPUT_MAP = {
    "залізна руда": "iron",
    "камінь":        "stone",
    "золото":        "gold",
}

SMELT_RECIPES = {
    "iron":  {"in_qty": 3,  "out_key": "iron_ingot",  "out_name": "Залізний злиток"},
    "stone": {"in_qty": 10, "out_key": "roundstone",   "out_name": "Кругляк"},
    "gold":  {"in_qty": 2,  "out_key": "gold_ingot",   "out_name": "Золотий злиток"},
}

CRAFT_RECIPES = {
    "круглякова кирка": {
        "in": {"roundstone": 12, "wood_handle": 1},
        "out_key": "roundstone_pickaxe",
        "out_name": "🔨 Круглякова кирка"
    },
    "залізна кирка": {
        "in": {"iron_ingot": 10, "wood_handle": 1},
        "out_key": "iron_pickaxe",
        "out_name": "⛏️ Залізна кирка"
    },
    "золота кирка": {
        "in": {"gold_ingot": 7, "wood_handle": 1},
        "out_key": "gold_pickaxe",
        "out_name": "✨ Золота кирка"
    },
}