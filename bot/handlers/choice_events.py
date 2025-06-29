# File: bot/handlers/choice_events.py
import random

from aiogram import F, Bot, types, Router
from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot.db_local import add_energy, add_item, add_money, add_xp, db
from bot.handlers.items import ITEM_DEFS

router = Router()

CHOICE_EVENTS: dict[str, dict] = {
    "mystic_chest": {
        "text": "🎁 Ты натыкаешься на старый запечатанный сундук.",
        "options": {
            "open": {
                "label": "Открыть",
                "outcomes": [
                    {"field": "coins",  "sign": "+", "amt_min": 120, "amt_max": 300, "weight": 70},
                    {"field": "coins",  "sign": "-", "amt_min": 80,  "amt_max": 200, "weight": 30},
                ]
            },
            "leave": {
                "label": "Оставить",
                "outcomes": [
                    {"field": "xp",     "sign": "+", "amt_min": 50, "amt_max": 90,  "weight": 60},
                    {"field": "energy", "sign": "-", "amt_min": 25, "amt_max": 45,  "weight": 40},
                ]
            }
        }
    },

    "strange_mushroom": {
        "text": "🍄 В сырой пещере растёт странный гриб.",
        "options": {
            "eat": {
                "label": "Съесть",
                "outcomes":[
                    {"field": "energy", "sign":"+","amt_min":30,"amt_max":60,"weight":65},
                    {"field": "hunger", "sign":"-","amt_min":20,"amt_max":40,"weight":35},
                ]
            },
            "ignore":{
                "label":"Игнорировать",
                "outcomes":[
                    {"field": "xp", "sign":"+","amt_min":40,"amt_max":70,"weight":80},
                    {"field": "coins","sign":"-","amt_min":50,"amt_max":80,"weight":20},
                ]
            }
        }
    },
}

CHOICE_EVENTS.update({
    "old_miner": {
        "text": "👴 Ты встречаешь старого шахтёра у костра.",
        "options": {
            "share_ore": {
                "label": "Отдать немного руды",
                "outcomes": [
                    # старик благодарит монетами
                    {"field": "coins", "sign": "+", "amt_min": 90, "amt_max": 160, "weight": 80},
                    # иногда дарит редкую кирку
                    {"field": "item",  "sign": "+", "item": "iron_pickaxe", "amt_min": 1, "amt_max": 1, "weight": 20},
                ]
            },
            "refuse": {
                "label": "Отказать",
                "outcomes": [
                    {"field": "xp",    "sign": "+", "amt_min": 40, "amt_max": 70, "weight": 60},
                    {"field": "coins", "sign": "-", "amt_min": 60, "amt_max": 90, "weight": 40},
                ]
            }
        }
    },

    "underground_lake": {
        "text": "🌊 Подземное озеро! Вода выглядит кристально чистой.",
        "options": {
            "drink": {
                "label": "Напиться",
                "outcomes": [
                    {"field": "energy", "sign": "+", "amt_min": 35, "amt_max": 55, "weight": 70},
                    {"field": "hunger", "sign": "-", "amt_min": 30, "amt_max": 50, "weight": 30},
                ]
            },
            "fill_bottle": {
                "label": "Наполнить флягу",
                "outcomes": [
                    {"field": "item", "sign": "+", "item": "water_bottle", "amt_min": 1, "amt_max": 1, "weight": 100},
                ]
            }
        }
    },

    # ─────────────────────────────────────────────
    "lost_miner": {
        "text": "⛏️ В глубине шахты ты наткнулся на растерянного шахтёра-новичка. Он просит проводника.",
        "options": {
            "help": {
                "label": "Показать путь ↑",
                "outcomes": [
                    {"field": "coins", "sign": "+", "amt_min": 100, "amt_max": 140, "weight": 70},
                    {"field": "xp",    "sign": "+", "amt_min": 20,  "amt_max": 40,  "weight": 30},
                ]
            },
            "ignore": {
                "label": "Проигнорировать",
                "outcomes": [
                    {"field": "xp",    "sign": "-", "amt_min": 5,   "amt_max": 15,  "weight": 100},
                ]
            }
        }
    },

    # ─────────────────────────────────────────────
    "mysterious_altar": {
        "text": "🔮 Ты обнаружил таинственный обсидиановый алтарь с пульсирующим кристаллом.",
        "options": {
            "touch": {
                "label": "Дотронуться",
                "outcomes": [
                    {"field": "energy", "sign": "+", "amt_min": 20,  "amt_max": 30, "weight": 80},
                    {"field": "xp",     "sign": "+", "amt_min": 15,  "amt_max": 25, "weight": 20},
                ]
            },
            "mine": {
                "label": "Попробовать добыть",
                "outcomes": [
                    {"field": "item",   "sign": "+", "item": "obsidian_shard", "amt_min": 1, "amt_max": 1, "weight": 60},
                    {"field": "energy", "sign": "-", "amt_min": 10,  "amt_max": 15, "weight": 40},
                ]
            },
            "leave": {
                "label": "Отойти",
                "outcomes": [
                    {"field": "xp", "sign": "+", "amt_min": 5, "amt_max": 10, "weight": 100},
                ]
            }
        }
    },

    # ─────────────────────────────────────────────
    "cave_stream": {
        "text": "🌊 Подземный поток преграждает путь.",
        "options": {
            "swim": {
                "label": "Переплыть",
                "outcomes": [
                    {"field": "energy", "sign": "-", "amt_min": 8,  "amt_max": 12, "weight": 70},
                    {"field": "xp",     "sign": "+", "amt_min": 10, "amt_max": 20, "weight": 30},
                ]
            },
            "build_bridge": {
                "label": "Соорудить мост",
                "outcomes": [
                    {"field": "coins", "sign": "+", "amt_min": 60, "amt_max": 100, "weight": 70},
                    {"field": "xp",    "sign": "+", "amt_min": 5,  "amt_max": 10,  "weight": 30},
                ]
            },
            "turn_back": {
                "label": "Вернуться",
                "outcomes": [
                    {"field": "xp", "sign": "+", "amt_min": 3, "amt_max": 6, "weight": 100},
                ]
            }
        }
    },

    # ─────────────────────────────────────────────
    "greedy_bat": {
        "text": "🦇 Летучая мышь вылетает из-за спины и пытается стащить твою добычу!",
        "options": {
            "shoo": {
                "label": "Отмахнуться",
                "outcomes": [
                    {"field": "coins", "sign": "+", "amt_min": 25, "amt_max": 40, "weight": 100},
                ]
            },
            "feed": {
                "label": "Дать кусочек мяса",
                "outcomes": [
                    {"field": "item",  "sign": "+", "item": "amethyst", "amt_min": 1, "amt_max": 1, "weight": 70},
                    {"field": "xp",    "sign": "+", "amt_min": 5,  "amt_max": 10, "weight": 30},
                ]
            },
            "ignore": {
                "label": "Игнорировать",
                "outcomes": [
                    {"field": "item", "sign": "-", "item": "stone", "amt_min": 3, "amt_max": 6, "weight": 100},
                ]
            }
        }
    },
})

async def build_mention(bot: Bot, chat_id: int, user_id: int) -> str:
    """
    Возвращает mention пользователя:
        • @username   – если есть ник
        • tg://user…  – если ника нет
    """
    m = await bot.get_chat_member(chat_id, user_id)
    if m.user.username:
        return f"@{m.user.username}"
    # HTML-link без пробелов в id
    return f'<a href="tg://user?id={user_id}">{m.user.full_name}</a>'


def _choice_weighted_pick(outcomes: list[dict]) -> dict:
    total = sum(o["weight"] for o in outcomes)
    rnd   = random.randint(1, total)
    acc   = 0
    for o in outcomes:
        acc += o["weight"]
        if rnd <= acc:
            return o
    return outcomes[-1]   # fallback


async def _apply_choice_effect(bot: Bot, chat_id: int, user_id: int,
                               outcome: dict) -> str:
    amt = random.randint(outcome["amt_min"], outcome["amt_max"])
    if outcome["sign"] == "-":
        amt = -amt

    fld = outcome["field"]
    if fld == "coins":
        await add_money(chat_id, user_id, amt)
    elif fld == "xp":
        await add_xp(chat_id, user_id, amt)
    elif fld == "energy":
        await add_energy(chat_id, user_id, amt)
    elif fld == "hunger":
        # hunger растёт «в минус», поэтому инвертируем знак
        await db.execute("""UPDATE progress_local
                               SET hunger = LEAST(100, GREATEST(0, hunger - :d))
                             WHERE chat_id=:c AND user_id=:u""",
                         {"d": amt, "c": chat_id, "u": user_id})
    elif fld == "item":
        await add_item(chat_id, user_id, outcome["item"], outcome["amt_min"])
        return f"+1 предмет: {ITEM_DEFS.get(outcome['item'], {}).get('name', outcome['item'])}"

    return f"{'+' if amt>0 else ''}{amt} {fld.upper()}"

async def maybe_send_choice_card(bot: Bot, cid: int, uid: int):
    if random.random() > 0.30:          # 20 % шанс что вообще появится карточка
        return

    ev_key, ev = random.choice(list(CHOICE_EVENTS.items()))
    kb = InlineKeyboardBuilder()
    for opt_key, opt in ev["options"].items():
        kb.button(
            text=opt["label"],
            callback_data=f"choice:{ev_key}:{opt_key}:{uid}"
        )
    kb.adjust(2)

    mention = await build_mention(bot, cid, uid)

    await bot.send_message(
        cid,
        f"{mention}, {ev['text']}\n\n<i>Сделай выбор:</i>",
        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )

@router.callback_query(F.data.startswith("choice:"))
async def choice_callback(cb: types.CallbackQuery):
    cid, clicker = cb.message.chat.id, cb.from_user.id
    _, ev_key, opt_key, orig_uid = cb.data.split(":")
    orig_uid = int(orig_uid)

    # кнопка только для автора
    if clicker != orig_uid:
        return await cb.answer("Это не твой выбор 😅", show_alert=True)

    ev  = CHOICE_EVENTS[ev_key]
    opt = ev["options"][opt_key]

    outcome = _choice_weighted_pick(opt["outcomes"])
    summary = await _apply_choice_effect(cb.bot, cid, orig_uid, outcome)

    await cb.message.edit_text(
        f"🎲 {opt['label']} → {summary}",
        parse_mode="HTML"
    )
    await cb.answer()

