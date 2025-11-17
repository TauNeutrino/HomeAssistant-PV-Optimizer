"""PV Optimizer integration for Home Assistant."""
import asyncio
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv

from .const import (
    DOMAIN,
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
from .coordinator import PVOptimizerCoordinator
from .mod_view import async_setup_panel

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "switch", "number"]

# Service schemas
SERVICE_ADD_DEVICE_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_PRIORITY): vol.All(vol.Coerce(int), vol.Range(min=1, max=10)),
    vol.Required(CONF_POWER): vol.Coerce(float),
    vol.Required(CONF_TYPE): vol.In([TYPE_SWITCH, TYPE_NUMERIC]),
    vol.Optional(CONF_SWITCH_ENTITY_ID): cv.entity_id,
    vol.Optional(CONF_NUMERIC_TARGETS): vol.All(cv.ensure_list, [vol.Schema({
        vol.Required(CONF_NUMERIC_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_ACTIVATED_VALUE): vol.Coerce(float),
        vol.Required(CONF_DEACTIVATED_VALUE): vol.Coerce(float),
    })]),
    vol.Optional(CONF_MIN_ON_TIME): vol.Coerce(int),
    vol.Optional(CONF_MIN_OFF_TIME): vol.Coerce(int),
    vol.Optional(CONF_OPTIMIZATION_ENABLED, default=True): cv.boolean,
    vol.Optional(CONF_MEASURED_POWER_ENTITY_ID): cv.entity_id,
    vol.Optional(CONF_POWER_THRESHOLD): vol.Coerce(float),
    vol.Optional(CONF_INVERT_SWITCH, default=False): cv.boolean,
})

SERVICE_REMOVE_DEVICE_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME): cv.string,
})


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up the PV Optimizer integration."""
    # Register frontend panel using browser_mod-style approach
    await async_setup_panel(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up PV Optimizer from a config entry."""
    # Initialize the coordinator for handling optimization cycles
    coordinator = PVOptimizerCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    # Store the coordinator in hass.data for access by platforms
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    # Forward setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register update listener for config changes
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    # Register services
    async def handle_add_device(call: ServiceCall) -> None:
        """Handle add device service call."""
        device_config = dict(call.data)
        
        # Validate device type requirements
        if device_config[CONF_TYPE] == TYPE_SWITCH and CONF_SWITCH_ENTITY_ID not in device_config:
            _LOGGER.error("Switch type device requires switch_entity_id")
            return
        
        if device_config[CONF_TYPE] == TYPE_NUMERIC and CONF_NUMERIC_TARGETS not in device_config:
            _LOGGER.error("Numeric type device requires numeric_targets")
            return
        
        # Check if device name already exists
        for device in coordinator.devices:
            if device[CONF_NAME] == device_config[CONF_NAME]:
                _LOGGER.error(f"Device with name '{device_config[CONF_NAME]}' already exists")
                return
        
        # Add device to coordinator
        coordinator.devices.append(device_config)
        
        # Update config entry
        config_data = dict(entry.data)
        config_data["devices"] = coordinator.devices
        hass.config_entries.async_update_entry(entry, data=config_data)
        
        _LOGGER.info(f"Added device: {device_config[CONF_NAME]}")
        
        # Reload entry to create new entities
        await async_reload_entry(hass, entry)

    async def handle_remove_device(call: ServiceCall) -> None:
        """Handle remove device service call."""
        device_name = call.data[CONF_NAME]
        
        # Find and remove device
        initial_count = len(coordinator.devices)
        coordinator.devices = [d for d in coordinator.devices if d[CONF_NAME] != device_name]
        
        if len(coordinator.devices) == initial_count:
            _LOGGER.error(f"Device '{device_name}' not found")
            return
        
        # Update config entry
        config_data = dict(entry.data)
        config_data["devices"] = coordinator.devices
        hass.config_entries.async_update_entry(entry, data=config_data)
        
        _LOGGER.info(f"Removed device: {device_name}")
        
        # Reload entry to remove entities
        await async_reload_entry(hass, entry)

    hass.services.async_register(
        DOMAIN,
        "add_device",
        handle_add_device,
        schema=SERVICE_ADD_DEVICE_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        "remove_device",
        handle_remove_device,
        schema=SERVICE_REMOVE_DEVICE_SCHEMA,
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        # Remove coordinator from hass.data
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
