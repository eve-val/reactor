from typing import Dict


JITA_REGION_ID = 10000002

# Activity IDs are used in industry-activity tables. See ramActivities.csv.
INDUSTRY_ACTIVITIES: Dict[str, int] = {
    "manufacturing": 1,
    "copying": 5,
}
