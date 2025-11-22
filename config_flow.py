"""
Config Flow for PV Optimizer Integration - Multi-Config-Entry Architecture

This module handles the configuration flow for both service and device entries:
- Service Entry: Created on first install, contains global configuration
- Device Entries: Created for each device, contains device-specific configuration

Flow Logic:
----------
1. User clicks "Add Integration" → PV Optimizer
2. Check if service entry exists:
   - NO → Create service entry (global config)
   - YES → Create device entry (device config)
"""

import logging
from typing import Any, Dict, Optional

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    CONF_SURPLUS_SENSOR_ENTITY_ID,
    CONF_INVERT_SURPLUS_VALUE,
    CONF_SLIDING_WINDOW_SIZE,
    CONF_OPTIMIZATION_CYCLE_TIME,
    CONF_NAME,
    CONF_TYPE,
    CONF_PRIORITY,
    CONF_POWER,
    CONF_SWITCH_ENTITY_ID,
    CONF_NUMERIC_TARGETS,
    CONF_NUMERIC_ENTITY_ID,
    CONF_ACTIVATED_VALUE,
    CONF_DEACTIVATED_VALUE,
    CONF_MIN_ON_TIME,
    CONF_MIN_OFF_TIME,
    CONF_OPTIMIZATION_ENABLED,
    CONF_SIMULATION_ACTIVE,
    CONF_MEASURED_POWER_ENTITY_ID,
    CONF_POWER_THRESHOLD,
    CONF_INVERT_SWITCH,
    TYPE_SWITCH,
    TYPE_NUMERIC,
)

_LOGGER = logging.getLogger(__name__)


def _get_service_entry(hass):
    """Get the service config entry if it exists."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.data.get("entry_type") == "service":
            return entry
    return None


class PVOptimizerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for PV Optimizer."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize config flow."""
        self._device_base_config = None  # Stores device config before numeric targets step

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """
        Handle the initial step - route to service or device setup.
        
        Logic:
        ------
        - If no service entry exists → create service entry (first install)
        - If service entry exists → create device entry
        """
        service_entry = _get_service_entry(self.hass)
        
        if service_entry is None:
            # No service entry → first install
            return await self.async_step_service_config(user_input)
        else:
            # Service exists → add device
            return await self.async_step_device_type(user_input)

    async def async_step_service_config(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Configure the service entry (global configuration)."""
        if user_input is not None:
            # Create service entry
            return self.async_create_entry(
                title="PV Optimizer Service",
                data={
                    "entry_type": "service",
                    "global": user_input,
                },
            )

        # Schema for global configuration
        schema = vol.Schema({
            vol.Required(CONF_SURPLUS_SENSOR_ENTITY_ID): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="power"),
            ),
            vol.Optional(CONF_INVERT_SURPLUS_VALUE, default=False): selector.BooleanSelector(),
            vol.Required(CONF_SLIDING_WINDOW_SIZE, default=5): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=60, unit_of_measurement="minutes"),
            ),
            vol.Required(CONF_OPTIMIZATION_CYCLE_TIME, default=60): selector.NumberSelector(
                selector.NumberSelectorConfig(min=10, max=300, unit_of_measurement="seconds"),
            ),
        })

        return self.async_show_form(
            step_id="service_config",
            data_schema=schema,
            description_placeholders={
                "info": "Configure global settings for PV Optimizer. You can add devices after setup."
            }
        )

    async def async_step_device_type(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Let user choose device type (Switch or Numeric)."""
        if user_input is not None:
            # Store device type for use in next step
            self._device_type = user_input[CONF_TYPE]
            return await self.async_step_device_config()

        schema = vol.Schema({
            vol.Required(CONF_TYPE): selector.SelectSelector(
                selector.SelectSelectorConfig(options=[
                    selector.SelectOptionDict(value=TYPE_SWITCH, label="Switch Device (On/Off Control)"),
                    selector.SelectOptionDict(value=TYPE_NUMERIC, label="Numeric Device (Value Adjustment)"),
                ]),
            ),
        })

        return self.async_show_form(
            step_id="device_type",
            data_schema=schema,
            description_placeholders={
                "info": "Select the type of device you want to add."
            }
        )

    async def async_step_device_config(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Configure device based on type."""
        # Get device type from instance variable
        device_type = getattr(self, '_device_type', TYPE_SWITCH)
        
        if user_input is not None:
            device_config = {
                CONF_TYPE: device_type,
                **user_input,
            }
            
            if device_type == TYPE_SWITCH:
                # Create switch device entry
                return self.async_create_entry(
                    title=f"PVO {user_input[CONF_NAME]}",
                    data={
                        "entry_type": "device",
                        "device_config": device_config,
                    },
                )
            elif device_type == TYPE_NUMERIC:
                # Store base config and move to numeric targets step
                self._device_base_config = device_config
                return await self.async_step_numeric_targets()

        # Build schema based on device type
        base_schema = {
            vol.Required(CONF_NAME): selector.TextSelector(),
            vol.Required(CONF_PRIORITY, default=5): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=10, mode=selector.NumberSelectorMode.BOX),
            ),
            vol.Required(CONF_POWER, default=0): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, 
                    step=0.1, 
                    unit_of_measurement="W",
                    mode=selector.NumberSelectorMode.BOX
                ),
            ),
            vol.Optional(CONF_OPTIMIZATION_ENABLED, default=True): selector.BooleanSelector(),
            vol.Optional(CONF_SIMULATION_ACTIVE, default=False): selector.BooleanSelector(),
        }

        # Add type-specific fields
        if device_type == TYPE_SWITCH:
            base_schema[vol.Required(CONF_SWITCH_ENTITY_ID)] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="switch"),
            )
            base_schema[vol.Optional(CONF_INVERT_SWITCH, default=False)] = selector.BooleanSelector()

        # Common optional fields
        base_schema.update({
            vol.Optional(CONF_MEASURED_POWER_ENTITY_ID): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="power"),
            ),
            vol.Optional(CONF_POWER_THRESHOLD, default=100): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, 
                    step=0.1, 
                    unit_of_measurement="W",
                    mode=selector.NumberSelectorMode.BOX
                ),
            ),
            vol.Optional(CONF_MIN_ON_TIME, default=0): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, 
                    unit_of_measurement="minutes",
                    mode=selector.NumberSelectorMode.BOX
                ),
            ),
            vol.Optional(CONF_MIN_OFF_TIME, default=0): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, 
                    unit_of_measurement="minutes",
                    mode=selector.NumberSelectorMode.BOX
                ),
            ),
        })

        device_label = "Switch" if device_type == TYPE_SWITCH else "Numeric"
        return self.async_show_form(
            step_id="device_config",
            data_schema=vol.Schema(base_schema),
            description_placeholders={
                "info": f"Configure {device_label} device for PV Optimizer."
            }
        )

    async def async_step_numeric_targets(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Configure numeric targets for numeric devices."""
        if user_input is not None:
            # Add targets to device config
            device_config = self._device_base_config
            device_config[CONF_NUMERIC_TARGETS] = [
                {
                    CONF_NUMERIC_ENTITY_ID: user_input[CONF_NUMERIC_ENTITY_ID],
                    CONF_ACTIVATED_VALUE: user_input[CONF_ACTIVATED_VALUE],
                    CONF_DEACTIVATED_VALUE: user_input[CONF_DEACTIVATED_VALUE],
                }
            ]
            
            # Create numeric device entry
            return self.async_create_entry(
                title=f"PVO {device_config[CONF_NAME]}",
                data={
                    "entry_type": "device",
                    "device_config": device_config,
                },
            )

        schema = vol.Schema({
            vol.Required(CONF_NUMERIC_ENTITY_ID): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="number"),
            ),
            vol.Required(CONF_ACTIVATED_VALUE): selector.NumberSelector(
                selector.NumberSelectorConfig(mode=selector.NumberSelectorMode.BOX),
            ),
            vol.Required(CONF_DEACTIVATED_VALUE): selector.NumberSelector(
                selector.NumberSelectorConfig(mode=selector.NumberSelectorMode.BOX),
            ),
        })

        return self.async_show_form(
            step_id="numeric_targets",
            data_schema=schema,
            description_placeholders={
                "info": "Configure the numeric target for this device."
            }
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
        entry_type = self.config_entry.data.get("entry_type")
        
        if entry_type == "service":
            # Service entry → only global config options
            return await self.async_step_global_config(user_input)
        else:
            # Device entry → device config options
            return await self.async_step_device_config(user_input)

    async def async_step_global_config(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Handle global configuration options."""
        if user_input is not None:
            # Update global config
            new_data = dict(self.config_entry.data)
            new_data["global"] = user_input
            self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)
            return self.async_create_entry(title="", data={})

        # Get current global config
        global_config = self.config_entry.data.get("global", {})
        
        schema = vol.Schema({
            vol.Required(
                CONF_SURPLUS_SENSOR_ENTITY_ID,
                default=global_config.get(CONF_SURPLUS_SENSOR_ENTITY_ID)
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="power"),
            ),
            vol.Optional(
                CONF_INVERT_SURPLUS_VALUE,
                default=global_config.get(CONF_INVERT_SURPLUS_VALUE, False)
            ): selector.BooleanSelector(),
            vol.Required(
                CONF_SLIDING_WINDOW_SIZE,
                default=global_config.get(CONF_SLIDING_WINDOW_SIZE, 5)
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=60, unit_of_measurement="minutes"),
            ),
            vol.Required(
                CONF_OPTIMIZATION_CYCLE_TIME,
                default=global_config.get(CONF_OPTIMIZATION_CYCLE_TIME, 60)
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=10, max=300, unit_of_measurement="seconds"),
            ),
        })

        return self.async_show_form(
            step_id="global_config",
            data_schema=schema,
            description_placeholders={
                "info": "Configure global parameters for the PV Optimizer."
            }
        )

    async def async_step_device_config(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Handle device configuration options."""
        if user_input is not None:
            # Update device config
            new_data = dict(self.config_entry.data)
            device_config = dict(new_data.get("device_config", {}))
            # Update only the editable fields
            device_config.update({
                CONF_PRIORITY: user_input[CONF_PRIORITY],
                CONF_POWER: user_input[CONF_POWER],
                CONF_OPTIMIZATION_ENABLED: user_input.get(CONF_OPTIMIZATION_ENABLED, True),
                CONF_SIMULATION_ACTIVE: user_input.get(CONF_SIMULATION_ACTIVE, False),
                CONF_MIN_ON_TIME: user_input.get(CONF_MIN_ON_TIME, 0),
                CONF_MIN_OFF_TIME: user_input.get(CONF_MIN_OFF_TIME, 0),
            })
            new_data["device_config"] = device_config
            self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)
            return self.async_create_entry(title="", data={})

        # Get current device config
        device_config = self.config_entry.data.get("device_config", {})
        
        schema = vol.Schema({
            vol.Required(
                CONF_PRIORITY,
                default=device_config.get(CONF_PRIORITY, 5)
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=10, mode=selector.NumberSelectorMode.BOX),
            ),
            vol.Required(
                CONF_POWER,
                default=device_config.get(CONF_POWER, 0)
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, 
                    step=0.1, 
                    unit_of_measurement="W",
                    mode=selector.NumberSelectorMode.BOX
                ),
            ),
            vol.Optional(
                CONF_OPTIMIZATION_ENABLED,
                default=device_config.get(CONF_OPTIMIZATION_ENABLED, True)
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_SIMULATION_ACTIVE,
                default=device_config.get(CONF_SIMULATION_ACTIVE, False)
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_MIN_ON_TIME,
                default=device_config.get(CONF_MIN_ON_TIME, 0)
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, 
                    unit_of_measurement="minutes",
                    mode=selector.NumberSelectorMode.BOX
                ),
            ),
            vol.Optional(
                CONF_MIN_OFF_TIME,
                default=device_config.get(CONF_MIN_OFF_TIME, 0)
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, 
                    unit_of_measurement="minutes",
                    mode=selector.NumberSelectorMode.BOX
                ),
            ),
        })

        device_name = device_config.get(CONF_NAME, "Device")
        return self.async_show_form(
            step_id="device_config",
            data_schema=schema,
            description_placeholders={
                "info": f"Configure options for {device_name}."
            }
        )
