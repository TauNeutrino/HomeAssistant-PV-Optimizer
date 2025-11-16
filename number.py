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
    CONF_PRIORITY,
    CONF_MIN_ON_TIME,
    CONF_MIN_OFF_TIME,
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

    # Create dynamic config numbers for all devices - priority, min_on_time, min_off_time
    for device in coordinator.devices:
        device_name = device[CONF_NAME]
        entities.append(PVOptimizerPriorityNumber(coordinator, device_name))
        entities.append(PVOptimizerMinOnTimeNumber(coordinator, device_name))
        entities.append(PVOptimizerMinOffTimeNumber(coordinator, device_name))

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


class PVOptimizerPriorityNumber(CoordinatorEntity, NumberEntity):
    """Dynamic config number for device priority - dynamic config entity."""

    def __init__(self, coordinator: PVOptimizerCoordinator, device_name: str) -> None:
        """Initialize the priority number."""
        super().__init__(coordinator)
        self._device_name = device_name
        self._attr_name = f"PVO {device_name} Priority"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{device_name}_priority"
        self._attr_min_value = 1
        self._attr_max_value = 10
        self._attr_step = 1
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{coordinator.config_entry.entry_id}_{device_name}")},
            "name": f"PVO {device_name}",
            "manufacturer": "Custom",
            "model": "PV Appliance",
        }

    @property
    def native_value(self) -> float:
        """Return the current priority value."""
        # This solves the problem of reading the current priority from device config
        for device in self.coordinator.devices:
            if device[CONF_NAME] == self._device_name:
                return device.get(CONF_PRIORITY, 5)
        return 5  # Default

    async def async_set_native_value(self, value: float) -> None:
        """Set the priority value."""
        # This solves the problem of dynamically updating device priority
        for i, device in enumerate(self.coordinator.devices):
            if device[CONF_NAME] == self._device_name:
                self.coordinator.devices[i][CONF_PRIORITY] = int(value)
                # Update config entry data
                config_data = dict(self.coordinator.config_entry.data)
                config_data["devices"] = self.coordinator.devices
                self.hass.config_entries.async_update_entry(self.coordinator.config_entry, data=config_data)
                _LOGGER.info(f"Updated priority for device {self._device_name} to {int(value)}")
                break


class PVOptimizerMinOnTimeNumber(CoordinatorEntity, NumberEntity):
    """Dynamic config number for minimum on time - dynamic config entity."""

    def __init__(self, coordinator: PVOptimizerCoordinator, device_name: str) -> None:
        """Initialize the min on time number."""
        super().__init__(coordinator)
        self._device_name = device_name
        self._attr_name = f"PVO {device_name} Min On Time"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{device_name}_min_on_time"
        self._attr_min_value = 0
        self._attr_max_value = 1440  # 24 hours in minutes
        self._attr_step = 1
        self._attr_unit_of_measurement = "min"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{coordinator.config_entry.entry_id}_{device_name}")},
            "name": f"PVO {device_name}",
            "manufacturer": "Custom",
            "model": "PV Appliance",
        }

    @property
    def native_value(self) -> float:
        """Return the current min on time value."""
        for device in self.coordinator.devices:
            if device[CONF_NAME] == self._device_name:
                return device.get(CONF_MIN_ON_TIME, 0)
        return 0

    async def async_set_native_value(self, value: float) -> None:
        """Set the min on time value."""
        for i, device in enumerate(self.coordinator.devices):
            if device[CONF_NAME] == self._device_name:
                self.coordinator.devices[i][CONF_MIN_ON_TIME] = int(value)
                config_data = dict(self.coordinator.config_entry.data)
                config_data["devices"] = self.coordinator.devices
                self.hass.config_entries.async_update_entry(self.coordinator.config_entry, data=config_data)
                _LOGGER.info(f"Updated min on time for device {self._device_name} to {int(value)} min")
                break


class PVOptimizerMinOffTimeNumber(CoordinatorEntity, NumberEntity):
    """Dynamic config number for minimum off time - dynamic config entity."""

    def __init__(self, coordinator: PVOptimizerCoordinator, device_name: str) -> None:
        """Initialize the min off time number."""
        super().__init__(coordinator)
        self._device_name = device_name
        self._attr_name = f"PVO {device_name} Min Off Time"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{device_name}_min_off_time"
        self._attr_min_value = 0
        self._attr_max_value = 1440  # 24 hours in minutes
        self._attr_step = 1
        self._attr_unit_of_measurement = "min"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{coordinator.config_entry.entry_id}_{device_name}")},
            "name": f"PVO {device_name}",
            "manufacturer": "Custom",
            "model": "PV Appliance",
        }

    @property
    def native_value(self) -> float:
        """Return the current min off time value."""
        for device in self.coordinator.devices:
            if device[CONF_NAME] == self._device_name:
                return device.get(CONF_MIN_OFF_TIME, 0)
        return 0

    async def async_set_native_value(self, value: float) -> None:
        """Set the min off time value."""
        for i, device in enumerate(self.coordinator.devices):
            if device[CONF_NAME] == self._device_name:
                self.coordinator.devices[i][CONF_MIN_OFF_TIME] = int(value)
                config_data = dict(self.coordinator.config_entry.data)
                config_data["devices"] = self.coordinator.devices
                self.hass.config_entries.async_update_entry(self.coordinator.config_entry, data=config_data)
                _LOGGER.info(f"Updated min off time for device {self._device_name} to {int(value)} min")
                break
