import dataclasses
import sqlite3
from typing import Dict, List, Optional

from eve.orm_util import dataclass_from_row

JITA_REGION_ID = 10000002
SYNDICATE_REGION_ID = 10000041
METOPOLIS_REGION_ID = 10000042

MY_REGIONS = [
    SYNDICATE_REGION_ID,
    10000001,
    10000002,
    10000016,
    10000020,
    10000028,
    10000030,
    10000032,
    10000033,
    10000036,
    10000037,
    10000038,
    10000041,
    10000042,
    10000043,
    10000044,
    10000048,
    10000049,
    10000052,
    10000054,
    10000064,
    10000065,
    10000067,
    10000068,
    10000069,
]

JITA_4_4_STATION_ID = 60003760

# Activity IDs are used in industry-activity tables. See ramActivities.csv.
INDUSTRY_ACTIVITY_MANUFACTURING = 1
INDUSTRY_ACTIVITY_REACTIONS = 11

UNKNOWN_NAME = "<unknown>"
MAX_VALID_STATION_ID = 100000000


@dataclasses.dataclass(frozen=True)
class Station:
    id: int = -1
    name: str = UNKNOWN_NAME
    security: float = -1.0

    @property
    def is_private(self) -> bool:
        return self.id > MAX_VALID_STATION_ID


@dataclasses.dataclass(frozen=True)
class ItemType:
    id: int = -1
    name: str = UNKNOWN_NAME
    group: str = UNKNOWN_NAME
    category: str = UNKNOWN_NAME

    @property
    def full_name(self) -> str:
        return f"{self.name} / {self.group} / {self.category} ({self.id})"

    @property
    def is_blueprint(self) -> bool:
        return self.category == "Blueprint"

    @property
    def is_reaction_blueprint(self) -> bool:
        return self.is_blueprint and self.group.endswith(" Reaction Formulas")

    @property
    def is_ship(self) -> bool:
        return self.category == "Ship"

    @property
    def is_rig(self) -> bool:
        return self.group.startswith("Rig ")

    @property
    def is_capital(self) -> bool:
        return self.name.startswith("Capital ") or self.name.startswith(
            "CONCORD Capital "
        )

    @property
    def is_huge(self) -> bool:
        return (
            self.is_capital
            or self.group.startswith("Infrastructure Upgrade")
            or self.name.startswith("Standup")
            or self.name.startswith("Starbase")
        )


@dataclasses.dataclass(frozen=True)
class ItemQuantity:
    item_type: ItemType
    quantity: float


@dataclasses.dataclass(frozen=True)
class Formula:
    blueprint: ItemType
    time: float
    output: ItemQuantity
    inputs: List[ItemQuantity]

    def pretty_str(self) -> str:
        return (
            f"{self.output.quantity}x {self.output.item_type.name} "
            f"in {self.time}s from:\n"
            + "\n".join(
                f"  {i.quantity}x {i.item_type.name}" for i in self.inputs
            )
        )


class FormulaNotFound(LookupError):
    pass


class World:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def find_station(self, station_id: int) -> Station:
        if station_id > MAX_VALID_STATION_ID:
            return Station(station_id, "<private>", -1.0)
        cursor = self.conn.execute(
            "SELECT "
            "  stationID id, stationName name, security "
            "FROM staStations WHERE stationID = ?",
            (station_id,),
        )
        return dataclass_from_row(Station, cursor.fetchone())

    def find_item_type(self, type_id: int) -> ItemType:
        cursor = self.conn.execute(
            "SELECT "
            "  T.typeID id, T.typeName name, G.groupName 'group', "
            "  C.categoryName category "
            "FROM invTypes T JOIN invGroups G ON T.groupID = G.groupID "
            "  JOIN invCategories C ON G.categoryID = C.categoryID "
            "WHERE T.typeID = ?",
            (type_id,),
        )
        return dataclass_from_row(ItemType, cursor.fetchone())

    def find_item_type_by_name(self, name: str) -> ItemType:
        cursor = self.conn.execute(
            "SELECT "
            "  T.typeID id, T.typeName name, G.groupName 'group', "
            "  C.categoryName category "
            "FROM invTypes T JOIN invGroups G ON T.groupID = G.groupID "
            "  JOIN invCategories C ON G.categoryID = C.categoryID "
            "WHERE T.typeName = ?",
            (name,),
        )
        return dataclass_from_row(ItemType, cursor.fetchone())

    def find_blueprint(self, item: ItemType) -> Optional[ItemType]:
        row = self.conn.execute(
            "SELECT typeID FROM industryActivityProducts "
            "WHERE productTypeID = ? AND activityID IN (?, ?) "
            "  AND typeID != 45732",  # "Test Reaction".
            (
                item.id,
                INDUSTRY_ACTIVITY_MANUFACTURING,
                INDUSTRY_ACTIVITY_REACTIONS,
            ),
        ).fetchone()
        if not row:
            return None
        return self.find_item_type(row[0])

    def find_formula(self, blueprint: ItemType) -> Formula:
        if not blueprint.is_blueprint:
            raise ValueError(f"{blueprint.name} is not a blueprint")
        activity_id = (
            INDUSTRY_ACTIVITY_REACTIONS
            if blueprint.is_reaction_blueprint
            else INDUSTRY_ACTIVITY_MANUFACTURING
        )
        row = self.conn.execute(
            "SELECT time FROM industryActivity "
            "WHERE typeID = ? AND activityID = ?",
            (blueprint.id, activity_id),
        ).fetchone()
        if not row:
            raise FormulaNotFound(
                f"{blueprint.full_name} not found in industryActivities"
            )
        time = row[0]
        row = self.conn.execute(
            "SELECT productTypeID, quantity FROM industryActivityProducts "
            "WHERE typeID = ? AND activityID = ?",
            (blueprint.id, activity_id),
        ).fetchone()
        if not row:
            raise FormulaNotFound(
                f"{blueprint.name} not found in industryActivityProducts"
            )
        productTypeID, quantity = row
        output = ItemQuantity(self.find_item_type(productTypeID), quantity)
        mat_rows = self.conn.execute(
            "SELECT materialTypeID, quantity FROM industryActivityMaterials "
            "WHERE typeID = ? AND activityID = ?",
            (blueprint.id, activity_id),
        )
        inputs = []
        for row in mat_rows:
            inputs.append(ItemQuantity(self.find_item_type(row[0]), row[1]))
        return Formula(blueprint, time, output, inputs)


10000001,
10000002,
10000016,
10000020,
10000028,
10000030,
10000032,
10000033,
10000036,
10000037,
10000038,
10000041,
10000042,
10000043,
10000044,
10000048,
10000049,
10000052,
10000054,
10000064,
10000065,
10000067,
10000068,
10000069,
