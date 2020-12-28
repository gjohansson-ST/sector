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
from homeassistant.exceptions import PlatformNotReady, ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import device_registry as dr
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_DISARMED,
    STATE_ALARM_PENDING,
)
from homeassistant.const import (
    STATE_LOCKED,
    STATE_UNKNOWN,
    STATE_UNLOCKED,
)

_LOGGER = logging.getLogger(__name__)

DOMAIN = "sector"
DEFAULT_NAME = "sector"

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
UPDATE_INTERVAL = 60
UPDATE_INTERVAL_TEMP = 300

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
    hass.data[DOMAIN] = sector_data

    panel_data = await sector_data.get_panel()
    if panel_data is None:
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
    hass.data[DOMAIN] = sector_data
    #unsub = entry.add_update_listener(update_listener)

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
    if panel_data is None:
        _LOGGER.error("Platform not ready")
        raise ConfigEntryNotReady

    else:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, "alarm_control_panel")
            )

    temp_data = await sector_data.get_thermometers()
    if temp_data is None or temp_data == [] or sector_temp == False:
        _LOGGER.debug("Temp not configured or Temp sensors not found")
    else:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, "sensor")
            )

    lock_data = await sector_data.get_locks()
    if lock_data is None or lock_data == [] or sector_lock == False:
        _LOGGER.debug("Lock not configured or door lock not found")
    else:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, "lock")
            )

    return True

#async def update_listener(hass, entry):
#    """Handle options update."""

async def async_unload_entry(hass, entry):
    """Unload a config entry."""

    sector_lock = entry.data[CONF_LOCK]
    sector_temp = entry.data[CONF_TEMP]

    Platforms = ["alarm_control_panel"]
    if sector_lock == True:
        Platforms.append("lock")
    if sector_temp == True:
        Platforms.append("sensor")

    #unsub()
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in Platforms
            ]
        )
    )

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok

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
        self._last_updated_temp = datetime.utcnow() - timedelta(hours=2)
        self._timeout = 15
        self._panel = []
        self._temps = []
        self._locks = []
        self._panel_id = None
        self._update_sensors = True

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

    async def async_update(self, force_update=False):
        """ Fetch updates """

        now = datetime.utcnow()
        if (
            now - self._last_updated < timedelta(seconds=UPDATE_INTERVAL)
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
        if self._panel == []:
            response = await self._request(API_URL + "/Panel/getFullSystem")
            if response is None:
                return None
            json_data = await response.json()
            if json_data is not None:
                self._panel = json_data["Panel"]
                self._panel_id = json_data["Panel"]["PanelId"]
                self._temps = json_data["Temperatures"]
                self._locks = json_data["Locks"]

        now = datetime.utcnow()
        if (
            now - self._last_updated_temp < timedelta(seconds=UPDATE_INTERVAL_TEMP)
        ):
            self._update_sensors = False
        else:
            self._update_sensors = True
            self._last_updated_temp = now

        response = await self._request(API_URL + "/Panel/GetPanelStatus?panelId={}".format(self._panel_id))
        if response is not None:
            json_data = await response.json()
            self._alarmstatus = json_data["Status"]
            _LOGGER.debug("self._alarmstatus = %s", self._alarmstatus)

        if self._temps != [] and self._sector_temp == True and self._update_sensors == True:
            response = await self._request(API_URL + "/Panel/GetTemperatures?panelId={}".format(self._panel_id))
            if response is not None:
                self._tempdata = await response.json()
                _LOGGER.debug("self._tempdata = %s", self._tempdata)

        if self._locks != [] and self._sector_lock == True:
            response = await self._request(API_URL + "/Panel/GetLockStatus?panelId={}".format(self._panel_id))
            if response is not None:
                self._lockdata = await response.json()
                _LOGGER.debug("self._lockdata = %s", self._lockdata)

        response = await self._request(API_URL + "/Panel/GetLogs?panelId={}".format(self._panel_id))
        if response is not None:
            json_data = await response.json()
            for users in json_data:
                if users['User'] != "" and "arm" in users['EventType']:
                    self._changed_by = users['User']
                    break
                else:
                    self._changed_by = "unknown"
            _LOGGER.debug("self._changed_by = %s", self._changed_by)

    async def _request(self, url, json_data=None, retry=3):
        if self._access_token is None:
            result = await self._login()
            if result is None:
                return None

        headers = {
                    "Authorization": self._access_token,
                    "API-Version":"6",
                    "Platform":"iOS",
                    "User-Agent":"  SectorAlarm/387 CFNetwork/1206 Darwin/20.1.0",
                    "Version":"2.0.27",
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

            if response.status == 401:
                self._access_token = None
                await asyncio.sleep(2)
                if retry > 0:
                    return await self._request(url, json_data, retry=retry - 1)

            if response.status == 200 or response.status == 204:
                _LOGGER.debug(f"Info retrieved successfully URL: {url}")
                _LOGGER.debug(f"request status: {response.status}")
                return response

            return None

        except aiohttp.ClientConnectorError as e:
            _LOGGER.error("ClientError connecting to Sector: %s ", e, exc_info=True)
            raise CannotConnectError from e

        except aiohttp.ContentTypeError as e:
            _LOGGER.error("ContentTypeError connecting to Sector: %s ", c)
            raise CannotConnectError from e

        except asyncio.TimeoutError:
            _LOGGER.error("Timed out when connecting to Sector")
            raise OperationError("Timeout")

        except asyncio.CancelledError:
            _LOGGER.error("Task was cancelled")
            raise OperationError("Cancelled")

        return None

    async def _login(self):
        """ Login to retrieve access token """
        try:
            with async_timeout.timeout(self._timeout):
                response = await self.websession.post(
                f"{API_URL}/Login/Login",
                headers={
                        "API-Version":"6",
                        "Platform":"iOS",
                        "User-Agent":"  SectorAlarm/387 CFNetwork/1206 Darwin/20.1.0",
                        "Version":"2.0.27",
                        "Connection":"keep-alive",
                        "Content-Type":"application/json",
                    },
                json={
                    "UserId": self._userid,
                    "Password": self._password,
                    },
                )

                if response.status == 401:
                    self._access_token = None
                    raise UnauthorizedError("Invalid username or password")
                    return None

                if response.status == 200 or response.status == 204:
                    token_data = await response.json()
                    self._access_token = token_data['AuthorizationToken']
                    return self._access_token

                return None

        except aiohttp.ClientConnectorError as e:
            _LOGGER.error("ClientError connecting to Sector: %s ", e, exc_info=True)
            raise CannotConnectError from e

        except aiohttp.ContentTypeError as c:
            _LOGGER.error("ContentTypeError connecting to Sector: %s ", c)
            raise CannotConnectError from c

        except asyncio.TimeoutError:
            _LOGGER.error("Timed out when connecting to Sector")
            raise OperationError("Timeout")

        except asyncio.CancelledError:
            _LOGGER.error("Task was cancelled")
            raise OperationError("Cancelled")

        return None

    @property
    def alarm_state(self):
        if self._alarmstatus == 3:
            return STATE_ALARM_ARMED_AWAY
        elif self._alarmstatus == 2:
            return STATE_ALARM_ARMED_HOME
        elif self._alarmstatus == 1:
            return STATE_ALARM_DISARMED
        else:
            return STATE_ALARM_PENDING

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


class UnauthorizedError(HomeAssistantError):
    """Exception to indicate an error in authorization."""

class CannotConnectError(HomeAssistantError):
    """Exception to indicate an error in client connection."""

class OperationError(HomeAssistantError):
    """Exception to indicate an error in operation."""
