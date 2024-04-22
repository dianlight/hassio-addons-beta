# BeSIM-MQTT (temp name project)

A simulator and a proxy for the cloud server the BeSMART thermostat/wifi box connects to.
It is based on the [BeSIM Project](https://github.com/jimmyH/BeSIM) by [
jimmyH](https://github.com/jimmyH) extended to act as "__Man in the Middle__" and allow the use local service to manage BeSMART environment also without internet connectivity

## Scope of the project

Integrate the BeSMART environment with HomeAssistant or other Home controller and resolve the many issues on the Riello cloud services.

## Note

Note that this project is not affiliated to Riello SpA which produces and sells the BeSMART products.

Meteorological data is kindly provided by: The Norwegian Meteorological Institute

## What is BeSMART?

BeSMART allows you to connect multiple thermostats to your boiler and control them from your tablet or smartphone.

## What is BeSIM-MQTT?

A way you can control the BeSMART thermostat from within your own home, without having to use the original cloud server but also continue to use official Mobile Apps.

It consists of four components:
 - A UDP Server which handles the messaging to/from the BeSMART wifi box.
 - A UDP Proxy that handles the messaging to/from the BeSMART cloud.
 - A REST API that allows you to get/set parameters from the BeSMART thermostats.
 - An HTTP Proxy that allows get/set parameters from the BeSMART cloud and use the Mobile Apps<sup>1</sup>

A few ways you can control the thermostat:
 - via the REST API (see curl examples below)
 - via Home Assistant, see https://github.com/jimmyH/ha-besim
 - via a (very) basic angular app, see https://github.com/jimmyH/BeSIM-GUI
 - via an Alexa Skill, if anyone is interested I'll find some time to create an example repository


<sup>1: Only iOS App now works because of the leak of HTTPS connection and the Certificate PIN security</sup>

## Caveats

This project is currently only a **proof-of-concept** implementation. Use at your own risk.

It does not yet support:
 - OpenTherm parameters when connected via OT
 - There is no authentication on the rest api
 - Not all UDP Proxy implementation are working


<sup>Note: that CORS (Cross-origin resource sharing) headers are set on the server.<sup>

<sup>Note: that currently when you modify a value the API may return the old value for up to 40s (the thermostat sends periodic status reports every 40s).<sup>

## How do I use BeSIM-MQTT?

### With BeSIM addon

BeSIM-MQTT is part of the BeSIM HomeAssistant Addon that you will find in 
- [ ] [Dianlight BETA Add-ons Repository](https://github.com/dianlight/hassio-addons) <sup>2</sup>
- [ ] [Dianlight Add-ons Repository](https://github.com/dianlight/hassio-addons) <sup>2</sup>

<sup>2: Not yet released!</sup>

### Standalone

BeSIM-MQTT can either be run as a standalone python3 script (tested on python3.12 only).
 - It is recommended to run from a virtual environment, and you can install the dependencies from requirements.txt `pip install -r requirements.txt`.
 - To start the server, just run 'python app.py'. (use -h parameter for options and parameters)

The BeSMART thermostat connects:
 - api.besmart-home.com:6199 (udp)
 - api.besmart-home.com:80 (tcp, http get)
 - www.cloudwarm.com:80 (tcp, http post)

To redirect the traffic to BeSIM-MQTT you need to do one of the following:
 - Configure your NAT router to redirect outgoing traffic with destination api.besmart-home.com to your BeSIM-MQTT instance. You will probably also need to flush the connection tracking state in the router so it picks up the new destination.
 - Update DNS on your router to change the IP address for api.besmart-home.com to your BeSIM instance. You will probably need to reboot the BeSMART wifi box so it picks up the new IP address.

You should then see traffic arriving on BeSIM from your BeSMART device.

You can then use the rest Api to query the state, for example (replace 192.168.0.10 with the IP address of your BeSIM-MQTT instance):
 - Get a list of connected devices: `curl http://192.168.0.10/api/v1.0/devices`
 - Get a list of rooms (thermostats) from the device: `curl http://192.168.0.10/api/v1.0/devices/<deviceid>/rooms`
 - Get the state of the thermostat: `curl http://192.168.0.10/api/v1.0/devices/<deviceid>/rooms/<roomid>`
 - Set T3 temperature (to 19.2degC): `curl http://192.168.0.10/api/v1.0/devices/<deviceid>/rooms/<roomid>/t3 -H "Content-Type: application/json" -X PUT -d 192`
 - ...
