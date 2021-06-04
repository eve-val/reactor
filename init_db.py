from eve import market, services

def init_db():
    serv = services.Services()
    market.create_tables(serv.store_db)