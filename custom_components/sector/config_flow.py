"""Config flow for Sector Alarm integration."""

from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import CONF_PANEL_CODE, CONF_PANEL_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)


class SectorAlarmConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sector Alarm."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            email = user_input[CONF_EMAIL]
            password = user_input[CONF_PASSWORD]
            panel_id = user_input[CONF_PANEL_ID]
            panel_code = user_input[CONF_PANEL_CODE]

            # Import SectorAlarmAPI here to avoid blocking calls during module import
            from .client import AuthenticationError, SectorAlarmAPI

            api = SectorAlarmAPI(self.hass, email, password, panel_id, panel_code)
            try:
                await api.login()
                await api.retrieve_all_data()
            except AuthenticationError:
                errors["base"] = "authentication_failed"
            except Exception as e:
                errors["base"] = "unknown_error"
                _LOGGER.exception("Unexpected exception during authentication: %s", e)
            else:
                return self.async_create_entry(
                    title=f"Sector Alarm {panel_id}",
                    data={
                        CONF_EMAIL: email,
                        CONF_PASSWORD: password,
                        CONF_PANEL_ID: panel_id,
                        CONF_PANEL_CODE: panel_code,
                    },
                )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_EMAIL): TextSelector(
                    TextSelectorConfig(
                        type=TextSelectorType.EMAIL, autocomplete="email"
                    )
                ),
                vol.Required(CONF_PASSWORD): TextSelector(
                    TextSelectorConfig(
                        type=TextSelectorType.PASSWORD, autocomplete="current-password"
                    )
                ),
                vol.Required(CONF_PANEL_ID): TextSelector(),
                vol.Required(CONF_PANEL_CODE): TextSelector(),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                data_schema, user_input or {}
            ),
            errors=errors,
        )
