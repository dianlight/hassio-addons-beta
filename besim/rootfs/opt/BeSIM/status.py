#
# This is where we store the status of any connected peers/devices
#
# import logging
# from pprint import pformat
from uuid import uuid4


Status = {"peers": {}, "devices": {}, "token": str(uuid4())}
# Status = {
#    "peers": {("192.168.0.105", 6199): {"devices": {596505258}, "seq": 1306}},
#    "devices": {},
#    "token": str(uuid4()),
# }


def getStatus():
    return Status


def getPeerFromDeviceId(deviceId):
    value = dict(
        filter(lambda pair: deviceId in pair[1]["devices"], Status["peers"].items())
    ).keys()
    # logging.debug(
    #    pformat((Status, value, len(value), list(value)[0] if len(value) > 0 else None))
    # )
    return list(value)[0] if len(value) > 0 else None


def getPeerStatus(addr):
    if addr not in Status["peers"]:
        Status["peers"][addr] = {"devices": set()}
    return Status["peers"][addr]


def getDeviceStatus(deviceid):
    if deviceid not in Status["devices"]:
        # cseq is control plane sequence number, 0..0xfd
        # results is a dict holding the results from a request
        # 'results' = { <sequence number of request sent> : { 'ev' : <threading.Event>,
        # 'val' : <result of requested operation> }, ... }
        Status["devices"][deviceid] = {"rooms": {}, "cseq": 0x0, "results": {}}
    return Status["devices"][deviceid]


def getRoomStatus(deviceid, room):
    deviceStatus = getDeviceStatus(deviceid)

    if room not in deviceStatus["rooms"]:
        deviceStatus["rooms"][room] = {"days": {}}
    return deviceStatus["rooms"][room]
