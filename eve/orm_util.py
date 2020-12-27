from typing import Any, Dict, Type
import sqlite3
import dataclasses
import datetime


def dataclass_from_row(cls: Type, row: sqlite3.Row):
    if row is None:
        return cls()
    vals: Dict[str, Any] = {}
    for f in dataclasses.fields(cls):
        v: Any = row[f.name]
        if f.type is datetime.datetime:
            v = datetime.datetime.fromtimestamp(v)
        vals[f.name] = f.type(v)
    return cls(**vals)
