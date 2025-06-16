from .base_commands import router as base_router
from .shop import router as shop_router

def register_handlers(dp):
    dp.include_router(base_router)
    dp.include_router(shop_router)