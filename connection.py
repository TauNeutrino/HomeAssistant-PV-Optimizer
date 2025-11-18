
import logging
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er

from .const import (
    DOMAIN,
    CONF_NAME,
    CONF_TYPE,
    CONF_PRIORITY,
    CONF_POWER,
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

_LOGGER = logging.getLogger(__name__)

async def async_setup_connection(hass):
    """Set up WebSocket API handlers for PV Optimizer."""
    
    @websocket_api.websocket_command(
        {
            vol.Required("type"): f"{DOMAIN}/config",
        }
    )
    @websocket_api.async_response
    async def handle_get_config(hass, connection, msg):
        """Get the PV Optimizer configuration."""
        if not hass.data.get(DOMAIN):
            connection.send_error(msg["id"], "not_ready", "PV Optimizer not configured")
            return
            
        try:
            coordinator = next(iter(hass.data[DOMAIN].values()))
            response_data = {
                "global_config": coordinator.global_config,
                "devices": [],
            }

            for device_config in coordinator.devices:
                device_name = device_config[CONF_NAME]
                device_state = coordinator.device_states.get(device_name, {})
                response_data["devices"].append({
                    "config": device_config,
                    "state": device_state,
                })
            connection.send_result(msg["id"], response_data)
        except (StopIteration, KeyError, AttributeError) as e:
            connection.send_error(msg["id"], "not_ready", f"PV Optimizer not ready: {str(e)}")

    @websocket_api.websocket_command(
        {
            vol.Required("type"): f"{DOMAIN}/set_config",
            vol.Optional("data"): dict,
        }
    )
    @websocket_api.async_response
    async def handle_set_config(hass, connection, msg):
        """Set the PV Optimizer global configuration."""
        data = msg.get("data", {})
        
        if not hass.data.get(DOMAIN):
            connection.send_error(msg["id"], "not_ready", "PV Optimizer not configured")
            return
            
        try:
            coordinator = next(iter(hass.data[DOMAIN].values()))
            await coordinator.async_set_config(data)
            connection.send_result(msg["id"])
        except (StopIteration, KeyError, AttributeError) as e:
            connection.send_error(msg["id"], "not_ready", f"PV Optimizer not ready: {str(e)}")

    @websocket_api.websocket_command(
        {
            vol.Required("type"): f"{DOMAIN}/add_device",
            vol.Required("device"): dict,
        }
    )
    @websocket_api.async_response
    async def handle_add_device(hass, connection, msg):
        """Add a new device to PV Optimizer."""
        device_config = msg.get("device", {})
        
        if not hass.data.get(DOMAIN):
            connection.send_error(msg["id"], "not_ready", "PV Optimizer not configured")
            return
            
        try:
            coordinator = next(iter(hass.data[DOMAIN].values()))
            
            # Validate device configuration
            error = _validate_device_config(device_config, coordinator.devices)
            if error:
                connection.send_error(msg["id"], "invalid_config", error)
                return
            
            # Add device to coordinator
            coordinator.devices.append(device_config)
            
            # Update config entry
            config_data = dict(coordinator.config_entry.data)
            config_data["devices"] = coordinator.devices
            hass.config_entries.async_update_entry(coordinator.config_entry, data=config_data)
            
            # Reload the config entry to create new entities
            await hass.config_entries.async_reload(coordinator.config_entry.entry_id)
            
            _LOGGER.info(f"Added device: {device_config.get(CONF_NAME)}")
            connection.send_result(msg["id"], {"success": True})
        except (StopIteration, KeyError, AttributeError) as e:
            connection.send_error(msg["id"], "error", f"Failed to add device: {str(e)}")

    @websocket_api.websocket_command(
        {
            vol.Required("type"): f"{DOMAIN}/update_device",
            vol.Required("device_name"): str,
            vol.Required("device"): dict,
        }
    )
    @websocket_api.async_response
    async def handle_update_device(hass, connection, msg):
        """Update an existing device in PV Optimizer."""
        device_name = msg.get("device_name")
        device_config = msg.get("device", {})
        
        if not hass.data.get(DOMAIN):
            connection.send_error(msg["id"], "not_ready", "PV Optimizer not configured")
            return
            
        try:
            coordinator = next(iter(hass.data[DOMAIN].values()))
            
            # Find device index
            device_index = None
            for i, device in enumerate(coordinator.devices):
                if device[CONF_NAME] == device_name:
                    device_index = i
                    break
            
            if device_index is None:
                connection.send_error(msg["id"], "not_found", f"Device '{device_name}' not found")
                return
            
            # Validate device configuration (excluding itself from duplicate check)
            other_devices = [d for d in coordinator.devices if d[CONF_NAME] != device_name]
            error = _validate_device_config(device_config, other_devices)
            if error:
                connection.send_error(msg["id"], "invalid_config", error)
                return
            
            # Update device
            coordinator.devices[device_index] = device_config
            
            # Update config entry
            config_data = dict(coordinator.config_entry.data)
            config_data["devices"] = coordinator.devices
            hass.config_entries.async_update_entry(coordinator.config_entry, data=config_data)
            
            # Reload if device name changed (requires entity recreation)
            if device_name != device_config.get(CONF_NAME):
                await hass.config_entries.async_reload(coordinator.config_entry.entry_id)
            
            _LOGGER.info(f"Updated device: {device_name} -> {device_config.get(CONF_NAME)}")
            connection.send_result(msg["id"], {"success": True})
        except (StopIteration, KeyError, AttributeError) as e:
            connection.send_error(msg["id"], "error", f"Failed to update device: {str(e)}")

    @websocket_api.websocket_command(
        {
            vol.Required("type"): f"{DOMAIN}/delete_device",
            vol.Required("device_name"): str,
        }
    )
    @websocket_api.async_response
    async def handle_delete_device(hass, connection, msg):
        """Delete a device from PV Optimizer."""
        device_name = msg.get("device_name")
        
        if not hass.data.get(DOMAIN):
            connection.send_error(msg["id"], "not_ready", "PV Optimizer not configured")
            return
            
        try:
            coordinator = next(iter(hass.data[DOMAIN].values()))
            
            # Find and remove device
            device_found = False
            for i, device in enumerate(coordinator.devices):
                if device[CONF_NAME] == device_name:
                    coordinator.devices.pop(i)
                    device_found = True
                    break
            
            if not device_found:
                connection.send_error(msg["id"], "not_found", f"Device '{device_name}' not found")
                return
            
            # Update config entry
            config_data = dict(coordinator.config_entry.data)
            config_data["devices"] = coordinator.devices
            hass.config_entries.async_update_entry(coordinator.config_entry, data=config_data)
            
            # Reload to remove entities
            await hass.config_entries.async_reload(coordinator.config_entry.entry_id)
            
            _LOGGER.info(f"Deleted device: {device_name}")
            connection.send_result(msg["id"], {"success": True})
        except (StopIteration, KeyError, AttributeError) as e:
            connection.send_error(msg["id"], "error", f"Failed to delete device: {str(e)}")

    @websocket_api.websocket_command(
        {
            vol.Required("type"): f"{DOMAIN}/get_available_entities",
            vol.Optional("domain"): str,
        }
    )
    @websocket_api.async_response
    async def handle_get_available_entities(hass, connection, msg):
        """Get available entities for device configuration."""
        domain = msg.get("domain")
        
        try:
            entity_reg = er.async_get(hass)
            entities = []
            
            for entity in entity_reg.entities.values():
                # Filter by domain if specified
                if domain and not entity.entity_id.startswith(f"{domain}."):
                    continue
                
                state = hass.states.get(entity.entity_id)
                if state:
                    entities.append({
                        "entity_id": entity.entity_id,
                        "name": entity.name or state.attributes.get("friendly_name", entity.entity_id),
                        "domain": entity.domain,
                    })
            
            connection.send_result(msg["id"], {"entities": entities})
        except Exception as e:
            connection.send_error(msg["id"], "error", f"Failed to get entities: {str(e)}")

    # Register all commands
    websocket_api.async_register_command(hass, handle_get_config)
    websocket_api.async_register_command(hass, handle_set_config)
    websocket_api.async_register_command(hass, handle_add_device)
    websocket_api.async_register_command(hass, handle_update_device)
    websocket_api.async_register_command(hass, handle_delete_device)
    websocket_api.async_register_command(hass, handle_get_available_entities)


def _validate_device_config(device_config, existing_devices):
    """Validate device configuration."""
    # Check required fields
    if not device_config.get(CONF_NAME):
        return "Device name is required"
    
    if not device_config.get(CONF_TYPE):
        return "Device type is required"
    
    if not device_config.get(CONF_PRIORITY):
        return "Device priority is required"
    
    if not device_config.get(CONF_POWER):
        return "Device power is required"
    
    # Check for duplicate names
    for device in existing_devices:
        if device[CONF_NAME] == device_config[CONF_NAME]:
            return f"Device name '{device_config[CONF_NAME]}' already exists"
    
    # Validate type-specific fields
    device_type = device_config[CONF_TYPE]
    
    if device_type == TYPE_SWITCH:
        if not device_config.get(CONF_SWITCH_ENTITY_ID):
            return "Switch entity ID is required for switch-type devices"
    
    elif device_type == TYPE_NUMERIC:
        if not device_config.get(CONF_NUMERIC_TARGETS):
            return "Numeric targets are required for numeric-type devices"
        
        targets = device_config[CONF_NUMERIC_TARGETS]
        if not isinstance(targets, list) or len(targets) == 0:
            return "At least one numeric target is required"
        
        for target in targets:
            if not target.get(CONF_NUMERIC_ENTITY_ID):
                return "Numeric entity ID is required for all targets"
            if CONF_ACTIVATED_VALUE not in target:
                return "Activated value is required for all targets"
            if CONF_DEACTIVATED_VALUE not in target:
                return "Deactivated value is required for all targets"
    
    else:
        return f"Invalid device type: {device_type}"
    
    return None
