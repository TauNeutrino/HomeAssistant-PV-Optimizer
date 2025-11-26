"""
PV Optimizer Integration - Main Entry Point

Multi-Config-Entry Architecture:
- Service Entry: Creates ServiceCoordinator, manages global config
- Device Entries: Create DeviceCoordinators, register with service

Flow:
1. Service entry setup → creates global sensors
2. Device entry setup → creates device entities, registers with service coordinator
"""

import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .coordinators import ServiceCoordinator,  DeviceCoordinator
from .panel import async_setup_panel
from .connection import async_setup_connection

_LOGGER = logging.getLogger(__name__)

# Configuration schema - PV Optimizer uses config flow exclusively
CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """
    Set up the PV Optimizer component (global initialization).
    
    Called once when Home Assistant loads the integration.
    Sets up shared resources (panel, WebSocket API).
    """
    # Initialize domain data storage
    hass.data.setdefault(DOMAIN, {})
    
    # Register sidebar panel
    await async_setup_panel(hass)
    
    # Register WebSocket API handlers
    await async_setup_connection(hass)
    
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """
    Set up PV Optimizer from a config entry.
    
    Routes to service or device setup based on entry_type.
    """
    entry_type = entry.data.get("entry_type")
    
    _LOGGER.debug(f"Setting up entry: {entry.title} (type={entry_type})")
    
    if entry_type == "service":
        return await _async_setup_service_entry(hass, entry)
    else:
        return await _async_setup_device_entry(hass, entry)


async def _async_setup_service_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """
    Set up service entry - creates ServiceCoordinator.
    
    The service coordinator:
    - Manages global configuration
    - Orchestrates optimization across all devices
    - Provides global sensors (power budget, surplus)
    """
    _LOGGER.info("Setting up PV Optimizer Service")
    
    # Create service coordinator
    coordinator = ServiceCoordinator(hass, entry)
    
    # Store in hass.data with special "service" key
    hass.data[DOMAIN]["service"] = coordinator
    hass.data[DOMAIN][entry.entry_id] = coordinator
    
    # Setup sensor platform for global sensors
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    
    # Create service device in device registry
    device_reg = dr.async_get(hass)
    device_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "service")},
        name="PV Optimizer",
        manufacturer="PV Optimizer",
        model="Service",
        entry_type=dr.DeviceEntryType.SERVICE,
    )
    
    # Initial refresh
    await coordinator.async_refresh()
    
    # Register update listener
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    
    _LOGGER.info("PV Optimizer Service setup complete")
    return True


async def _async_setup_device_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """
    Set up device entry - creates DeviceCoordinator.
    
    The device coordinator:
    - Manages individual device state
    - Provides device entities (switches, numbers, sensors)
    - Registers with service coordinator for optimization
    """
    device_config = entry.data.get("device_config", {})
    device_name = device_config.get("name", "Unknown")
    
    _LOGGER.info(f"Setting up PV Optimizer Device: {device_name}")
    
    # Create device coordinator
    coordinator = DeviceCoordinator(hass, entry)
    
    # Store coordinator
    hass.data[DOMAIN][entry.entry_id] = coordinator
    
    # Register with service coordinator
    # Note: Service entry may not be set up yet due to parallel setup
    service_coordinator = hass.data[DOMAIN].get("service")
    if service_coordinator:
        service_coordinator.register_device_coordinator(coordinator)
        _LOGGER.info(f"Registered device coordinator: {device_name}")
    else:
        # Service coordinator not ready yet - schedule delayed registration
        _LOGGER.warning(f"Service coordinator not found when setting up device: {device_name}, will retry")
        
        async def _delayed_registration():
            """Retry registration after service coordinator is ready."""
            import asyncio
            for attempt in range(10):  # Try for up to 5 seconds
                await asyncio.sleep(0.5)
                service_coordinator = hass.data[DOMAIN].get("service")
                if service_coordinator:
                    service_coordinator.register_device_coordinator(coordinator)
                    _LOGGER.info(f"Registered device coordinator (delayed): {device_name}")
                    return
            _LOGGER.error(f"Failed to register device coordinator after retries: {device_name}")
        
        # Schedule delayed registration
        hass.async_create_task(_delayed_registration())
    
    # Create device in device registry FIRST (before platforms)
    from .const import normalize_device_name
    
    device_type = device_config.get("type")
    normalized_name = normalize_device_name(device_name)
    device_reg = dr.async_get(hass)
    device_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, f"{entry.entry_id}_{normalized_name}")},
        name=f"PVO {device_name}",
        manufacturer="PV Optimizer",
        model=f"{device_type.capitalize()} Device" if device_type else "Unknown Device",
    )
    
    # Setup platforms based on device type (AFTER device exists)
    platforms = ["sensor", "switch", "binary_sensor", "button"]  # All devices have sensors, switches, binary_sensors, and buttons
    
    if device_type == "switch":
        platforms.append("number")  # Switch devices also have number controls
    elif device_type == "numeric":
        platforms.append("number")  # Numeric devices also have number controls
    
    await hass.config_entries.async_forward_entry_setups(entry, platforms)
    
    # Initial refresh
    await coordinator.async_refresh()
    
    # Don't register reload listener for device entries
    # Device config changes are handled in-memory by the coordinator
    # Only service entries need to reload on config changes
    
    _LOGGER.info(f"PV Optimizer Device setup complete: {device_name}")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """
    Unload a config entry.
    
    Handles cleanup for both service and device entries.
    """
    entry_type = entry.data.get("entry_type")
    
    _LOGGER.debug(f"Unloading entry: {entry.title} (type={entry_type})")
    
    if entry_type == "service":
        # Unload service entry
        unload_ok = await hass.config_entries.async_unload_platforms(entry, ["sensor"])
        
        if unload_ok:
            # Remove from hass.data
            hass.data[DOMAIN].pop("service", None)
            hass.data[DOMAIN].pop(entry.entry_id, None)
        
        return unload_ok
    
    else:
        # Unload device entry
        device_config = entry.data.get("device_config", {})
        device_type = device_config.get("type")
        device_name = device_config.get("name", "Unknown")
        
        platforms = ["sensor", "binary_sensor", "button"]
        if device_type == "switch":
            platforms.extend(["switch", "number"])
        elif device_type == "numeric":
            platforms.extend(["number"])
        
        unload_ok = await hass.config_entries.async_unload_platforms(entry, platforms)
        
        if unload_ok:
            # Unregister from service coordinator
            coordinator = hass.data[DOMAIN].pop(entry.entry_id, None)
            if coordinator:
                service_coordinator = hass.data[DOMAIN].get("service")
                if service_coordinator:
                    service_coordinator.unregister_device_coordinator(device_name)
        
        return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """
    Reload a config entry.
    
    Called when configuration changes.
    """
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
