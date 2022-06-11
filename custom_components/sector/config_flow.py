"""Adds config flow for Sector integration."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from aiohttp.client_exceptions import ContentTypeError
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_CODE, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .const import API_URL, CONF_CODE_FORMAT, CONF_TEMP, DOMAIN, LOGGER, UPDATE_INTERVAL

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_CODE): cv.string,
        vol.Optional(CONF_CODE_FORMAT, default=6): cv.positive_int,
        vol.Optional(CONF_TEMP, default=False): cv.boolean,
    }
)
DATA_SCHEMA_AUTH = vol.Schema(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }
)


async def validate_input(
    hass: core.HomeAssistant, username: str, password: str
) -> None:
    """Validate the user input allows us to connect."""
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
            "UserId": username,
            "Password": password,
        },
    )
    if login.status == 401:
        text = await login.text()
        LOGGER.error("Auth failure %s, status %s", text, login.status)
        raise AuthenticationError

    try:
        token_data = await login.json()
    except ContentTypeError as error:
        text = await login.text()
        LOGGER.error("ContentTypeError %s, status %s", text, login.status)
        raise CannotConnect from error
    if not token_data:
        LOGGER.error("Failed to login to retrieve token: %d", login.status)
        raise CannotConnect

    access_token = token_data["AuthorizationToken"]

    try:
        response = await websession.get(
            f"{API_URL}/account/GetPanelList",
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
    except ContentTypeError as error:
        text = await login.text()
        LOGGER.error("ContentTypeError %s, status %s", text, response.status)
        raise CannotConnect from error

    if response.status not in (200, 204) or panel_data is None:
        LOGGER.error("Failed to login to retrieve Panel ID: %d", response.status)
        raise CannotConnect


class SectorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sector integration."""

    VERSION = 3

    entry: config_entries.ConfigEntry | None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> SectorOptionFlow:
        """Get the options flow for this handler."""
        return SectorOptionFlow(config_entry)

    async def async_step_reauth(self, data: Mapping[str, Any]) -> FlowResult:
        """Handle re-authentication."""

        self.entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm re-authentication with Sensibo."""
        errors: dict[str, str] = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]
            try:
                await validate_input(self.hass, username, password)
            except CannotConnect:
                errors = {"base": "connection_error"}
            except AuthenticationError:
                errors = {"base": "auth_error"}
            else:
                assert self.entry is not None
                if username == self.entry.unique_id:
                    self.hass.config_entries.async_update_entry(
                        self.entry,
                        data={
                            **self.entry.data,
                            CONF_USERNAME: username,
                            CONF_PASSWORD: password,
                        },
                    )
                    await self.hass.config_entries.async_reload(self.entry.entry_id)
                    return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=DATA_SCHEMA_AUTH,
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]
            try:
                await validate_input(self.hass, username, password)
            except CannotConnect:
                errors = {"base": "connection_error"}
            except AuthenticationError:
                errors = {"base": "auth_error"}
            else:
                await self.async_set_unique_id(username)
                self._abort_if_unique_id_configured()

                LOGGER.info("Login succesful. Config entry created")
                return self.async_create_entry(
                    title=username,
                    data={
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                        CONF_TEMP: user_input[CONF_TEMP],
                    },
                    options={
                        UPDATE_INTERVAL: 60,
                        CONF_CODE: user_input.get(CONF_CODE),
                        CONF_CODE_FORMAT: user_input.get(CONF_CODE_FORMAT),
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )


class SectorOptionFlow(config_entries.OptionsFlow):
    """Handle a options config flow for Sector integration."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize config flow."""
        self.config_entry: config_entries.ConfigEntry = config_entry

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Manage the Sector options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        data_schema = vol.Schema(
            {
                vol.Required(
                    UPDATE_INTERVAL,
                    description={
                        "suggested_value": self.config_entry.options.get(
                            UPDATE_INTERVAL, 60
                        )
                    },
                ): cv.positive_int,
                vol.Optional(
                    CONF_CODE,
                    description={
                        "suggested_value": self.config_entry.options.get(CONF_CODE)
                    },
                ): cv.string,
                vol.Optional(
                    CONF_CODE_FORMAT,
                    description={
                        "suggested_value": self.config_entry.options.get(
                            CONF_CODE_FORMAT, 6
                        )
                    },
                ): cv.positive_int,
            }
        )

        return self.async_show_form(step_id="init", data_schema=data_schema)


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class AuthenticationError(exceptions.HomeAssistantError):
    """Error to indicate authentication failure."""
