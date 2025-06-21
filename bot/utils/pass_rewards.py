from typing import Dict, Any, List
from bot.db_local import add_item, add_money, add_xp

async def grant_pass_reward(cid:int, uid:int, reward_type:str, data:Dict[str,Any]):
    if reward_type == "coins":
        await add_money(cid, uid, int(data["coins"]))
    elif reward_type == "xp":
        await add_xp(cid, uid, int(data["xp"]))
    elif reward_type == "item":
        for itm in data["items"]:
            await add_item(cid, uid, itm["item"], int(itm["qty"]))

    else:
        raise ValueError(f"Unknown reward_type: {reward_type}")
