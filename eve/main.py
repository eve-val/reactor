from bravado.client import SwaggerClient
from typing import Any, NamedTuple

from eve.iteminfo import ItemInfoCache

JITA = 10000002
# api.Contracts.get_contracts_public_region_id(
#     region_id=10000002,
#     page=1,
# ).response()
# _request_options={"headers": {"If-None-Match": '"4192a69a52032f7e0825b4a7268bdbe7df4b7a5fa4059813d692656"'}}


# def get_item_type(api: SwaggerClient, type_id: int):
#     props = (
#         api.Universe.get_universe_types_type_id(type_id=type_id)
#         .response()
#         .result
#     )
#     r = ItemInfo(
#         type_id=type_id,
#         name=props["name"],
#         volume=props["volume"],
#         price_history=api.Market.get_markets_region_id_history(
#             region_id=JITA, type_id=type_id
#         )
#         .response()
#         .result,
#         buy_orders=api.Market.get_markets_region_id_orders(
#             region_id=JITA, type_id=type_id, order_type="buy"
#         )
#         .response()
#         .result,
#         sell_orders=api.Market.get_markets_region_id_orders(
#             region_id=JITA, type_id=type_id, order_type="sell"
#         )
#         .response()
#         .result,
#     )
#     return r


class ContractList(NamedTuple):
    region_id: int
    first_page_hash: str
    contracts: Any


def get_all_contracts(api: SwaggerClient, region_id: int = JITA):
    resp = api.Contracts.get_contracts_public_region_id(
        region_id=region_id,
        page=1,
    ).response()
    contracts = list(resp.result)
    page_count = int(resp.metadata.headers["X-Pages"])
    first_page_hash = resp.metadata.headers["ETag"].strip('"')
    for page in range(2, page_count + 1):
        resp = api.Contracts.get_contracts_public_region_id(
            region_id=region_id, page=page
        ).response()
        contracts.extend(resp.result)
    contracts = [c for c in contracts if c["type"] == "item_exchange"]
    return ContractList(
        region_id=region_id,
        first_page_hash=first_page_hash,
        contracts=contracts,
    )


ITEM_CACHE_FILE_NAME = '/home/inazarenko/src/eve/data/item_info_cache.pickle'

def main():
    print("Hi there")
    api = SwaggerClient.from_url(
        "https://esi.evetech.net/latest/swagger.json?datasource=tranquility",
        config={"use_models": False},
    )
    print("API initialized")
    items = ItemInfoCache.load(ITEM_CACHE_FILE_NAME, api)
    print(items.get(685))
    print(items.get(584))
    print(items.get(11195))
    items.save(ITEM_CACHE_FILE_NAME)
