import logging

from eve import contract, market, services, world

DB_FILE_NAME = "/home/inazarenko/src/eve/data/db.sqlite"


def main():
    logging.basicConfig(level=logging.INFO)
    serv = services.Services()
    w = world.World(serv.reference_db)
    ipc = market.ItemPriceCache(serv.store_db, serv.api)

    for region_id in world.MY_REGIONS:
        contract.refresh_contracts(serv.store_db, serv.api, region_id)

    for region_id in world.MY_REGIONS:
        contract.update_region_estimates(serv.store_db, w, ipc, region_id)

    contract.print_profitable_contracts(serv.store_db, w)


if __name__ == "__main__":
    main()
