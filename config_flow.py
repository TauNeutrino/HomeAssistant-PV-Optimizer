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
    CONF_NAME,
    CONF_PRIORITY,
    CONF_POWER,
    CONF_TYPE,
    CONF_SWITCH_ENTITY_ID,
    CONF_NUMERIC_TARGETS,
    CONF_NUMERIC_ENTITY_ID,
    CONF_ACTIVATED_VALUE,
    CONF_DEACTIVATED_VALUE,
    CONF_MIN_ON_TIME,
    CONF_MIN_OFF_TIME,
    CONF_OPTIMIZATION_ENABLED,
    CONF_MEASURED_POWER_ENTITY_ID,
    CONF_POWER_THRESHOLD,
    CONF_INVERT_SWITCH,
    TYPE_SWITCH,
    TYPE_NUMERIC,
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

# Schema for adding a device
DEVICE_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): str,
        vol.Required(CONF_PRIORITY, default=5): vol.All(vol.Coerce(int), vol.Range(min=1, max=10)),
        vol.Required(CONF_POWER): vol.All(vol.Coerce(float), vol.Range(min=0)),
        vol.Required(CONF_TYPE): vol.In([TYPE_SWITCH, TYPE_NUMERIC]),
        vol.Optional(CONF_MIN_ON_TIME): vol.All(vol.Coerce(int), vol.Range(min=0)),
        vol.Optional(CONF_MIN_OFF_TIME): vol.All(vol.Coerce(int), vol.Range(min=0)),
        vol.Required(CONF_OPTIMIZATION_ENABLED, default=True): bool,
        vol.Optional(CONF_MEASURED_POWER_ENTITY_ID): EntitySelector({"domain": "sensor"}),
        vol.Optional(CONF_POWER_THRESHOLD, default=100): vol.All(vol.Coerce(float), vol.Range(min=0)),
        vol.Optional(CONF_INVERT_SWITCH, default=False): bool,
    }
)

# Additional schema for switch type
SWITCH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SWITCH_ENTITY_ID): EntitySelector({"domain": "switch"}),
    }
)

# Additional schema for numeric type
NUMERIC_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NUMERIC_TARGETS): vol.All(
            list,
            [
                vol.Schema(
                    {
                        vol.Required(CONF_NUMERIC_ENTITY_ID): EntitySelector(
                            {"domain": ["number", "input_number"]}
                        ),
                        vol.Required(CONF_ACTIVATED_VALUE): vol.Coerce(float),
                        vol.Required(CONF_DEACTIVATED_VALUE): vol.Coerce(float),
                    }
                )
            ],
        ),
    }
)


class PVOptimizerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for PV Optimizer."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize the config flow."""
        self.global_config = {}
        self.devices = []

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Handle the initial step."""
        if user_input is not None:
            self.global_config = user_input
            return await self.async_step_add_devices()

        return self.async_show_form(
            step_id="user",
            data_schema=GLOBAL_CONFIG_SCHEMA,
        )

    async def async_step_add_devices(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Ask if user wants to add devices."""
        if user_input is not None:
            if user_input.get("add_devices", False):
                return await self.async_step_device()
            else:
                # Create the config entry without devices
                return self.async_create_entry(
                    title="PV Optimizer",
                    data={
                        "global": self.global_config,
                        "devices": [],
                    },
                )

        return self.async_show_form(
            step_id="add_devices",
            data_schema=vol.Schema({
                vol.Optional("add_devices", default=False): bool,
            }),
        )

    async def async_step_device(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Handle device configuration step."""
        if user_input is not None:
            device_config = user_input.copy()

            # Handle type-specific fields
            if device_config[CONF_TYPE] == TYPE_SWITCH:
                # In a real implementation, you'd collect switch_entity_id here
                # For simplicity, assume it's part of user_input or prompt separately
                pass  # Placeholder
            elif device_config[CONF_TYPE] == TYPE_NUMERIC:
                # Similarly for numeric_targets
                pass  # Placeholder

            self.devices.append(device_config)

            # Ask if user wants to add another device
            return await self.async_step_add_another()

        # Show device config form
        schema = DEVICE_CONFIG_SCHEMA
        if self.devices:
            schema = schema.extend(
                {
                    vol.Optional("add_another", default=False): bool,
                }
            )

        return self.async_show_form(
            step_id="device",
            data_schema=schema,
        )

    async def async_step_add_another(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Ask if user wants to add another device."""
        if user_input is None or user_input.get("add_another", False):
            return await self.async_step_device()

        # Create the config entry
        return self.async_create_entry(
            title="PV Optimizer",
            data={
                "global": self.global_config,
                "devices": self.devices,
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return PVOptimizerOptionsFlow(config_entry)


class PVOptimizerOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for PV Optimizer."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # Build options schema from current config
        options = dict(self.config_entry.data)
        schema = vol.Schema(
            {
                vol.Required(CONF_SURPLUS_SENSOR_ENTITY_ID, default=options.get("global", {}).get(CONF_SURPLUS_SENSOR_ENTITY_ID)): EntitySelector(
                    {"domain": "sensor", "device_class": "power"}
                ),
                vol.Required(CONF_SLIDING_WINDOW_SIZE, default=options.get("global", {}).get(CONF_SLIDING_WINDOW_SIZE, 5)): NumberSelector(
                    {"min": 1, "max": 60, "unit_of_measurement": "minutes"}
                ),
                vol.Required(CONF_OPTIMIZATION_CYCLE_TIME, default=options.get("global", {}).get(CONF_OPTIMIZATION_CYCLE_TIME, 60)): NumberSelector(
                    {"min": 10, "max": 300, "unit_of_measurement": "seconds"}
                ),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
        )
