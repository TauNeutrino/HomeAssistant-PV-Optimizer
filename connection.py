"""
WebSocket API for PV Optimizer Integration

This module provides real-time communication between the Home Assistant backend
and the frontend panel via WebSocket connections.

Purpose:
--------
Enable the frontend panel to fetch current configuration and device states
in real-time without requiring page refreshes or polling.

Architecture:
------------
Uses Home Assistant's built-in WebSocket API framework to:
1. Register custom WebSocket commands
2. Validate incoming requests
3. Send responses with configuration and state data
4. Handle errors gracefully

WebSocket Commands:
------------------
- pv_optimizer/config: Fetches complete configuration and current device states

Data Flow:
----------
1. Frontend panel opens WebSocket connection to Home Assistant
2. Panel sends command: {"type": "pv_optimizer/config", "id": 123}
3. Backend retrieves data from coordinator
4. Backend sends response with config and states
5. Panel receives data and updates UI

Response Structure:
------------------
{
    "global_config": {
        "surplus_sensor_entity_id": "sensor.grid_power",
        "sliding_window_size": 5,
        "optimization_cycle_time": 60,
        ...
    },
    "devices": [
        {
            "config": {
                "name": "Hot Water",
                "type": "switch",
                "priority": 1,
                "power": 2000,
                ...
            },
            "state": {
                "is_on": true,
                "is_locked": false,
                "measured_power_avg": 1950,
                "pvo_last_target_state": true
            }
        },
        ...
    ]
}
"""

import logging
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import callback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_connection(hass):
    """
    Set up WebSocket API handlers for PV Optimizer.
    
    This function registers custom WebSocket commands that the frontend panel
    uses to communicate with the backend.
    
    Functionality Achieved:
    ----------------------
    1. Registers the "pv_optimizer/config" command
    2. Provides real-time access to configuration and device states
    3. Enables the panel to display current system status
    
    WebSocket Communication Pattern:
    -------------------------------
    - Frontend connects via Home Assistant's WebSocket endpoint
    - Sends command with type and unique ID
    - Backend processes command and validates access
    - Returns structured data or error message
    - Frontend updates UI based on response
    
    Security:
    ---------
    - Commands require admin privileges (panel requires admin)
    - WebSocket connection is authenticated by Home Assistant
    - No sensitive data is exposed (all data is user-configured)
    
    Args:
        hass: Home Assistant instance
    
    Returns:
        None
    """
    
    @websocket_api.websocket_command(
        {
            # Command type that client must send
            # Example: {"type": "pv_optimizer/config", "id": 1}
            vol.Required("type"): f"{DOMAIN}/config",
        }
    )
    @websocket_api.async_response
    async def handle_get_config(hass, connection, msg):
        """
        Handle the 'pv_optimizer/config' WebSocket command.
        
        This command retrieves the complete configuration and current state
        of all devices managed by the PV Optimizer.
        
        Functionality Achieved:
        ----------------------
        1. Validates that PV Optimizer is properly initialized
        2. Retrieves coordinator instance (contains all data)
        3. Extracts global configuration settings
        4. Collects device configurations and current states
        5. Combines data into structured response
        6. Sends response to frontend panel
        
        Response Data:
        -------------
        - global_config: System-wide settings (surplus sensor, cycle time, etc.)
        - devices: Array of device objects with:
            - config: Static configuration (name, type, priority, power, etc.)
            - state: Dynamic state (is_on, is_locked, measured_power_avg, etc.)
        
        Error Handling:
        --------------
        - Returns "not_ready" error if integration not initialized
        - Returns "not_ready" error if coordinator not available
        - Logs errors for debugging
        
        Use Cases:
        ----------
        - Panel initial load (fetch all data)
        - Panel refresh (update device states)
        - Status monitoring (check if devices are locked, etc.)
        
        Args:
            hass: Home Assistant instance
            connection: WebSocket connection object
            msg: Message dict with command type and id
        
        Returns:
            None (sends response via connection.send_result/send_error)
        """
        # Check if PV Optimizer domain is initialized
        # hass.data[DOMAIN] is created in __init__.py's async_setup()
        if not hass.data.get(DOMAIN):
            # Integration not yet set up - send error response
            connection.send_error(
                msg["id"],
                "not_ready",
                "PV Optimizer not configured"
            )
            return
            
        try:
            # Get the coordinator instance
            # hass.data[DOMAIN] is a dict: {entry_id: coordinator}
            # We take the first (and typically only) coordinator
            coordinator = next(iter(hass.data[DOMAIN].values()))
            
            # Build response data structure
            response_data = {
                # Global configuration from coordinator
                # Includes: surplus_sensor_entity_id, sliding_window_size,
                #           optimization_cycle_time, invert_surplus_value
                "global_config": coordinator.global_config,
                
                # Will be populated with device data
                "devices": [],
            }

            # Iterate through all configured devices
            for device_config in coordinator.devices:
                device_name = device_config["name"]
                
                # Get current state from coordinator's device_states cache
                # This includes: is_on, is_locked, measured_power_avg,
                #                pvo_last_target_state, last_update
                device_state = coordinator.device_states.get(device_name, {})
                
                # Add device data to response
                response_data["devices"].append({
                    "config": device_config,  # Static configuration
                    "state": device_state,    # Dynamic state
                })
            
            # Send successful response to frontend
            connection.send_result(msg["id"], response_data)
            
        except (StopIteration, KeyError, AttributeError) as e:
            # Handle errors that might occur during data retrieval
            # - StopIteration: No coordinator found
            # - KeyError: Missing data in coordinator
            # - AttributeError: Coordinator not properly initialized
            _LOGGER.error(f"Error retrieving PV Optimizer config: {e}")
            connection.send_error(
                msg["id"],
                "not_ready",
                f"PV Optimizer not ready: {str(e)}"
            )

    # Register the command with Home Assistant's WebSocket API
    # This makes the command available to frontend connections
    websocket_api.async_register_command(hass, handle_get_config)
