import dataclasses
import datetime
import logging
import math
import random
import sqlite3
from typing import Any, Dict, List

import bravado
from bravado.client import SwaggerClient

from eve import world
from eve.orm_util import adopt_json_for_db, dataclass_from_row


@dataclasses.dataclass(frozen=True)
class ItemPrice:
    type_id: int = -1
    last_refreshed: datetime.datetime = datetime.datetime.fromtimestamp(0)
    daily_trade_volume: float = 0.0
    low_price: float = 0.0
    high_price: float = math.inf

    def is_traded(self):
        return math.isfinite(self.high_price)


@dataclasses.dataclass(frozen=True)
class ItemPriceWithDetails:
    item_price: ItemPrice
    history: List[Any]
    buy_orders: List[Any]
    sell_orders: List[Any]


MIN_TOTAL_COST = 100000000
MIN_TOTAL_QTY = 2
BUY_ORDER_SETUP_DISCOUNT = 0.95
SELL_ORDER_SETUP_DISCOUNT = 1.05


def buy_order_price(buy_orders: List[Dict[str, Any]]) -> float:
    prices = [
        (x["volume_remain"], x["price"])
        for x in buy_orders
        if x["is_buy_order"] and x["volume_remain"] > 0
    ]
    prices.sort(key=lambda p: p[1], reverse=True)
    total_cost = 0.0
    total_qty = 0.0
    for p in prices:
        total_cost += p[0] * p[1]
        total_qty += p[0]
        if total_cost >= MIN_TOTAL_COST and total_qty >= MIN_TOTAL_QTY:
            return p[1]
    return 0.0


def is_good_sell_order(x: Dict[str, Any]) -> bool:
    return (
        (not x["is_buy_order"])
        and x["volume_remain"] > 0
        and x["location_id"] == world.JITA_4_4_STATION_ID
    )


def sell_order_price(sell_orders: List[Dict[str, Any]]) -> float:
    prices = [
        (x["volume_remain"], x["price"])
        for x in sell_orders
        if is_good_sell_order(x)
    ]
    prices.sort(key=lambda p: p[1])
    total_cost = 0.0
    total_qty = 0.0
    for p in prices:
        total_cost += p[0] * p[1]
        total_qty += p[0]
        if total_cost >= MIN_TOTAL_COST and total_qty >= MIN_TOTAL_QTY:
            return p[1]
    return math.inf


def get_market_orders(
    api: SwaggerClient, type_id: int, order_type: str
) -> List[Any]:
    try:
        return (
            api.Market.get_markets_region_id_orders(
                region_id=world.JITA_REGION_ID,
                type_id=type_id,
                order_type=order_type,
            )
            .response()
            .result
        )
    except bravado.exception.HTTPNotFound:
        return []


def get_market_data(api: SwaggerClient, type_id: int) -> ItemPriceWithDetails:
    low_price = 0.0
    high_price = math.inf
    daily_trade_volume = 0.0

    try:
        history = (
            api.Market.get_markets_region_id_history(
                region_id=world.JITA_REGION_ID, type_id=type_id
            )
            .response()
            .result
        )
        history = sorted(history, key=lambda d: d["date"])
        if len(history) > 90:
            history = history[-90:]
        history = list(history)
        if len(history) > 30:
            short = history[-30:]
        else:
            short = history[:]
        if short:
            daily_trade_volume = sum([d["volume"] for d in short]) / len(short)
        valid_days = [d for d in short if d["volume"] >= MIN_TOTAL_QTY]
        if len(valid_days) > 10:
            low_price = BUY_ORDER_SETUP_DISCOUNT * min(
                d["lowest"] for d in valid_days
            )
            high_price = SELL_ORDER_SETUP_DISCOUNT * max(
                d["highest"] for d in valid_days
            )
    except bravado.exception.HTTPNotFound:
        history = []
        pass

    buy_orders = get_market_orders(api, type_id, "buy")
    low_price = max(low_price, buy_order_price(buy_orders))

    sell_orders = get_market_orders(api, type_id, "sell")
    high_price = min(high_price, sell_order_price(sell_orders))

    return ItemPriceWithDetails(
        ItemPrice(
            type_id,
            datetime.datetime.now(),
            daily_trade_volume,
            low_price,
            high_price,
        ),
        history,
        buy_orders,
        sell_orders,
    )


def store_item_price(conn: sqlite3.Connection, ipwd: ItemPriceWithDetails):
    ip = ipwd.item_price
    with conn:
        conn.execute(
            "REPLACE INTO eveMarket( "
            "  type_id,  last_refreshed, daily_trade_volume, "
            "  low_price, high_price, history"
            ") VALUES (?, ?, ?, ?, ?, ?)",
            (
                ip.type_id,
                int(ip.last_refreshed.timestamp()),
                ip.daily_trade_volume,
                ip.low_price,
                ip.high_price,
                adopt_json_for_db(ipwd.history),
            ),
        )
        if ipwd.sell_orders or ipwd.buy_orders:
            conn.execute(
                "INSERT INTO eveMarketHistory("
                "   type_id, retrieved_on, buy_orders, sell_orders) "
                "VALUES (?, ?, ?, ?)",
                (
                    ip.type_id,
                    int(ip.last_refreshed.timestamp()),
                    adopt_json_for_db(ipwd.buy_orders),
                    adopt_json_for_db(ipwd.sell_orders),
                ),
            )


class ItemPriceCache:
    def __init__(self, conn: sqlite3.Connection, api: SwaggerClient):
        self.conn = conn
        self.api = api

    def find_item_price(self, item_type: world.ItemType) -> ItemPrice:
        ip = dataclass_from_row(
            ItemPrice,
            self.conn.execute(
                "SELECT "
                "  type_id, last_refreshed, daily_trade_volume, "
                "  low_price, high_price "
                "FROM eveMarket WHERE type_id = ?",
                (item_type.id,),
            ).fetchone(),
        )
        if datetime.datetime.now() - ip.last_refreshed <= datetime.timedelta(
            hours=random.uniform(6, 6)
        ):
            return ip
        logging.info("retriving pricing data for %s", item_type.name)
        ipwd = get_market_data(self.api, item_type.id)
        store_item_price(self.conn, ipwd)
        return ipwd.item_price


def create_table(conn: sqlite3.Connection):
    CREATE_TABLE_SQL = """
        CREATE TABLE IF NOT EXISTS "eveMarket" (
            "type_id" INTEGER PRIMARY KEY NOT NULL,
            "last_refreshed" INTEGER NOT NULL,
            "daily_trade_volume" REAL NOT NULL,
            "low_price" REAL NOT NULL,
            "high_price" REAL NOT NULL,
            "history" JSON NOT NULL
        );
        CREATE TABLE IF NOT EXISTS "eveMarketHistory" (
            "type_id" INTEGER PRIMARY KEY NOT NULL,
            "retrieved_on" INTEGER NOT NULL,
            "buy_orders" JSON NOT NULL,
            "sell_orders" JSON NOT NULL
        );
        """
    conn.execute(CREATE_TABLE_SQL)
