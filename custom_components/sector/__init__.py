"""SECTOR ALARM INTEGRATION FOR HOME ASSISTANT"""
import logging
import json
import asyncio
import aiohttp
import async_timeout
from datetime import datetime, timedelta
import voluptuous as vol
from homeassistant import exceptions
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
from homeassistant.helpers import discovery
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import device_registry as dr

_LOGGER = logging.getLogger(__name__)

DOMAIN = "sector"
DEFAULT_NAME = "sector"
DATA_SA = "sector"

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

API_URL = "https://mypagesapi.sectoralarm.net/api"

async def async_setup(hass, config):

    conf = config.get(DOMAIN)
    if conf is None:
        return True

    userid = config[DOMAIN][CONF_USERID]
    password = config[DOMAIN][CONF_PASSWORD]
    sector_lock = config[DOMAIN][CONF_LOCK]
    sector_temp = config[DOMAIN][CONF_TEMP]

    sector_data = SectorAlarmHub(
    sector_lock, sector_temp, userid, password, websession=async_get_clientsession(hass)
    )
    await sector_data.async_update(force_update=True)
    hass.data[DATA_SA] = sector_data

    panel_data = await sector_data.get_panel()
    if panel_data is None or panel_data == []:
        _LOGGER.error("Platform not ready")
        raise PlatformNotReady
        return False
    else:
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

    temp_data = await sector_data.get_thermometers()
    if temp_data is None or temp_data == [] or sector_temp == False:
        _LOGGER.debug("Temp not configured")
    else:
        hass.async_create_task(
                discovery.async_load_platform(hass, "sensor", DOMAIN, {}, config)
            )

    lock_data = await sector_data.get_locks()
    if lock_data is None or lock_data == [] or sector_lock == False:
        _LOGGER.debug("Lock not configured")
    else:
        hass.async_create_task(
                discovery.async_load_platform(
                    hass, 'lock', DOMAIN, {
                        CONF_CODE_FORMAT: config[DOMAIN][CONF_CODE_FORMAT],
                        CONF_CODE: config[DOMAIN][CONF_CODE]
                    }, config))

    return True

async def async_setup_entry(hass, entry):
    """ Setup from config entries """

    userid = entry.data[CONF_USERID]
    password = entry.data[CONF_PASSWORD]
    sector_lock = entry.data[CONF_LOCK]
    sector_temp = entry.data[CONF_TEMP]

    sector_data = SectorAlarmHub(
    sector_lock, sector_temp, userid, password, websession=async_get_clientsession(hass)
    )
    await sector_data.async_update(force_update=True)
    hass.data[DATA_SA] = sector_data

    device_registry = await dr.async_get_registry(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "sa_hub_"+str(sector_data.alarm_id))},
        manufacturer="Sector Alarm",
        name="Sector Hub",
        model="Hub",
        sw_version="master",
    )

    panel_data = await sector_data.get_panel()
    if panel_data is None or panel_data == []:
        _LOGGER.error("Platform not ready")
        raise PlatformNotReady
        return False
    else:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, "alarm_control_panel")
            )

    temp_data = await sector_data.get_thermometers()
    if temp_data is None or temp_data == [] or sector_temp == False:
        _LOGGER.debug("Temp not configured")
    else:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, "sensor")
            )

    lock_data = await sector_data.get_locks()
    if lock_data is None or lock_data == [] or sector_lock == False:
        _LOGGER.debug("Lock not configured")
    else:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, "lock")
            )

    return True

async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    unload_alarm = await hass.config_entries.async_forward_entry_unload(
        entry, "alarm_control_panel"
    )
    unload_sensor = await hass.config_entries.async_forward_entry_unload(
        entry, "sensor"
    )
    unload_lock = await hass.config_entries.async_forward_entry_unload(
        entry, "lock"
    )
    if unload_lock == True and unload_alarm == True and unload_sensor == True:
        return True
    else:
        return False

class SectorAlarmHub(object):
    """ Sector connectivity hub """

    def __init__(self, sector_lock, sector_temp, userid, password, websession):
        self._lockstatus = {}
        self._tempstatus = {}
        self._lockdata = None
        self._tempdata = None
        self._alarmstatus = None
        self._changed_by = None
        self.websession = websession
        self._sector_temp = sector_temp
        self._sector_lock = sector_lock
        self._userid = userid
        self._password = password
        self._access_token = None
        self._last_updated = datetime.utcnow() - timedelta(hours=2)
        self._timeout = 15
        self._panel = []
        self._temps = []
        self._locks = []
        self._panel_id = None

    async def get_thermometers(self):
        temps = self._temps

        if temps is None or temps == []:
            _LOGGER.debug("Failed to fetch temperature sensors")
            return None

        return (temp["SerialNo"] for temp in temps)

    async def get_name(self, serial, command):
        _LOGGER.debug("Command is: %s", command)
        _LOGGER.debug("Serial is: %s", serial)
        if command == "temp":
            names = self._temps
        elif command == "lock":
            names = self._locks
        else:
            return None

        for name in names:
            if command == "temp":
                if name["SerialNo"] == serial:
                    _LOGGER.debug("Returning label: %s", name["Label"])
                    return name["Label"]
            elif command =="lock":
                if name["Serial"] == serial:
                    _LOGGER.debug("Returning label: %s", name["Label"])
                    return name["Label"]
            else:
                _LOGGER.debug("Get_name no command, return Not found")
                return "Not found"

    async def get_autolock(self, serial):
        _LOGGER.debug("Serial is: %s", serial)
        autolocks = self._locks

        for autolock in autolocks:
            if autolock["Serial"] == serial:
                _LOGGER.debug("Returning AutoLockEnabled: %s", autolock["AutoLockEnabled"])
                return autolock["AutoLockEnabled"]

        return "Not found"

    async def get_locks(self):
        locks = self._locks

        if locks is None or locks == []:
            _LOGGER.debug("Failed to fetch locks")
            return None

        return (lock["Serial"] for lock in locks)

    async def get_panel(self):
        panel = self._panel

        if panel is None or panel == []:
            _LOGGER.debug("Failed to fetch panel")
            return None

        return panel["PanelDisplayName"]


    async def triggerlock(self, lock, code, command):

        message_json = {
                "LockSerial": lock,
                "PanelCode": code,
                "PanelId": self._panel_id,
                "Platform": "app"
            }

        if command == "unlock":
            response = await self._request(API_URL + "/Panel/Unlock", json_data=message_json)
        else:
            response = await self._request(API_URL + "/Panel/Lock", json_data=message_json)

        await self.async_update(force_update=True)
        return True

    async def triggeralarm(self, command, code):

        message_json = {
                "PanelCode": code,
                "PanelId": self._panel_id,
                "Platform": "app"
            }

        if command == "full":
            response = await self._request(API_URL + "/Panel/Arm", json_data=message_json)
        elif command == "partial":
            response = await self._request(API_URL + "/Panel/PartialArm", json_data=message_json)
        else:
            response = await self._request(API_URL + "/Panel/Disarm", json_data=message_json)

        await self.async_update(force_update=True)
        return True

    async def async_update(self, force_update=False):
        """ Fetch updates """

        now = datetime.utcnow()
        if (
            now - self._last_updated < timedelta(seconds=60)
            and not force_update
        ):
            return
        self._last_updated = now
        await self.fetch_info()

        temps = self._tempdata
        if temps is not None and temps != [] and self._sector_temp == True:
            self._tempstatus = {
                            temperature["SerialNo"]: temperature["Temprature"]
                            for temperature in temps
                        }

        locks = self._lockdata
        if locks is not None and locks != [] and self._sector_lock == True:
            self._lockstatus = {
                            lock["Serial"]: lock["Status"]
                            for lock in locks
                        }

        return True

    async def fetch_info(self):
        """ Fetch info from API """
        response = await self._request(API_URL + "/Panel/getFullSystem")
        if response is None:
            return
        json_data = await response.json()
        if json_data is None:
            return

        self._panel = json_data["Panel"]
        self._panel_id = json_data["Panel"]["PanelId"]
        self._temps = json_data["Temperatures"]
        self._locks = json_data["Locks"]

        response = await self._request(API_URL + "/Panel/GetPanelStatus?panelId={}".format(self._panel_id))
        json_data = await response.json()
        self._alarmstatus = json_data["Status"]
        _LOGGER.debug("self._alarmstatus = %s", self._alarmstatus)

        if self._temps != [] and self._sector_temp == True:
            response = await self._request(API_URL + "/Panel/GetTemperatures?panelId={}".format(self._panel_id))
            json_data = await response.json()
            if json_data is not None:
                self._tempdata = json_data
            _LOGGER.debug("self._tempdata = %s", self._tempdata)

        if self._locks != [] and self._sector_lock == True:
            response = await self._request(API_URL + "/Panel/GetLockStatus?panelId={}".format(self._panel_id))
            json_data = await response.json()
            if json_data is not None:
                self._lockdata = json_data
            _LOGGER.debug("self._lockdata = %s", self._lockdata)

        response = await self._request(API_URL + "/Panel/GetLogs?panelId={}".format(self._panel_id))
        json_data = await response.json()
        if json_data is not None:
            for users in json_data:
                if users['User'] != "" and "arm" in users['EventType']:
                    self._changed_by = users['User']
                    break
                else:
                    self._changed_by = "unknown"
            _LOGGER.debug("self._changed_by = %s", self._changed_by)

    async def _request(self, url, json_data=None, retry=3):
        if self._access_token is None:
            response = await self.websession.post(
                f"{API_URL}/Login/Login",
                headers={
                        "API-Version":"6",
                        "Platform":"iOS",
                        "User-Agent":"SectorAlarm/356 CFNetwork/1152.2 Darwin/19.4.0",
                        "Version":"2.0.20",
                        "Connection":"keep-alive",
                        "Content-Type":"application/json",
                    },
                json={
                    "UserId": self._userid,
                    "Password": self._password,
                },
            )
            token_data = await response.json()
            if token_data is None or token_data == "":
                _LOGGER.error("Error connecting to Sector")
                raise CannotConnect
            self._access_token = token_data['AuthorizationToken']
        headers = {
                    "Authorization": self._access_token,
                    "API-Version":"6",
                    "Platform":"iOS",
                    "User-Agent":"SectorAlarm/356 CFNetwork/1152.2 Darwin/19.4.0",
                    "Version":"2.0.20",
                    "Connection":"keep-alive",
                    "Content-Type":"application/json",
                }

        try:
            with async_timeout.timeout(self._timeout):
                if json_data:
                    response = await self.websession.post(
                        url, json=json_data, headers=headers
                    )
                else:
                    response = await self.websession.get(url, headers=headers)
            if response.status != 200:
                self._access_token = None
                if retry > 0:
                    await asyncio.sleep(1)
                    return await self._request(url, json_data, retry=retry - 1)
                _LOGGER.error(
                    "Error connecting to Sector, response: %s %s", response.status, response.reason
                )

                return None
        except aiohttp.ClientError as err:
            self._access_token = None
            if retry > 0:
                return await self._request(url, json_data, retry=retry - 1)
            _LOGGER.error("Error connecting to Sector: %s ", err, exc_info=True)
            raise
        except asyncio.TimeoutError:
            self._access_token = None
            if retry > 0:
                return await self._request(url, json_data, retry=retry - 1)
            _LOGGER.error("Timed out when connecting to Sector")
            raise
        _LOGGER.debug("request response = %s", response)
        return response

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
        return self._panel['PanelId']

    @property
    def alarm_displayname(self):
        return self._panel['PanelDisplayName']

    @property
    def alarm_isonline(self):
        return self._panel['IsOnline']

class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""
