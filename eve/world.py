import dataclasses
import sqlite3
from typing import Dict, List

from eve.orm_util import dataclass_from_row

JITA_REGION_ID = 10000002
SYNDICATE_REGION_ID = 10000041
METOPOLIS_REGION_ID = 10000042
MY_REGIONS = [
    JITA_REGION_ID,
    SYNDICATE_REGION_ID,
    METOPOLIS_REGION_ID,
]
JITA_4_4_STATION_ID = 60003760

# Activity IDs are used in industry-activity tables. See ramActivities.csv.
INDUSTRY_ACTIVITIES: Dict[str, int] = {
    "manufacturing": 1,
    "copying": 5,
}
INDUSTRY_ACTIVITY_MANUFACTURING = 1

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
    category: str = UNKNOWN_NAME

    @property
    def is_blueprint(self) -> bool:
        return self.category == "Blueprint"


@dataclasses.dataclass(frozen=True)
class ItemQuantity:
    item_type: ItemType
    quantity: int


@dataclasses.dataclass(frozen=True)
class Formula:
    blueprint: ItemType
    time: int
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
            "  T.typeID id, T.typeName name, C.categoryName category "
            "FROM invTypes T JOIN invGroups G ON T.groupID = G.groupID "
            "  JOIN invCategories C ON G.categoryID = C.categoryID "
            "WHERE T.typeID = ?",
            (type_id,),
        )
        return dataclass_from_row(ItemType, cursor.fetchone())

    def find_formula(self, type_id: int) -> Formula:
        blueprint = self.find_item_type(type_id)
        if not blueprint.is_blueprint:
            raise ValueError(f"{blueprint.name} is not a blueprint")
        row = self.conn.execute(
            "SELECT time FROM industryActivity "
            "WHERE typeID = ? AND activityID = ?",
            (type_id, INDUSTRY_ACTIVITY_MANUFACTURING),
        ).fetchone()
        if not row:
            raise ValueError(
                f"{blueprint.name} not found in industryActivities"
            )
        time = row[0]
        row = self.conn.execute(
            "SELECT productTypeID, quantity FROM industryActivityProducts "
            "WHERE typeID = ? AND activityID = ?",
            (type_id, INDUSTRY_ACTIVITY_MANUFACTURING),
        ).fetchone()
        if not row:
            raise ValueError(
                f"{blueprint.name} not found in industryActivityProducts"
            )
        productTypeID, quantity = row
        output = ItemQuantity(self.find_item_type(productTypeID), quantity)
        mat_rows = self.conn.execute(
            "SELECT materialTypeID, quantity FROM industryActivityMaterials "
            "WHERE typeID = ? AND activityID = ?",
            (type_id, INDUSTRY_ACTIVITY_MANUFACTURING),
        )
        inputs = []
        for row in mat_rows:
            inputs.append(ItemQuantity(self.find_item_type(row[0]), row[1]))
        return Formula(blueprint, time, output, inputs)


# sqlite> SELECT R.regionID, R.regionName, F.factionName FROM mapRegions R JOIN chrFactions F ON R.factionID = F.factionID;
# 10000001|Derelik|Ammatar Mandate
# 10000002|The Forge|Caldari State
# 10000011|Great Wildlands|Thukker Tribe
# 10000012|Curse|Angel Cartel
# 10000015|Venal|Guristas Pirates
# 10000016|Lonetrek|Caldari State
# 10000017|J7HZ-F|Jove Empire
# 10000019|A821-A|Jove Empire
# 10000020|Tash-Murkon|Amarr Empire
# 10000022|Stain|Sansha's Nation
# 10000028|Molden Heath|Minmatar Republic
# 10000030|Heimatar|Minmatar Republic
# 10000032|Sinq Laison|Gallente Federation
# 10000033|The Citadel|Caldari State
# 10000036|Devoid|Amarr Empire
# 10000037|Everyshore|Gallente Federation
# 10000038|The Bleak Lands|Amarr Empire
# 10000041|Syndicate|The Syndicate
# 10000042|Metropolis|Minmatar Republic
# 10000043|Domain|Amarr Empire
# 10000044|Solitude|Gallente Federation
# 10000048|Placid|Gallente Federation
# 10000049|Khanid|Khanid Kingdom
# 10000052|Kador|Amarr Empire
# 10000054|Aridia|Amarr Empire
# 10000057|Outer Ring|ORE
# 10000064|Essence|Gallente Federation
# 10000065|Kor-Azor|Amarr Empire
# 10000067|Genesis|Amarr Empire
# 10000068|Verge Vendor|Gallente Federation
# 10000069|Black Rise|Caldari State
# 10000070|Pochven|Triglavian Collective
