"""
Config Flow for PV Optimizer Integration

UPDATED: Added simulation_active option for devices
- Backward compatible: defaults to False for existing devices
- Can be enabled independently from optimization_enabled
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
    CONF_SIMULATION_ACTIVE,  # NEW
    CONF_MEASURED_POWER_ENTITY_ID,
    CONF_POWER_THRESHOLD,
    CONF_INVERT_SWITCH,
    TYPE_SWITCH,
    TYPE_NUMERIC,
)

_LOGGER = logging.getLogger(__name__)


class PVOptimizerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for PV Optimizer (initial setup)."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Handle the initial setup step - configure global parameters only."""
        if user_input is not None:
            # Create the config entry with only global config
            return self.async_create_entry(
                title="PV Optimizer",
                data={
                    "global": user_input,
                    "devices": [],  # Start with empty devices list
                },
            )

        # Schema for global configuration
        schema = vol.Schema(
            {
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
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
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
        self._device_to_edit = None
        self._device_to_delete = None
        self._device_base_config = None  # Stores base config before numeric targets step

    async def async_step_init(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Manage the options - show menu."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["global_config", "manage_devices"],
        )

    async def async_step_global_config(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Handle global configuration."""
        if user_input is not None:
            # Update global config
            new_data = dict(self.config_entry.data)
            new_data["global"] = user_input
            self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)
            return self.async_create_entry(title="", data={})

        # Get current global config
        global_config = self.config_entry.data.get("global", {})
        
        schema = vol.Schema(
            {
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
            }
        )

        return self.async_show_form(
            step_id="global_config",
            data_schema=schema,
            description_placeholders={
                "info": "Configure global parameters for the PV Optimizer."
            }
        )

    async def async_step_manage_devices(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Show device management menu."""
        return self.async_show_menu(
            step_id="manage_devices",
            menu_options=["add_switch_device", "add_numeric_device"],
        )

    async def async_step_add_switch_device(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Add a new switch device."""
        errors = {}

        if user_input is not None:
            # Validate device name is unique
            devices = self.config_entry.data.get("devices", [])
            if any(d[CONF_NAME] == user_input[CONF_NAME] for d in devices):
                errors["base"] = "duplicate_name"
            else:
                # Add switch device
                device_config = {
                    CONF_NAME: user_input[CONF_NAME],
                    CONF_TYPE: TYPE_SWITCH,
                    CONF_PRIORITY: user_input[CONF_PRIORITY],
                    CONF_POWER: user_input[CONF_POWER],
                    CONF_SWITCH_ENTITY_ID: user_input[CONF_SWITCH_ENTITY_ID],
                    CONF_INVERT_SWITCH: user_input.get(CONF_INVERT_SWITCH, False),
                    CONF_OPTIMIZATION_ENABLED: user_input.get(CONF_OPTIMIZATION_ENABLED, True),
                    CONF_SIMULATION_ACTIVE: user_input.get(CONF_SIMULATION_ACTIVE, False),  # NEW
                    CONF_MEASURED_POWER_ENTITY_ID: user_input.get(CONF_MEASURED_POWER_ENTITY_ID),
                    CONF_POWER_THRESHOLD: user_input.get(CONF_POWER_THRESHOLD, 100),
                    CONF_MIN_ON_TIME: user_input.get(CONF_MIN_ON_TIME, 0),
                    CONF_MIN_OFF_TIME: user_input.get(CONF_MIN_OFF_TIME, 0),
                }
                
                # Save device
                new_data = dict(self.config_entry.data)
                if "devices" not in new_data:
                    new_data["devices"] = []
                # Create a new list to ensure it's mutable
                devices_list = list(new_data["devices"])
                devices_list.append(device_config)
                new_data["devices"] = devices_list
                
                _LOGGER.debug(f"Saving new device. Total devices: {len(new_data['devices'])}")
                _LOGGER.debug(f"New data to save: {new_data}")
                
                self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)
                
                # Reload to create entities
                await self.hass.config_entries.async_reload(self.config_entry.entry_id)
                
                return self.async_create_entry(title="", data={})

        # Schema for switch device
        schema = vol.Schema({
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
            vol.Required(CONF_SWITCH_ENTITY_ID): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="switch"),
            ),
            vol.Optional(CONF_INVERT_SWITCH, default=False): selector.BooleanSelector(),
            vol.Optional(CONF_OPTIMIZATION_ENABLED, default=True): selector.BooleanSelector(),
            vol.Optional(CONF_SIMULATION_ACTIVE, default=False): selector.BooleanSelector(),  # NEW
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

        return self.async_show_form(
            step_id="add_switch_device",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "info": "Configure a new switch-type controllable device."
            }
        )

    async def async_step_add_numeric_device(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Add a new numeric device."""
        errors = {}

        if user_input is not None:
            # Validate device name is unique
            devices = self.config_entry.data.get("devices", [])
            if any(d[CONF_NAME] == user_input[CONF_NAME] for d in devices):
                errors["base"] = "duplicate_name"
            else:
                # Store base config and move to numeric targets step
                self._device_base_config = {
                    CONF_NAME: user_input[CONF_NAME],
                    CONF_TYPE: TYPE_NUMERIC,
                    CONF_PRIORITY: user_input[CONF_PRIORITY],
                    CONF_POWER: user_input[CONF_POWER],
                    CONF_OPTIMIZATION_ENABLED: user_input.get(CONF_OPTIMIZATION_ENABLED, True),
                    CONF_SIMULATION_ACTIVE: user_input.get(CONF_SIMULATION_ACTIVE, False),  # NEW
                    CONF_MEASURED_POWER_ENTITY_ID: user_input.get(CONF_MEASURED_POWER_ENTITY_ID),
                    CONF_POWER_THRESHOLD: user_input.get(CONF_POWER_THRESHOLD, 100),
                    CONF_MIN_ON_TIME: user_input.get(CONF_MIN_ON_TIME, 0),
                    CONF_MIN_OFF_TIME: user_input.get(CONF_MIN_OFF_TIME, 0),
                }
                return await self.async_step_numeric_targets()

        # Schema for numeric device (without switch-specific fields)
        schema = vol.Schema({
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
            vol.Optional(CONF_SIMULATION_ACTIVE, default=False): selector.BooleanSelector(),  # NEW
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

        return self.async_show_form(
            step_id="add_numeric_device",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "info": "Configure a new numeric-type device. After clicking Next, you'll configure numeric targets."
            }
        )

    async def async_step_numeric_targets(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Configure numeric targets (max 5)."""
        if user_input is not None:
            # Collect non-empty targets
            targets = []
            for i in range(1, 6):
                entity = user_input.get(f"target_{i}_entity")
                if entity:  # Only add if entity is specified
                    targets.append({
                        CONF_NUMERIC_ENTITY_ID: entity,
                        CONF_ACTIVATED_VALUE: user_input.get(f"target_{i}_on", 0),
                        CONF_DEACTIVATED_VALUE: user_input.get(f"target_{i}_off", 0),
                    })
            
            # Add targets to device config
            self._device_base_config[CONF_NUMERIC_TARGETS] = targets
            
            # Save device
            new_data = dict(self.config_entry.data)
            if "devices" not in new_data:
                new_data["devices"] = []
            # Create a new list to ensure it's mutable
            devices_list = list(new_data["devices"])
            devices_list.append(self._device_base_config)
            new_data["devices"] = devices_list
            
            _LOGGER.debug(f"Saving new numeric device. Total devices: {len(new_data['devices'])}")
            
            self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)
            
            # Reload to create entities
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            
            self._device_base_config = None
            return self.async_create_entry(title="", data={})

        # Get existing targets if editing
        existing_targets = []
        if self._device_to_edit:
            devices = self.config_entry.data.get("devices", [])
            device = next((d for d in devices if d[CONF_NAME] == self._device_to_edit), None)
            if device:
                existing_targets = device.get(CONF_NUMERIC_TARGETS, [])

        # Build schema for 5 targets
        schema = {}
        for i in range(1, 6):
            target = existing_targets[i-1] if i-1 < len(existing_targets) else {}
            
            schema[vol.Optional(f"target_{i}_entity", default=target.get(CONF_NUMERIC_ENTITY_ID, ''))] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["number", "input_number"]),
            )
            schema[vol.Optional(f"target_{i}_on", default=target.get(CONF_ACTIVATED_VALUE, 0))] = selector.NumberSelector(
                selector.NumberSelectorConfig(mode=selector.NumberSelectorMode.BOX, step="any"),
            )
            schema[vol.Optional(f"target_{i}_off", default=target.get(CONF_DEACTIVATED_VALUE, 0))] = selector.NumberSelector(
                selector.NumberSelectorConfig(mode=selector.NumberSelectorMode.BOX, step="any"),
            )

        return self.async_show_form(
            step_id="numeric_targets",
            data_schema=vol.Schema(schema),
            description_placeholders={
                "info": "Configure up to 5 numeric targets. Leave entity empty to skip. For each target, specify the entity and values for activated (ON) and deactivated (OFF) states."
            }
        )


