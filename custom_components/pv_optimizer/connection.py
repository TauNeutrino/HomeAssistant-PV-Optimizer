"""
WebSocket API for PV Optimizer Integration - Multi-Config-Entry Architecture

This module provides real-time communication between the Home Assistant backend
and the frontend panel via WebSocket connections.

Updated for multi-config-entry architecture:
- ServiceCoordinator provides global config
- DeviceCoordinators provide device states
"""

import logging
import voluptuous as vol
from datetime import datetime

from homeassistant.components import websocket_api
from homeassistant.core import callback
from homeassistant.loader import async_get_integration

from .const import DOMAIN
from .coordinators import ServiceCoordinator, DeviceCoordinator

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
        """Handle the 'pv_optimizer/config' WebSocket command."""
        # Check if PV Optimizer domain is initialized
        if not hass.data.get(DOMAIN):
            connection.send_error(
                msg["id"],
                "not_ready",
                "PV Optimizer not configured"
            )
            return
            
        try:
            # Get the service coordinator
            service_coordinator = hass.data[DOMAIN].get("service")
            
            if not service_coordinator:
                connection.send_error(
                    msg["id"],
                    "not_ready",
                    "PV Optimizer service not ready"
                )
                return
            
            # Get integration version
            integration = await async_get_integration(hass, DOMAIN)
            version = integration.version

            # Build response data structure
            response_data = {
                "version": version,
                "global_config": service_coordinator.global_config,
                "devices": [],
            }

            # Iterate through all device coordinators
            for device_name, device_coordinator in service_coordinator.device_coordinators.items():
                # Get device config and state
                device_config = device_coordinator.device_config
                device_state = device_coordinator.data if device_coordinator.data else {}
                
                # Add device data to response
                response_data["devices"].append({
                    "config": device_config,
                    "state": device_state,
                })

            # Get optimizer statistics directly from coordinator
            optimizer_stats = service_coordinator.data.get("optimizer_stats", {}) if service_coordinator.data else {}
            
            # Add timestamp info
            last_update_timestamp = service_coordinator.data.get("last_update_timestamp") if service_coordinator.data else None
            elapsed_seconds = (datetime.now(last_update_timestamp.tzinfo) - last_update_timestamp).total_seconds() if last_update_timestamp else None

            # Ensure all keys are present for frontend
            response_data["optimizer_stats"] = {
                "surplus_current": optimizer_stats.get("surplus_current", 0.0),
                "surplus_average": optimizer_stats.get("surplus_average", 0.0),
                "power_rated_total": optimizer_stats.get("power_rated_total", 0.0),
                "power_measured_total": optimizer_stats.get("power_measured_total", 0.0),
                "last_update_timestamp": last_update_timestamp.isoformat() if last_update_timestamp else None,
                "elapsed_seconds_since_update": elapsed_seconds,
                "surplus_offset": optimizer_stats.get("surplus_offset", 0.0),
            }
            
            # Send successful response to frontend
            connection.send_result(msg["id"], response_data)
            
        except (StopIteration, KeyError, AttributeError) as e:
            _LOGGER.error(f"Error retrieving PV Optimizer config: {e}")
            connection.send_error(
                msg["id"],
                "not_ready",
                f"PV Optimizer not ready: {str(e)}"
            )

    @websocket_api.websocket_command(
        {
            vol.Required("type"): f"{DOMAIN}/history",
            vol.Optional("hours", default=24): int,
        }
    )
    @websocket_api.async_response
    async def handle_get_history(hass, connection, msg):
        """Handle the 'pv_optimizer/history' WebSocket command."""
        try:
            # Get service entry
            service_coordinator = hass.data[DOMAIN].get("service")
            if not service_coordinator:
                connection.send_error(msg["id"], "not_found", "Service coordinator not found")
                return
            
            # Get history tracker
            entry_id = service_coordinator.config_entry.entry_id
            history_tracker = hass.data[DOMAIN].get(f"{entry_id}_history")
            
            if not history_tracker:
                connection.send_error(msg["id"], "not_found", "History tracker not found")
                return
            
            # Get snapshots for requested time range
            hours = msg.get("hours", 24)
            snapshots = history_tracker.get_snapshots(hours)
            
            connection.send_result(msg["id"], {
                "snapshots": snapshots,
                "count": len(snapshots)
            })
            
        except Exception as err:
            _LOGGER.error("Error getting history: %s", err)
            connection.send_error(msg["id"], "unknown_error", str(err))
    
    @websocket_api.websocket_command(
        {
            vol.Required("type"): f"{DOMAIN}/statistics",
        }
    )
    @websocket_api.async_response
    async def handle_get_statistics(hass, connection, msg):
        """Handle the 'pv_optimizer/statistics' WebSocket command."""
        try:
            # Get service entry
            service_coordinator = hass.data[DOMAIN].get("service")
            if not service_coordinator:
                connection.send_error(msg["id"], "not_found", "Service coordinator not found")
                return
            
            # Get history tracker
            entry_id = service_coordinator.config_entry.entry_id
            history_tracker = hass.data[DOMAIN].get(f"{entry_id}_history")
            
            if not history_tracker:
                connection.send_error(msg["id"], "not_found", "History tracker not found")
                return
            
            # Get calculated statistics
            statistics = history_tracker.get_statistics()
            
            connection.send_result(msg["id"], statistics)
            
        except Exception as err:
            _LOGGER.error("Error getting statistics: %s", err)
            connection.send_error(msg["id"], "unknown_error", str(err))
    
    # Register the command with Home Assistant's WebSocket API
    websocket_api.async_register_command(hass, handle_get_config)

    @websocket_api.websocket_command(
        {
            vol.Required("type"): f"{DOMAIN}/set_simulation_offset",
            vol.Required("offset"): vol.Coerce(float),
        }
    )
    @websocket_api.async_response
    async def handle_set_simulation_offset(hass, connection, msg):
        """Handle the 'pv_optimizer/set_simulation_offset' WebSocket command."""
        try:
            service_coordinator = hass.data[DOMAIN].get("service")
            if not service_coordinator:
                raise ValueError("Service coordinator not found")
                
            offset = msg["offset"]
            service_coordinator.set_simulation_surplus_offset(offset)
            
            connection.send_result(msg["id"], {"success": True})
            
        except Exception as e:
            _LOGGER.error(f"Error setting simulation offset: {e}")
            connection.send_error(msg["id"], "update_failed", str(e))

    websocket_api.async_register_command(hass, handle_set_simulation_offset)

    @websocket_api.websocket_command(
        {
            vol.Required("type"): f"{DOMAIN}/reset_device",
            vol.Required("device_name"): str,
        }
    )
    @websocket_api.async_response
    async def handle_reset_device(hass, connection, msg):
        """Handle the 'pv_optimizer/reset_device' WebSocket command."""
        try:
            service_coordinator = hass.data[DOMAIN].get("service")
            if not service_coordinator:
                raise ValueError("Service coordinator not found")
                
            device_name = msg["device_name"]
            device_coordinator = service_coordinator.device_coordinators.get(device_name)
            
            if not device_coordinator:
                raise ValueError(f"Device coordinator not found: {device_name}")
            
            await device_coordinator.reset_target_state()
            
            connection.send_result(msg["id"], {"success": True})
            
        except Exception as e:
            _LOGGER.error(f"Error resetting device: {e}")
            connection.send_error(msg["id"], "reset_failed", str(e))

    websocket_api.async_register_command(hass, handle_reset_device)

    @websocket_api.websocket_command(
        {
            vol.Required("type"): f"{DOMAIN}/update_device_config",
            vol.Required("device_name"): str,
            vol.Required("updates"): dict,
        }
    )
    @websocket_api.async_response
    async def handle_update_device_config(hass, connection, msg):
        """Handle the 'pv_optimizer/update_device_config' WebSocket command."""
        try:
            service_coordinator = hass.data[DOMAIN].get("service")
            if not service_coordinator:
                raise ValueError("Service coordinator not found")
                
            device_name = msg["device_name"]
            device_coordinator = service_coordinator.device_coordinators.get(device_name)
            
            if not device_coordinator:
                raise ValueError(f"Device coordinator not found: {device_name}")
            
            updates = msg["updates"]
            await device_coordinator.async_update_device_config(updates)
            
            connection.send_result(msg["id"], {"success": True})
            
        except Exception as e:
            _LOGGER.error(f"Error updating device config: {e}")
            connection.send_error(msg["id"], "update_failed", str(e))

    websocket_api.async_register_command(hass, handle_update_device_config)
    websocket_api.async_register_command(hass, handle_reset_device)
    websocket_api.async_register_command(hass, handle_set_simulation_offset)
    websocket_api.async_register_command(hass, handle_get_history)
    websocket_api.async_register_command(hass, handle_get_statistics)
    
    # Handler for updating device color
    @websocket_api.websocket_command(
        {
            vol.Required("type"): "pv_optimizer/update_device_color",
            vol.Required("device_name"): str,
            vol.Required("color"): str,
        }
    )
    @websocket_api.async_response
    async def handle_update_device_color(
        hass: HomeAssistant,
        connection: websocket_api.ActiveConnection,
        msg: dict,
    ) -> None:
        """Update device color."""
        try:
            service_entry = _get_service_entry(hass)
            if not service_entry:
                raise ValueError("Service entry not found")
                
            service_coordinator = hass.data[DOMAIN].get(service_entry.entry_id)
            if not service_coordinator:
                raise ValueError("Service coordinator not found")
                
            device_name = msg["device_name"]
            device_coordinator = service_coordinator.device_coordinators.get(device_name)
            
            if not device_coordinator:
                raise ValueError(f"Device coordinator not found: {device_name}")
            
            # Import CONF_DEVICE_COLOR
            from .const import CONF_DEVICE_COLOR
            
            # Update device config with new color
            await device_coordinator.async_update_device_config({CONF_DEVICE_COLOR: msg["color"]})
            
            connection.send_result(msg["id"], {"success": True})
            
        except Exception as e:
            _LOGGER.error(f"Error updating device color: {e}")
            connection.send_error(msg["id"], "update_failed", str(e))
    
    websocket_api.async_register_command(hass, handle_update_device_color)
    
    _LOGGER.info("WebSocket API handlers registered for PV Optimizer")
