import logging
import json
import asyncio
import aiohttp
from datetime import datetime, timedelta

API_URL = "https://mypagesapi.sectoralarm.net/api"


async def main():
    message_headers = {
        "API-Version": "6",
        "Platform": "iOS",
        "User-Agent": "  SectorAlarm/387 CFNetwork/1206 Darwin/20.1.0",
        "Version": "2.0.27",
        "Connection": "keep-alive",
        "Content-Type": "application/json",
    }

    json_data = {"UserId": "INSERT_USERNAME_HERE", "Password": "INSERT_PASSWORD_HERE"}
    async with aiohttp.ClientSession() as session:
        print(datetime.now())
        async with session.post(
            "https://mypagesapi.sectoralarm.net/api/Login/Login",
            headers=message_headers,
            json=json_data,
        ) as response:
            if response.status != 200:
                # _LOGGER.debug("Sector: Failed to send Login: %d", response.status)
                print("Funkar inte")
            else:
                data_out = await response.json()
                AUTH_TOKEN = data_out["AuthorizationToken"]
            # _LOGGER.debug("Sector: AUTH: %s", AUTH_TOKEN)

            message_headers = {
                "Authorization": AUTH_TOKEN,
                "API-Version": "6",
                "Platform": "iOS",
                "User-Agent": "SectorAlarm/356 CFNetwork/1152.2 Darwin/19.4.0",
                "Version": "2.0.20",
                "Connection": "keep-alive",
                "Content-Type": "application/json",
            }
        print(datetime.now())
        async with session.get(
            API_URL + "/Panel/getFullSystem", headers=message_headers
        ) as response:
            if response.status != 200:
                # _LOGGER.debug("Sector: Failed to get Full system: %d", response.status)
                # raise PlatformNotReady
                print("Funkar inte")
            else:
                firstrun = await response.json()

        PANELID = firstrun["Panel"]["PanelId"]
        FULLSYSTEMINFO = firstrun
        print("FULLSYSTEMINFO")
        print(FULLSYSTEMINFO)

        print(datetime.now())
        async with session.get(
            API_URL + "/Panel/GetPanelStatus?panelId={}".format(PANELID),
            headers=message_headers,
        ) as response:
            if response.status != 200:
                # _LOGGER.debug("Sector: Failed to get Full system: %d", response.status)
                # raise PlatformNotReady
                print("Funkar inte")
            else:
                GetPanelStatus = await response.json()

        print("GetPanelStatus")
        print(GetPanelStatus)

        print(datetime.now())
        async with session.get(
            API_URL + "/Panel/GetTemperatures?panelId={}".format(PANELID),
            headers=message_headers,
        ) as response:
            if response.status != 200:
                # _LOGGER.debug("Sector: Failed to get Full system: %d", response.status)
                # raise PlatformNotReady
                print("Funkar inte")
            else:
                GetTemperatures = await response.json()

        print("GetTemperatures")
        print(GetTemperatures)

        print(datetime.now())
        async with session.get(
            API_URL + "/Panel/GetLockStatus?panelId={}".format(PANELID),
            headers=message_headers,
        ) as response:
            if response.status != 200:
                # _LOGGER.debug("Sector: Failed to get Full system: %d", response.status)
                # raise PlatformNotReady
                print("Funkar inte")
            else:
                GetLockStatus = await response.json()

        print("GetLockStatus")
        print(GetLockStatus)

        print(datetime.now())
        async with session.get(
            API_URL + "/Panel/GetLogs?panelId={}".format(PANELID),
            headers=message_headers,
        ) as response:
            if response.status != 200:
                # _LOGGER.debug("Sector: Failed to get Full system: %d", response.status)
                # raise PlatformNotReady
                print("Funkar inte")
            else:
                GetLogs = await response.json()

        print("GetLogs")
        print(GetLogs)

        print(datetime.now())


loop = asyncio.get_event_loop()
loop.run_until_complete(main())
