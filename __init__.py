"""PV Optimizer integration for Home Assistant."""
import asyncio
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .coordinator import PVOptimizerCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "switch", "number"]


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up the PV Optimizer integration."""
    # Register the frontend static path
    hass.http.register_static_path(
        "/pv_optimizer",
        hass.config.path("custom_components/pv_optimizer/www"),
        cache_headers=False,
    )

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
