"""Services for PV Optimizer integration."""
import logging
from typing import Any

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import PVOptimizerCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_register_services(hass: HomeAssistant) -> None:
    """Register services for PV Optimizer."""
    
    async def run_optimization_service(call: ServiceCall) -> None:
        """Manually trigger the optimization cycle."""
        _LOGGER.info("Manual optimization triggered via service call")
        
        # Find the PV Optimizer coordinator
        for entry_id, coordinator in hass.data.get(DOMAIN, {}).items():
            if isinstance(coordinator, PVOptimizerCoordinator):
                # Force an immediate update cycle
                try:
                    await coordinator.async_request_refresh()
                    _LOGGER.info(f"Optimization cycle triggered for entry {entry_id}")
                except Exception as e:
                    _LOGGER.error(f"Failed to trigger optimization cycle: {e}")
                break
        else:
            _LOGGER.warning("No PV Optimizer coordinator found to trigger optimization")

    # Register the service
    hass.services.async_register(
        DOMAIN,
        "run",
        run_optimization_service,
        schema=None,
    )
    
    _LOGGER.info("PV Optimizer services registered successfully")