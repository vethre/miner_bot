PASS_REWARDS = {
    1: {
        "free": {"type": "money", "data": 300},
        "premium": {"type": "achievement", "data": "eonite_owner"}
    },
    2: {
        "free": {"type": "item", "data": "coal", "qty": 10},
        "premium": {"type": "money", "data": 500}
    },
    3: {
        "free": {"type": "item", "data": "iron", "qty": 3},
        "premium": {"type": "xp", "data": 100}
    },
    4: {
        "free": {"type": "item", "data": "roundstone", "qty": 15},
        "premium": {"type": "item", "data": "coal", "qty": 30}
    },
    5: {
        "free": {"type": "item", "data": "iron_ingot", "qty": 5},
        "premium": {"type": "money", "data": 50}
    },
    6: {
        "free": {"type": "money", "data": 200},
        "premium": {"type": "item", "data": "iron", "qty": 10}
    },
    7: {
        "free": {"type": "item", "data": "coal", "qty": 30},
        "premium": {"type": "item", "data": "amethyst", "qty": 2}
    },
    8: {
        "free": {"type": "item", "data": "wood_handle", "qty": 3},
        "premium": {"type": "badge", "data": "eonite_beacon"}
    },
    9: {
        "free": {"type": "item", "data": "gold", "qty": 5},
        "premium": {"type": "item", "data": "lapis", "qty": 3}
    },
    10: {
        "free": {"type": "pickaxe", "data": "iron_pickaxe", "qty": 1},
        "premium": {"type": "money", "data": 500}
    },
    11: {
        "free": {"type": "money", "data": 300},
        "premium": {"type": "cave_cases", "data": 1}
    },
    12: {
        "free": {"type": "item", "data": "coal", "qty": 50},
        "premium": {"type": "item", "data": "gold_ingot", "qty": 5}
    },
    13: {
        "free": {"type": "item", "data": "lapis", "qty": 3},
        "premium": {"type": "item", "data": "amethyst", "qty": 5}
    },
    14: {
        "free": {"type": "money", "data": 400},
        "premium": {"type": "item", "data": "iron", "qty": 15}
    },
    15: {
        "free": {"type": "xp", "data": 150},
        "premium": {"type": "pickaxe", "data": "proto_eonite_pickaxe", "qty": 1}
    },
    16: {
        "free": {"type": "xp", "data": 200},
        "premium": {"type": "xp", "data": 250}
    },
    17: {
        "free": {"type": "cave_cases", "data": 1},
        "premium": {"type": "cave_cases", "data": 2}
    },
    18: {
        "free": {"type": "xp", "data": 220},
        "premium": {"type": "item", "data": "lapis", "qty": 7}
    },
    19: {
        "free": {"type": "item", "data": "coal", "qty": 70},
        "premium": {"type": "item", "data": "emerald", "qty": 2}
    },
    20: {
        "free": {"type": "cave_cases", "data": 3},
        "premium": {"type": "cave_cases", "data": 5}
    },

    
}



REWARD_DISPLAY = {
    "money": lambda a: f"💰 {a} монет",
    "xp":    lambda a: f"📘 {a} XP",
    "item":  lambda i, a: f"{a}× {i}",
    "badge": lambda b: f"🏅 бейдж {b}",
    "achievement": lambda c: f"🏆 ачивка {c}",
    "multi": lambda r: " + ".join([REWARD_DISPLAY[x["type"]](*x.values()) for x in r])
}