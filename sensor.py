"""Sensors for PV Optimizer integration."""
import logging
from typing import Any, Dict, Optional

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    CONF_NAME,
    ATTR_IS_LOCKED,
    ATTR_MEASURED_POWER_AVG,
    ATTR_PVO_LAST_TARGET_STATE,
)
from .coordinator import PVOptimizerCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors for PV Optimizer."""
    coordinator: PVOptimizerCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = []

    # Controller sensors
    entities.append(PVOptimizerControllerSensor(coordinator, "power_budget", "Power Budget", "W"))
    entities.append(PVOptimizerControllerSensor(coordinator, "surplus_avg", "Averaged Surplus", "W"))

    # Appliance sensors - monitoring entities as per requirements
    for device in coordinator.devices:
        device_name = device[CONF_NAME]
        entities.append(PVOptimizerApplianceSensor(coordinator, device_name, ATTR_IS_LOCKED, "Locked", None))
        entities.append(PVOptimizerApplianceSensor(coordinator, device_name, ATTR_MEASURED_POWER_AVG, "Measured Power Avg", "W"))
        entities.append(PVOptimizerApplianceSensor(coordinator, device_name, ATTR_PVO_LAST_TARGET_STATE, "Last Target State", None))
        entities.append(PVOptimizerApplianceSensor(coordinator, device_name, "contribution_to_budget", "Contribution to Budget", "W"))

    async_add_entities(entities)


class PVOptimizerControllerSensor(CoordinatorEntity, SensorEntity):
    """Sensor for PV Optimizer controller."""

    def __init__(self, coordinator: PVOptimizerCoordinator, data_key: str, name: str, unit: Optional[str]) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._data_key = data_key
        self._attr_name = f"PV Optimizer {name}"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{data_key}"
        self._attr_unit_of_measurement = unit
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.config_entry.entry_id)},
            "name": "PV Optimizer Controller",
            "manufacturer": "Custom",
            "model": "PV Optimizer",
        }

    @property
    def state(self) -> Any:
        """Return the state of the sensor."""
        return self.coordinator.data.get(self._data_key, 0)


class PVOptimizerApplianceSensor(CoordinatorEntity, SensorEntity):
    """Sensor for PV Optimizer appliance."""

    def __init__(self, coordinator: PVOptimizerCoordinator, device_name: str, data_key: str, name: str, unit: Optional[str]) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._device_name = device_name
        self._data_key = data_key
        self._attr_name = f"PVO {device_name} {name}"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{device_name}_{data_key}"
        self._attr_unit_of_measurement = unit
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{coordinator.config_entry.entry_id}_{device_name}")},
            "name": f"PVO {device_name}",
            "manufacturer": "Custom",
            "model": "PV Appliance",
        }

    @property
    def state(self) -> Any:
        """Return the state of the sensor."""
        device_data = self.coordinator.device_states.get(self._device_name, {})
        if self._data_key == ATTR_IS_LOCKED:
            return device_data.get(ATTR_IS_LOCKED, False)
        elif self._data_key == ATTR_MEASURED_POWER_AVG:
            return device_data.get(ATTR_MEASURED_POWER_AVG, 0)
        elif self._data_key == ATTR_PVO_LAST_TARGET_STATE:
            return device_data.get(ATTR_PVO_LAST_TARGET_STATE, False)
        elif self._data_key == "contribution_to_budget":
            # This solves the problem of showing each device's contribution to the total power budget
            # when it's currently on and managed by the optimizer
            if device_data.get("is_on") and not device_data.get(ATTR_IS_LOCKED, False):
                return device_data.get(ATTR_MEASURED_POWER_AVG, 0)
            return 0
        return None
