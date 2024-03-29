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
INDUSTRY_ACTIVITY_INVENTION = 8
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
    name: str = dataclasses.field(
        default=UNKNOWN_NAME, hash=False, compare=False
    )
    group: str = dataclasses.field(
        default=UNKNOWN_NAME, hash=False, compare=False
    )
    category: str = dataclasses.field(
        default=UNKNOWN_NAME, hash=False, compare=False
    )
    volume_m3: float = dataclasses.field(
        default=0.0, hash=False, compare=False
    )

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
    probability: float = 1.0
    intermediates: List[ItemQuantity] = dataclasses.field(default_factory=list)

    def pretty_str(self) -> str:
        return (
            f"{self.output.quantity}x {self.output.item_type.name} "
            f"in {self.time}s ({self.probability * 100:.0f}%) from:\n"
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
            "  C.categoryName category, T.volume volume_m3 "
            "FROM invTypes T JOIN invGroups G ON T.groupID = G.groupID "
            "  JOIN invCategories C ON G.categoryID = C.categoryID "
            "WHERE T.typeID = ?",
            (type_id,),
        )
        return dataclass_from_row(ItemType, cursor.fetchone())

    def find_item_type_by_name(self, name: str) -> ItemType:
        row = self.conn.execute(
            "SELECT "
            "  T.typeID id, T.typeName name, G.groupName 'group', "
            "  C.categoryName category, T.volume volume_m3 "
            "FROM invTypes T JOIN invGroups G ON T.groupID = G.groupID "
            "  JOIN invCategories C ON G.categoryID = C.categoryID "
            "WHERE T.typeName = ?",
            (name,),
        ).fetchone()
        if not row:
            raise ValueError(f"item type '{name}' not found")
        return dataclass_from_row(ItemType, row)

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

    def find_material_uses(self, mat: ItemType) -> List[Formula]:
        cursor = self.conn.execute(
            "SELECT typeID FROM industryActivityMaterials "
            "WHERE materialTypeID = ? AND activityID IN (?, ?) "
            "  AND typeID != 45732",  # "Test Reaction".
            (
                mat.id,
                INDUSTRY_ACTIVITY_MANUFACTURING,
                INDUSTRY_ACTIVITY_REACTIONS,
            ),
        )
        blueprint_ids = set(row[0] for row in cursor)
        return [
            self.find_formula(self.find_item_type(bpid))
            for bpid in blueprint_ids
        ]

    def _read_formula_time(
        self, blueprint: ItemType, activity_id: int
    ) -> float:
        row = self.conn.execute(
            "SELECT time FROM industryActivity "
            "WHERE typeID = ? AND activityID = ?",
            (blueprint.id, activity_id),
        ).fetchone()
        if not row:
            raise FormulaNotFound(
                f"{blueprint.full_name} not found in industryActivities"
            )
        return row[0]

    def _read_formula_inputs(
        self, blueprint: ItemType, activity_id: int
    ) -> List[ItemQuantity]:
        mat_rows = self.conn.execute(
            "SELECT materialTypeID, quantity FROM industryActivityMaterials "
            "WHERE typeID = ? AND activityID = ?",
            (blueprint.id, activity_id),
        )
        inputs = []
        for row in mat_rows:
            inputs.append(ItemQuantity(self.find_item_type(row[0]), row[1]))
        return inputs

    def _read_formula_output(
        self, blueprint: ItemType, activity_id: int
    ) -> ItemQuantity:
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
        return ItemQuantity(self.find_item_type(productTypeID), quantity)

    def find_formula(self, blueprint: ItemType) -> Formula:
        if not blueprint.is_blueprint:
            raise ValueError(f"{blueprint.name} is not a blueprint")
        activity_id = (
            INDUSTRY_ACTIVITY_REACTIONS
            if blueprint.is_reaction_blueprint
            else INDUSTRY_ACTIVITY_MANUFACTURING
        )
        time = self._read_formula_time(blueprint, activity_id)
        output = self._read_formula_output(blueprint, activity_id)
        inputs = self._read_formula_inputs(blueprint, activity_id)
        return Formula(blueprint, time, output, inputs)

    def find_invention_formula(
        self, output_blueprint: ItemType
    ) -> Optional[Formula]:
        if not output_blueprint.is_blueprint:
            raise ValueError(f"{output_blueprint.name} is not a blueprint")
        row = self.conn.execute(
            "SELECT typeID, quantity FROM industryActivityProducts "
            "WHERE productTypeID = ? AND activityID = ?",
            (output_blueprint.id, INDUSTRY_ACTIVITY_INVENTION),
        ).fetchone()
        if not row:
            return None
        input_blueprint = self.find_item_type(row[0])
        output = ItemQuantity(output_blueprint, row[1])
        time = self._read_formula_time(
            input_blueprint, INDUSTRY_ACTIVITY_INVENTION
        )
        inputs = self._read_formula_inputs(
            input_blueprint, INDUSTRY_ACTIVITY_INVENTION
        )
        row = self.conn.execute(
            "SELECT probability FROM industryActivityProbabilities "
            "WHERE typeID = ? AND productTypeID = ? AND activityID = ?",
            (
                input_blueprint.id,
                output_blueprint.id,
                INDUSTRY_ACTIVITY_INVENTION,
            ),
        ).fetchone()
        if not row:
            raise FormulaNotFound(
                f"{output_blueprint.name} not found in "
                "industryActivityProbabilities"
            )
        return Formula(output_blueprint, time, output, inputs, float(row[0]))
