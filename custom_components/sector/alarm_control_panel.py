"""Adds Alarm Panel for Sector integration."""
import logging
from datetime import timedelta
from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    FORMAT_NUMBER,
)
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    UpdateFailed,
)
from homeassistant.components.alarm_control_panel.const import (
    SUPPORT_ALARM_ARM_AWAY,
    SUPPORT_ALARM_ARM_HOME,
)
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_DISARMED,
    STATE_ALARM_PENDING,
)
from .const import (
    DOMAIN,
    CONF_CODE,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """ No setup from yaml """
    return True


async def async_setup_entry(hass, entry, async_add_entities):

    sector_hub = hass.data[DOMAIN][entry.entry_id]["api"]
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    code = entry.data[CONF_CODE]

    async_add_entities([SectorAlarmPanel(sector_hub, coordinator, code)])

    return True


class SectorAlarmAlarmDevice(AlarmControlPanelEntity):
    @property
    def device_info(self):
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self.name,
            "manufacturer": "Sector Alarm",
            "model": "Alarmpanel",
            "sw_version": "master",
            "via_device": (DOMAIN, f"sa_hub_{str(self._hub.alarm_id)}"),
        }


class SectorAlarmPanel(CoordinatorEntity, SectorAlarmAlarmDevice):
    def __init__(self, hub, coordinator, code):
        self._hub = hub
        super().__init__(coordinator)
        self._code = code if code != "" else None
        self._state = STATE_ALARM_PENDING
        self._changed_by = None
        self._displayname = self._hub.alarm_displayname
        self._isonline = self._hub.alarm_isonline

    @property
    def unique_id(self):
        """Return a unique ID to use for this sensor."""
        return f"sa_panel_{str(self._hub.alarm_id)}"

    @property
    def name(self):
        return f"Sector Alarmpanel {self._hub.alarm_id}"

    @property
    def available(self):
        return True

    @property
    def changed_by(self):
        return self._hub.alarm_changed_by

    @property
    def supported_features(self) -> int:
        return SUPPORT_ALARM_ARM_HOME | SUPPORT_ALARM_ARM_AWAY

    @property
    def code_arm_required(self):
        return False

    @property
    def state(self):
        return self._hub.alarm_state

    @property
    def code_format(self):
        """Return one or more digits/characters."""
        return FORMAT_NUMBER

    @property
    def device_state_attributes(self):
        return {"Display name": self._displayname, "Is Online": self._isonline}

    def _validate_code(self, code):
        check = self._code is None or code == self._code
        if not check:
            _LOGGER.warning("Invalid code given")
        return check

    async def async_alarm_arm_home(self, code=None):
        command = "partial"
        if code is not None:
            _LOGGER.debug("Trying to arm home with supplied code")
            if not self._validate_code(code):
                return

        _LOGGER.debug("Trying to arm home Sector Alarm")
        result = await self._hub.triggeralarm(command, code=code)
        if result:
            _LOGGER.debug("Armed home")
            self._state = STATE_ALARM_ARMED_HOME
            await self.coordinator.async_refresh()

    async def async_alarm_disarm(self, code=None):
        command = "disarm"
        if code is not None:
            _LOGGER.debug("Trying to disarm home with supplied code")
            if not self._validate_code(code):
                return

        _LOGGER.debug("Trying to disarm")
        result = await self._hub.triggeralarm(command, code=code)
        if result:
            _LOGGER.debug("Disarmed Sector Alarm")
            self._state = STATE_ALARM_DISARMED
            await self.coordinator.async_refresh()

    async def async_alarm_arm_away(self, code=None):
        command = "full"
        if code is not None:
            _LOGGER.debug("Trying to arm away with supplied code")
            if not self._validate_code(code):
                return

        _LOGGER.debug("Trying to arm away")
        result = await self._hub.triggeralarm(command, code=code)
        if result:
            _LOGGER.debug("Armed away Sector Alarm")
            self._state = STATE_ALARM_ARMED_AWAY
            await self.coordinator.async_refresh()
