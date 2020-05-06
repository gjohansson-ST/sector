import logging

from homeassistant.components.alarm_control_panel import AlarmControlPanel

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

import custom_components.sector as sector

DEPENDENCIES = ["sector"]

_LOGGER = logging.getLogger(__name__)

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):

    sector_hub = hass.data[sector.DATA_SA]
    code = discovery_info[sector.CONF_CODE]
    code_format = discovery_info[sector.CONF_CODE_FORMAT]

    async_add_entities([SectorAlarmPanel(sector_hub, code, code_format)])


class SectorAlarmPanel(AlarmControlPanel):
    """
    Get the latest data from the Sector Alarm hub
    and arm/disarm alarm.
    """

    def __init__(self, hub, code, code_format):
        self._hub = hub
        self._code = code if code != "" else None
        self._code_format = code_format

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Sector Alarm {}".format(self._hub.alarm_id)

    @property
    def changed_by(self):
        """Return the last change triggered by."""
        return self._hub.alarm_changed_by

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return SUPPORT_ALARM_ARM_HOME | SUPPORT_ALARM_ARM_AWAY

    @property
    def state(self):
        """Return the state of the sensor."""
        state = self._hub.alarm_state

        if state == "armed":
            return STATE_ALARM_ARMED_AWAY

        elif state == "partialarmed":
            return STATE_ALARM_ARMED_HOME

        elif state == "disarmed":
            return STATE_ALARM_DISARMED

        elif state == "pending":
            return STATE_ALARM_PENDING

        return "unknown"

    @property
    def code_format(self):
        """Regex for code format or None if no code is required."""
        return self._code_format if self._code_format != "" else None

    def _validate_code(self, code):
        """Validate given code."""
        check = self._code is None or code == self._code
        if not check:
            _LOGGER.warning("Invalid code given")
        return check

    async def async_alarm_arm_home(self, code=None):
        """ Try to arm home. """
        if not self._validate_code(code):
            return

        _LOGGER.debug("Trying to arm home Sector Alarm")
        result = await self._hub.arm_home(code=code)
        if result:
            _LOGGER.debug("Armed home Sector Alarm")

    async def async_alarm_disarm(self, code=None):
        if not self._validate_code(code):
            return

        _LOGGER.debug("Trying to disarm Sector Alarm")
        result = await self._hub.disarm(code=code)
        if result:
            _LOGGER.debug("Disarmed Sector Alarm")

    async def async_alarm_arm_away(self, code=None):
        if not self._validate_code(code):
            return

        _LOGGER.debug("Trying to arm away Sector Alarm")
        result = await self._hub.arm_away(code=code)
        if result:
            _LOGGER.debug("Armed away Sector Alarm")

    async def async_update(self):
        update = self._hub.async_update()
        if update:
            await update
