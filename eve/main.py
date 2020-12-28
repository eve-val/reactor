import sqlite3
import logging
from bravado.client import SwaggerClient

from eve import contract
from eve import world
from eve import market


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
    # print(market.get_market_data(api, 34))
    # print(market.get_market_data(api, 45626))

    for region_id in world.MY_REGIONS:
        contract.refresh_contracts(conn, api, region_id)

    w = world.World(conn)
    ipc = market.ItemPriceCache(conn, api)
    for region_id in world.MY_REGIONS:
        contract.update_region_estimates(conn, w, ipc, region_id)

    contract.print_profitable_contracts(conn, w)
    # c = contract.get_contract(conn, w, 165610141)
    # print(c.pretty_str())
    # print(contract.estimate_contract_value(w, ipc, c))


if __name__ == "__main__":
    main()
