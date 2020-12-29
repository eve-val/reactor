import functools
import logging
import os
import sqlite3

from bravado.client import SwaggerClient

REFERENCE_DB_FILE_NAME = "../reference/sqlite-latest.sqlite"
STORE_DB_FILE_NAME = "../data/db.sqlite"


class Services:
    @functools.cached_property
    def api(self) -> SwaggerClient:
        logging.info("initializing connection to EVE server")
        api = SwaggerClient.from_url(
            "https://esi.evetech.net/latest/swagger.json?datasource=tranquility",
            config={"use_models": False},
        )
        logging.info("EVE API initialized")
        return api

    @functools.cached_property
    def reference_db(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            os.path.join(os.path.dirname(__file__), REFERENCE_DB_FILE_NAME)
        )
        conn.row_factory = sqlite3.Row
        return conn

    @functools.cached_property
    def store_db(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            os.path.join(os.path.dirname(__file__), STORE_DB_FILE_NAME)
        )
        conn.row_factory = sqlite3.Row
        return conn
