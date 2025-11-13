"""Config flow for PV Optimizer."""
import logging
from typing import Any, Dict, Optional, List

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_DEVICES,
    CONF_PV_SURPLUS_SENSOR,
    DOMAIN,
    CONF_POLLING_FREQUENCY,
    CONF_SWITCH_ENTITY_ID,
    CONF_NOMINAL_POWER,
    CONF_PRIORITY,
    CONF_POWER_THRESHOLD,
    CONF_DURATION_ON,
    CONF_DURATION_OFF,
    CONF_INVERT_SWITCH,
    DEFAULT_POWER_THRESHOLD,
)

_LOGGER = logging.getLogger(__name__)


def get_device_schema(device: Optional[Dict[str, Any]] = None) -> vol.Schema:
    """Return the schema for a single device, pre-filled if editing."""
    # If no device is provided, create an empty dict to avoid errors.
    device = device or {}
    return vol.Schema(
        {
            vol.Required("name", default=device.get("name", "")): str,
            vol.Required(CONF_SWITCH_ENTITY_ID, default=device.get(CONF_SWITCH_ENTITY_ID, "")): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["switch", "light", "fan"]),
            ),
            # Power consumption of the device in Watts.
            vol.Required(CONF_NOMINAL_POWER, default=device.get(CONF_NOMINAL_POWER, 0)): vol.All(
                vol.Coerce(int), vol.Range(min=0)
            ),
            # Priority of the device (1-10), lower number means higher priority.
            vol.Required(CONF_PRIORITY, default=device.get(CONF_PRIORITY, 10)): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=10)
            ),
            vol.Optional(CONF_POWER_THRESHOLD, default=device.get(CONF_POWER_THRESHOLD, DEFAULT_POWER_THRESHOLD)): vol.All(
                vol.Coerce(int), vol.Range(min=0)
            ),
            # Minimum time the device should stay on after being turned on, in minutes.
            vol.Optional(CONF_DURATION_ON, default=device.get(CONF_DURATION_ON, 10)): vol.All(
                vol.Coerce(int), vol.Range(min=0)
            ),
            # Minimum time the device should stay off after being turned off, in minutes.
            vol.Optional(CONF_DURATION_OFF, default=device.get(CONF_DURATION_OFF, 10)): vol.All(
                vol.Coerce(int), vol.Range(min=0)
            ),
            vol.Optional(CONF_INVERT_SWITCH, default=device.get(CONF_INVERT_SWITCH, False)): bool,
            vol.Optional("power_sensor_entity_id", default=device.get("power_sensor_entity_id", "")): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor"),
            ),
        }
    )


@config_entries.HANDLERS.register(DOMAIN)
class PvoConfigFlow(config_entries.ConfigFlow):
    """Handle a config flow for PV Optimizer."""

    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self.pvo_config = {}

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Handle the initial step."""
        # Abort if an instance of the integration is already configured.
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            # Store the PV surplus sensor and move to the next step (device configuration).
            self.pvo_config[CONF_PV_SURPLUS_SENSOR] = user_input[CONF_PV_SURPLUS_SENSOR]
            self.pvo_config[CONF_POLLING_FREQUENCY] = user_input[CONF_POLLING_FREQUENCY]
            return await self.async_step_device()

        schema = vol.Schema(
            {
                # Ask the user to select the sensor that measures PV surplus power.
                vol.Required(CONF_PV_SURPLUS_SENSOR): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor"),
                ),
                vol.Required(CONF_POLLING_FREQUENCY, default=60): vol.All(
                    vol.Coerce(int), vol.Range(min=1)
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_device(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Handle the device configuration step."""
        # This step is for adding the very first device during initial setup.
        if user_input is not None:
            self.pvo_config[CONF_DEVICES] = [user_input]
            return self.async_create_entry(title="PV Optimizer", data=self.pvo_config)

        return self.async_show_form(
            step_id="device", data_schema=get_device_schema()
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return PvoOptionsFlowHandler(config_entry)


class PvoOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle an options flow for PV Optimizer."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry
        # Make a copy of the existing config to modify.
        self.options = dict(config_entry.options)
        self.device_index = None

    async def async_step_init(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            # Based on user's choice, either add a new device or prepare to edit an existing one.
            if user_input.get("action") == "add":
                return await self.async_step_add_device()
            self.device_index = user_input.get("device_index")
            return await self.async_step_edit_device()

        # Display the list of currently configured devices.
        devices = self.config_entry.data.get(CONF_DEVICES, [])
        device_list = [f"{i}: {d['name']}" for i, d in enumerate(devices)]

        schema = vol.Schema(
            {
                vol.Optional("action", default="edit"): vol.In({"add": "Add a new device", "edit": "Edit a device"}),
                vol.Optional("device_index"): vol.In(
                    {str(i): name for i, name in enumerate(device_list)}
                ),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)

    async def async_step_add_device(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Handle adding a new device."""
        if user_input is not None:
            devices: List[Dict[str, Any]] = self.config_entry.data.get(CONF_DEVICES, [])
            devices.append(user_input)
            self.hass.config_entries.async_update_entry(self.config_entry, data={**self.config_entry.data, CONF_DEVICES: devices})
            return self.async_create_entry(title="", data=self.options)

        return self.async_show_form(
            step_id="add_device", data_schema=get_device_schema()
        )

    async def async_step_edit_device(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Handle editing a device."""
        # This should not happen, but as a safeguard.
        if self.device_index is None:
            return self.async_abort(reason="no_device_selected")

        device_index = int(self.device_index)
        devices: List[Dict[str, Any]] = self.config_entry.data.get(CONF_DEVICES, [])
        device_to_edit = devices[device_index]

        if user_input is not None:
            # Update the device configuration at the specified index.
            devices[device_index] = user_input
            self.hass.config_entries.async_update_entry(self.config_entry, data={**self.config_entry.data, CONF_DEVICES: devices})
            return self.async_create_entry(title="", data=self.options)

        # Show the edit form, pre-filled with the existing device's data.
        return self.async_show_form(
            step_id="edit_device",
            data_schema=get_device_schema(device_to_edit),
            description_placeholders={"device_name": device_to_edit.get("name")},
        )
