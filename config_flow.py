"""Config flow for PV Optimizer."""
import logging
from typing import Any, Dict, Optional, List

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import CONF_DEVICES, CONF_PV_SURPLUS_SENSOR, DOMAIN

_LOGGER = logging.getLogger(__name__)


def get_device_schema(device: Optional[Dict[str, Any]] = None) -> vol.Schema:
    """Return the schema for a single device, pre-filled if editing."""
    # If no device is provided, create an empty dict to avoid errors.
    device = device or {}
    return vol.Schema(
        {
            vol.Required("name", default=device.get("name", "")): str,
            vol.Required(
                "switch_entity_id", default=device.get("switch_entity_id", "")
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["switch", "light", "fan"]),
            ),
            # Power consumption of the device in Watts.
            vol.Required("power", default=device.get("power", 0)): vol.All(
                vol.Coerce(int), vol.Range(min=0)
            ),
            # Priority of the device (1-10), lower number means higher priority.
            vol.Required("priority", default=device.get("priority", 10)): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=10)
            ),
            # Minimum time the device should stay on after being turned on, in minutes.
            vol.Optional("min_on_time", default=device.get("min_on_time", 0)): vol.All(
                vol.Coerce(int), vol.Range(min=0)
            ),
            # Minimum time the device should stay off after being turned off, in minutes.
            vol.Optional("min_off_time", default=device.get("min_off_time", 0)): vol.All(
                vol.Coerce(int), vol.Range(min=0)
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
            return await self.async_step_device()

        schema = vol.Schema(
            {
                # Ask the user to select the sensor that measures PV surplus power.
                vol.Required(CONF_PV_SURPLUS_SENSOR): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor"),
                )
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_device(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Handle the device configuration step."""
        # This step is for adding the very first device during initial setup.
        if user_input is not None:
            options = {CONF_DEVICES: [user_input]}
            return self.async_create_entry(
                title="PV Optimizer", data=self.pvo_config, options=options
            )

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
        # Make a copy of the existing options to modify.
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
        devices = self.options.get(CONF_DEVICES, [])
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
            devices: List[Dict[str, Any]] = self.options.get(CONF_DEVICES, [])
            devices.append(user_input)
            self.options[CONF_DEVICES] = devices
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
        devices: List[Dict[str, Any]] = self.options.get(CONF_DEVICES, [])
        device_to_edit = devices[device_index]

        if user_input is not None:
            # Update the device configuration at the specified index.
            devices[device_index] = user_input
            self.options[CONF_DEVICES] = devices
            return self.async_create_entry(title="", data=self.options)

        # Show the edit form, pre-filled with the existing device's data.
        return self.async_show_form(
            step_id="edit_device",
            data_schema=get_device_schema(device_to_edit),
            description_placeholders={"device_name": device_to_edit.get("name")},
        )
