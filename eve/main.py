import sqlite3
import logging
from bravado.client import SwaggerClient
from typing import Any, NamedTuple

from eve import contract
from eve import world
from eve import market

JITA = 10000002


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


DB_FILE_NAME = "/home/inazarenko/src/eve/data/db.sqlite"


def main():
    logging.basicConfig(level=logging.INFO)
    conn = sqlite3.connect(DB_FILE_NAME)
    conn.row_factory = sqlite3.Row
    logging.info("initializing...")
    api = SwaggerClient.from_url(
        "https://esi.evetech.net/latest/swagger.json?datasource=tranquility",
        config={"use_models": False},
    )
    logging.info("EVE API initialized")
    ipc = market.ItemPriceCache(conn, api)
    print(market.get_market_data(api, 34))
    # for region_id in world.MY_REGIONS:
    #     contract.refresh_contracts(conn, api, region_id)
    # contract.print_contract(conn, api, 165851510)
    # items = ItemInfoCache.load(ITEM_CACHE_FILE_NAME, api)
    # print(items.get(685))
    # print(items.get(584))
    # print(items.get(11195))
    # items.save(ITEM_CACHE_FILE_NAME)
