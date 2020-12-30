import dataclasses
import logging
import sqlite3
import datetime
import math
import bravado
import random
from typing import Any, Dict, List

from bravado.client import SwaggerClient
from eve.orm_util import dataclass_from_row
from eve import world


@dataclasses.dataclass(frozen=True)
class ItemPrice:
    type_id: int = -1
    last_refreshed: datetime.datetime = datetime.datetime.fromtimestamp(0)
    daily_trade_volume: float = 0.0
    low_price: float = 0.0
    high_price: float = math.inf

    def is_traded(self):
        return math.isfinite(self.high_price)


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


def get_market_data(api: SwaggerClient, type_id: int) -> ItemPrice:
    low_price = 0.0
    high_price = math.inf
    daily_trade_volume = 0.0

    try:
        hist = (
            api.Market.get_markets_region_id_history(
                region_id=world.JITA_REGION_ID, type_id=type_id
            )
            .response()
            .result
        )
        hist = sorted(hist, key=lambda d: d["date"])
        if len(hist) > 30:
            hist = hist[-30:]
        if hist:
            daily_trade_volume = sum([d["volume"] for d in hist]) / len(hist)
        valid_days = [d for d in hist if d["volume"] >= MIN_TOTAL_QTY]
        if len(valid_days) > 10:
            low_price = BUY_ORDER_SETUP_DISCOUNT * min(
                d["lowest"] for d in valid_days
            )
            high_price = SELL_ORDER_SETUP_DISCOUNT * max(
                d["highest"] for d in valid_days
            )
    except bravado.exception.HTTPNotFound:
        pass

    try:
        buy_orders = (
            api.Market.get_markets_region_id_orders(
                region_id=world.JITA_REGION_ID,
                type_id=type_id,
                order_type="buy",
            )
            .response()
            .result
        )
        low_price = max(low_price, buy_order_price(buy_orders))
    except bravado.exception.HTTPNotFound:
        pass

    try:
        sell_orders = (
            api.Market.get_markets_region_id_orders(
                region_id=world.JITA_REGION_ID,
                type_id=type_id,
                order_type="sell",
            )
            .response()
            .result
        )
        high_price = min(high_price, sell_order_price(sell_orders))
    except bravado.exception.HTTPNotFound:
        pass

    return ItemPrice(
        type_id,
        datetime.datetime.now(),
        daily_trade_volume,
        low_price,
        high_price,
    )


def store_item_price(conn: sqlite3.Connection, ip: ItemPrice):
    with conn:
        conn.execute(
            "REPLACE INTO eveMarket( "
            "  type_id,  last_refreshed, daily_trade_volume, "
            "  low_price, high_price"
            ") VALUES (?, ?, ?, ?, ?)",
            (
                ip.type_id,
                int(ip.last_refreshed.timestamp()),
                ip.daily_trade_volume,
                ip.low_price,
                ip.high_price,
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
        if datetime.datetime.now() - ip.last_refreshed > datetime.timedelta(
            hours=random.uniform(6, 6)
        ):
            logging.info("retriving pricing data for %s", item_type.name)
            ip = get_market_data(self.api, item_type.id)
            store_item_price(self.conn, ip)
        return ip


def create_table(conn: sqlite3.Connection):
    CREATE_TABLE_SQL = """
        CREATE TABLE IF NOT EXISTS "eveMarket" (
            "type_id" INTEGER PRIMARY KEY NOT NULL,
            "last_refreshed" INTEGER NOT NULL,
            "daily_trade_volume" REAL NOT NULL,
            "low_price" REAL NOT NULL,
            "high_price" REAL NOT NULL
        );
        """
    conn.execute(CREATE_TABLE_SQL)