from typing import Any, Callable, Dict, TypeVar, Union
import sqlite3
import dataclasses
import datetime

T = TypeVar("T")

def dataclass_from_row(
    cls: Callable[..., T], row: Union[sqlite3.Row, Dict[str, Any]]
) -> T:
    if row is None:
        return cls()
    vals: Dict[str, Any] = {}
    for f in dataclasses.fields(cls):
        v: Any = row[f.name]
        if f.type is datetime.datetime:
            v = datetime.datetime.fromtimestamp(v)
        else:
            v = f.type(v)
        vals[f.name] = v
    return cls(**vals)
