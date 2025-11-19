"""
PV Optimizer Integration - Main Entry Point

This module serves as the main entry point for the PV Optimizer custom integration.
It handles the component lifecycle (setup, reload, unload) and coordinates the
initialization of all sub-components.

Architecture Overview:
---------------------
1. Panel Setup: Registers the sidebar panel for UI interaction
2. WebSocket API: Sets up real-time communication with the frontend
3. Coordinator: Initializes the optimization logic and scheduling
4. Platforms: Creates entities (sensors, switches, numbers) for monitoring and control
5. Device Registry: Registers devices in Home Assistant's device registry

Flow of Operations:
------------------
1. async_setup() - Called when integration is first loaded
   - Initializes global data storage
   - Sets up the sidebar panel
   - Registers WebSocket API handlers

2. async_setup_entry() - Called when a config entry is set up
   - Creates the coordinator (handles optimization cycles)
   - Forwards setup to entity platforms
   - Registers devices in device registry
   - Performs initial data refresh
   - Registers reload listener for config changes

3. async_unload_entry() - Called when unloading the integration
   - Unloads all platforms
   - Cleans up coordinator data

4. async_reload_entry() - Called when configuration changes
   - Unloads existing entry
   - Reloads with new configuration
"""

import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN
from .coordinator import PVOptimizerCoordinator
from .panel import async_setup_panel
from .connection import async_setup_connection
from .device_registry import async_setup_devices

_LOGGER = logging.getLogger(__name__)

# Configuration schema - PV Optimizer uses config flow exclusively, YAML not supported
CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

# Entity platforms that will be set up for this integration
# These create the monitoring and control entities in Home Assistant
PLATFORMS = ["sensor", "switch", "number"]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """
    Set up the PV Optimizer component (global initialization).
    
    This function is called once when Home Assistant loads the integration,
    regardless of how many config entries exist. It performs one-time setup
    that is shared across all instances.
    
    Functionality Achieved:
    ----------------------
    1. Initializes the global data store for all PV Optimizer instances
    2. Registers the sidebar panel (visible to all users)
    3. Sets up WebSocket API handlers for frontend communication
    
    Args:
        hass: Home Assistant instance
        config: Full Home Assistant configuration (not used - config flow only)
    
    Returns:
        bool: True if setup was successful
    """
    # Initialize the domain's data storage in hass.data
    # This dictionary will store coordinator instances keyed by config_entry.entry_id
    hass.data.setdefault(DOMAIN, {})
    
    # Register the sidebar panel that provides the UI interface
    # This makes the "PV Optimizer" panel appear in the Home Assistant sidebar
    await async_setup_panel(hass)
    
    # Register WebSocket API handlers for frontend-backend communication
    # This enables the panel to fetch configuration and device states in real-time
    await async_setup_connection(hass)
    
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """
    Set up PV Optimizer from a config entry (per-instance initialization).
    
    This function is called for each configured instance of the integration.
    It creates a coordinator for this specific instance and sets up all the
    entities (sensors, switches, numbers) associated with it.
    
    Functionality Achieved:
    ----------------------
    1. Creates a coordinator instance that manages the optimization logic
    2. Stores the coordinator in hass.data for access by platforms and services
    3. Sets up entity platforms (sensor, switch, number) which create monitoring entities
    4. Registers devices in Home Assistant's device registry for UI organization
    5. Performs initial data refresh to populate entity states
    6. Registers a listener to reload when configuration changes
    
    Detailed Flow:
    -------------
    1. Coordinator Creation:
       - Instantiates PVOptimizerCoordinator with global config and device list
       - Coordinator handles periodic optimization cycles
       - Sets up device instances (SwitchDevice, NumericDevice)
    
    2. Platform Setup:
       - sensor.py: Creates monitoring sensors (power budget, device states, etc.)
       - switch.py: Creates control switches (device on/off, optimization enabled)
       - number.py: Creates adjustable numbers (priority, min times, numeric targets)
    
    3. Device Registry:
       - Creates a device entry for each configured PV device
       - Links entities to their parent devices
       - Allows devices to appear in Home Assistant's device UI
    
    4. Initial Refresh:
       - Runs the first optimization cycle
       - Populates all sensor states
       - Establishes baseline device states
    
    5. Update Listener:
       - Monitors for config changes (via options flow)
       - Triggers reload when devices are added/edited/deleted
    
    Args:
        hass: Home Assistant instance
        entry: ConfigEntry containing global config and device list
    
    Returns:
        bool: True if setup was successful
    """
    # Debug logging to track configuration during setup
    _LOGGER.debug(f"Setup entry - entry.data: {entry.data}")
    _LOGGER.debug(f"Setup entry - entry.data keys: {entry.data.keys()}")
    _LOGGER.debug(f"Setup entry - devices: {entry.data.get('devices', [])}")
    
    # Create the coordinator instance that manages optimization cycles
    # The coordinator is the heart of the integration - it:
    # - Runs periodic optimization cycles
    # - Calculates power budget
    # - Determines ideal device states
    # - Controls device activation/deactivation
    coordinator = PVOptimizerCoordinator(hass, entry)
    
    # Store coordinator in hass.data for access by platforms and services
    # Format: hass.data[DOMAIN][entry_id] = coordinator
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Forward setup to entity platforms
    # This calls async_setup_entry in sensor.py, switch.py, and number.py
    # Each platform creates its entities based on the configured devices
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Set up devices in device registry AFTER platforms are set up
    # This ensures entities already have their device_info set, which is used
    # to link entities to their parent devices in the UI
    # This makes devices appear in Settings -> Devices & Services -> PV Optimizer
    await async_setup_devices(hass, entry)

    # Perform first refresh after platforms are ready
    # This triggers the coordinator's _async_update_data() method which:
    # - Aggregates device data
    # - Calculates power budget
    # - Determines ideal states
    # - Synchronizes device states
    await coordinator.async_refresh()

    # Register update listener for config changes
    # When the user modifies configuration via options flow, this triggers
    # async_reload_entry to apply the changes
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """
    Unload a config entry (cleanup when removing or reloading integration).
    
    This function is called when the integration is being removed or reloaded.
    It performs cleanup to ensure no orphaned resources remain.
    
    Functionality Achieved:
    ----------------------
    1. Unloads all entity platforms (removes entities from Home Assistant)
    2. Removes the coordinator from memory
    3. Stops any running optimization cycles
    
    Flow:
    -----
    1. Platform Unload:
       - Calls async_unload_entry in sensor.py, switch.py, and number.py
       - Each platform removes its entities
       - Entity states are no longer updated
    
    2. Coordinator Cleanup:
       - Removes coordinator from hass.data
       - Stops the periodic update cycle
       - Frees memory and resources
    
    Note: Device registry entries are NOT removed here - they persist
    until explicitly deleted by the user or when devices are removed
    from configuration.
    
    Args:
        hass: Home Assistant instance
        entry: ConfigEntry being unloaded
    
    Returns:
        bool: True if unload was successful, False if any platform failed to unload
    """
    # Unload all platforms (sensor, switch, number)
    # This removes all entities created by this config entry
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        # Remove coordinator from hass.data to free memory
        # This also stops the periodic optimization cycle
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """
    Reload config entry (apply configuration changes).
    
    This function is called when configuration changes are made through the
    options flow (e.g., adding/editing/deleting devices, changing global config).
    
    Functionality Achieved:
    ----------------------
    1. Cleanly unloads the current integration instance
    2. Reloads with the updated configuration
    3. Recreates all entities with new settings
    
    Flow:
    -----
    1. Unload Phase:
       - Stops optimization cycles
       - Removes all entities
       - Cleans up coordinator
    
    2. Reload Phase:
       - Creates new coordinator with updated config
       - Recreates entity platforms with new device list
       - Updates device registry
       - Starts optimization with new settings
    
    Use Cases:
    ----------
    - User adds a new device via options flow
    - User edits device parameters (priority, min times, etc.)
    - User deletes a device
    - User changes global configuration (surplus sensor, cycle time, etc.)
    
    Args:
        hass: Home Assistant instance
        entry: ConfigEntry with updated configuration
    
    Returns:
        None
    """
    # Unload the existing entry (cleanup)
    await async_unload_entry(hass, entry)
    
    # Set up the entry again with updated configuration
    await async_setup_entry(hass, entry)

