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

            # Calculate optimizer statistics
            surplus_sensor_entity_id = service_coordinator.global_config.get("surplus_sensor_entity_id")
            current_surplus_state = hass.states.get(surplus_sensor_entity_id) if surplus_sensor_entity_id else None
            current_surplus = float(current_surplus_state.state) if current_surplus_state and current_surplus_state.state not in ['unknown', 'unavailable'] else 0.0
            
            # Default inversion (Negative = Surplus -> Positive = Surplus)
            current_surplus *= -1
            
            if service_coordinator.global_config.get("invert_surplus_value", False):
                current_surplus *= -1

            potential_power = sum(d["config"].get("power", 0) for d in response_data["devices"] if d["state"].get("is_on"))
            measured_power = sum(d["state"].get("measured_power_avg", 0) for d in response_data["devices"] if d["state"].get("is_on") and d["state"].get("measured_power_avg") is not None)
            
            last_update_timestamp = service_coordinator.data.get("last_update_timestamp") if service_coordinator.data else None
            elapsed_seconds = (datetime.now(last_update_timestamp.tzinfo) - last_update_timestamp).total_seconds() if last_update_timestamp else None

            response_data["optimizer_stats"] = {
                "current_surplus": current_surplus,
                "averaged_surplus": service_coordinator.data.get("surplus_avg", 0.0) if service_coordinator.data else 0.0,
                "potential_power_on_devices": potential_power,
                "measured_power_on_devices": measured_power,
                "last_update_timestamp": last_update_timestamp.isoformat() if last_update_timestamp else None,
                "elapsed_seconds_since_update": elapsed_seconds,
                "elapsed_seconds_since_update": elapsed_seconds,
                "simulation_surplus_offset": service_coordinator.simulation_surplus_offset,
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

    # Register the command with Home Assistant's WebSocket API
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
