"""Config flow for PV Optimizer integration."""
import logging
from typing import Any, Dict, Optional

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from homeassistant.helpers.selector import EntitySelector, NumberSelector

from .const import (
    DOMAIN,
    CONF_SURPLUS_SENSOR_ENTITY_ID,
    CONF_SLIDING_WINDOW_SIZE,
    CONF_OPTIMIZATION_CYCLE_TIME,
)

_LOGGER = logging.getLogger(__name__)

# Schema for global configuration step
GLOBAL_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SURPLUS_SENSOR_ENTITY_ID): EntitySelector(
            {"domain": "sensor", "device_class": "power"}
        ),
        vol.Required(CONF_SLIDING_WINDOW_SIZE, default=5): NumberSelector(
            {"min": 1, "max": 60, "unit_of_measurement": "minutes"}
        ),
        vol.Required(CONF_OPTIMIZATION_CYCLE_TIME, default=60): NumberSelector(
            {"min": 10, "max": 300, "unit_of_measurement": "seconds"}
        ),
    }
)


class PVOptimizerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for PV Optimizer."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Handle the initial step - only global config, no devices."""
        if user_input is not None:
            # Create the config entry with only global config
            # Devices will be managed via the frontend panel
            return self.async_create_entry(
                title="PV Optimizer",
                data={
                    "global": user_input,
                    "devices": [],  # Start with empty devices list
                },
            )

        return self.async_show_form(
            step_id="user",
            data_schema=GLOBAL_CONFIG_SCHEMA,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return PVOptimizerOptionsFlow(config_entry)


class PVOptimizerOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for PV Optimizer - only global settings."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Manage the options - update global config only."""
        if user_input is not None:
            # Update the config entry with new global settings
            # Devices remain unchanged (managed via frontend)
            new_data = dict(self.config_entry.data)
            new_data["global"] = user_input
            self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)
            return self.async_create_entry(title="", data={})

        # Build options schema from current global config
        global_config = self.config_entry.data.get("global", {})
        schema = vol.Schema(
            {
                vol.Required(CONF_SURPLUS_SENSOR_ENTITY_ID, default=global_config.get(CONF_SURPLUS_SENSOR_ENTITY_ID)): EntitySelector(
                    {"domain": "sensor", "device_class": "power"}
                ),
                vol.Required(CONF_SLIDING_WINDOW_SIZE, default=global_config.get(CONF_SLIDING_WINDOW_SIZE, 5)): NumberSelector(
                    {"min": 1, "max": 60, "unit_of_measurement": "minutes"}
                ),
                vol.Required(CONF_OPTIMIZATION_CYCLE_TIME, default=global_config.get(CONF_OPTIMIZATION_CYCLE_TIME, 60)): NumberSelector(
                    {"min": 10, "max": 300, "unit_of_measurement": "seconds"}
                ),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
        )
