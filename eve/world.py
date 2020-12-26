from typing import Dict, Optional
import sqlite3


JITA_REGION_ID = 10000002
SYNDICATE_REGION_ID = 10000041

# Activity IDs are used in industry-activity tables. See ramActivities.csv.
INDUSTRY_ACTIVITIES: Dict[str, int] = {
    "manufacturing": 1,
    "copying": 5,
}


class World:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def station_name(self, station_id: int) -> Optional[str]:
        if station_id > 100000000:
            return "<Private>"
        cursor = self.conn.execute(
            "SELECT stationName FROM staStations WHERE stationID = ?",
            (station_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return row[0]

    def item_name(self, type_id: int) -> Optional[str]:
        cursor = self.conn.execute(
            "SELECT typeName FROM invTypes WHERE typeID = ?",
            (type_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return row[0]

