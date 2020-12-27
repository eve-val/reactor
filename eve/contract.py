from eve.orm_util import dataclass_from_row
import sqlite3
import datetime
import json
import logging
import bravado
from typing import Any, Dict, List, Optional
from bravado.client import SwaggerClient
from eve.world import Station, World, ItemType
import dataclasses
import textwrap


def _db_json_encoder(v: Any) -> Any:
    if type(v) == datetime.datetime:
        return int(v.timestamp())
    return v


def adopt_json_for_db(src: Any) -> str:
    return json.dumps(src, default=_db_json_encoder)


def create_table(conn: sqlite3.Connection):
    CREATE_TABLE_SQL = """
        CREATE TABLE IF NOT EXISTS "eveContracts" (
            "contract_id" INTEGER PRIMARY KEY NOT NULL,
            "last_seen" INTEGER NOT NULL,
            "region_id" INTEGER NOT NULL,
            "title" TEXT,
            "price" REAL NOT NULL,
            "raw_data" JSON,
            "items" JSON
        );
        """
    conn.execute(CREATE_TABLE_SQL)


def insert_contracts(
    conn: sqlite3.Connection,
    last_seen: datetime.datetime,
    region_id: int,
    contracts: List[Dict[str, Any]],
):
    expiration_cutoff = last_seen + datetime.timedelta(hours=1)
    data = [
        (
            c["contract_id"],
            int(last_seen.timestamp()),
            region_id,
            c["title"],
            c["price"],
            adopt_json_for_db(c),
        )
        for c in contracts
        if c["type"] == "item_exchange"
        and c["date_expired"] >= expiration_cutoff
    ]
    logging.info("inserting %s contracts", len(data))
    with conn:
        result = conn.executemany(
            "INSERT INTO eveContracts("
            "  contract_id, last_seen, region_id, title, price, raw_data) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(contract_id) DO "
            "  UPDATE SET last_seen = excluded.last_seen",
            data,
        )
        logging.info("rows updated: %s", result.rowcount)


def delete_old_contracts(
    conn: sqlite3.Connection, last_seen: datetime.datetime, region_id: int
):
    with conn:
        r = conn.execute(
            "DELETE FROM eveContracts WHERE last_seen < ? AND region_id = ?",
            (int(last_seen.timestamp()), region_id),
        )
        logging.info("deleted %s obsolete contracts", r.rowcount)


def delete_contract(conn: sqlite3.Connection, contract_id: int):
    with conn:
        conn.execute(
            "DELETE FROM eveContracts WHERE contract_id = ?",
            (contract_id,),
        )


def retrieve_contract_items(
    conn: sqlite3.Connection, api: SwaggerClient, contract_id: int
):
    try:
        resp = api.Contracts.get_contracts_public_items_contract_id(
            contract_id=contract_id
        ).response()
    except (bravado.exception.HTTPForbidden, bravado.exception.HTTPNotFound):
        logging.info(
            "contract %s returns 'forbidden' or 'not found'", contract_id
        )
        delete_contract(conn, contract_id)
        return
    except Exception as e:
        logging.info(
            "contract %s cannot be retrieved; exception: %s", contract_id, e
        )
        logging.info("exc type: %s", type(e))
        return

    if resp.metadata.status_code == 204:
        logging.info(
            "contract %s returns 204: accepted or expired", contract_id
        )
        delete_contract(conn, contract_id)
        return

    logging.info("contract %s has %s items", contract_id, len(resp.result))
    with conn:
        conn.execute(
            "UPDATE eveContracts SET items = ? WHERE contract_id = ?",
            (adopt_json_for_db(resp.result), contract_id),
        )


def get_items_for_contracts(
    conn: sqlite3.Connection, api: SwaggerClient, region_id: int
):
    cursor = conn.cursor()
    cursor.execute(
        "SELECT contract_id FROM eveContracts "
        "WHERE region_id = ? AND items IS NULL",
        (region_id,),
    )
    contract_ids = [row[0] for row in cursor.fetchall()]
    logging.info(
        "fetching contract items for %s contracts in region %s",
        len(contract_ids),
        region_id,
    )
    for cid in contract_ids:
        retrieve_contract_items(conn, api, cid)


def refresh_contracts(
    conn: sqlite3.Connection,
    api: SwaggerClient,
    region_id: int,
):
    last_seen = datetime.datetime.now(datetime.timezone.utc)
    resp = api.Contracts.get_contracts_public_region_id(
        region_id=region_id,
        page=1,
    ).response()
    page_count = int(resp.metadata.headers["X-Pages"])
    logging.info(
        "found %s pages of contracts for region %s", page_count, region_id
    )
    insert_contracts(conn, last_seen, region_id, resp.result)
    for page in range(2, page_count + 1):
        resp = api.Contracts.get_contracts_public_region_id(
            region_id=region_id, page=page
        ).response()
        insert_contracts(conn, last_seen, region_id, resp.result)
    delete_old_contracts(conn, last_seen, region_id)
    get_items_for_contracts(conn, api, region_id)


@dataclasses.dataclass(frozen=True)
class Blueprint:
    material_efficiency: int
    time_efficiency: int
    is_copy: bool
    runs: int

    def pretty_str(self) -> str:
        bp_type = f"BPC:{self.runs}" if self.is_copy else "BPO"
        return (
            f"{bp_type} ME:{self.material_efficiency} "
            f"TE:{self.time_efficiency}"
        )


@dataclasses.dataclass(frozen=True)
class ContractItem:
    quantity: int
    item_type: ItemType
    blueprint: Optional[Blueprint]

    def pretty_str(self) -> str:
        s = f"{self.quantity}x {self.item_type.name}"
        if self.blueprint:
            s += " " + self.blueprint.pretty_str()
        return s


@dataclasses.dataclass(frozen=True)
class Contract:
    id: int
    region_id: int
    title: str
    price: float
    volume: float
    date_expired: datetime.datetime
    station: Station
    items: List[ContractItem]

    def pretty_str(self) -> str:
        s = [f"Contract ({self.id}): {self.title}"]
        s.append(f"Price: {self.price:,.0f}")
        s.append(f"Valid until: {self.date_expired}")
        s.append(f"Volume: {self.volume:,.0f}")
        s.append(f"Located: {self.station.name} ({self.station.security:.1f})")
        for item in self.items:
            s.append(textwrap.indent(item.pretty_str(), "  "))
        return "\n".join(s)


def parse_contract_item(w: World, item: Dict[str, Any]) -> ContractItem:
    quantity = item["quantity"]
    it = w.find_item_type(item["type_id"])
    bp = None
    if it.is_blueprint:
        bp = Blueprint(
            item["material_efficiency"],
            item["time_efficiency"],
            bool(item["is_blueprint_copy"]),
            int(item["runs"] or 0),
        )
    return ContractItem(item_type=it, blueprint=bp, quantity=quantity)


def parse_contract_row(w: World, row: sqlite3.Row) -> Contract:
    cid, region_id, title, price, raw_data_s, items_s = row
    raw_data = json.loads(raw_data_s)
    items = json.loads(items_s)
    parsed_items = [parse_contract_item(w, i) for i in items]

    return Contract(
        cid,
        region_id,
        title,
        price,
        raw_data["volume"],
        datetime.datetime.fromtimestamp(raw_data["date_expired"]),
        w.find_station(raw_data["end_location_id"]),
        parsed_items,
    )


def get_contract(
    conn: sqlite3.Connection, w: World, contract_id: int
):
    row = conn.execute(
        "SELECT "
        "  contract_id, region_id, title, price, raw_data, items "
        "FROM eveContracts "
        "WHERE contract_id = ?",
        (contract_id,),
    ).fetchone()
    if row is None:
        return None
    return parse_contract_row(w, row)


# api.Contracts.get_contracts_public_region_id(
#     region_id=10000002,
#     page=1,
# ).response()
# _request_options={"headers": {"If-None-Match": '"4192a69a52032f7e0825b4a7268bdbe7df4b7a5fa4059813d692656"'}}
