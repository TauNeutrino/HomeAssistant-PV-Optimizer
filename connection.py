
import logging
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import callback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_connection(hass):
    @websocket_api.websocket_command(
        {
            vol.Required("type"): f"{DOMAIN}/get_config",
        }
    )
    @websocket_api.async_response
    async def handle_get_config(hass, connection, msg):
        """Get the PV Optimizer configuration."""
        # Get the first available coordinator (assuming single config entry)
        coordinator = next(iter(hass.data[DOMAIN].values()))
        config = coordinator.global_config
        connection.send_result(msg["id"], config)

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
        # Get the first available coordinator (assuming single config entry)
        coordinator = next(iter(hass.data[DOMAIN].values()))
        await coordinator.async_set_config(data)
        connection.send_result(msg["id"])

    websocket_api.async_register_command(hass, handle_get_config)
    websocket_api.async_register_command(hass, handle_set_config)
