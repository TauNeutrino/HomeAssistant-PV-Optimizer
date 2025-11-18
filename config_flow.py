"""Config flow for PV Optimizer integration."""
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
    CONF_SLIDING_WINDOW_SIZE,
    CONF_OPTIMIZATION_CYCLE_TIME,
    CONF_NAME,
    CONF_TYPE,
    CONF_PRIORITY,
    CONF_POWER,
    CONF_SWITCH_ENTITY_ID,
    CONF_NUMERIC_TARGETS,
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


class PVOptimizerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for PV Optimizer."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Handle the initial step - only global config."""
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
            menu_options=["device_list", "add_device"],
        )

    async def async_step_device_list(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Show list of devices with options to edit or delete."""
        devices = self.config_entry.data.get("devices", [])
        
        if not devices:
            return self.async_show_form(
                step_id="device_list",
                data_schema=vol.Schema({}),
                description_placeholders={
                    "info": "No devices configured. Use 'Add Device' to create one."
                }
            )

        if user_input is not None:
            # User selected a device action
            action = user_input.get("action")
            device_name = user_input.get("device")
            
            if action == "edit":
                self._device_to_edit = device_name
                return await self.async_step_edit_device()
            elif action == "delete":
                self._device_to_delete = device_name
                return await self.async_step_confirm_delete()
            
            return await self.async_step_init()

        # Build device selection
        device_options = [
            selector.SelectOptionDict(value=device[CONF_NAME], label=f"{device[CONF_NAME]} ({device[CONF_TYPE]})")
            for device in devices
        ]

        schema = vol.Schema({
            vol.Required("device"): selector.SelectSelector(
                selector.SelectSelectorConfig(options=device_options),
            ),
            vol.Required("action"): selector.SelectSelector(
                selector.SelectSelectorConfig(options=[
                    selector.SelectOptionDict(value="edit", label="Edit"),
                    selector.SelectOptionDict(value="delete", label="Delete"),
                ]),
            ),
        })

        return self.async_show_form(
            step_id="device_list",
            data_schema=schema,
            description_placeholders={
                "info": f"Select a device and action. Total devices: {len(devices)}"
            }
        )

    async def async_step_add_device(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Add a new device."""
        errors = {}

        if user_input is not None:
            # Validate device name is unique
            devices = self.config_entry.data.get("devices", [])
            if any(d[CONF_NAME] == user_input[CONF_NAME] for d in devices):
                errors["base"] = "duplicate_name"
            else:
                # Add device
                device_config = {
                    CONF_NAME: user_input[CONF_NAME],
                    CONF_TYPE: user_input[CONF_TYPE],
                    CONF_PRIORITY: user_input[CONF_PRIORITY],
                    CONF_POWER: user_input[CONF_POWER],
                    CONF_OPTIMIZATION_ENABLED: user_input.get(CONF_OPTIMIZATION_ENABLED, True),
                    CONF_MEASURED_POWER_ENTITY_ID: user_input.get(CONF_MEASURED_POWER_ENTITY_ID),
                    CONF_POWER_THRESHOLD: user_input.get(CONF_POWER_THRESHOLD, 100),
                    CONF_MIN_ON_TIME: user_input.get(CONF_MIN_ON_TIME, 0),
                    CONF_MIN_OFF_TIME: user_input.get(CONF_MIN_OFF_TIME, 0),
                }

                if user_input[CONF_TYPE] == TYPE_SWITCH:
                    device_config[CONF_SWITCH_ENTITY_ID] = user_input[CONF_SWITCH_ENTITY_ID]
                    device_config[CONF_INVERT_SWITCH] = user_input.get(CONF_INVERT_SWITCH, False)
                elif user_input[CONF_TYPE] == TYPE_NUMERIC:
                    # For now, numeric targets need to be configured via YAML
                    device_config[CONF_NUMERIC_TARGETS] = []

                new_data = dict(self.config_entry.data)
                new_data["devices"].append(device_config)
                self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)
                
                return self.async_create_entry(title="", data={})

        # Build dynamic schema based on device type
        device_type = user_input.get(CONF_TYPE, TYPE_SWITCH) if user_input else TYPE_SWITCH

        base_schema = {
            vol.Required(CONF_NAME): selector.TextSelector(),
            vol.Required(CONF_TYPE, default=device_type): selector.SelectSelector(
                selector.SelectSelectorConfig(options=[
                    selector.SelectOptionDict(value=TYPE_SWITCH, label="Switch (On/Off Control)"),
                    selector.SelectOptionDict(value=TYPE_NUMERIC, label="Numeric (Value Adjustment)"),
                ]),
            ),
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

        return self.async_show_form(
            step_id="add_device",
            data_schema=vol.Schema(base_schema),
            errors=errors,
            description_placeholders={
                "info": "Configure a new controllable device. For numeric devices, targets must be configured via YAML after initial creation."
            }
        )

    async def async_step_edit_device(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Edit an existing device."""
        devices = self.config_entry.data.get("devices", [])
        device_to_edit = next((d for d in devices if d[CONF_NAME] == self._device_to_edit), None)
        
        if not device_to_edit:
            return await self.async_step_init()

        if user_input is not None:
            # Update device
            device_config = {
                CONF_NAME: device_to_edit[CONF_NAME],  # Name cannot be changed
                CONF_TYPE: user_input[CONF_TYPE],
                CONF_PRIORITY: user_input[CONF_PRIORITY],
                CONF_POWER: user_input[CONF_POWER],
                CONF_OPTIMIZATION_ENABLED: user_input.get(CONF_OPTIMIZATION_ENABLED, True),
                CONF_MEASURED_POWER_ENTITY_ID: user_input.get(CONF_MEASURED_POWER_ENTITY_ID),
                CONF_POWER_THRESHOLD: user_input.get(CONF_POWER_THRESHOLD, 100),
                CONF_MIN_ON_TIME: user_input.get(CONF_MIN_ON_TIME, 0),
                CONF_MIN_OFF_TIME: user_input.get(CONF_MIN_OFF_TIME, 0),
            }

            if user_input[CONF_TYPE] == TYPE_SWITCH:
                device_config[CONF_SWITCH_ENTITY_ID] = user_input[CONF_SWITCH_ENTITY_ID]
                device_config[CONF_INVERT_SWITCH] = user_input.get(CONF_INVERT_SWITCH, False)
            elif user_input[CONF_TYPE] == TYPE_NUMERIC:
                # Preserve existing numeric targets
                device_config[CONF_NUMERIC_TARGETS] = device_to_edit.get(CONF_NUMERIC_TARGETS, [])

            # Replace device in list
            new_data = dict(self.config_entry.data)
            device_index = next(i for i, d in enumerate(new_data["devices"]) if d[CONF_NAME] == self._device_to_edit)
            new_data["devices"][device_index] = device_config
            self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)
            
            self._device_to_edit = None
            return self.async_create_entry(title="", data={})

        # Build schema with current values
        device_type = device_to_edit.get(CONF_TYPE, TYPE_SWITCH)

        base_schema = {
            vol.Required(CONF_TYPE, default=device_type): selector.SelectSelector(
                selector.SelectSelectorConfig(options=[
                    selector.SelectOptionDict(value=TYPE_SWITCH, label="Switch (On/Off Control)"),
                    selector.SelectOptionDict(value=TYPE_NUMERIC, label="Numeric (Value Adjustment)"),
                ]),
            ),
            vol.Required(CONF_PRIORITY, default=device_to_edit.get(CONF_PRIORITY, 5)): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=10, mode=selector.NumberSelectorMode.BOX),
            ),
            vol.Required(CONF_POWER, default=device_to_edit.get(CONF_POWER, 0)): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, 
                    step=0.1, 
                    unit_of_measurement="W",
                    mode=selector.NumberSelectorMode.BOX
                ),
            ),
            vol.Optional(
                CONF_OPTIMIZATION_ENABLED, 
                default=device_to_edit.get(CONF_OPTIMIZATION_ENABLED, True)
            ): selector.BooleanSelector(),
        }

        # Add type-specific fields
        if device_type == TYPE_SWITCH:
            base_schema[vol.Required(
                CONF_SWITCH_ENTITY_ID,
                default=device_to_edit.get(CONF_SWITCH_ENTITY_ID)
            )] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="switch"),
            )
            base_schema[vol.Optional(
                CONF_INVERT_SWITCH, 
                default=device_to_edit.get(CONF_INVERT_SWITCH, False)
            )] = selector.BooleanSelector()

        # Common optional fields
        base_schema.update({
            vol.Optional(
                CONF_MEASURED_POWER_ENTITY_ID,
                default=device_to_edit.get(CONF_MEASURED_POWER_ENTITY_ID)
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="power"),
            ),
            vol.Optional(
                CONF_POWER_THRESHOLD, 
                default=device_to_edit.get(CONF_POWER_THRESHOLD, 100)
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, 
                    step=0.1, 
                    unit_of_measurement="W",
                    mode=selector.NumberSelectorMode.BOX
                ),
            ),
            vol.Optional(
                CONF_MIN_ON_TIME, 
                default=device_to_edit.get(CONF_MIN_ON_TIME, 0)
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, 
                    unit_of_measurement="minutes",
                    mode=selector.NumberSelectorMode.BOX
                ),
            ),
            vol.Optional(
                CONF_MIN_OFF_TIME, 
                default=device_to_edit.get(CONF_MIN_OFF_TIME, 0)
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, 
                    unit_of_measurement="minutes",
                    mode=selector.NumberSelectorMode.BOX
                ),
            ),
        })

        return self.async_show_form(
            step_id="edit_device",
            data_schema=vol.Schema(base_schema),
            description_placeholders={
                "device_name": device_to_edit[CONF_NAME],
                "info": f"Editing device: {device_to_edit[CONF_NAME]}. Device name cannot be changed."
            }
        )

    async def async_step_confirm_delete(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Confirm device deletion."""
        if user_input is not None:
            if user_input.get("confirm"):
                # Delete device
                new_data = dict(self.config_entry.data)
                new_data["devices"] = [
                    d for d in new_data["devices"] 
                    if d[CONF_NAME] != self._device_to_delete
                ]
                self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)
                
            self._device_to_delete = None
            return self.async_create_entry(title="", data={})

        schema = vol.Schema({
            vol.Required("confirm", default=False): selector.BooleanSelector(),
        })

        return self.async_show_form(
            step_id="confirm_delete",
            data_schema=schema,
            description_placeholders={
                "device_name": self._device_to_delete,
                "warning": f"Are you sure you want to delete device '{self._device_to_delete}'? This action cannot be undone."
            }
        )
