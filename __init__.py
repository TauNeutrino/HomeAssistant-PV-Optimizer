"""The PV Optimizer integration."""
import logging
from typing import List

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform

from .const import DOMAIN, CONF_DEVICES
from .coordinator import PvoCoordinator

_LOGGER = logging.getLogger(__name__)

# Define the platforms that this integration will set up.
PLATFORMS: List[Platform] = [Platform.SWITCH]

async def async_update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update."""
    # This function is called when the user updates the options from the UI.
    _LOGGER.debug("Configuration options updated, reloading integration")
    # Reload the integration to apply the new options.
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up PV Optimizer from a config entry."""
    # This function is called when Home Assistant sets up the integration from a config entry.
    hass.data.setdefault(DOMAIN, {})

    coordinator = PvoCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh() # Initial data fetch.

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Add a listener for option updates.
    entry.async_on_unload(entry.add_update_listener(async_update_listener))

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # This function is called when Home Assistant unloads the integration.
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        # Clean up the data stored in hass.data.
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
