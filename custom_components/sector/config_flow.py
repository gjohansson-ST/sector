"""Config flow for Sector Alarm integration."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlowWithReload
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .client import (
    ApiError,
    AsyncTokenProvider,
    AuthenticationError,
    LoginError,
    SectorAlarmAPI,
)
from .const import CONF_IGNORE_QUICK_ARM, CONF_PANEL_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)


def build_data_schema(default_email: str = "") -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_EMAIL, default=default_email): TextSelector(
                TextSelectorConfig(type=TextSelectorType.EMAIL, autocomplete="email")
            ),
            vol.Required(CONF_PASSWORD): TextSelector(
                TextSelectorConfig(
                    type=TextSelectorType.PASSWORD, autocomplete="current-password"
                )
            ),
        }
    )


def build_data_options_schema() -> vol.Schema:
    return vol.Schema(
        {
            vol.Optional(CONF_IGNORE_QUICK_ARM, default=False): bool,
        }
    )


class SectorAlarmConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sector Alarm."""

    VERSION = 1

    def __init__(self):
        self._email: str | None
        self._password: str | None
        self._ignore_quick_arm: bool | None
        self._panel_ids: dict[str, str]

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry):
        return SectorAlarmOptionsFlow()

    async def async_step_reauth(self, entry_data: Mapping[str, Any]):
        """Handle re-authentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None):
        """Confirm re-authentication."""
        entry = self._get_reauth_entry()
        errors = {}

        if user_input:
            self._email = user_input[CONF_EMAIL]
            self._password = user_input[CONF_PASSWORD]

            client_session = async_get_clientsession(self.hass)
            token_provider = AsyncTokenProvider(client_session, self._email, self._password)
            try:
                await token_provider.get_token()
            except LoginError:
                errors["base"] = "authentication_failed"
            except AuthenticationError:
                errors["base"] = "authentication_failed"
            except Exception as e:
                errors["base"] = "unknown_error"
                _LOGGER.exception("Unexpected exception during authentication: %s", e)
            else:
                self.async_update_reload_and_abort(entry, data_updates=user_input)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=build_data_schema(entry.data.get(CONF_EMAIL, "")),
            errors=errors,
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None):
        entry = self._get_reconfigure_entry()
        errors = {}

        if user_input is not None:
            self._email = user_input[CONF_EMAIL]
            self._password = user_input[CONF_PASSWORD]

            client_session = async_get_clientsession(self.hass)
            token_provider = AsyncTokenProvider(client_session, self._email, self._password)
            try:
                await token_provider.get_token()
            except LoginError:
                errors["base"] = "authentication_failed"
            except AuthenticationError:
                errors["base"] = "authentication_failed"
            except Exception as e:
                errors["base"] = "unknown_error"
                _LOGGER.exception("Unexpected exception during authentication: %s", e)
            else:
                self.hass.config_entries.async_update_entry(
                    entry,
                    data={
                        **entry.data,
                        CONF_EMAIL: user_input[CONF_EMAIL],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                )
                return self.async_abort(reason="reconfigure_successful")

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=build_data_schema(entry.data.get(CONF_EMAIL, "")),
            errors=errors,
        )

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            self._email = user_input[CONF_EMAIL]
            self._password = user_input[CONF_PASSWORD]
            self._ignore_quick_arm = bool(user_input[CONF_IGNORE_QUICK_ARM])

            client_session = async_get_clientsession(self.hass)
            token_provider = AsyncTokenProvider(
                client_session, self._email, self._password
            )
            api = SectorAlarmAPI(client_session, None, token_provider)
            try:
                # dict[str, str]
                response = await api.get_panel_list()
                if not response.is_ok():
                    raise ApiError(
                        f"Failed to retrieve panel information' (HTTP {response.response_code} - {response.response_data})"
                    )
                if not response.is_json():
                    raise ApiError(
                        f"Failed to retrieve panel information' (response data is not JSON '{response.response_data}')"
                    )

                panel_list: dict[str, str] = response.response_data
                self._panel_ids = panel_list
                _LOGGER.debug(f"panel_ids: {self._panel_ids}")
                if not self._panel_ids:
                    errors["base"] = "no_panels_found"
                elif len(self._panel_ids) == 1:
                    # Only one panel_id found, directly save it
                    return self.async_create_entry(
                        title=f"Sector Alarm {list(self._panel_ids.keys())[0]}",
                        data={
                            CONF_EMAIL: self._email,
                            CONF_PASSWORD: self._password,
                            CONF_PANEL_ID: list(self._panel_ids.keys())[0],
                        },
                        options={
                            CONF_IGNORE_QUICK_ARM: self._ignore_quick_arm,
                        },
                    )
                else:
                    # More than one panel_id, prompt user to select one
                    return await self.async_step_select_panel()

            except LoginError:
                errors["base"] = "authentication_failed"
            except AuthenticationError:
                errors["base"] = "authentication_failed"
            except Exception as e:
                errors["base"] = "unknown_error"
                _LOGGER.exception("Unexpected exception during authentication: %s", e)

        data_schema = build_data_schema()
        data_schema_options = build_data_options_schema()
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                data_schema.extend(data_schema_options.schema), user_input or {}
            ),
            errors=errors,
        )

    async def async_step_select_panel(self, user_input: dict[str, Any] | None = None):
        """Handle the panel selection step."""
        if user_input is not None:
            # User selected a panel_id; complete the setup
            return self.async_create_entry(
                title=f"Sector Alarm {user_input[CONF_PANEL_ID]}",
                data={
                    CONF_EMAIL: self._email,
                    CONF_PASSWORD: self._password,
                    CONF_PANEL_ID: user_input[CONF_PANEL_ID],
                },
                options={
                    CONF_IGNORE_QUICK_ARM: self._ignore_quick_arm,
                },
            )

        # Generate dropdown options based on retrieved panel IDs
        panel_options = [
            SelectOptionDict(value=pid, label=f"Panel {name}")
            for pid, name in self._panel_ids.items()
        ]
        data_schema = vol.Schema(
            {
                vol.Required(CONF_PANEL_ID): SelectSelector(
                    SelectSelectorConfig(
                        options=panel_options, mode=SelectSelectorMode.DROPDOWN
                    )
                )
            }
        )

        return self.async_show_form(step_id="select_panel", data_schema=data_schema)


class SectorAlarmOptionsFlow(OptionsFlowWithReload):
    """Handle Sector options."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Manage Sector options."""

        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                build_data_options_schema(),
                self.config_entry.options,
            ),
        )
