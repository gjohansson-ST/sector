"""Adds config flow for Sector integration."""
import logging

import voluptuous as vol
import aiohttp

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession

API_URL = "https://mypagesapi.sectoralarm.net/api"
DOMAIN = "sector"
DEFAULT_NAME = "sector"
DATA_SA = "sector"

CONF_USERID = "userid"
CONF_PASSWORD = "password"
CONF_CODE_FORMAT = "code_format"
CONF_CODE = "code"
CONF_TEMP = "temp"
CONF_LOCK = "lock"

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
    vol.Required(CONF_USERID): str,
    vol.Required(CONF_PASSWORD): str,
    vol.Optional(CONF_CODE, default=""): str,
    vol.Optional(CONF_CODE_FORMAT, default="^\\d{4,6}$"): str,
    vol.Optional(CONF_TEMP, default=True): bool,
    vol.Optional(CONF_LOCK, default=True): bool
    }
)

async def validate_input(hass: core.HomeAssistant, userid, password):
    """Validate the user input allows us to connect."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.data["userid"] == userid:
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

    token_data = await login.json()
    if token_data is None or token_data == "":
        _LOGGER.error("Failed to login to retrieve token: %d", response.status)
        raise CannotConnect
    access_token = token_data['AuthorizationToken']

    response = await websession.get(
                f"{API_URL}/Panel/getFullSystem",
                headers = {
                    "Authorization": access_token,
                    "API-Version":"6",
                    "Platform":"iOS",
                    "User-Agent":"SectorAlarm/356 CFNetwork/1152.2 Darwin/19.4.0",
                    "Version":"2.0.20",
                    "Connection":"keep-alive",
                    "Content-Type":"application/json",
                },
            )

    panel_data = await response.json()
    if response.status != 200 or panel_data is None or panel_data == "":
        _LOGGER.error("Failed to login to retrieve Panel ID: %d", response.status)
        raise CannotConnect

    return panel_data["Panel"]["PanelId"]

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
                panel_id = await validate_input(self.hass, userid, password)
                unique_id = "sa_"+panel_id
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=unique_id, data={
                    CONF_USERID: userid,
                    CONF_PASSWORD: password,
                    CONF_CODE: user_input[CONF_CODE].replace(" ", ""),
                    CONF_CODE_FORMAT: user_input[CONF_CODE_FORMAT].replace(" ", ""),
                    CONF_TEMP: user_input[CONF_TEMP],
                    CONF_LOCK: user_input[CONF_LOCK],
                    },
                )
                _LOGGER.info("Login succesful. Config entry created.")

            except AlreadyConfigured:
                return self.async_abort(reason="already_configured")
            except CannotConnect:
                errors["base"] = "connection_error"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors,
        )

class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""

class AlreadyConfigured(exceptions.HomeAssistantError):
    """Error to indicate host is already configured."""
