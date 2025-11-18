
import logging
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import callback

from .const import DOMAIN, CONF_NAME

_LOGGER = logging.getLogger(__name__)

async def async_setup_connection(hass):
    @websocket_api.websocket_command(
        {
            vol.Required("type"): f"{DOMAIN}/config",
        }
    )
    @websocket_api.async_response
    async def handle_get_config(hass, connection, msg):
        """Get the PV Optimizer configuration."""
        # Check if any coordinators are available
        if not hass.data.get(DOMAIN):
            connection.send_error(msg["id"], "not_ready", "PV Optimizer not configured")
            return
            
        # Get the first available coordinator (assuming single config entry)
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
        """Set the PV Optimizer configuration."""
        data = msg.get("data", {})
        
        # Check if any coordinators are available
        if not hass.data.get(DOMAIN):
            connection.send_error(msg["id"], "not_ready", "PV Optimizer not configured")
            return
            
        # Get the first available coordinator (assuming single config entry)
        try:
            coordinator = next(iter(hass.data[DOMAIN].values()))
            await coordinator.async_set_config(data)
            connection.send_result(msg["id"])
        except (StopIteration, KeyError, AttributeError) as e:
            connection.send_error(msg["id"], "not_ready", f"PV Optimizer not ready: {str(e)}")

    websocket_api.async_register_command(hass, handle_get_config)
    websocket_api.async_register_command(hass, handle_set_config)
