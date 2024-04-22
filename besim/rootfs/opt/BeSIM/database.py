import logging

from numpy import byte
from databaseConnection import DatabaseType, DatabaseConnection
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)


class Singleton(type):
    _instances = {}

    def __call__(self, *args, **kwargs):
        if self not in self._instances:
            self._instances[self] = super(Singleton, self).__call__(*args, **kwargs)
        return self._instances[self]


class Database(metaclass=Singleton):

    VERSION = 7

    def __init__(self, name: str = __name__, log=False) -> None:
        self.name: str = name
        self.log: bool = log

    def create_tables(self, conn=None):
        if not conn:
            conn = self.get_connection()
            closeit = True
        else:
            closeit = False
        sql = "create table if not exists besim_outside_temperature(ts DATETIME, temp NUMERIC)"
        conn.run_sql(sql, log=self.log)
        sql = "create table if not exists besim_temperature(ts DATETIME, thermostat TEXT, temp NUMERIC, settemp NUMERIC, heating NUMERIC)"
        conn.run_sql(sql, log=self.log)
        sql = "create table if not exists web_traces(ts DATETIME, source TEXT, adapterMap TEXT, host TEXT, uri TEXT, elapsed NUMERIC, response_status TEXT)"
        conn.run_sql(sql, log=self.log)
        sql = "create table if not exists unknown_udp(ts DATETIME, source TEXT, type TEXT, code NUMETIC, payload BLOB, unparsed_payload BLOB, raw_data BLOB)"
        conn.run_sql(sql, log=self.log)
        sql = "create table if not exists unknown_api(ts DATETIME, source TEXT, host TEXT, method TEXT, uri TEXT, headers TEXT, body BLOB, rm_resp_code TEXT, rm_res_body TEXT)"
        conn.run_sql(sql, log=self.log)
        if closeit:
            conn.close(commit=True)

    def _get_user_version(self, conn):
        user_version = None
        rc = conn.fetchone("pragma user_version", log=self.log)
        if rc is not None and "user_version" in rc:
            user_version = rc["user_version"]
        return user_version

    def _set_user_version(self, user_version, conn):
        conn.fetchone(f"pragma user_version = {user_version}", log=self.log)

    def check_migrations(self, conn=None):
        success = True
        if not conn:
            conn = self.get_connection()
            closeit = True
        else:
            closeit = False

        user_version = self._get_user_version(conn=conn)
        if user_version is not None:

            if user_version == 0:
                logger.warning(f"Initialising Database to version {self.VERSION}")
                self.create_tables(conn=conn)
                self._set_user_version(self.VERSION, conn=conn)
            elif user_version != self.VERSION:
                logger.warning(
                    f"Database needs upgrading from version {user_version} to {self.VERSION}"
                )
                logger.error(
                    "Migration not yet implemented :(. Drop all database and restart!"
                )
                success = False
        else:
            logger.error("Failed to get database version")
            success = False

        if closeit:
            conn.close(commit=True)

        return success

    def get_connection(self):
        dbConnection = DatabaseConnection(DatabaseType.SQLITE3, self.name)
        dbConnection.connect()
        return dbConnection

    def log_outside_temperature(self, temp, conn=None):
        if not conn:
            conn = self.get_connection()
            closeit = True
        else:
            closeit = False
        now = datetime.now(timezone.utc).astimezone().isoformat()
        sql = "insert into besim_outside_temperature(ts, temp) values (?,?)"
        values = (now, temp)
        conn.run_sql(sql, values, log=self.log)
        if closeit:
            conn.close(commit=True)

    def log_temperature(self, thermostat, temp, settemp, heating, conn=None):
        if not conn:
            conn = self.get_connection()
            closeit = True
        else:
            closeit = False
        now = datetime.now(timezone.utc).astimezone().isoformat()
        sql = "insert into besim_temperature(ts, thermostat, temp, settemp, heating) values (?,?,?,?,?)"
        values = (now, thermostat, temp, settemp, heating)
        conn.run_sql(sql, values, log=self.log)
        if closeit:
            conn.close(commit=True)

    def log_traces(
        self,
        source: str,
        host: str,
        adapterMap: str,
        uri: str,
        elapsed: int,
        response_status: str,
        conn=None,
    ) -> None:
        if not conn:
            conn = self.get_connection()
            closeit = True
        else:
            closeit = False
        now: str = datetime.now(timezone.utc).astimezone().isoformat()
        sql = "insert into web_traces(ts, source, adapterMap, host, uri, elapsed, response_status) values (?,?,?,?,?,?,?)"
        values = (now, source, adapterMap, host, uri, elapsed, response_status)
        conn.run_sql(sql, values, log=self.log)
        if closeit:
            conn.close(commit=True)

    def log_unknown_udp(
        self,
        source: str,
        type: str,
        code: int,
        raw_data: bytes,
        payload: bytes,
        unparsed_payload: bytes = bytes([]),
        conn=None,
    ) -> None:
        if not conn:
            conn = self.get_connection()
            closeit = True
        else:
            closeit = False
        now: str = datetime.now(timezone.utc).astimezone().isoformat()
        sql = "insert into unknown_udp(ts, source, type, code, payload, unparsed_payload, raw_data) values (?,?,?,?,?,?,?)"
        values = (now, source, type, code, payload, unparsed_payload, raw_data)
        conn.run_sql(sql, values, log=self.log)
        if closeit:
            conn.close(commit=True)

    def log_unknown_api(
        self,
        source: str,
        host: str,
        method: str,
        uri: str,
        headers,
        body: bytes,
        rm_resp_code: str,
        rm_res_body: str,
        conn=None,
    ) -> None:
        if not conn:
            conn = self.get_connection()
            closeit = True
        else:
            closeit = False
        now: str = datetime.now(timezone.utc).astimezone().isoformat()
        sql = "insert into unknown_api(ts, source, host, method, uri, headers, body, rm_resp_code, rm_res_body) values (?,?,?,?,?,?,?,?,?)"
        values = (
            now,
            source,
            host,
            method,
            uri,
            headers,
            body,
            rm_resp_code,
            rm_res_body,
        )
        conn.run_sql(sql, values, log=self.log)
        if closeit:
            conn.close(commit=True)

    def purge(self, daysToKeep, conn=None):
        if not conn:
            conn = self.get_connection()
            closeit = True
        else:
            closeit = False
        now: datetime = datetime.now(timezone.utc).astimezone()
        limit: datetime = now - timedelta(days=daysToKeep)
        sql: str = (
            f"delete from besim_outside_temperature where ts < '{limit.isoformat()}'"
        )
        conn.run_sql(sql, log=self.log)
        sql: str = f"delete from besim_temperature where ts < '{limit.isoformat()}'"
        conn.run_sql(sql, log=self.log)
        sql: str = f"delete from web_traces where ts < '{limit.isoformat()}'"
        conn.run_sql(sql, log=self.log)
        sql: str = f"delete from unknown_udp where ts < '{limit.isoformat()}'"
        conn.run_sql(sql, log=self.log)
        sql: str = f"delete from unknown_api where ts < '{limit.isoformat()}'"
        conn.run_sql(sql, log=self.log)
        if closeit:
            conn.close(commit=True)

    def get_outside_temperature(self, date_from=None, date_to=None, conn=None):
        if date_from is None:
            date_from = (
                datetime.now(timezone.utc).astimezone() - timedelta(days=14)
            ).isoformat()
        if date_to is None:
            date_to = datetime.now(timezone.utc).astimezone().isoformat()

        if not conn:
            conn = self.get_connection()
            closeit = True
        else:
            closeit = False
        sql = "select ts,temp from besim_outside_temperature where ts between ? and ?"
        values = (date_from, date_to)
        rc = conn.run_sql(sql, values, log=self.log)
        if closeit:
            conn.close(commit=True)
        return rc

    def get_temperature(self, thermostat, date_from=None, date_to=None, conn=None):
        if date_from is None:
            date_from = (
                datetime.now(timezone.utc).astimezone() - timedelta(days=14)
            ).isoformat()
        if date_to is None:
            date_to = datetime.now(timezone.utc).astimezone().isoformat()

        if not conn:
            conn = self.get_connection()
            closeit = True
        else:
            closeit = False
        sql = "select ts,temp,settemp,heating from besim_temperature where thermostat = ? and ts between ? and ?"
        values = (thermostat, date_from, date_to)
        rc = conn.run_sql(sql, values, log=self.log)
        if closeit:
            conn.close(commit=True)
        return rc

    def get_calls(
        self,
        date_from=None,
        date_to=None,
        sort=None,
        filter=None,
        limit=200,
        offset=0,
        conn=None,
    ):  # -> List[Any] | Any:
        if date_from is None:
            date_from = (
                datetime.now(timezone.utc).astimezone() - timedelta(days=14)
            ).isoformat()
        if date_to is None:
            date_to = datetime.now(timezone.utc).astimezone().isoformat()

        if not conn:
            conn = self.get_connection()
            closeit = True
        else:
            closeit = False
        sql = "select rowid,ts,source,adapterMap,host,uri,elapsed,response_status from web_traces where ts between ? and ? "
        values = (date_from, date_to)
        if filter:
            filter_sql = str()
            for key in filter:
                filter_sql += f"and {key} like ? "
                values += (f"%{filter[key]}%",)
            sql += filter_sql

        sqlcount = f"select count(*) as total from ({sql})"
        sql += f" order by {sort}" if sort else ""
        sql += f" LIMIT {offset},{limit}"
        logger.debug((sql, sqlcount))
        rcc = conn.run_sql(sqlcount, values, log=self.log)
        rc = conn.run_sql(sql, values, log=self.log)
        if closeit:
            conn.close(commit=True)
        return {"meta": rcc[0], "data": rc}

    def get_calls_group(
        self,
        date_from=None,
        date_to=None,
        sort=None,
        filter=None,
        limit=200,
        offset=0,
        conn=None,
    ):  # -> List[Any] | Any:
        if date_from is None:
            date_from = (
                datetime.now(timezone.utc).astimezone() - timedelta(days=14)
            ).isoformat()
        if date_to is None:
            date_to = datetime.now(timezone.utc).astimezone().isoformat()

        if not conn:
            conn = self.get_connection()
            closeit = True
        else:
            closeit = False
        sql = "select max(rowid) as rowId,count(*) as cardinal ,max(ts) as ts,source,adapterMap,host,avg(elapsed) as elapsed,response_status from web_traces where ts between ? and ? "
        values = (date_from, date_to)
        if filter:
            filter_sql = str()
            for key in filter:
                filter_sql += f"and {key} like ? "
                values += (f"%{filter[key]}%",)
            sql += filter_sql

        sql += " group by source,adapterMap,host,response_status "
        sqlcount = f"select count(*) as total from ({sql})"
        sql += f" order by {sort}" if sort else ""
        sql += f" LIMIT {offset},{limit}"
        #  logger.debug((sql, sqlcount))
        rcc = conn.run_sql(sqlcount, values, log=self.log)
        rc = conn.run_sql(sql, values, log=self.log)
        if closeit:
            conn.close(commit=True)
        return {"meta": rcc[0], "data": rc}

    def get_unknown_udp(self, date_from=None, date_to=None, conn=None):
        if date_from is None:
            date_from = (
                datetime.now(timezone.utc).astimezone() - timedelta(days=14)
            ).isoformat()
        if date_to is None:
            date_to = datetime.now(timezone.utc).astimezone().isoformat()

        if not conn:
            conn = self.get_connection()
            closeit = True
        else:
            closeit = False
        sql = "select count(*) as count, max(ts) as ts, source, type, code, hex(payload) as payload, hex(unparsed_payload) as unparsed_payload, hex(raw_data) as raw_data from unknown_udp where ts between ? and ? group by source, type, code, payload, unparsed_payload, raw_data"
        values = (date_from, date_to)
        rc = conn.run_sql(sql, values, log=self.log)
        if closeit:
            conn.close(commit=True)
        return rc

    def get_unknown_api(self, date_from=None, date_to=None, conn=None):
        if date_from is None:
            date_from = (
                datetime.now(timezone.utc).astimezone() - timedelta(days=14)
            ).isoformat()
        if date_to is None:
            date_to = datetime.now(timezone.utc).astimezone().isoformat()

        if not conn:
            conn = self.get_connection()
            closeit = True
        else:
            closeit = False
        sql = "select count(*) as count, max(ts) as ts, source, host, method, uri, headers, hex(body) as body, rm_resp_code, rm_res_body from unknown_api where ts between ? and ? group by source, host, method, uri, headers, body, rm_resp_code, rm_res_body"
        values = (date_from, date_to)
        rc = conn.run_sql(sql, values, log=self.log)
        if closeit:
            conn.close(commit=True)
        return rc
