import dataclasses
import datetime
import math
import os
import pickle
from typing import Any, Dict, Tuple

from bravado.client import SwaggerClient

from eve import world


@dataclasses.dataclass
class ItemInfo:
    type_id: int
    name: str
    last_refresh: datetime.date
    daily_trade_volume: float
    low_price: float
    high_price: float
    properties: Dict[str, Any] = dataclasses.field(repr=False)

    def is_traded(self):
        return math.isfinite(self.high_price)


class ItemInfoCache:
    def __init__(self, api: SwaggerClient):
        self.api = api
        self.cache: Dict[int, ItemInfo] = {}
        self.today = datetime.date.today()
        self.needs_save = False

    @staticmethod
    def load(file_name: str, api: SwaggerClient) -> "ItemInfoCache":
        r = ItemInfoCache(api)
        if os.path.exists(file_name):
            with open(file_name, "rb") as f:
                r.cache = pickle.load(f)
        return r

    def get(self, type_id: int) -> ItemInfo:
        self._refresh_if_needed(type_id)
        return self.cache[type_id]

    def save(self, file_name: str):
        if not self.needs_save:
            return
        if os.path.exists(file_name):
            os.replace(file_name, f"{file_name}.backup")
        with open(file_name, "wb") as f:
            pickle.dump(self.cache, f)
        self.needs_save = True

    def _refresh_if_needed(self, type_id: int):
        if self._is_recent(type_id):
            return
        self.needs_save = True
        if type_id in self.cache:
            props = self.cache[type_id].properties
        else:
            props = self._load_props(type_id)
        name = props["name"]
        daily_trade_volume, low_price, high_price = self._get_market_data(
            type_id
        )
        self.cache[type_id] = ItemInfo(
            type_id=type_id,
            name=name,
            last_refresh=self.today,
            daily_trade_volume=daily_trade_volume,
            low_price=low_price,
            high_price=high_price,
            properties=props,
        )

    def _get_market_data(self, type_id: int) -> Tuple[float, float, float]:
        hist = (
            self.api.Market.get_markets_region_id_history(
                region_id=world.JITA_REGION_ID, type_id=type_id
            )
            .response()
            .result
        )
        if not hist:
            return 0.0, 0.0, math.inf
        hist = sorted(hist, key=lambda d: d["date"])
        if len(hist) > 30:
            hist = hist[-30:]
        daily_trade_volume = sum([d["volume"] for d in hist]) / len(hist)
        valid_days = [d for d in hist if d["volume"] > 0]
        low_price = min(d["lowest"] for d in valid_days)
        high_price = max(d["highest"] for d in valid_days)
        # TODO: the above are safe but too conservative; we can narrow down
        # the range using sell/buy orders with sufficient quantity.
        return daily_trade_volume, low_price, high_price

    def _is_recent(self, type_id: int) -> bool:
        if type_id not in self.cache:
            return False
        return self.today - self.cache[
            type_id
        ].last_refresh > datetime.timedelta(days=2)

    def _load_props(self, type_id: int):
        result = (
            self.api.Universe.get_universe_types_type_id(type_id=type_id)
            .response()
            .result
        )
        return {str(k): v for k, v in result.items()}


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
