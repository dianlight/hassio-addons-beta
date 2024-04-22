import sqlite3
import logging
import contextlib
from enum import Enum

from typing import List
from typing import Union

logger = logging.getLogger(__name__)


class DatabaseType(Enum):
    SQLITE3 = 1
    UNSET = 2


class DatabaseConnection:
    conn: sqlite3.Connection | None

    def __init__(self, databaseType=None, databaseName=None) -> None:
        self.databaseType = databaseType
        self.databaseName = databaseName
        self.conn = None

    def connect(self):
        if self.databaseName is not None and self.conn is None:
            self.conn = sqlite3.connect(
                self.databaseName, autocommit=False
            )  # PEP 249 compliant Python3.12+
        return self.conn

    def close(self, commit=False):
        if self.conn is not None:
            self.conn.close()
            self.conn = None

    def getConn(self) -> sqlite3.Connection:
        if self.conn is None:
            self.connect()
        return self.conn  # type: ignore

    def commit(self) -> None:
        if self.getConn() is not None:
            self.getConn().commit()

    def rollback(self):
        if self.getConn() is not None:
            self.getConn().rollback()

    def run_sql(self, sql, values=None, log=False) -> List:
        if values is None:
            values = ()
        if log:
            logger.info(sql)
        if self.getConn() is not None:
            with contextlib.closing(
                self.getConn().cursor()
            ) as cursor:  # Use contextlib since sqlite3 cursors do not support __enter__
                cursor.execute(sql, values)
                if (
                    cursor.description is None
                ):  # sqlite3 will not return anything on a create/insert etc
                    result = None
                else:
                    cols = [x[0] for x in cursor.description]
                    result = [dict(zip(cols, row)) for row in cursor.fetchall()]
            self.getConn().commit()
            if log:
                logger.info(result)
            return result
        else:
            return None

    def fetchmany(self, sql, values=None, log=False) -> List:
        return self.run_sql(sql, values, log)

    def fetchone(self, sql, values=None, log=False):
        rc = self.run_sql(sql, values, log)
        if rc is not None and len(rc) > 0:
            return rc[0]
        else:
            return None

    def truncate_tables(self, tables: Union[str, List[str]], log=False) -> List:
        if not isinstance(tables, list):
            tables = [tables]
        for table in tables:
            if self.databaseType == DatabaseType.SQLITE3:
                sql = f"delete from {table}"
            else:
                sql = f"truncate table {table}"
            return self.run_sql(sql, log)
