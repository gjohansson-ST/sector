"""Adds config flow for Sector integration."""
import logging

import voluptuous as vol
import aiohttp

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession

API_URL = "https://mypagesapi.sectoralarm.net/api"
DOMAIN = "sector"

_LOGGER = logging.getLogger(__name__)

CONF_USERID = "userid"
CONF_PASSWORD = "password"
CONF_CODE_FORMAT = "code_format"
CONF_CODE = "code"
CONF_TEMP = "temp"
CONF_LOCK = "lock"

DATA_SCHEMA = vol.Schema(
    {
    vol.Required(CONF_USERID): str,
    vol.Required(CONF_PASSWORD): str,
    vol.Optional(CONF_CODE, default=""): str,
    vol.Optional(CONF_CODE_FORMAT, default="^\\d{4,6}$"): str,
    vol.Optional(CONF_TEMP, default=True): bool,
    vol.Optional(CONF_LOCK, default=True): bool}
)

async def validate_input(hass: core.HomeAssistant, userid, password):
    """Validate the user input allows us to connect."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.data["account_id"] == account_id:
            raise AlreadyConfigured

    websession = async_get_clientsession(hass)
    login = await websession.post(
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
                    "UserId": userid,
                    "Password": password,
                },
            )

    if login.status != 200:
        _LOGGER.error("Failed to login to retrieve token: %d", response.status)
        raise CannotConnect

    response = await websession.get(
                f"{API_URL}/Login/Login",
                headers = {
                    "Authorization": login["AuthorizationToken"],
                    "API-Version":"6",
                    "Platform":"iOS",
                    "User-Agent":"SectorAlarm/356 CFNetwork/1152.2 Darwin/19.4.0",
                    "Version":"2.0.20",
                    "Connection":"keep-alive",
                    "Content-Type":"application/json",
                },
            )

    if response.status != 200:
        _LOGGER.error("Failed to login to retrieve token: %d", response.status)
        raise CannotConnect

    return response["Panel"]["PanelId"]

class SectorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sector integration."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            try:
                userid = user_input[CONF_USERID].replace(" ", "")
                password = user_input[CONF_PASSWORD].replace(" ", "")
                panel_id = await validate_input(self.hass, account_id, password)
                unique_id = "sa_"+panel_id
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=unique_id, data={"unique_id": unique_id},
                )
                _LOGGER.info("Login succesful. Config entry created.")

            except AlreadyConfigured:
                return self.async_abort(reason="already_configured")
            except CannotConnect:
                errors["base"] = "connection_error"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors,
        )

class SectorOptionsFlow(config_entries.OptionsFlow):
    """ Handle the Options Flow for Sector integration"""

    def __init__(self, config_entry):
        """Initialize Hue options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        errors = {}

        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_CODE,
                        default=self.config_entry.options.get(
                            CONF_CODE, ""
                        ),
                    ): str,
                    vol.Optional(
                        CONF_CODE_FORMAT,
                        default=self.config_entry.options.get(
                            CONF_CODE_FORMAT, ""
                        ),
                    ): str,
                    vol.Optional(
                        CONF_TEMP,
                        default=self.config_entry.options.get(
                            CONF_TEMP, True
                        ),
                    ): bool,
                    vol.Optional(
                        CONF_LOCK,
                        default=self.config_entry.options.get(
                            CONF_LOCK, True
                        ),
                    ): bool,
                }
            ),
        )

class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""

class AlreadyConfigured(exceptions.HomeAssistantError):
    """Error to indicate host is already configured."""
