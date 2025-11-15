"""Numbers for PV Optimizer integration."""
import logging
from typing import Any, Dict, List, Optional

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    CONF_NAME,
    CONF_TYPE,
    CONF_NUMERIC_TARGETS,
    CONF_NUMERIC_ENTITY_ID,
    CONF_ACTIVATED_VALUE,
    CONF_DEACTIVATED_VALUE,
    TYPE_NUMERIC,
)
from .coordinator import PVOptimizerCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up numbers for PV Optimizer."""
    coordinator: PVOptimizerCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = []

    # Create numbers for numeric-type devices
    for device in coordinator.devices:
        if device[CONF_TYPE] == TYPE_NUMERIC:
            numeric_targets = device.get(CONF_NUMERIC_TARGETS, [])
            for target in numeric_targets:
                entities.append(PVOptimizerNumber(coordinator, device, target))

    async_add_entities(entities)


class PVOptimizerNumber(CoordinatorEntity, NumberEntity):
    """Number for PV Optimizer appliance."""

    def __init__(self, coordinator: PVOptimizerCoordinator, device: Dict[str, Any], target: Dict[str, Any]) -> None:
        """Initialize the number."""
        super().__init__(coordinator)
        self._device = device
        self._target = target
        self._device_name = device[CONF_NAME]
        self._numeric_entity_id = target[CONF_NUMERIC_ENTITY_ID]
        self._activated_value = target[CONF_ACTIVATED_VALUE]
        self._deactivated_value = target[CONF_DEACTIVATED_VALUE]
        self._attr_name = f"PVO {self._device_name} {self._numeric_entity_id.split('.')[-1]}"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{self._device_name}_{self._numeric_entity_id}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{coordinator.config_entry.entry_id}_{self._device_name}")},
            "name": f"PVO {self._device_name}",
            "manufacturer": "Custom",
            "model": "PV Appliance",
        }
        # Set min/max based on activated/deactivated values
        self._attr_min_value = min(self._activated_value, self._deactivated_value)
        self._attr_max_value = max(self._activated_value, self._deactivated_value)

    @property
    def value(self) -> float:
        """Return the current value."""
        state = self.hass.states.get(self._numeric_entity_id)
        return float(state.state) if state else 0.0

    async def async_set_value(self, value: float) -> None:
        """Set the value."""
        # This is for manual control; the coordinator handles optimization
        # But we can allow manual override
        await self.hass.services.async_call(
            "number", "set_value",
            {"entity_id": self._numeric_entity_id, "value": value}
        )
