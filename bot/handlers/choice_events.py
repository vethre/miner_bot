# File: bot/handlers/choice_events.py
import asyncio
import random

from aiogram import F, Bot, types, Router
import aiogram
from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot.db_local import add_energy, add_item, add_money, add_xp, db
from bot.handlers.items import ITEM_DEFS

router = Router()
CARD_LIFETIME_MIN = 600      # 10 мин
CARD_LIFETIME_MAX = 900      # 15 мин

CHOICE_EVENTS: dict[str, dict] = {
    # ────────────────────────── mystic_chest
    "mystic_chest": {
        "text": "🎁 В пыли лежит старый сундук, закованный ржавыми цепями.",
        "options": {

            "open": {               # риск–награда
                "label": "Взломать крышку",
                "outcomes": [
                    # 35 % – горсть золотых
                    {"field": "coins",  "sign": "+", "amt_min": 120, "amt_max": 280, "weight": 35},
                    # 10 % – редкий лут
                    {"field": "item",   "sign": "+", "item": "diamond", "amt_min": 1, "amt_max": 1, "weight": 10},
                    # 30 % – ловушка-бомба: монеты летят прочь
                    {"field": "coins",  "sign": "-", "amt_min": 100, "amt_max": 220, "weight": 30},
                    # 25 % – облако пыли, кашель → теряешь энергию
                    {"field": "energy", "sign": "-", "amt_min": 20,  "amt_max": 35,  "weight": 25},
                ]
            },

            "leave": {              # осторожный вариант
                "label": "Отойти тихо",
                "outcomes": [
                    # 20 % – чуточку опыта за благоразумие
                    {"field": "xp",     "sign": "+", "amt_min": 40,  "amt_max": 70,  "weight": 20},
                    # 80 % – ничего ценного: потеря времени → голод
                    {"field": "hunger", "sign": "-", "amt_min": 30,  "amt_max": 50,  "weight": 80},
                ]
            }
        }
    },

    # ────────────────────────── strange_mushroom
    "strange_mushroom": {
        "text": "🍄 Из влажной стены торчит пульсирующий гриб-мутант.",
        "options": {

            "eat": {
                "label": "Съесть (брр…)",
                "outcomes": [
                    # 25 % – прилив сил
                    {"field": "energy", "sign": "+", "amt_min": 25, "amt_max": 45, "weight": 25},
                    # 25 % – насыщение (чуть меньше голода)
                    {"field": "hunger", "sign": "+", "amt_min": 20, "amt_max": 35, "weight": 25},
                    # 50 % – отравление! падает энергия и голод
                    {"field": "energy", "sign": "-", "amt_min": 30, "amt_max": 50, "weight": 50},
                ]
            },

            "ignore": {
                "label": "Оставить в покое",
                "outcomes": [
                    # 15 % – любопытство даёт XP
                    {"field": "xp",    "sign": "+", "amt_min": 30, "amt_max": 60, "weight": 15},
                    # 35 % – глупо пинаешь гриб → спор разлетается, теряешь монеты
                    {"field": "coins", "sign": "-", "amt_min": 40, "amt_max": 90, "weight": 35},
                    # 50 % – ничего не произошло, но устал: −энергия
                    {"field": "energy","sign": "-", "amt_min": 10, "amt_max": 20, "weight": 50},
                ]
            }
        }
    },
}

CHOICE_EVENTS.update({
        "old_miner": {
        "text": "👴 У костра сидит дряхлый шахтёр и просит «чутка руды на зубок».",
        "options": {
            "share_ore": {          # добрый жест, но может оказаться убыточным
                "label": "Отсыпать руды",
                "outcomes": [
                    # 35 % — плюсовые монеты
                    {"field": "coins", "sign": "+", "amt_min": 70, "amt_max": 140, "weight": 35},
                    # 10 % — дарит кирку
                    {"field": "item",  "sign": "+", "item": "iron_pickaxe", "amt_min": 1, "amt_max": 1, "weight": 10},
                    # 55 % — «спасибо, сынок» и …ничего, ты в минусе
                    {"field": "coins", "sign": "-", "amt_min": 50, "amt_max": 120, "weight": 55},
                ]
            },
            "refuse": {
                "label": "Отказать",
                "outcomes": [
                    # 30 % — слегка растёт опыт (спокоен, но бессердечен)
                    {"field": "xp",    "sign": "+", "amt_min": 20, "amt_max": 40, "weight": 30},
                    # 70 % — дед ругается, кидает камнем → теряешь деньги
                    {"field": "coins", "sign": "-", "amt_min": 80, "amt_max": 160, "weight": 70},
                ]
            }
        }
    },

    # ────────────────────────────────── underground_lake
    "underground_lake": {
        "text": "🌊 Подземное озеро с обманчиво-чистой водой поблёскивает в глубине.",
        "options": {
            "drink": {
                "label": "Напиться",
                "outcomes": [
                    {"field": "energy", "sign": "+", "amt_min": 25, "amt_max": 45, "weight": 40},
                    # 60 % – заболит живот, падает сытость
                    {"field": "hunger", "sign": "-", "amt_min": 40, "amt_max": 70, "weight": 60},
                ]
            },
            "fill_bottle": {
                "label": "Набрать во флягу",
                "outcomes": [
                    # 80 % — вместо воды мутная жижа: придётся вылить (просто трата времени)
                    {"field": "xp",   "sign": "-", "amt_min": 5,  "amt_max": 15, "weight": 80},
                    # 20 % — реально чистая вода-бафф
                    {"field": "item", "sign": "+", "item": "water_bottle", "amt_min": 1, "amt_max": 1, "weight": 20},
                ]
            }
        }
    },

    # ────────────────────────────────── lost_miner
    "lost_miner": {
        "text": "⛏️ Из темноты выскакивает перепуганный новичок-шахтёр: «покажи дорогу…»",
        "options": {
            "help": {
                "label": "Проводить",
                "outcomes": [
                    {"field": "coins", "sign": "+", "amt_min": 60, "amt_max": 120, "weight": 40},
                    # устал → теряешь энергию
                    {"field": "energy","sign": "-", "amt_min": 15, "amt_max": 25, "weight": 60},
                ]
            },
            "ignore": {
                "label": "Сбежать",
                "outcomes": [
                    # карма – потеря XP / монет
                    {"field": "xp",    "sign": "-", "amt_min": 10, "amt_max": 25, "weight": 70},
                    {"field": "coins", "sign": "-", "amt_min": 40, "amt_max": 70, "weight": 30},
                ]
            }
        }
    },

    # ────────────────────────────────── mysterious_altar
    "mysterious_altar": {
        "text": "🔮 Обсидиановый алтарь мерцает зловещим светом.",
        "options": {
            "touch": {
                "label": "Прикоснуться",
                "outcomes": [
                    {"field": "energy", "sign": "+", "amt_min": 15, "amt_max": 25, "weight": 35},
                    {"field": "energy", "sign": "-", "amt_min": 20, "amt_max": 35, "weight": 65},
                ]
            },
            "mine": {
                "label": "Долбануть киркой",
                "outcomes": [
                    {"field": "item",   "sign": "+", "item": "obsidian_shard", "amt_min": 1, "amt_max": 1, "weight": 30},
                    {"field": "energy", "sign": "-", "amt_min": 25, "amt_max": 40, "weight": 70},
                ]
            },
            "leave": {
                "label": "Свалить подальше",
                "outcomes": [
                    {"field": "xp", "sign": "+", "amt_min": 5, "amt_max": 10, "weight": 100},
                ]
            }
        }
    },

    # ────────────────────────────────── cave_stream
    "cave_stream": {
        "text": "🌪️ Громкий подземный поток перекрывает тоннель.",
        "options": {
            "swim": {
                "label": "Рискнуть вплавь",
                "outcomes": [
                    {"field": "energy", "sign": "-", "amt_min": 15, "amt_max": 25, "weight": 75},
                    {"field": "xp",     "sign": "+", "amt_min": 15, "amt_max": 25, "weight": 25},
                ]
            },
            "build_bridge": {
                "label": "Соорудить хлипкий мост",
                "outcomes": [
                    {"field": "coins", "sign": "-", "amt_min": 30, "amt_max": 60, "weight": 60},
                    {"field": "coins", "sign": "+", "amt_min": 70, "amt_max": 120, "weight": 40},
                ]
            },
            "turn_back": {
                "label": "Развернуться",
                "outcomes": [
                    {"field": "xp", "sign": "+", "amt_min": 2, "amt_max": 5, "weight": 100},
                ]
            }
        }
    },

    # ────────────────────────────────── greedy_bat
    "greedy_bat": {
        "text": "🦇 Жирная летучая мышь вцепилась в твой мешок!",
        "options": {
            "shoo": {
                "label": "Размахнуться",
                "outcomes": [
                    {"field": "coins", "sign": "-", "amt_min": 20, "amt_max": 35, "weight": 60},
                    {"field": "coins", "sign": "+", "amt_min": 15, "amt_max": 25, "weight": 40},
                ]
            },
            "feed": {
                "label": "Отдать мясо",
                "outcomes": [
                    {"field": "item",  "sign": "-", "item": "meat", "amt_min": 1, "amt_max": 1, "weight": 60},
                    {"field": "item",  "sign": "+", "item": "amethyst", "amt_min": 1, "amt_max": 1, "weight": 40},
                ]
            },
            "ignore": {
                "label": "Пустить на самотёк",
                "outcomes": [
                    {"field": "item", "sign": "-", "item": "stone", "amt_min": 5, "amt_max": 10, "weight": 100},
                ]
            }
        }
    },

    "toxic_fumes": {
        "text": "☣️ В узком тоннеле чувствуется едкий запах газа.",
        "options": {
            "rush": {  # пробежать
                "label": "Прорыв вперёд",
                "outcomes": [
                    {"field": "energy", "sign": "-", "amt_min": 20, "amt_max": 35, "weight": 70},
                    {"field": "xp",     "sign": "+", "amt_min": 15, "amt_max": 25, "weight": 30},
                ]
            },
            "mask": {  # надеть импров. маску
                "label": "Соорудить маску",
                "outcomes": [
                    {"field": "item",   "sign": "+", "item": "coal", "amt_min": 1, "amt_max": 2, "weight": 40},
                    {"field": "energy", "sign": "-", "amt_min": 10, "amt_max": 15, "weight": 60},
                ]
            },
            "retreat": {
                "label": "Отойти подальше",
                "outcomes": [
                    {"field": "xp", "sign": "-", "amt_min": 5, "amt_max": 10, "weight": 100},
                ]
            },
        }
    },

    # 2 ▸ ОБРУШЕНИЕ
    "cave_in": {
        "text": "🪨 С потолка посыпались камни — начинается обрушение!",
        "options": {
            "shield": {
                "label": "Прикрыться щитом",
                "outcomes": [
                    {"field": "item",   "sign": "-", "item": "iron_ingot", "amt_min": 1, "amt_max": 2, "weight": 90},
                    {"field": "xp",     "sign": "+", "amt_min": 20, "amt_max": 35, "weight": 10},
                ]
            },
            "sprint": {
                "label": "Бежать изо всех сил",
                "outcomes": [
                    {"field": "energy", "sign": "-", "amt_min": 25, "amt_max": 40, "weight": 70},
                    {"field": "coins",  "sign": "-", "amt_min": 50, "amt_max": 90, "weight": 30},
                ]
            },
        }
    },

    # 3 ▸ ПРОКЛЯТЫЙ САМОРОДОК
    "cursed_nugget": {
        "text": "💀 Ты нашёл странный мерцающий самородок — он выглядит… не по-добру.",
        "options": {
            "take": {
                "label": "Забрать",
                "outcomes": [
                    {"field": "item",  "sign": "+", "item": "gold", "amt_min": 1, "amt_max": 2, "weight": 30},
                    {"field": "hunger","sign": "-", "amt_min": 25,  "amt_max": 40, "weight": 70},
                ]
            },
            "leave": {
                "label": "Оставить как есть",
                "outcomes": [
                    {"field": "xp", "sign": "+", "amt_min": 10, "amt_max": 20, "weight": 40},
                    {"field": "coins","sign": "-", "amt_min": 30, "amt_max": 60, "weight": 60},
                ]
            }
        }
    },

    # 4 ▸ ГНОМ-РОСТОВЩИК
    "gnome_loan": {
        "text": "💰 Миниатюрный гном-ростовщик предлагает «выгодный» займ под 200 %.",
        "options": {
            "accept": {
                "label": "Взять монеты",
                "outcomes": [
                    {"field": "coins", "sign": "+", "amt_min": 120, "amt_max": 180, "weight": 30},
                    {"field": "coins", "sign": "-", "amt_min": 200, "amt_max": 300, "weight": 70},
                ]
            },
            "decline":{
                "label":"Отказаться",
                "outcomes":[
                    {"field": "xp", "sign":"-", "amt_min": 10, "amt_max": 20, "weight": 100},
                ]
            }
        }
    },

    # 5 ▸ СКОЛЬЗКИЙ УКЛОН
    "slippery_slope": {
        "text": "🧊 Пол покрыт ледяной коркой — каждый шаг риск сорваться вниз.",
        "options": {
            "slide_down": {
                "label": "Съехать намеренно",
                "outcomes": [
                    {"field": "energy", "sign": "-", "amt_min": 15, "amt_max": 25, "weight": 60},
                    {"field": "item",   "sign": "+", "item": "stone", "amt_min": 5, "amt_max": 8, "weight": 40},
                ]
            },
            "crawl_back": {
                "label": "Ползти наверх",
                "outcomes": [
                    {"field": "xp",    "sign": "+", "amt_min": 15, "amt_max": 25, "weight": 30},
                    {"field": "hunger","sign": "-", "amt_min": 20, "amt_max": 35, "weight": 70},
                ]
            }
        }
    },

    # 6 ▸ НЕИСПРАВНАЯ ЛАМПА
    "broken_lantern": {
        "text": "🔦 Масляная лампа мерцает… и вдруг гаснет!",
        "options": {
            "relight": {
                "label": "Попробовать зажечь снова",
                "outcomes": [
                    {"field": "energy", "sign": "-", "amt_min": 10, "amt_max": 20, "weight": 60},
                    {"field": "xp",     "sign": "+", "amt_min": 10, "amt_max": 20, "weight": 40},
                ]
            },
            "leave_dark": {
                "label": "Идти в темноте",
                "outcomes": [
                    {"field": "item",  "sign": "-", "item": "coal", "amt_min": 2, "amt_max": 4, "weight": 80},
                    {"field": "energy","sign": "-", "amt_min": 5,  "amt_max": 10, "weight": 20},
                ]
            }
        }
    },
})

async def _expire_choice_card(bot: Bot, cid: int, mid: int):
    """Через 10-15 мин удаляем/переводим карточку в ‘expired’-вид."""
    await asyncio.sleep(random.randint(CARD_LIFETIME_MIN, CARD_LIFETIME_MAX))

    try:
        await bot.edit_message_text(
            "⌛ <i>Ты потерял свой шанс…</i>\n<b>Карточка устарела.</b>",
            chat_id=cid, message_id=mid, parse_mode="HTML"
        )
    except aiogram.exceptions.TelegramBadRequest:
        # сообщение уже удалено/отредактировано коллбэком — молча игнорируем
        pass

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
    if random.random() > 0.20:          # 20 % шанс что вообще появится карточка
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

    msg = await bot.send_message(
        cid,
        f"{mention}, {ev['text']}\n\n<i>Сделай выбор:</i>",
        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )
    asyncio.create_task(_expire_choice_card(bot, cid, msg.message_id))

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

