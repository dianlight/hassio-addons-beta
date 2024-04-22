import binascii
from enum import Enum
from io import BytesIO
import io
import itertools
import os
import pickle
from pprint import pformat
import logging
from wsgiref.types import StartResponse, WSGIEnvironment
from werkzeug import datastructures
import dns.resolver
from flask import Flask, Request, json
import http.client
import re
import typing as t
import hexdump

from database import Database
import time

BEHAVIOUR = Enum(
    "BEHAVIOUR",
    [
        "REMOTE_FIRST",  # If remote and local differs return remote
        "LOCAL_FIRST",  # If remote and local differs return local
        "REMOTE_IF_MISSING",  # If local don't exist return remote otherwise return act as LOCAL_FIRST
        "ONLY_REMOTE",  # Ignore local
        "ONLY_LOCAL",  # Ingore remote
    ],
)

""" Standard Behaviour is REMOTE_IF_MISSING """
PROXY_URL_BEHAVIOUR = {
    r"^/static.*": BEHAVIOUR.ONLY_LOCAL,
    r"^[/|/index\.html]$": BEHAVIOUR.ONLY_LOCAL,
    r"^/api/v1\.0/.*": BEHAVIOUR.ONLY_LOCAL,
    r"^/fwUpgrade/PR06549/version\.txt": BEHAVIOUR.LOCAL_FIRST,
    r"^/WifiBoxInterface_vokera/getWebTemperature\.php": BEHAVIOUR.REMOTE_FIRST,
}


def timing(f):
    def wrap(*args, **kwargs):
        time1: float = time.time()
        try:
            ret = f(*args, **kwargs)
        except Exception as e:
            ret = repr(e)
            logging.error(ret)
            raise e
        finally:
            time2: float = time.time()
            # logging.info(pformat((args, kwargs, ret)))
            logging.debug(
                "{:s} function took {:.3f} ms".format(
                    args[1]["RAW_URI"], (time2 - time1) * 1000.0
                )
            )

            response_status = (
                args[1]["RESPONSE_STATUS"]
                if "RESPONSE_STATUS" in args[1]
                else pformat(ret)
            )

            Database().log_traces(
                source=args[1]["SERVER_PROTOCOL"],
                host=args[1]["REMOTE_ADDR"],
                adapterMap=(
                    json.dumps(args[1]["REQUEST_ADAPTER_MAP"])
                    if "REQUEST_ADAPTER_MAP" in args[1]
                    else "NOT FOUND"
                ),
                uri=f"{args[1]['REQUEST_METHOD']} {args[1]['RAW_URI']}",
                elapsed=int((time2 - time1) * 1000.0),
                response_status=str(response_status),
            )

        return ret

    return wrap


class ProxyMiddleware(object):

    upstream_resolver = dns.resolver.Resolver()
    http_connection: dict[str, http.client.HTTPConnection] = {}

    def __init__(
        self, app: Flask, upstream: str, datalog: t.Optional[io.TextIOWrapper]
    ) -> None:
        self._app = app.wsgi_app
        self.app: Flask = app

        if app.config["weather_location_latitude"][0] is not None:
            PROXY_URL_BEHAVIOUR[r"/WifiBoxInterface_vokera/getWebTemperature\.php"] = (
                BEHAVIOUR.LOCAL_FIRST
            )

        self.upstream_resolver.nameservers = [upstream]
        logging.info(
            f"Upstream DNS Check: google.com = {pformat(next(self.upstream_resolver.query('google.com', 'A').__iter__()).to_text())}"  # type: ignore
        )
        # for answer in self.upstream_resolver.query('google.com', "A"):
        #    logging.info(answer.to_text())
        self.datalog: io.TextIOWrapper | None = datalog

    def check_path_exists(self, env: WSGIEnvironment) -> bool:
        path = env["PATH_INFO"]
        method = env["REQUEST_METHOD"]
        try:
            vreq = Request(env)
            adapter = self.app.create_url_adapter(request=vreq)
            if adapter is not None:
                # logging.debug(pformat(adapter.map))
                env["REQUEST_ADAPTER_MAP"] = adapter.match(path, method)
            else:
                return False
        except Exception as e:
            logging.debug(e)
            return False
        logging.debug(f"Match Rule {pformat(env['REQUEST_ADAPTER_MAP'])}")
        return True

    @timing
    def __call__(
        self, env: WSGIEnvironment, resp: StartResponse
    ) -> t.Iterable[bytes]:  # sourcery skip: identity-comprehension

        http_host: str | None = env.get("HTTP_HOST")
        if http_host is None:
            raise ValueError("Internal server error. HTTP_HOST env is null!")

        if (
            re.match(
                r"((\w+\-besim\w{0,1})|(127\.\d\.\d\.\d)|(localhost.*))(:\d+){0,1}",
                http_host,
                re.IGNORECASE,
            )
            is not None
        ):

            self.check_path_exists(env)
            logging.debug(
                f"{env['REMOTE_ADDR']} {env['REQUEST_METHOD']} {env['REQUEST_URI']} {BEHAVIOUR.ONLY_LOCAL.name}"
            )

            def intercept_response_direct(
                status: str, headers, *args
            ):  # -> Callable[..., object]:
                env["RESPONSE_STATUS"] = status
                return resp(status, headers, *args)

            return self._app(env, intercept_response_direct)

        def check_behaviour(path: str) -> BEHAVIOUR:
            for reg, bev in PROXY_URL_BEHAVIOUR.items():
                if re.match(reg, path, re.IGNORECASE) is not None:
                    logging.debug(f"{path} Match {pformat((reg, bev))}")
                    return bev
            return BEHAVIOUR.REMOTE_IF_MISSING

        # behaviour = PROXY_URL_BEHAVIOUR[req.path] if req.path in PROXY_URL_BEHAVIOUR else BEHAVIOUR.REMOTE_IF_MISSING
        behaviour: BEHAVIOUR = check_behaviour(env["REQUEST_URI"])
        logging.debug(f"Working on behaviour: {behaviour}")

        if behaviour != BEHAVIOUR.ONLY_LOCAL and (
            http_host not in self.http_connection
            or self.http_connection[http_host] is None
        ):
            try:
                ip = next(self.upstream_resolver.query(http_host, "A").__iter__()).to_text()  # type: ignore
                logging.info(
                    f"Upstream Connection for {http_host} is {pformat(ip)}:{env.get('SERVER_PORT','80')}"
                )
                self.http_connection[http_host] = http.client.HTTPConnection(
                    ip, int(env.get("SERVER_PORT", "80"))
                )
                self.http_connection[http_host].auto_open = True
            except Exception as e:
                logging.warning(e)
                if behaviour == BEHAVIOUR.ONLY_REMOTE:
                    raise e
                behaviour = BEHAVIOUR.ONLY_LOCAL

        req_headers = datastructures.EnvironHeaders(env)

        if behaviour == BEHAVIOUR.REMOTE_IF_MISSING and not self.check_path_exists(env):
            logging.warn(
                f"Method {env['REQUEST_METHOD']} {env['REQUEST_URI']} don't exist. Force ONLY_REMOTE"
            )
            env["MISSING_API"] = True
            behaviour = BEHAVIOUR.ONLY_REMOTE
        elif behaviour == BEHAVIOUR.REMOTE_IF_MISSING:
            behaviour = BEHAVIOUR.LOCAL_FIRST

        length = int(env.get("CONTENT_LENGTH", "0"))
        body = BytesIO(env["wsgi.input"].read(length))
        env["wsgi.input"] = body
        proxy_body: bytes = body.read(length)
        body.seek(0)
        
        if self.datalog:
            self.datalog.write(f'"I","{hexdump.dump(pickle.dumps(env), sep='')}","{hexdump.dump(proxy_body, sep='')}"\r\n')
            self.datalog.flush()
            os.fsync(self.datalog)

        if behaviour != BEHAVIOUR.ONLY_LOCAL:
            logging.debug(
                pformat(
                    (
                        "PROXY_CALL",
                        env["REQUEST_METHOD"],
                        env["REQUEST_URI"],
                        proxy_body,
                        {x: y for x, y in req_headers.items()},
                        # {x: y for x, y in req.headers.to_wsgi_list()}
                    )
                )
            )
            self.http_connection[http_host].connect()
            self.http_connection[http_host].request(
                env["REQUEST_METHOD"],
                env["REQUEST_URI"],
                proxy_body,
                {x: y for x, y in req_headers.items()},
                # {x: y for x, y in req.headers.to_wsgi_list()}
            )

            resp_org: http.client.HTTPResponse = self.http_connection[
                http_host
            ].getresponse()
            body_org: str = "".join([chr(b) for b in resp_org.read()])
            logging.debug(
                pformat(("PROXY_RESPONSE", resp_org.headers.items(), body_org))
            )

        def intercept_response(
            status: str, headers, *args
        ):  # -> Callable[..., object]:
            if self.datalog:
                self.datalog.write(
                    f'"O","{status}","{hexdump.dump(pickle.dumps(env), sep='')}","{hexdump.dump(pickle.dumps(headers), sep='')}","{hexdump.dump(body_org, sep='')}"\r\n'
                )
                self.datalog.flush()
                os.fsync(self.datalog)

            env["RESPONSE_STATUS"] = status
            if behaviour in [BEHAVIOUR.REMOTE_FIRST, BEHAVIOUR.ONLY_REMOTE]:
                headers = resp_org.headers.items()
                status = str(resp_org.status)

                if "MISSING_API" in env:
                    Database().log_unknown_api(
                        env["REMOTE_ADDR"],
                        env["HTTP_HOST"],
                        env["REQUEST_METHOD"],
                        env["REQUEST_URI"],
                        pformat({x: y for x, y in req_headers.items()}),
                        proxy_body,
                        str(resp_org.status),
                        body_org,
                    )

            resp_int = resp(status, headers, *args)

            def writer(data) -> object:
                logging.debug(("RESPONSE_BODY", data))
                return resp_int(data)

            env["RESPONSE_STATUS"] = status
            logging.debug(pformat(("RESPONSE", status, headers, args)))
            return writer

        iterable: t.Iterable[bytes] = self._app(env, intercept_response)
        (org, copy) = itertools.tee(iterable)

        body_api: str = "".join([b.decode("utf-8") for b in copy])

        logging.debug(("RESPONSE_ITERABLE", body_api))

        """Check Reponse on Request For Proxy"""
        logging.info(
            f"{env['REMOTE_ADDR']} {env['REQUEST_METHOD']} {env['REQUEST_URI']} {behaviour.name}"
        )
        if (
            behaviour not in (BEHAVIOUR.ONLY_LOCAL, BEHAVIOUR.ONLY_REMOTE)
            and body_api != body_org
        ):
            logging.warning(
                f'Response form original_server and API differs Cloud="{body_org}" Local="{body_api}"'
            )
            logging.debug(
                (
                    ("REQ", req_headers.__dict__, body),
                    (
                        "REQ_CLOUD",
                        env["REQUEST_METHOD"],
                        env["REQUEST_URI"],
                        proxy_body,
                        {x: y for x, y in req_headers.items()},
                    ),
                    ("RESP_CLOUD", resp_org.headers.__dict__, body_org),
                    ("RESP", body_api),
                )
            )

        return (
            iter([body_org.encode()])
            if behaviour in [BEHAVIOUR.REMOTE_FIRST, BEHAVIOUR.ONLY_REMOTE]
            else org
        )
