import sqlite3
import logging
from bravado.client import SwaggerClient
from typing import Any, NamedTuple

from eve import contract
from eve import world
from eve import market

JITA = 10000002


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
    #ipc = market.ItemPriceCache(conn, api)
    #print(market.get_market_data(api, 34))
    # for region_id in world.MY_REGIONS:
    #     contract.refresh_contracts(conn, api, region_id)
    w = world.World(conn)
    c = contract.get_contract(conn, w, 165851510)
    print(c.pretty_str())
    # items = ItemInfoCache.load(ITEM_CACHE_FILE_NAME, api)
    # print(items.get(685))
    # print(items.get(584))
    # print(items.get(11195))
    # items.save(ITEM_CACHE_FILE_NAME)
