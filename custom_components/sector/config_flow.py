"""Adds config flow for Sector integration."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from aiohttp.client_exceptions import ContentTypeError
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import API_URL, CONF_CODE_FORMAT, CONF_TEMP, DOMAIN, LOGGER

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): TextSelector(
            TextSelectorConfig(type=TextSelectorType.EMAIL)
        ),
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
        vol.Optional(CONF_CODE_FORMAT, default=6): NumberSelector(
            NumberSelectorConfig(min=0, max=6, step=1, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(CONF_TEMP, default=False): BooleanSelector(),
    }
)
DATA_SCHEMA_AUTH = vol.Schema(
    {
        vol.Required(CONF_USERNAME): TextSelector(
            TextSelectorConfig(type=TextSelectorType.EMAIL)
        ),
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)


async def validate_input(
    hass: core.HomeAssistant, username: str, password: str
) -> None:
    """Validate the user input allows us to connect."""
    websession = async_get_clientsession(hass)
    login = await websession.post(
        f"{API_URL}/api/Login/Login",
        headers={
            "API-Version": "6",
            "Platform": "iOS",
            "User-Agent": "SectorAlarm/387 CFNetwork/1206 Darwin/20.1.0",
            "Version": "2.0.27",
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
            f"{API_URL}/api/account/GetPanelList",
            headers={
                "Authorization": access_token,
                "API-Version": "6",
                "Platform": "iOS",
                "User-Agent": "SectorAlarm/387 CFNetwork/1206 Darwin/20.1.0",
                "Version": "2.0.27",
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

    async def async_step_reauth(self, user_input: Mapping[str, Any]) -> FlowResult:
        """Handle re-authentication."""

        self.entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm re-authentication with Sector."""
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
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]
            code_format = user_input[CONF_CODE_FORMAT]
            try:
                await validate_input(self.hass, username, password)
            except CannotConnect:
                errors = {"base": "connection_error"}
            except AuthenticationError:
                errors = {"base": "auth_error"}
            else:
                await self.async_set_unique_id(username)
                self._abort_if_unique_id_configured()

                LOGGER.debug("Login successful. Config entry created")
                return self.async_create_entry(
                    title=username,
                    data={
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                        CONF_TEMP: user_input[CONF_TEMP],
                    },
                    options={
                        CONF_CODE_FORMAT: int(code_format),
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )


class SectorOptionFlow(config_entries.OptionsFlowWithConfigEntry):
    """Handle an options config flow for Sector integration."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the Sector options."""
        if user_input is not None:
            data = {**user_input, CONF_CODE_FORMAT: int(user_input[CONF_CODE_FORMAT])}
            return self.async_create_entry(data=data)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_CODE_FORMAT,
                        description={
                            "suggested_value": self.config_entry.options.get(
                                CONF_CODE_FORMAT, 6
                            )
                        },
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=0, max=6, step=1, mode=NumberSelectorMode.BOX
                        )
                    ),
                }
            ),
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class AuthenticationError(exceptions.HomeAssistantError):
    """Error to indicate authentication failure."""
