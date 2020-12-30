from typing import Any, Callable, Dict, TypeVar, Union
import sqlite3
import dataclasses
import datetime
import json

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


def _db_json_encoder(v: Any) -> Any:
    if type(v) == datetime.datetime:
        return int(v.timestamp())
    if type(v) == datetime.date:
        return v.isoformat()
    return v


def adopt_json_for_db(src: Any) -> str:
    return json.dumps(src, default=_db_json_encoder)
