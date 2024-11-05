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
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    NumberSelectorMode
)

from .const import CONF_CODE_FORMAT, CONF_PANEL_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)


class SectorAlarmConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sector Alarm."""

    VERSION = 1

    def __init__(self):
        self.email = None
        self.password = None
        self.code_format = None
        self.panel_ids = []

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            self.email = user_input[CONF_EMAIL]
            self.password = user_input[CONF_PASSWORD]
            self.code_format = user_input[CONF_CODE_FORMAT]
            _LOGGER.debug("Setting CONF_CODE_FORMAT: %s", self.code_format)

            # Import SectorAlarmAPI here to avoid blocking calls during module import
            from .client import AuthenticationError, SectorAlarmAPI

            api = SectorAlarmAPI(self.hass, self.email, self.password, None)
            try:
                await api.login()
                panel_list = await api.get_panel_list()

                # Since panel_list is a list, we directly assign it to self.panel_ids
                self.panel_ids = panel_list
                _LOGGER.error(f"panel_ids: {self.panel_ids}")
                if not self.panel_ids:
                    errors["base"] = "no_panels_found"
                elif len(self.panel_ids) == 1:
                    # Only one panel_id found, directly save it
                    return self.async_create_entry(
                        title=f"Sector Alarm {self.panel_ids[0]}",
                        data={
                            CONF_EMAIL: self.email,
                            CONF_PASSWORD: self.password,
                            CONF_PANEL_ID: self.panel_ids[0],
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
                vol.Optional(CONF_CODE_FORMAT, default=6): NumberSelector(
                    NumberSelectorConfig(min=0, max=6, step=1, mode=NumberSelectorMode.BOX)
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                data_schema, user_input or {}
            ),
            errors=errors,
        )

    async def async_step_select_panel(self, user_input=None):
        """Handle the panel selection step."""
        if user_input is not None:
            # User selected a panel_id; complete the setup
            return self.async_create_entry(
                title=f"Sector Alarm {user_input[CONF_PANEL_ID]}",
                data={
                    CONF_EMAIL: self.email,
                    CONF_PASSWORD: self.password,
                    CONF_CODE_FORMAT: self.code_format,
                    CONF_PANEL_ID: user_input[CONF_PANEL_ID],
                },
            )

        # Generate dropdown options based on retrieved panel IDs
        panel_options = [{"value": pid, "label": f"Panel {pid}"} for pid in self.panel_ids]
        data_schema = vol.Schema(
            {
                vol.Required(CONF_PANEL_ID): SelectSelector(
                    SelectSelectorConfig(
                        options=panel_options,
                        mode=SelectSelectorMode.DROPDOWN
                    )
                )
            }
        )

        return self.async_show_form(step_id="select_panel", data_schema=data_schema)
