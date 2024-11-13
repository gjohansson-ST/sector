"""Config flow for Sector Alarm integration."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithConfigEntry,
)
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .client import AuthenticationError, SectorAlarmAPI
from .const import CONF_CODE_FORMAT, CONF_PANEL_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): TextSelector(
            TextSelectorConfig(type=TextSelectorType.EMAIL, autocomplete="email")
        ),
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD, autocomplete="current-password"
            )
        ),
    }
)
DATA_SCHEMA_OPTIONS = vol.Schema(
    {
        vol.Optional(CONF_CODE_FORMAT, default=6): NumberSelector(
            NumberSelectorConfig(min=0, max=6, step=1, mode=NumberSelectorMode.BOX)
        ),
    }
)


class SectorAlarmConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sector Alarm."""

    VERSION = 4

    def __init__(self):
        self.email: str | None
        self.password: str | None
        self.code_format: int | None
        self.panel_ids: dict[str, str]

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication with Sensibo."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm re-authentication with Sensibo."""
        errors: dict[str, str] = {}

        if user_input:
            reauth_entry = self._get_reauth_entry()
            email = user_input[CONF_EMAIL]
            password = user_input[CONF_PASSWORD]
            api = SectorAlarmAPI(self.hass, email, password, None)
            try:
                await api.login()
            except AuthenticationError:
                errors["base"] = "authentication_failed"
            except Exception as e:
                errors["base"] = "unknown_error"
                _LOGGER.exception("Unexpected exception during authentication: %s", e)
            else:
                self.async_update_reload_and_abort(
                    reauth_entry, data_updates=user_input
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self.email = user_input[CONF_EMAIL]
            self.password = user_input[CONF_PASSWORD]
            self.code_format = int(user_input[CONF_CODE_FORMAT])
            _LOGGER.debug("Setting CONF_CODE_FORMAT: %s", self.code_format)

            api = SectorAlarmAPI(self.hass, self.email, self.password, None)
            try:
                await api.login()
                panel_list = await api.get_panel_list()

                self.panel_ids = panel_list
                _LOGGER.debug(f"panel_ids: {self.panel_ids}")
                if not self.panel_ids:
                    errors["base"] = "no_panels_found"
                elif len(self.panel_ids) == 1:
                    # Only one panel_id found, directly save it
                    return self.async_create_entry(
                        title=f"Sector Alarm {list(self.panel_ids.keys())[0]}",
                        data={
                            CONF_EMAIL: self.email,
                            CONF_PASSWORD: self.password,
                            CONF_PANEL_ID: list(self.panel_ids.keys())[0],
                        },
                        options={
                            CONF_CODE_FORMAT: self.code_format,
                        },
                    )
                else:
                    # More than one panel_id, prompt user to select one
                    return await self.async_step_select_panel()

            except AuthenticationError:
                errors["base"] = "authentication_failed"
            except Exception as e:
                errors["base"] = "unknown_error"
                _LOGGER.exception("Unexpected exception during authentication: %s", e)

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                DATA_SCHEMA.extend(DATA_SCHEMA_OPTIONS.schema), user_input or {}
            ),
            errors=errors,
        )

    async def async_step_select_panel(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the panel selection step."""
        if user_input is not None:
            # User selected a panel_id; complete the setup
            return self.async_create_entry(
                title=f"Sector Alarm {user_input[CONF_PANEL_ID]}",
                data={
                    CONF_EMAIL: self.email,
                    CONF_PASSWORD: self.password,
                    CONF_PANEL_ID: user_input[CONF_PANEL_ID],
                },
                options={
                    CONF_CODE_FORMAT: self.code_format,
                },
            )

        # Generate dropdown options based on retrieved panel IDs
        panel_options = [
            SelectOptionDict(value=pid, label=f"Panel {name}")
            for pid, name in self.panel_ids.items()
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


class SectorAlarmOptionsFlow(OptionsFlowWithConfigEntry):
    """Handle Sector options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage Sector options."""

        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                DATA_SCHEMA_OPTIONS,
                self.config_entry.options,
            ),
        )
