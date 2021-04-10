"""Adds config flow for Sector integration."""
import logging

import voluptuous as vol
import aiohttp

import homeassistant.helpers.config_validation as cv
from homeassistant import config_entries, core, exceptions
from homeassistant.core import callback
from homeassistant.const import CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    DOMAIN,
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

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERID): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_CODE, default=""): cv.string,
        vol.Optional(CONF_CODE_FORMAT, default=6): cv.positive_int,
        vol.Optional(CONF_TEMP, default=True): cv.boolean,
        vol.Optional(CONF_LOCK, default=True): cv.boolean,
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
            "API-Version": "6",
            "Platform": "iOS",
            "User-Agent": "SectorAlarm/356 CFNetwork/1152.2 Darwin/19.4.0",
            "Version": "2.0.20",
            "Connection": "keep-alive",
            "Content-Type": "application/json",
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
    access_token = token_data["AuthorizationToken"]

    response = await websession.get(
        f"{API_URL}/Panel/getFullSystem",
        headers={
            "Authorization": access_token,
            "API-Version": "6",
            "Platform": "iOS",
            "User-Agent": "SectorAlarm/356 CFNetwork/1152.2 Darwin/19.4.0",
            "Version": "2.0.20",
            "Connection": "keep-alive",
            "Content-Type": "application/json",
        },
    )

    panel_data = await response.json()
    if response.status != 200 or panel_data is None or panel_data == "":
        _LOGGER.error("Failed to login to retrieve Panel ID: %d", response.status)
        raise CannotConnect

    return panel_data["Panel"]["PanelId"]


class SectorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sector integration."""

    VERSION = 2
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return SectorOptionFlow(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            userid = user_input[CONF_USERID].replace(" ", "")
            password = user_input[CONF_PASSWORD].replace(" ", "")
            try:
                panel_id = await validate_input(self.hass, userid, password)

            except AlreadyConfigured:
                return self.async_abort(reason="already_configured")
            except CannotConnect:
                return self.async_show_form(
                    step_id="user",
                    data_schema=DATA_SCHEMA,
                    errors={"base": "connection_error"},
                    description_placeholders={},
                )

            unique_id = "sa_" + panel_id
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=unique_id,
                data={
                    CONF_USERID: userid,
                    CONF_PASSWORD: password,
                    CONF_CODE: user_input[CONF_CODE].replace(" ", ""),
                    CONF_CODE_FORMAT: user_input[CONF_CODE_FORMAT],
                    CONF_TEMP: user_input[CONF_TEMP],
                    CONF_LOCK: user_input[CONF_LOCK],
                },
            )
            _LOGGER.info("Login succesful. Config entry created.")

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )


class SectorOptionFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the Sector options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        data_schema = vol.Schema(
            {
                vol.Required(
                    UPDATE_INTERVAL,
                    default=self.config_entry.options.get(UPDATE_INTERVAL, 60),
                ): vol.All(cv.positive_int, vol.Clamp(min=MIN_SCAN_INTERVAL)),
            }
        )

        return self.async_show_form(step_id="init", data_schema=data_schema)


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class AlreadyConfigured(exceptions.HomeAssistantError):
    """Error to indicate host is already configured."""
