import bot
from .base_commands import router as base_router
from .shop import router as shop_router
from .crafting import router as crafting_router
from .eat import router as eat_router
from .use import router as use_router
from .groups import router as group_router
from .cases import router as cases_router
from .cavepass import router as pass_router
from .devutils import router as dev_router
from .badgeshop import router as badgeshop_router
from .code import router as code_router
from .seals import router as seals_router
from .cave_clash import router as clash_router, setup_weekly_reset
from .choice_events import router as choice_events_router
from .pass_track import router as pass_track_router
from .helmets import router as helmets_router
from .aliases import router as alias_router

def register_handlers(dp):
    dp.include_router(base_router)
    dp.include_router(shop_router)
    dp.include_router(crafting_router)
    dp.include_router(eat_router)
    dp.include_router(use_router)
    dp.include_router(group_router)
    dp.include_router(cases_router)
    dp.include_router(pass_router)
    dp.include_router(dev_router)
    dp.include_router(code_router)
    dp.include_router(badgeshop_router)
    dp.include_router(seals_router)
    dp.include_router(clash_router)
    dp.include_router(choice_events_router)
    dp.include_router(pass_track_router)
    dp.include_router(helmets_router)
    dp.include_router(alias_router)

    setup_weekly_reset(bot)