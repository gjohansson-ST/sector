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
from homeassistant.exceptions import (
    PlatformNotReady,
    ConfigEntryNotReady,
    HomeAssistantError,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
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

from .const import (
    DOMAIN,
    DEPENDENCIES,
    CONF_USERID,
    CONF_PASSWORD,
    CONF_CODE_FORMAT,
    CONF_CODE,
    CONF_TEMP,
    CONF_LOCK,
    UPDATE_INTERVAL,
    MIN_SCAN_INTERVAL,
    API_URL,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERID): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_CODE, default=""): cv.string,
                vol.Optional(CONF_CODE_FORMAT, default=6): cv.positive_int,
                vol.Optional(CONF_TEMP, default=True): cv.boolean,
                vol.Optional(CONF_LOCK, default=True): cv.boolean,
                vol.Required(UPDATE_INTERVAL, default=60): vol.All(
                    cv.positive_int, vol.Clamp(min=MIN_SCAN_INTERVAL)
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """ No setup from yaml """
    return True


async def async_migrate_entry(hass, entry):
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s", entry.version)

    if entry.version == 1:

        new = {**entry.options}
        new[UPDATE_INTERVAL] = 60

        entry.options = {**new}

        new2 = {**entry.data}
        new2[CONF_CODE_FORMAT] = 6

        entry.data = {**new2}

        entry.version = 2

    _LOGGER.info("Migration to version %s successful", entry.version)

    return True


async def async_setup_entry(hass, entry):
    """ Setup from config entries """
    hass.data.setdefault(DOMAIN, {})
    title = entry.title

    if UPDATE_INTERVAL not in entry.options:
        _LOGGER.info(
            "Set 60 seconds as update_interval as default. Adjust in options for integration"
        )
        hass.config_entries.async_update_entry(entry, options={UPDATE_INTERVAL: 60})

    websession = async_get_clientsession(hass)

    api = SectorAlarmHub(
        entry.data[CONF_LOCK],
        entry.data[CONF_TEMP],
        entry.data[CONF_USERID],
        entry.data[CONF_PASSWORD],
        entry.options.get(UPDATE_INTERVAL, 60),
        websession=websession,
    )

    async def async_update_data():
        """ Fetch data """

        now = datetime.utcnow()
        hass.data[DOMAIN][entry.entry_id]["last_updated"] = now
        _LOGGER.debug(f"UPDATE_INTERVAL = {entry.options[UPDATE_INTERVAL]}")
        _LOGGER.debug(
            "last updated = %s", hass.data[DOMAIN][entry.entry_id]["last_updated"]
        )
        await api.fetch_info()

        return True

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="sector_api",
        update_method=async_update_data,
        update_interval=timedelta(seconds=entry.options[UPDATE_INTERVAL]),
    )

    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "coordinator": coordinator,
        "last_updated": datetime.utcnow() - timedelta(hours=2),
        "data_listener": [entry.add_update_listener(update_listener)],
    }
    _LOGGER.debug("Connected to Sector Alarm API")

    await coordinator.async_refresh()
    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    panel_data = await api.get_panel()
    if panel_data is None:
        _LOGGER.error("Platform not ready")
        raise ConfigEntryNotReady

    else:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, "alarm_control_panel")
        )

    temp_data = await api.get_thermometers()
    if temp_data is None or entry.data[CONF_TEMP] == False:
        _LOGGER.debug("Temp not configured or Temp sensors not found")
    else:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, "sensor")
        )

    lock_data = await api.get_locks()
    if lock_data is None or entry.data[CONF_LOCK] == False:
        _LOGGER.debug("Lock not configured or door lock not found")
    else:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, "lock")
        )

    device_registry = await dr.async_get_registry(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "sa_hub_" + str(api.alarm_id))},
        manufacturer="Sector Alarm",
        name="Sector Hub",
        model="Hub",
        sw_version="master",
    )

    return True


async def update_listener(hass, entry):
    """Update when config_entry options update."""
    controller = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    old_update_interval = controller.update_interval
    controller.update_interval = timedelta(seconds=entry.options.get(UPDATE_INTERVAL))
    if old_update_interval != controller.update_interval:
        _LOGGER.debug(
            "Changing scan_interval from %s to %s",
            old_update_interval,
            controller.update_interval,
        )


async def async_unload_entry(hass, entry):
    """Unload a config entry."""

    sector_lock = entry.data[CONF_LOCK]
    sector_temp = entry.data[CONF_TEMP]

    Platforms = ["alarm_control_panel"]
    if sector_lock == True:
        Platforms.append("lock")
    if sector_temp == True:
        Platforms.append("sensor")

    for listener in hass.data[DOMAIN][entry.entry_id]["data_listener"]:
        listener()

    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in Platforms
            ]
        )
    )

    title = entry.title
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        _LOGGER.debug("Unloaded entry for %s", title)
        return unload_ok
    return False


class SectorAlarmHub(object):
    """ Sector connectivity hub """

    def __init__(
        self, sector_lock, sector_temp, userid, password, timesync, websession
    ):
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
        self._timesync = timesync

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
            elif command == "lock":
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
                _LOGGER.debug(
                    "Returning AutoLockEnabled: %s", autolock["AutoLockEnabled"]
                )
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
            "Platform": "app",
        }

        if command == "unlock":
            response = await self._request(
                API_URL + "/Panel/Unlock", json_data=message_json
            )
        else:
            response = await self._request(
                API_URL + "/Panel/Lock", json_data=message_json
            )

        if response is not None:
            await self.fetch_info(False)
            return True

    async def triggeralarm(self, command, code):

        message_json = {"PanelCode": code, "PanelId": self._panel_id, "Platform": "app"}

        if command == "full":
            response = await self._request(
                API_URL + "/Panel/Arm", json_data=message_json
            )
        elif command == "partial":
            response = await self._request(
                API_URL + "/Panel/PartialArm", json_data=message_json
            )
        else:
            response = await self._request(
                API_URL + "/Panel/Disarm", json_data=message_json
            )

        if response is not None:
            await self.fetch_info(False)
            return True

    async def fetch_info(self, tempcheck=True):
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
        _LOGGER.debug(f"self._last_updated_temp = {self._last_updated_temp}")
        _LOGGER.debug(f"self._timesync * 5 = {self._timesync*5}")
        _LOGGER.debug(
            f"Evaluate should temp sensors update {now - self._last_updated_temp}"
        )
        if tempcheck == False:
            self._update_sensors = False
        elif now - self._last_updated_temp < timedelta(seconds=self._timesync * 5):
            self._update_sensors = False
        else:
            self._update_sensors = True
            self._last_updated_temp = now

        response = await self._request(
            API_URL + "/Panel/GetPanelStatus?panelId={}".format(self._panel_id)
        )
        if response is not None:
            json_data = await response.json()
            self._alarmstatus = json_data["Status"]
            _LOGGER.debug("self._alarmstatus = %s", self._alarmstatus)

        if (
            self._temps != []
            and self._sector_temp == True
            and self._update_sensors == True
        ):
            response = await self._request(
                API_URL + "/Panel/GetTemperatures?panelId={}".format(self._panel_id)
            )
            if response is not None:
                self._tempdata = await response.json()
                if (
                    self._tempdata is not None
                    and self._tempdata != []
                    and self._sector_temp == True
                ):
                    self._tempstatus = {
                        temperature["SerialNo"]: temperature["Temprature"]
                        for temperature in self._tempdata
                    }
                _LOGGER.debug("self._tempdata = %s", self._tempdata)

        if self._locks != [] and self._sector_lock == True:
            response = await self._request(
                API_URL + "/Panel/GetLockStatus?panelId={}".format(self._panel_id)
            )
            if response is not None:
                self._lockdata = await response.json()
                if (
                    self._lockdata is not None
                    and self._lockdata != []
                    and self._sector_lock == True
                ):
                    self._lockstatus = {
                        lock["Serial"]: lock["Status"] for lock in self._lockdata
                    }
                _LOGGER.debug("self._lockdata = %s", self._lockdata)

        response = await self._request(
            API_URL + "/Panel/GetLogs?panelId={}".format(self._panel_id)
        )
        if response is not None:
            json_data = await response.json()
            for users in json_data:
                if users["User"] != "" and "arm" in users["EventType"]:
                    self._changed_by = users["User"]
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
            "API-Version": "6",
            "Platform": "iOS",
            "User-Agent": "  SectorAlarm/387 CFNetwork/1206 Darwin/20.1.0",
            "Version": "2.0.27",
            "Connection": "keep-alive",
            "Content-Type": "application/json",
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

        except aiohttp.ContentTypeError as e:
            _LOGGER.error("ContentTypeError connecting to Sector: %s ", e)

        except asyncio.TimeoutError:
            _LOGGER.error("Timed out when connecting to Sector")

        except asyncio.CancelledError:
            _LOGGER.error("Task was cancelled")

        return None

    async def _login(self):
        """ Login to retrieve access token """
        try:
            with async_timeout.timeout(self._timeout):
                response = await self.websession.post(
                    f"{API_URL}/Login/Login",
                    headers={
                        "API-Version": "6",
                        "Platform": "iOS",
                        "User-Agent": "  SectorAlarm/387 CFNetwork/1206 Darwin/20.1.0",
                        "Version": "2.0.27",
                        "Connection": "keep-alive",
                        "Content-Type": "application/json",
                    },
                    json={
                        "UserId": self._userid,
                        "Password": self._password,
                    },
                )

                if response.status == 401:
                    self._access_token = None
                    return None

                if response.status == 200 or response.status == 204:
                    token_data = await response.json()
                    self._access_token = token_data["AuthorizationToken"]
                    return self._access_token

        except aiohttp.ClientConnectorError as e:
            _LOGGER.error("ClientError connecting to Sector: %s ", e, exc_info=True)

        except aiohttp.ContentTypeError as c:
            _LOGGER.error("ContentTypeError connecting to Sector: %s ", c)

        except asyncio.TimeoutError:
            _LOGGER.error("Timed out when connecting to Sector")

        except asyncio.CancelledError:
            _LOGGER.error("Task was cancelled")

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
        return self._panel["PanelId"]

    @property
    def alarm_displayname(self):
        return self._panel["PanelDisplayName"]

    @property
    def alarm_isonline(self):
        return self._panel["IsOnline"]


class UnauthorizedError(HomeAssistantError):
    """Exception to indicate an error in authorization."""


class CannotConnectError(HomeAssistantError):
    """Exception to indicate an error in client connection."""


class OperationError(HomeAssistantError):
    """Exception to indicate an error in operation."""
