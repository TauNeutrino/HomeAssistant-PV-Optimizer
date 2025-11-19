"""
Device Registry Integration for PV Optimizer

This module manages the registration of devices in Home Assistant's device registry.
It ensures that each configured PV device appears as a device in the UI, allowing
users to see all PV devices organized under the PV Optimizer integration.

Purpose:
--------
Create and maintain device entries in Home Assistant's device registry for each
configured PV optimizer device, enabling:
1. Organized device view in Settings -> Devices & Services
2. Entity grouping under their parent devices
3. Device cards with manufacturer, model, and version info
4. Automatic cleanup of removed devices

Architecture:
------------
The device registry is Home Assistant's central registry for all devices.
This module:
1. Creates a device entry for each PV device (switch or numeric)
2. Links entities to their parent devices via device_info
3. Maintains device metadata (name, manufacturer, model)
4. Removes devices when they're deleted from configuration

Device Hierarchy:
----------------
Integration: PV Optimizer
  └── Config Entry: PV Optimizer instance
       ├── Device: PVO Hot Water Heater
       │    ├── sensor.pvo_hot_water_heater_locked
       │    ├── sensor.pvo_hot_water_heater_measured_power_avg
       │    ├── switch.pvo_hot_water_heater_optimization_enabled
       │    └── number.pvo_hot_water_heater_priority
       ├── Device: PVO Heat Pump
       │    └── [entities...]
       └── Controller Device: PV Optimizer Controller
            ├── sensor.pv_optimizer_power_budget
            └── sensor.pv_optimizer_averaged_surplus

Flow:
-----
1. Called during async_setup_entry after platforms are set up
2. Retrieves existing devices for this integration
3. Creates/updates devices for current configuration
4. Removes devices no longer in configuration
5. Entities link to devices via device_info in entity classes
"""

import logging
import re
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, CONF_NAME

_LOGGER = logging.getLogger(__name__)


def normalize_device_name(name: str) -> str:
    """
    Normalize device name to a safe identifier (entity_id format).
    
    This function converts user-provided device names into safe identifiers that
    can be used in device identifiers. It ensures compatibility with Home Assistant's
    naming requirements.
    
    Functionality Achieved:
    ----------------------
    1. Converts to lowercase for consistency
    2. Replaces spaces and special characters with underscores
    3. Removes leading/trailing underscores
    4. Collapses multiple consecutive underscores into single underscore
    
    Examples:
    --------
    "Hot Water Heater" -> "hot_water_heater"
    "Heizstab (Küche)!" -> "heizstab_kuche"
    "  Test__Device  " -> "test_device"
    
    Note: This is duplicated from const.py to avoid circular imports
    during module initialization.
    
    Args:
        name: User-provided device name
    
    Returns:
        str: Normalized name safe for use in device identifiers
    """
    # Convert to lowercase
    name = name.lower()
    # Replace spaces and special characters with underscores
    name = re.sub(r'[^a-z0-9_]+', '_', name)
    # Remove leading/trailing underscores
    name = name.strip('_')
    # Replace multiple consecutive underscores with single underscore
    name = re.sub(r'_+', '_', name)
    return name


async def async_setup_devices(hass, config_entry):
    """
    Set up devices in Home Assistant's device registry.
    
    This function is called during integration setup (after platforms are ready)
    to create device entries for all configured PV devices. It also handles
    cleanup of devices that have been removed from configuration.
    
    Functionality Achieved:
    ----------------------
    1. Device Creation: Creates device entries for all configured PV devices
    2. Device Updates: Updates existing devices if configuration changed
    3. Device Cleanup: Removes device entries for deleted PV devices
    4. Entity Linking: Enables entities to link to their parent devices
    
    Device Entry Structure:
    ----------------------
    Each device entry contains:
    - identifiers: Unique tuple (domain, device_id) for identification
    - name: Display name (e.g., "PVO Hot Water Heater")
    - manufacturer: "PV Optimizer"
    - model: Device type (e.g., "Switch Device", "Numeric Device")
    - sw_version: Integration version
    - config_entry_id: Links device to this integration instance
    
    Device Identifier Format:
    ------------------------
    {config_entry_id}_{normalized_device_name}
    
    Example: "abc123_hot_water_heater"
    
    This ensures:
    - Uniqueness across multiple PV Optimizer instances
    - Stability when device names don't change
    - Easy lookup by config entry
    
    Flow:
    -----
    1. Retrieve device registry instance
    2. Get list of configured devices from config entry
    3. Scan existing devices belonging to this integration
    4. For each configured device:
       - Normalize device name for identifier
       - Create or update device entry
       - Store identifier for comparison
    5. Identify devices to remove (exist in registry but not in config)
    6. Remove obsolete devices from registry
    
    Synchronization Strategy:
    ------------------------
    - Create: New devices in config -> create registry entries
    - Update: Existing devices -> update if needed (name, model, etc.)
    - Delete: Devices removed from config -> remove from registry
    
    Entity Linking:
    --------------
    Entities created by sensor.py, switch.py, and number.py use device_info
    to link themselves to these device entries. The device_info contains:
    {
        "identifiers": {(DOMAIN, device_identifier)},
        "name": "PVO {device_name}",
        "manufacturer": "PV Optimizer",
        "model": "{type} Device",
    }
    
    This allows Home Assistant to:
    - Group entities under their parent device
    - Show device cards with all entities
    - Navigate from device to entities and vice versa
    
    Args:
        hass: Home Assistant instance
        config_entry: ConfigEntry containing device configuration
    
    Returns:
        None
    """
    # Get the device registry instance
    device_reg = dr.async_get(hass)
    
    # Extract configured devices from config entry data
    # devices = list of device dicts with name, type, priority, etc.
    devices = config_entry.data.get("devices", [])
    
    # Log device count for debugging
    _LOGGER.debug(f"Setting up devices in registry. Found {len(devices)} devices in config.")
    
    # Handle case of no devices (e.g., during initial setup)
    # This is normal - user will add devices later via options flow
    if not devices:
        _LOGGER.debug("No devices in config, skipping device registry setup.")
        return
    
    # Step 1: Scan for existing PV Optimizer devices in registry
    # We need to identify devices that belong to this config entry so we can
    # determine which ones to keep, update, or remove
    existing_device_identifiers = set()
    
    # Iterate through ALL devices in the registry
    for device in device_reg.devices.values():
        # Check each device's identifiers
        for identifier in device.identifiers:
            # Identifier format: (domain, device_id)
            # Example: ("pv_optimizer", "abc123_hot_water_heater")
            if identifier[0] == DOMAIN and identifier[1].startswith(f"{config_entry.entry_id}_"):
                # This device belongs to our integration and config entry
                existing_device_identifiers.add(identifier[1])
    
    _LOGGER.debug(f"Existing PV Optimizer devices in registry: {existing_device_identifiers}")
    
    # Step 2: Create or update devices for current configuration
    current_device_identifiers = set()
    
    for device_config in devices:
        # Get device name from configuration
        device_name = device_config.get(CONF_NAME)
        
        # Validate device has a name
        if not device_name:
            _LOGGER.warning(f"Device config missing name, skipping: {device_config}")
            continue
        
        # Normalize name to create safe identifier
        # Example: "Hot Water Heater" -> "hot_water_heater"
        normalized_name = normalize_device_name(device_name)
        
        # Build unique device identifier
        # Format: {entry_id}_{normalized_name}
        # This ensures uniqueness across multiple integration instances
        device_identifier = f"{config_entry.entry_id}_{normalized_name}"
        current_device_identifiers.add(device_identifier)
        
        # Get device type for model string
        device_type = device_config.get('type', 'Unknown')
        
        # Create or update device in registry
        _LOGGER.debug(f"Creating/updating device: {device_name} ({device_identifier})")
        device_reg.async_get_or_create(
            # Link device to this config entry
            config_entry_id=config_entry.entry_id,
            
            # Unique identifier tuple (domain, id)
            identifiers={(DOMAIN, device_identifier)},
            
            # Display name (shown in UI)
            name=f"PVO {device_name}",
            
            # Manufacturer (shown in device info)
            manufacturer="PV Optimizer",
            
            # Model string (shown in device info)
            # Example: "Switch Device" or "Numeric Device"
            model=f"{device_type.capitalize()} Device",
            
            # Software version (integration version)
            sw_version=str(config_entry.version) if hasattr(config_entry, 'version') else "1.0",
        )
    
    _LOGGER.debug(f"Current devices from config: {current_device_identifiers}")
    
    # Step 3: Remove devices that no longer exist in configuration
    # Calculate set difference: devices in registry but not in current config
    devices_to_remove = existing_device_identifiers - current_device_identifiers
    
    if devices_to_remove:
        _LOGGER.info(f"Removing {len(devices_to_remove)} device(s) no longer in config: {devices_to_remove}")
        
        # Remove each obsolete device
        for device_identifier in devices_to_remove:
            # Retrieve device object from registry
            device = device_reg.async_get_device(identifiers={(DOMAIN, device_identifier)})
            
            if device:
                _LOGGER.info(f"Removing device from registry: {device_identifier}")
                # Remove device and all associated entities
                device_reg.async_remove_device(device.id)
    else:
        _LOGGER.debug("No devices to remove from registry.")