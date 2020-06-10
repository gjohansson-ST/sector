"""SECTOR ALARM INTEGRATION FOR HOME ASSISTANT"""
import logging
import json
import asyncio
import aiohttp
from datetime import datetime, timedelta
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
from homeassistant.helpers import discovery
from homeassistant.exceptions import PlatformNotReady

_LOGGER = logging.getLogger(__name__)

DOMAIN = "sector"

DEFAULT_NAME = "sector"
DATA_SA = "sector"

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)

CONF_USERID = "userid"
CONF_PASSWORD = "password"
CONF_CODE_FORMAT = "code_format"
CONF_CODE = "code"
CONF_TEMP = "temp"
CONF_LOCK = "lock"

CONFIG_SCHEMA = vol.Schema(
    {
    DOMAIN: vol.Schema(
        {
            vol.Required(CONF_USERID): cv.string,
            vol.Required(CONF_PASSWORD): cv.string,
            vol.Optional(CONF_CODE, default=""): cv.string,
            vol.Optional(CONF_CODE_FORMAT, default="^\\d{4,6}$"): cv.string,
            vol.Optional(CONF_TEMP, default=True): cv.boolean,
            vol.Optional(CONF_LOCK, default=True): cv.boolean,
        }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

async def async_setup(hass, config):

    firstrun = {}
    USERID = config[DOMAIN][CONF_USERID]
    PASSWORD = config[DOMAIN][CONF_PASSWORD]
    sector_lock = config[DOMAIN][CONF_LOCK]
    sector_temp = config[DOMAIN][CONF_TEMP]

    AUTH_TOKEN = ""
    FULLSYSTEMINFO = {}
    PANELID = ""

    message_headers = {
        "API-Version":"6",
        "Platform":"iOS",
        "User-Agent":"SectorAlarm/356 CFNetwork/1152.2 Darwin/19.4.0",
        "Version":"2.0.20",
        "Connection":"keep-alive",
        "Content-Type":"application/json"
    }

    json_data = {
        "UserId": USERID,
        "Password": PASSWORD
    }
    async with aiohttp.ClientSession() as session:
        async with session.post("https://mypagesapi.sectoralarm.net/api/Login/Login",
            headers=message_headers, json=json_data) as response:
            if response.status != 200:
                    _LOGGER.debug("Sector: Failed to send Login: %d", response.status)

            data_out = await response.json()
            AUTH_TOKEN = data_out['AuthorizationToken']
            _LOGGER.debug("Sector: AUTH: %s", AUTH_TOKEN)

            message_headers = {
                "Authorization": AUTH_TOKEN,
                "API-Version":"6",
                "Platform":"iOS",
                "User-Agent":"SectorAlarm/356 CFNetwork/1152.2 Darwin/19.4.0",
                "Version":"2.0.20",
                "Connection":"keep-alive",
                "Content-Type":"application/json"
            }

        async with session.get("https://mypagesapi.sectoralarm.net/api/panel/getFullSystem",
            headers=message_headers) as response:
            if response.status != 200:
                _LOGGER.debug("Sector: Failed to get Full system: %d", response.status)
                raise PlatformNotReady

            firstrun = await response.json()

    PANELID = firstrun['Panel']['PanelId']
    FULLSYSTEMINFO = firstrun

    sector_data = SectorAlarmHub(FULLSYSTEMINFO, PANELID, USERID, PASSWORD, AUTH_TOKEN)
    await sector_data.async_update()
    hass.data[DATA_SA] = sector_data

    if FULLSYSTEMINFO['Temperatures'] is None or FULLSYSTEMINFO['Temperatures'] == [] or sector_temp == False:
        _LOGGER.debug("Sector: No Temp devices found")
    else:
        _LOGGER.debug("Sector: Found Temp devices")
        _LOGGER.debug(firstrun['Temperatures'])
        hass.async_create_task(
                discovery.async_load_platform(hass, "sensor", DOMAIN, {}, config)
            )

    if FULLSYSTEMINFO['Locks'] is None or FULLSYSTEMINFO['Locks'] == [] or sector_lock == False:
        _LOGGER.debug("Sector: No Lock devices found")
    else:
        _LOGGER.debug("Sector: Found Lock devices")
        _LOGGER.debug(firstrun['Locks'])
        hass.async_create_task(
                discovery.async_load_platform(
                    hass, 'lock', DOMAIN, {
                        CONF_CODE_FORMAT: config[DOMAIN][CONF_CODE_FORMAT],
                        CONF_CODE: config[DOMAIN][CONF_CODE]
                    }, config))

    if FULLSYSTEMINFO['Panel'] is None or FULLSYSTEMINFO['Panel'] == []:
        _LOGGER.debug("Sector: Platform not ready")
        raise PlatformNotReady
    else:
        _LOGGER.debug("Sector: Found Alarm Panel")
        hass.async_create_task(
                discovery.async_load_platform(
                    hass,
                    "alarm_control_panel",
                    DOMAIN,
                    {
                        CONF_CODE_FORMAT: config[DOMAIN][CONF_CODE_FORMAT],
                        CONF_CODE: config[DOMAIN][CONF_CODE],
                    },
                    config,
                )
            )

    return True

class SectorAlarmHub(object):

    def __init__(self, fullsysteminfo, panel_id, userid, password, authtoken):
        self._lockstatus = {}
        self._tempstatus = {}
        self._alarmstatus = None
        self._changed_by = None
        self.fullsysteminfo = fullsysteminfo
        self.panel_id = panel_id
        self.userid = userid
        self.password = password
        self.authtoken = authtoken

    async def get_thermometers(self):
        temps = self.fullsysteminfo['Temperatures']

        if temps is None or temps == []:
            _LOGGER.debug("Sector: failed to fetch temperature sensors")
            return None

        return (temp["SerialNo"] for temp in temps)

    async def get_name(self, serial, command):
        _LOGGER.debug("Sector: command is: %s", command)
        _LOGGER.debug("Sector: serial is: %s", serial)
        if command == "temp":
            names = self.fullsysteminfo['Temperatures']
        elif command == "lock":
            names = self.fullsysteminfo['Locks']
        else:
            return None

        for name in names:
            if command == "temp":
                if name["SerialNo"] == serial:
                    _LOGGER.debug("Sector: Returning label: %s", name["Label"])
                    return name["Label"]
            elif command =="lock":
                if name["Serial"] == serial:
                    _LOGGER.debug("Sector: Returning label: %s", name["Label"])
                    return name["Label"]
            else:
                _LOGGER.debug("Sector: get_name no command, return Not found")
                return "Not found"

    async def get_autolock(self, serial):
        _LOGGER.debug("Sector: serial is: %s", serial)
        autolocks = self.fullsysteminfo['Locks']

        for autolock in autolocks:
            if autolock["Serial"] == serial:
                _LOGGER.debug("Sector: Returning AutoLockEnabled: %s", autolock["AutoLockEnabled"])
                return autolock["AutoLockEnabled"]

        return "Not found"

    async def get_locks(self):
        locks = self.fullsysteminfo['Locks']

        if locks is None or locks == []:
            _LOGGER.debug("Sector: failed to fetch locks")
            return None

        return (lock["Serial"] for lock in locks)

    async def get_panel(self):
        panel = self.fullsysteminfo['Panel']

        if panel is None or panel == []:
            _LOGGER.debug("Sector: failed to fetch panel")
            return None

        return panel["PanelDisplayName"]


    async def triggerlock(self, lock, code, command):
        AUTH_TOKEN = self.authtoken
        PANEL_ID = self.panel_id
        LOCKSERIAL = lock
        LOCKCODE = code
        COMMAND = command
        URL = ""
        async with aiohttp.ClientSession() as session2:
            message_headers = {
                "Authorization": AUTH_TOKEN,
                "API-Version":"6",
                "Platform":"iOS",
                "User-Agent":"SectorAlarm/356 CFNetwork/1152.2 Darwin/19.4.0",
                "Version":"2.0.20",
                "Connection":"keep-alive",
                "Content-Type":"application/json"
            }
            _LOGGER.debug("Sector: LOCKSERIAL: %s", LOCKSERIAL)
            _LOGGER.debug("Sector: LOCKCODE: %s", LOCKCODE)
            _LOGGER.debug("Sector: PANEL_ID: %s", PANEL_ID)
            message_json = {
                "LockSerial": LOCKSERIAL,
                "PanelCode": LOCKCODE,
                "PanelId": PANEL_ID,
                "Platform": "app"
            }
            if COMMAND == "unlock":
                URL = "https://mypagesapi.sectoralarm.net/api/Panel/Unlock"
            else:
                URL = "https://mypagesapi.sectoralarm.net/api/Panel/Lock"
            _LOGGER.debug("Sector: init command is %s", COMMAND)
            async with session2.post(URL, headers=message_headers, json=message_json) as response:
                if response.status != 200 and response.status !=204:
                    _LOGGER.debug("Sector: Failed to lock door: %d", response.status)
                    return False
                _LOGGER.debug("Sector: response.status: %d", response.status)
                _LOGGER.debug("Sector: response.headers is %s", response.headers)
            return True

    async def triggeralarm(self, command, code):
        AUTH_TOKEN = self.authtoken
        PANEL_ID = self.panel_id
        LOCKCODE = code
        COMMAND = command
        URL = ""
        async with aiohttp.ClientSession() as session2:
            message_headers = {
                "Authorization": AUTH_TOKEN,
                "API-Version":"6",
                "Platform":"iOS",
                "User-Agent":"SectorAlarm/356 CFNetwork/1152.2 Darwin/19.4.0",
                "Version":"2.0.20",
                "Connection":"keep-alive",
                "Content-Type":"application/json"
            }
            message_json = {
                "PanelCode": LOCKCODE,
                "PanelId": PANEL_ID,
                "Platform": "app"
            }
            if COMMAND == "full":
                URL = "https://mypagesapi.sectoralarm.net/api/Panel/Arm"
            elif COMMAND == "partial":
                URL = "https://mypagesapi.sectoralarm.net/api/Panel/PartialArm"
            else:
                URL = "https://mypagesapi.sectoralarm.net/api/Panel/Disarm"
            async with session2.post(URL, headers=message_headers, json=message_json) as response:
                if response.status != 200 and response.status != 204:
                    _LOGGER.debug("Sector: Failed to trigger alarm: %d", response.status)
                    return False

            if COMMAND == "full":
                self._alarmstatus = 3
            elif COMMAND == "partial":
                self._alarmstatus = 2
            else:
                self._alarmstatus = 1
            return True


    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        AUTH_TOKEN = self.authtoken
        async with aiohttp.ClientSession() as session:
            message_headers = {
                "Authorization": AUTH_TOKEN,
                "API-Version":"6",
                "Platform":"iOS",
                "User-Agent":"SectorAlarm/356 CFNetwork/1152.2 Darwin/19.4.0",
                "Version":"2.0.20",
                "Connection":"keep-alive",
                "Content-Type":"application/json",
            }

            async with session.get("https://mypagesapi.sectoralarm.net/api/panel/getFullSystem",
                headers=message_headers) as response:
                if response.status != 200:
                    _LOGGER.debug("Sector: Failed to get full system in async_update, run login: %d", response.status)
                    message_headers = {
                        "API-Version":"6",
                        "Platform":"iOS",
                        "User-Agent":"SectorAlarm/356 CFNetwork/1152.2 Darwin/19.4.0",
                        "Version":"2.0.20",
                        "Connection":"keep-alive",
                        "Content-Type":"application/json"
                    }

                    json_data = {
                        "UserId": self.userid,
                        "Password": self.password
                    }
                    async with session.post("https://mypagesapi.sectoralarm.net/api/Login/Login",
                        headers=message_headers, json=json_data) as response:
                        if response.status != 200:
                            _LOGGER.debug("Sector: Failed to send Login: %d", response.status)
                            return False
                        data_out = await response.json()
                        #return data_out
                        dateTimeObj = datetime.now()
                        timestampStr = dateTimeObj.strftime("%d-%b-%Y (%H:%M:%S.%f)")
                        _LOGGER.debug("Sector: SECTOR ALARM LOGIN RUN %s", timestampStr)
                        #returndata = await async_login()
                        AUTH_TOKEN = data_out['AuthorizationToken']
                        self.authtoken = data_out['AuthorizationToken']
                        message_headers = {
                            "Authorization": AUTH_TOKEN,
                            "API-Version":"6",
                            "Platform":"iOS",
                            "User-Agent":"SectorAlarm/356 CFNetwork/1152.2 Darwin/19.4.0",
                            "Version":"2.0.20",
                            "Connection":"keep-alive",
                            "Content-Type":"application/json"
                        }
                _LOGGER.debug("Sector: AUTH_TOKEN still valid: %s", AUTH_TOKEN)

            temps = self.fullsysteminfo['Temperatures']
            if temps is None or temps == [] or CONF_TEMP == False:
                _LOGGER.debug("Sector: No update temps")
            else:
                async with session.get("https://mypagesapi.sectoralarm.net/api/Panel/GetTemperatures?panelId={}".format(self.panel_id),
                    headers=message_headers) as response:
                    if response.status != 200:
                        _LOGGER.debug("Sector: Failed to get temperature update: %d", response.status)
                        return False
                    else:
                        tempinfo = await response.json()
                        self._tempstatus = {
                            temperature["SerialNo"]: temperature["Temprature"]
                            for temperature in tempinfo
                        }
                        _LOGGER.debug("Sector: Tempstatus fetch: %s", json.dumps(self._tempstatus))

            locks = self.fullsysteminfo['Locks']
            if locks is None or locks == [] or CONF_LOCK == False:
                _LOGGER.debug("Sector: No update locks")
            else:
                async with session.get("https://mypagesapi.sectoralarm.net/api/Panel/GetLockStatus?panelId={}".format(self.panel_id),
                    headers=message_headers) as response:
                    if response.status != 200:
                        _LOGGER.debug("Sector: Failed to get locks update: %d", response.status)
                        return False
                    else:
                        lockinfo = await response.json()
                        self._lockstatus = {
                            lock["Serial"]: lock["Status"]
                            for lock in lockinfo
                        }
                        _LOGGER.debug("Sector: Lockstatus fetch: %s", json.dumps(self._lockstatus))

            async with session.get("https://mypagesapi.sectoralarm.net/api/Panel/GetPanelStatus?panelId={}".format(self.panel_id),
                headers=message_headers) as response:
                if response.status != 200:
                    _LOGGER.debug("Sector: Failed to get panel update: %d", response.status)
                    return False
                else:
                    alarminfo = await response.json()
                    self._alarmstatus = alarminfo['Status']
                    _LOGGER.debug("Sector: Alarmstatus fetch: %s", json.dumps(self._alarmstatus))

            async with session.get("https://mypagesapi.sectoralarm.net/api/panel/GetLogs?panelId={}".format(self.panel_id),
                headers=message_headers) as response:
                if response.status != 200:
                    _LOGGER.debug("Sector: Failed to get logs update: %d", response.status)
                    return False
                else:
                    loginfo = await response.json()
                    for users in loginfo:
                        if users['User'] != "" and "arm" in users['EventType']:
                            self._changed_by = users['User']
                            #_LOGGER.debug("Sector: Last changed fetch: %s", json.dumps(self._changed_by))
                            break
                        else:
                            self._changed_by = "unknown"
                    _LOGGER.debug("Sector: Last changed fetch: %s", json.dumps(self._changed_by))

        return True

    @property
    def alarm_state(self):
        return self._alarmstatus

    @property
    def alarm_changed_by(self):
        return self._changed_by

    @property
    def temp_state(self):
        return self._tempstatus

    @property
    def lock_state(self):
        return self._lockstatus

    @property
    def alarm_id(self):
        return self.fullsysteminfo['Panel']['PanelId']

    @property
    def alarm_displayname(self):
        return self.fullsysteminfo['Panel']['PanelDisplayName']

    @property
    def alarm_isonline(self):
        return self.fullsysteminfo['Panel']['IsOnline']
