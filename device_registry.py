"""Device Registry integration for PV Optimizer."""
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN


async def async_setup_devices(hass, config_entry):
    """Set up devices in the device registry."""
    device_reg = dr.async_get(hass)
    devices = config_entry.data.get("devices", [])
    
    # Create a device for each configured PV device
    for device_config in devices:
        device_name = device_config["name"]
        
        # Create device in registry
        device_reg.async_get_or_create(
            config_entry_id=config_entry.entry_id,
            identifiers={(DOMAIN, f"{config_entry.entry_id}_{device_name}")},
            name=f"PVO {device_name}",
            manufacturer="PV Optimizer",
            model=f"{device_config['type'].capitalize()} Device",
            sw_version=config_entry.version,
        )