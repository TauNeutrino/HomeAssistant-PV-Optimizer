"""The PV Optimizer integration."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform, EVENT_HOMEASSISTANT_STARTED
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .coordinator import PVOptimizerCoordinator

_LOGGER = logging.getLogger(__name__)

# Define the platforms that this integration will set up.
PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.SWITCH, Platform.BINARY_SENSOR]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up PV Optimizer from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Create the coordinator.
    coordinator = PVOptimizerCoordinator(hass, entry.data)

    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Create a device for the PV Optimizer itself.
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "controller")},
        name="PV Optimizer Controller",
        manufacturer="PV Optimizer",
        model="Controller",
        entry_type=dr.DeviceEntryType.SERVICE,
    )

    # Forward the setup to the platforms.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Initialize devices and perform the first refresh.
    await coordinator.async_initialize_devices_and_refresh()

    # Add a listener for option updates.
    entry.async_on_unload(entry.add_update_listener(async_update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update."""
    _LOGGER.debug("Configuration options updated, reloading integration")
    await hass.config_entries.async_reload(entry.entry_id)
