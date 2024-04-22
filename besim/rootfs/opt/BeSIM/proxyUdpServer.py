import binascii
import io
import logging
import os
from typing import Optional

# from pprint import pformat

# from pprint import pformat
import hexdump
import dns.resolver
from status import getPeerFromDeviceId, getRoomStatus  # , getDeviceStatus
from udpserver import (
    # UNUSED_CSEQ,
    Frame,
    MsgId,
    UdpServer,
    Unpacker,
    Wrapper,
)
from database import Database
import time


class ProxyUdpServer(UdpServer):

    knocks = 0

    def __init__(
        self,
        addr,
        upstream: str,
        debugmode=False,
        datalog: Optional[io.TextIOWrapper] = None,
    ):
        super().__init__(addr, datalog=datalog)
        upstream_resolver = dns.resolver.Resolver()
        upstream_resolver.nameservers = [upstream]
        upstream_ip = next(
            upstream_resolver.query("api.besmart-home.com", "A").__iter__()  # type: ignore
        ).to_text()
        logging.info(f"Upstream DNS Check: api.besmart-home.com = {upstream_ip}")
        self.cloud_addr = (upstream_ip, 6199)
        self.debugmode = debugmode

    def run(self):
        logging.info(f"Proxy UDP server is running to {self.cloud_addr}")
        super().run()

    def send_ENCODED_FRAME(self, addr, payload, response=0, write=0):
        wrapper = Wrapper(payload=payload)
        payload = wrapper.encodeDL(MsgId.DEVICE_TIME, response, write=write)
        logging.info(f"Sending {wrapper}")
        frame = Frame(payload=payload)
        buf = frame.encode()
        logging.info(f"To {addr} {len(buf)} bytes : {hexdump.dump(buf)}")
        self.sendto(buf, addr)
        return

    def handleCloudMsg(self, data: bytes, addr) -> str:
        # sourcery skip: extract-method, merge-comparisons
        if self.datalog is not None:
            self.datalog.write(f'"C","{addr}","{hexdump.dump(data, sep='')}"\r\n')
            self.datalog.flush()
            os.fsync(self.datalog)

        frame = Frame()
        epayload = frame.decode(data)
        seq = frame.seq
        length = len(epayload) if epayload is not None else 0

        # peerStatus = getPeerStatus(addr)
        # peerStatus["seq"] = seq  # @todo handle sequence number

        # Now handle the payload

        wrapper = Wrapper(from_cloud=True)
        payload = wrapper.decodeUL(epayload)

        msgLen = len(payload)
        logging.info(f"Cloud: {seq=} {wrapper} {length=} {msgLen=}")

        unpack = Unpacker(payload)

        forward = False

        if wrapper.msgType == MsgId.STATUS and msgLen == 12:
            cseq, unk1, unk2, deviceid, lastseen = unpack("<BBHII")  # 1 1 2 4 4
            logging.info(
                f"Cloud {MsgId(wrapper.msgType).name=} {wrapper.msgType=:x} {cseq=:x} {unk1=:x} {unk2=:x} {deviceid=} {lastseen=}"
            )
            forward = True
        elif wrapper.msgType == MsgId.DEVICE_TIME and msgLen == 16:
            #  """PAYLOAD: 15000000AAF28D23"""
            cseq, unk1, unk2, deviceid, unk3, unk4 = unpack("<BBHIII")  # 1 1 2 4 4 4
            logging.info(
                f"Cloud {MsgId(wrapper.msgType).name=} {wrapper.msgType=:x} {cseq=:x} {unk1=:x} {unk2=:x} {deviceid=} {unk3=:x} {unk4=:x}"
            )
            forward = True
        elif wrapper.msgType == MsgId.DEVICE_TIME and msgLen == 8:
            #  """PAYLOAD: 15000000AAF28D23"""
            cseq, unk1, unk2, deviceid = unpack("<BBHI")  # 1 1 2 4
            logging.info(
                f"Cloud {MsgId(wrapper.msgType).name=} {wrapper.msgType=:x} {cseq=:x} {unk1=:x} {unk2=:x} {deviceid=}"
            )
            forward = True
        elif wrapper.msgType == MsgId.GET_PROG and msgLen == 16:
            #  """PAYLOAD: 11000000AAF28D23A6274304E00F8000"""
            cseq, unk1, unk2, deviceid, room, unk3 = unpack("<BBHIII")
            logging.info(
                f"Cloud {MsgId(wrapper.msgType).name=} {wrapper.msgType=:x} {cseq=:x} {unk1=:x} {unk2=:x} {deviceid=} {room=:x} {unk3=:x}"
            )
            forward = True
        elif wrapper.msgType in [MsgId.REFRESH, MsgId.SWVERSION] and msgLen == 8:
            #     """ PAYLOAD: 14000000AAF28D23  """ REFRESH
            #     """ PAYLOAD: 18000000AAF28D23  """ SWVERSION
            #     """ PAYLOAD: FF000000AAF28D2330363534393138303131313032 """ SWVERSION?
            cseq, unk1, unk2, deviceid = unpack("<BBHI")  # 1 1 2 4
            logging.info(
                f"Cloud {MsgId(wrapper.msgType).name=} {wrapper.msgType=:x} {cseq=:x} {unk1=:x} {unk2=:x} {deviceid=}"
            )
            forward = True
        elif wrapper.msgType == MsgId.PROGRAM and msgLen == 38:
            """
            [2024-02-21 18:01:53,113 udpserver.py->run():449] INFO: From ('104.46.56.16', 6199) 54 bytes : FA D4 2A 00 FF FF FF FF 0A 0F 1E 00 FF 00 00 00 AA F2 8D 23 A6 27 43 04 06 00 00 00 00 00 00 00 11 21 22 11 11 11 11 11 11 11 11 11 11 11 11 11 11 00 63 D7 2D DF
            [2024-02-21 18:01:53,114 proxyUdpServer.py->handleCloudMsg():52] INFO: Cloud: seq=4294967295 msgType=10(a) synclost=0 downlink=1 response=1 write=1 flags=f length=42 msgLen=38
            [2024-02-21 18:01:53,115 proxyUdpServer.py->handleCloudMsg():465] WARNING: Cloud Unhandled message 10 len:msgLen=38
            """
            cseq, unk1, unk2, deviceid, room, day, *prog = unpack(
                "<BBHIIH24B"
            )  # 1 1 2 4 4 2
            logging.info(
                f"Cloud {MsgId(wrapper.msgType).name=} {wrapper.msgType=:x} {cseq=:x} {unk1=:x} {unk2=:x} {deviceid=} {room=} {day=} prog={ [ hex(l) for l in prog ] }"
            )
            roomStatus = getRoomStatus(deviceid, room)
            roomStatus["days"][day] = prog

            forward = True
        elif wrapper.msgType == MsgId.PROG_END and msgLen == 14:
            """
            [2024-02-21 18:01:53,148 udpserver.py->run():449] INFO: From ('104.46.56.16', 6199) 30 bytes : FA D4 12 00 FF FF FF FF 2A 0F 06 00 FF 00 00 00 AA F2 8D 23 A6 27 43 04 14 0A D1 BF 2D DF
            [2024-02-21 18:01:53,149 proxyUdpServer.py->handleCloudMsg():52] INFO: Cloud: seq=4294967295 msgType=42(2a) synclost=0 downlink=1 response=1 write=1 flags=f length=18 msgLen=14
            [2024-02-21 18:01:53,150 proxyUdpServer.py->handleCloudMsg():465] WARNING: Cloud Unhandled message 42 len:msgLen=14
            """
            cseq, unk1, unk2, deviceid, room, unk3 = unpack("<BBHIIH")  # 1 1 2 4 4 2
            logging.info(
                f"Cloud {MsgId(wrapper.msgType).name=} {wrapper.msgType=:x} {cseq=:x} {unk1=:x} {unk2=:x} {deviceid=} {unk3=}"
            )
            forward = True
        elif wrapper.msgType == MsgId.PING and msgLen == 10:
            cseq, unk1, unk2, deviceid, unk3 = unpack("<BBHIH")  # 1 1 2 4 2

            logging.info(
                f"Cloud {MsgId(wrapper.msgType).name=} {wrapper.msgType=:x} {cseq=:x} {unk1=:x} {unk2=:x} {deviceid=} {unk3=}"
            )

            # Send a DL PING message
            self.send_PING(addr, deviceid, response=1)
        else:
            logging.warn(
                f"Cloud Unhandled message {MsgId(wrapper.msgType).name=} {wrapper.msgType=} len:{msgLen=}"
            )
            Database().log_unknown_udp(
                str(addr[0]),
                MsgId(wrapper.msgType).name,
                wrapper.msgType if wrapper.msgType is not None else -1,
                data,
                payload,
            )
            try:
                cseq, unk1, unk2, deviceid = unpack("<BBHI")  # 1 1 2 4
                logging.info(
                    f"Uknown Cloud {MsgId(wrapper.msgType).name=} {wrapper.msgType=:x} {cseq=:x} {unk1=:x} {unk2=:x} {deviceid=}"
                )
            except Exception as e:
                logging.warning(e)
            unpack.setOffset(msgLen)  # To skip false inernal error
            forward = True

        if unpack.getOffset() != msgLen:
            # Check we have consumed the complete message we received
            logging.warn(
                f"Cloud Incomplete Message Read - Internal error offset={unpack.getOffset()} {msgLen=}"
            )
            Database().log_unknown_udp(
                str(addr[0]),
                MsgId(wrapper.msgType).name,
                wrapper.msgType if wrapper.msgType is not None else -1,
                data,
                payload,
                unpack.subbuf(msgLen - unpack.getOffset()),
            )

        try:
            if (
                "deviceid" in locals()
                and forward
                and (paddr := getPeerFromDeviceId(deviceid)) is not None
            ):
                # logging.info(pformat(paddr))
                self.send_ENCODED_FRAME(paddr, payload, response=wrapper.response, write=wrapper.write)  # type: ignore
        except Exception as e:
            logging.debug(e)

        return MsgId(wrapper.msgType).name

    def handleMsg(self, data, addr):

        if len(data) == 1 and data[0] == 0x58:
            self.knocks += 1
            return
        time1: float = time.time()
        cret = "OK"
        ret = hexdump.dump(data, sep="")
        try:
            if addr == self.cloud_addr or self.knocks >= 3:
                self.knocks = 0
                ret = self.handleCloudMsg(data, addr)
                return ret
            if not self.debugmode:
                logging.debug(
                    f"Cloud replicate message {len(data)} bytes : {hexdump.dump(data, sep='')} from {self.addr} to {self.cloud_addr}"
                )
                self.sendto(data, self.cloud_addr)
            ret = super().handleMsg(data, addr)
            return ret
        except Exception as e:
            cret = repr(e)
            raise e
        finally:
            time2: float = time.time()
            # logging.info(pformat((args, kwargs, ret)))
            logging.debug(
                "{:s} function took {:.3f} ms".format(ret, (time2 - time1) * 1000.0)
            )
            Database().log_traces(
                source="UDP",
                host=str(addr[0]),
                adapterMap=ret,
                uri=ret,
                elapsed=int((time2 - time1) * 1000.0),
                response_status=cret,
            )
