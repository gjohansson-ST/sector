"""SECTOR ALARM INTEGRATION FOR HOME ASSISTANT."""
import asyncio
from datetime import datetime, timedelta
import logging

import aiohttp
from aiohttp import ClientResponse
import async_timeout
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_DISARMED,
    STATE_ALARM_PENDING,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    API_URL,
    CONF_CODE,
    CONF_CODE_FORMAT,
    CONF_LOCK,
    CONF_PASSWORD,
    CONF_TEMP,
    CONF_USERID,
    DOMAIN,
    MIN_SCAN_INTERVAL,
    PLATFORMS,
    UPDATE_INTERVAL,
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


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
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


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Sector Alarm as config entry."""
    hass.data.setdefault(DOMAIN, {})

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

    async def async_update_data() -> None:
        """Fetch data from api."""

        now = datetime.utcnow()
        hass.data[DOMAIN][entry.entry_id]["last_updated"] = now
        _LOGGER.debug("UPDATE_INTERVAL = %s", {entry.options[UPDATE_INTERVAL]})
        _LOGGER.debug(
            "last updated = %s", hass.data[DOMAIN][entry.entry_id]["last_updated"]
        )
        await api.fetch_info()

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

    await coordinator.async_refresh()
    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

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


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update when config_entry options update."""
    controller: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    controller.update_interval = timedelta(seconds=entry.options.get(UPDATE_INTERVAL))


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    for listener in hass.data[DOMAIN][entry.entry_id]["data_listener"]:
        listener()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    title = entry.title
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        _LOGGER.debug("Unloaded entry for %s", title)
        return unload_ok
    return False


class SectorAlarmHub(object):
    """Sector connectivity hub."""

    def __init__(
        self,
        sector_lock: bool,
        sector_temp: bool,
        userid: str,
        password: str,
        timesync: int,
        websession: aiohttp.ClientSession,
    ) -> None:
        """Initialize the sector hub."""
        self._lockstatus: dict = {}
        self._tempstatus: dict = {}
        self._switchstatus: dict = {}
        self._switchid: dict = {}
        self._lockdata: dict = {}
        self._tempdata: dict = {}
        self._switchdata: dict = {}
        self._alarmstatus: str = ""
        self._changed_by: str = ""
        self.websession = websession
        self._sector_temp = sector_temp
        self._sector_lock = sector_lock
        self._userid = userid
        self._password = password
        self._access_token: str = ""
        self._last_updated: datetime = datetime.utcnow() - timedelta(hours=2)
        self._last_updated_temp: datetime = datetime.utcnow() - timedelta(hours=2)
        self._timeout: int = 15
        self._panel: list = []
        self._temps: list = []
        self._locks: list = []
        self._switches: list = []
        self._panel_id: str = ""
        self._update_sensors: bool = True
        self._timesync = timesync

    async def get_thermometers(self) -> list:
        """Get temp sensors."""
        if self._temps:
            return (temp["SerialNo"] for temp in self._temps)

    async def get_name(self, serial: str, command: str) -> str:
        """Get name for sensors or locks."""
        if command == "temp":
            names = self._temps
        if command == "lock":
            names = self._locks
        if command == "switch":
            names = self._switches

        for name in names:
            if command == "temp":
                if name["SerialNo"] == serial:
                    return name["Label"]
            elif command == "lock":
                if name["Serial"] == serial:
                    return name["Label"]
            elif command == "switch":
                if name["SerialNo"] == serial:
                    return name["Label"]
        return

    async def get_autolock(self, serial: str) -> str:
        """Check if autolock is enabled."""
        for autolock in self._locks:
            if autolock["Serial"] == serial:
                return autolock["AutoLockEnabled"]

    async def get_locks(self) -> list:
        """Get locks."""
        if self._locks:
            return (lock["Serial"] for lock in self._locks)

    async def get_switches(self) -> list:
        """Get switches."""
        if self._switches:
            return (switch["SerialNo"] for switch in self._switches)

    async def get_panel(self) -> str:
        """Get Alarm panel."""
        if self._panel:
            return self._panel["PanelDisplayName"]

    async def triggerlock(self, lock: str, code: str, command: str) -> None:
        """Change status of lock."""

        message_json = {
            "LockSerial": lock,
            "PanelCode": code,
            "PanelId": self._panel_id,
            "Platform": "app",
        }

        if command == "unlock":
            await self._request(API_URL + "/Panel/Unlock", json_data=message_json)
        if command == "lock":
            await self._request(API_URL + "/Panel/Lock", json_data=message_json)
        await self.fetch_info(False)

    async def triggerswitch(self, identity: str, command: str) -> None:
        """Change status of switch."""

        message_json = {
            "PanelId": self._panel_id,
            "Platform": "app",
        }

        if command == "On":
            await self._request(
                f"{API_URL}/Panel/TurnOnSmartplug?switchId={identity}&panelId={self._panel_id}",
                json_data=message_json,
            )
        if command == "Off":
            await self._request(
                f"{API_URL}/Panel/TurnOffSmartplug?switchId={identity}&panelId={self._panel_id}",
                json_data=message_json,
            )
        await self.fetch_info(False)

    async def triggeralarm(self, command: str, code: str) -> None:
        """Change status of alarm."""

        message_json = {
            "PanelCode": code,
            "PanelId": self._panel_id,
            "Platform": "app",
        }

        if command == "full":
            await self._request(API_URL + "/Panel/Arm", json_data=message_json)
        if command == "partial":
            await self._request(API_URL + "/Panel/PartialArm", json_data=message_json)
        if command == "disarm":
            await self._request(API_URL + "/Panel/Disarm", json_data=message_json)
        await self.fetch_info(False)

    async def fetch_info(self, tempcheck: bool = True) -> None:
        """Fetch info from API."""
        if not self._panel:
            response = await self._request(API_URL + "/Panel/getFullSystem")
            if response is None:
                return None
            json_data = await response.json()
            if json_data is not None:
                self._panel = json_data["Panel"]
                self._panel_id = json_data["Panel"]["PanelId"]
                self._temps = json_data["Temperatures"]
                self._locks = json_data["Locks"]
                self._switches = json_data["Smartplugs"]

        now = datetime.utcnow()
        _LOGGER.debug("self._last_updated_temp = %s", self._last_updated_temp)
        _LOGGER.debug("self._timesync * 5 = %s", self._timesync * 5)
        _LOGGER.debug(
            "Evaluate should temp sensors update %s", now - self._last_updated_temp
        )
        if not tempcheck:
            self._update_sensors = False
        elif now - self._last_updated_temp < timedelta(seconds=self._timesync * 5):
            self._update_sensors = False
        else:
            self._update_sensors = True
            self._last_updated_temp = now

        response = await self._request(
            API_URL + "/Panel/GetPanelStatus?panelId={}".format(self._panel_id)
        )
        if response:
            json_data = await response.json()
            self._alarmstatus = json_data["Status"]
            _LOGGER.debug("self._alarmstatus = %s", self._alarmstatus)

        if self._temps and self._sector_temp and self._update_sensors:
            response = await self._request(
                API_URL + "/Panel/GetTemperatures?panelId={}".format(self._panel_id)
            )
            if response:
                self._tempdata = await response.json()
                if self._tempdata and self._tempdata and self._sector_temp:
                    self._tempstatus = {
                        temperature["SerialNo"]: temperature["Temprature"]
                        for temperature in self._tempdata
                    }
                _LOGGER.debug("self._tempdata = %s", self._tempdata)

        if self._locks and self._sector_lock:
            response = await self._request(
                API_URL + "/Panel/GetLockStatus?panelId={}".format(self._panel_id)
            )
            if response:
                self._lockdata = await response.json()
                if self._lockdata and self._lockdata and self._sector_lock:
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
                self._changed_by = "unknown"
            _LOGGER.debug("self._changed_by = %s", self._changed_by)

        response = await self._request(
            API_URL + "/Panel/GetSmartplugStatus?panelId={}".format(self._panel_id)
        )
        if response:
            self._switchdata = await response.json()
            if self._switchdata:
                self._switchstatus = {
                    switch["SerialNo"]: switch["Status"] for switch in self._switchdata
                }
                self._switchid = {
                    switch["SerialNo"]: switch["Id"] for switch in self._switchdata
                }
            _LOGGER.debug("self._switchdata = %s", self._switchdata)

    async def _request(
        self, url: str, json_data: dict = None, retry: int = 3
    ) -> ClientResponse:
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

            if response.status in (200, 204):
                _LOGGER.debug("Info retrieved successfully URL: %s", url)
                _LOGGER.debug("request status: %s", response.status)
                return response

            return None

        except aiohttp.ClientConnectorError as error:
            _LOGGER.error("ClientError connecting to Sector: %s ", error, exc_info=True)

        except aiohttp.ContentTypeError as error:
            _LOGGER.error("ContentTypeError connecting to Sector: %s ", error)

        except asyncio.TimeoutError:
            _LOGGER.error("Timed out when connecting to Sector")

        except asyncio.CancelledError:
            _LOGGER.error("Task was cancelled")

        return None

    async def _login(self) -> str:
        """Login to retrieve access token."""
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

                if response.status in (200, 204):
                    token_data = await response.json()
                    self._access_token = token_data["AuthorizationToken"]
                    return self._access_token

        except aiohttp.ClientConnectorError as error:
            _LOGGER.error("ClientError connecting to Sector: %s ", error, exc_info=True)

        except aiohttp.ContentTypeError as error:
            _LOGGER.error("ContentTypeError connecting to Sector: %s ", error)

        except asyncio.TimeoutError:
            _LOGGER.error("Timed out when connecting to Sector")

        except asyncio.CancelledError:
            _LOGGER.error("Task was cancelled")

        return None

    @property
    def alarm_state(self) -> str:
        """Check state of alarm."""
        if self._alarmstatus == 3:
            return STATE_ALARM_ARMED_AWAY
        if self._alarmstatus == 2:
            return STATE_ALARM_ARMED_HOME
        if self._alarmstatus == 1:
            return STATE_ALARM_DISARMED
        return STATE_ALARM_PENDING

    @property
    def alarm_changed_by(self) -> str:
        """Alarm changed by."""
        return self._changed_by

    @property
    def temp_state(self) -> dict:
        """State of temp."""
        return self._tempstatus

    @property
    def lock_state(self) -> dict:
        """State of locks."""
        return self._lockstatus

    @property
    def switch_state(self) -> dict:
        """State of switch."""
        return self._switchstatus

    @property
    def switch_id(self) -> dict:
        """Id of Switch"""
        return self._switchid

    @property
    def alarm_id(self) -> str:
        """Id for Alarm panel."""
        return self._panel["PanelId"]

    @property
    def alarm_displayname(self) -> str:
        """Displayname of alarm panel."""
        return self._panel["PanelDisplayName"]

    @property
    def alarm_isonline(self) -> str:
        """Check alarm online."""
        return self._panel["IsOnline"]


class UnauthorizedError(HomeAssistantError):
    """Exception to indicate an error in authorization."""


class CannotConnectError(HomeAssistantError):
    """Exception to indicate an error in client connection."""


class OperationError(HomeAssistantError):
    """Exception to indicate an error in operation."""
