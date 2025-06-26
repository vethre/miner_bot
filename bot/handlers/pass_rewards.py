PASS_REWARDS = {
    1: {"free": {"gold": 3}, "premium": {"achievement": "eonite_owner"}},
    2: {"free": {"coal": 10}, "premium": {"money": 300}},
    3: {"free": {"roundstone": 5}, "premium": {"gold": 15}},
    4: {"free": {"iron": 3}, "premium": {"coal": 30}},
    5: {"free": {"iron_ingot": 3}, "premium": {"money": 500}},
    6: {"free": {"money": 150}, "premium": {"iron": 10}},
    7: {"free": {"coal": 30}, "premium": {"amethyst": 2}},
    8: {"free": {"wood_handle": 3}, "premium": {"badge": "eonite_beacon"}},
    9: {"free": {"gold": 5}, "premium": {"lapis": 10}},
    10: {"free": {"pickaxe": "iron_pickaxe"}, "premium": {"money": 700}},
    11: {"free": {"money": 300}, "premium": {"cave_case": 1}},
    12: {"free": {"coal": 50}, "premium": {"gold_ingot": 2}},
    13: {"free": {"lapis": 5}, "premium": {"amethyst": 5}},
    14: {"free": {"money": 400}, "premium": {"iron": 15}},
    15: {"free": {"xp": 120}, "premium": {"pickaxe": "proto_eonite_pickaxe"}},
    16: {"free": {"roundstone": 10}, "premium": {"money": 600}},
    17: {"free": {"cave_case": 1}, "premium": {"cave_case": 2}},
    18: {"free": {"money": 200}, "premium": {"lapis": 15}},
    19: {"free": {"coal": 60}, "premium": {"iron_ingot": 5}},
    20: {"free": {"cave_case": 3}, "premium": {"cave_case": 3, "lapis": 3}},
}


REWARD_DISPLAY = {
    "money": lambda a: f"💰 {a} монет",
    "xp":    lambda a: f"📘 {a} XP",
    "item":  lambda i, a: f"{a}× {i}",
    "badge": lambda b: f"🏅 бейдж {b}",
    "achievement": lambda c: f"🏆 ачивка {c}",
    "multi": lambda r: " + ".join([REWARD_DISPLAY[x["type"]](*x.values()) for x in r])
}