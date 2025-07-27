import json
from aiogram import Router, F, types
from aiogram.filters import Command

from bot.db_local import cid_uid, get_progress, db

router = Router()

COMMAND_ALIASES = {
    "mine":         ["шахта копка", "шахта копать", "шахта шахта", "шахта рыть", "шахта попка", "шахта жопка"],
    "profile":      ["шахта акк", "шахта аккаунт", "шахта профиль"],
    "shop":         ["шахта магаз", "шахта магазин", "шахта шоп", "шахта крамниця"],
    "invetory":     ["шахта инвентарь", "шахта сумка", "шахта склад", "шахта склад", "шахта инв", "шахта рюкзак"],
    "case":         ["шахта кейс", "шахта кейв кейс"],
    "clashcase":    ["шахта клешкейс", "шахта клешк"],
    "clashrank":    ["шахта клешранк", "шахта ранг", "шахта клешранг", "шахта клеш"],
    "kiss":         ["цьомнуть", "цьом", "шахта поцеловать"],
    "hug":          ["шахта обнять"],
    "throwpick":    ["шахта кинуть", "кинуть кирку"],
    "pickaxes":     ["шахта кирки", "шахта кирка"],
    "cavepass":     ["шахта пас", "шахта пасс", "шахта кейвпасс"],
    "use": ["шахта юз", "шахта юзнуть", "шахта юзать", "шахта использовать", "шахта исп"],
    "eat": ["шахта есть", "шахта кушать", "шахта ит", "шахта поесть", "шахта пить", "шахта попить", "шахта дринк"],
    "smelt": ["шахта плавка", "шахта плавить", "шахта печка", "шахта печь"],
    "sell": ["шахта торг", "шахта продать", "шахта продажа", "шахта селл"]
}

MAX_ALIASES_PER_CMD = 8
def parse_aliases(raw):
    if not raw:
        return {}
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:
            return {}
    return raw

@router.message(Command("alias"))
async def alias_add_cmd(message: types.Message):
    cid, uid = await cid_uid(message)
    args = message.text.split(maxsplit=2)
    if (len(args)) < 3:
        return await message.reply(
            "Используй: /alias <code>команда алиас</code>\nПример: /alias mine бурить"
        )
    
    cmd, alias = args[1].strip(), args[2].strip().lower()
    if cmd not in COMMAND_ALIASES:
        return await message.reply(
            "Такой команды нет. Список команд: " +
            ", ".join(sorted(COMMAND_ALIASES.keys()))
        )
    
    prog = await get_progress(cid, uid)
    aliases = parse_aliases(prog.get("aliases"))
    user_aliases = aliases.get(cmd, [])
    if alias in user_aliases or alias in COMMAND_ALIASES[cmd]:
        return await message.reply("Этот алиас уже добавлен для этой команды.")
    if len(user_aliases) >= MAX_ALIASES_PER_CMD:
        return await message.reply(f"Максимум {MAX_ALIASES_PER_CMD} алиасов на команду!")
    user_aliases.append(alias)
    aliases[cmd] = user_aliases
    await db.execute(
        "UPDATE progress_local SET aliases = :al WHERE chat_id=:c AND user_id=:u",
        {"al": json.dumps(aliases), "c": cid, "u": uid}
    )
    await message.reply(f"✅ Алиас <b>{alias}</b> добавлен для <b>{cmd}</b>!", parse_mode="HTML")

@router.message(Command("aliasdel"))
async def alias_del_cmd(message: types.Message):
    cid, uid = await cid_uid(message)
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        return await message.reply(
            "Используй: /aliasdel <code>команда алиас</code>\nПример: /aliasdel mine бурить"
        )
    cmd, alias = args[1].strip(), args[2].strip().lower()
    prog = await get_progress(cid, uid)
    aliases = prog.get("aliases") or {}
    user_aliases = aliases.get(cmd, [])
    if alias not in user_aliases:
        return await message.reply("Такого алиаса у тебя нет для этой команды.")
    user_aliases.remove(alias)
    aliases[cmd] = user_aliases
    await db.execute(
        "UPDATE progress_local SET aliases = :al WHERE chat_id=:c AND user_id=:u",
        {"al": json.dumps(aliases), "c": cid, "u": uid}
    )
    await message.reply(f"❌ Алиас <b>{alias}</b> удалён для <b>{cmd}</b>.", parse_mode="HTML")

@router.message(Command("aliases"))
async def alias_list_cmd(message: types.Message):
    cid, uid = await cid_uid(message)
    prog = await get_progress(cid, uid)
    aliases = prog.get("aliases") or {}
    if not any(aliases.values()):
        return await message.reply("У тебя нет ни одного пользовательского алиаса.")
    lines = ["<b>Твои алиасы:</b>"]
    for cmd in sorted(aliases):
        arr = aliases[cmd]
        if arr:
            lines.append(f"<b>{cmd}:</b> {', '.join(arr)}")
    await message.reply("\n".join(lines), parse_mode="HTML")

@router.message()
async def smart_router(message: types.Message):
    txt = message.text.lower()
    cid, uid = await cid_uid(message)
    prog = await get_progress(cid, uid)
    user_aliases = prog.get("aliases") or {}

    for cmd, arr in user_aliases.items():
        if any(alias in txt for alias in arr):
            return await call_cmd_by_alias(cmd, message)

    for cmd, arr in COMMAND_ALIASES.items():
        if any(alias in txt for alias in arr):
            return await call_cmd_by_alias(cmd, message)

async def call_cmd_by_alias(cmd, message):
    from bot.handlers.base_commands import mine_cmd, profile_cmd, inventory_cmd, kiss_cmd, hug_cmd, throwpick_cmd, cavepass_cmd, smelt_cmd, sell_start, pickaxes_cmd
    from bot.handlers.cases import cave_case_cmd, clash_case_cmd
    from bot.handlers.cave_clash import clashrank
    from bot.handlers.use import use_cmd
    from bot.handlers.eat import eat_cmd
    from bot.handlers.shop import shop_cmd
    # Подключи все свои нужные команды
    if cmd == "mine":
        return await mine_cmd(message)
    if cmd == "profile":
        return await profile_cmd(message, message.bot)
    if cmd == "inventory":
        return await inventory_cmd(message)
    if cmd == "shop":
        return await shop_cmd(message)
    if cmd == "kiss":
        return await kiss_cmd(message)
    if cmd == "hug":
        return await hug_cmd(message)
    if cmd == "throwpick":
        return await throwpick_cmd(message)
    if cmd == "cavepass":
        return await cavepass_cmd(message)
    if cmd == "smelt":
        return await smelt_cmd(message)
    if cmd == "sell":
        return await sell_start(message)
    if cmd == "pickaxes":
        return await pickaxes_cmd(message)
    if cmd == "case":
        return await cave_case_cmd(message)
    if cmd == "clashcase":
        return await clash_case_cmd(message)
    if cmd == "clashrank":
        return await clashrank(message)
    if cmd == "use":
        return await use_cmd(message)
    if cmd == "eat":
        return await eat_cmd(message)