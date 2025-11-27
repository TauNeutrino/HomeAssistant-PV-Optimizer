"""
Number Entities for PV Optimizer Integration - Multi-Config-Entry Architecture

This module creates number entities for device entries:
- Priority Number (all devices)
- Min On Time Number (all devices)
- Min Off Time Number (all devices)
- Target Value Numbers (numeric devices only)
"""

import logging
from typing import Any, Dict, Optional

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.entity import EntityCategory

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
    normalize_device_name,
)
from .coordinators import DeviceCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up numbers for PV Optimizer device."""
    coordinator: DeviceCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    device_config = config_entry.data.get("device_config", {})
    device_type = device_config.get(CONF_TYPE)
    
    entities = []
    
    # Priority number (all devices)
    entities.append(DevicePriorityNumber(coordinator))
    
    # Min on/off time numbers (all devices)
    entities.append(DeviceMinOnTimeNumber(coordinator))
    entities.append(DeviceMinOffTimeNumber(coordinator))
    
    # Note: Numeric devices do NOT need target number entities here
    # They control external number entities defined in numeric_targets config
    
    async_add_entities(entities)


class DevicePriorityNumber(CoordinatorEntity, NumberEntity, RestoreEntity):
    """Priority number for device."""
    
    _attr_has_entity_name = True
    _attr_name = "Priority"
    
    def __init__(self, coordinator: DeviceCoordinator) -> None:
        """Initialize the number."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_priority"
        self._attr_native_min_value = 1
        self._attr_native_max_value = 10
        self._attr_native_step = 1
        
        # Link to device
        device_name = coordinator.device_name
        device_type = coordinator.device_config.get(CONF_TYPE, "Unknown")
        normalized_name = normalize_device_name(device_name)
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{coordinator.config_entry.entry_id}_{normalized_name}")},
        }
    
    async def async_added_to_hass(self) -> None:
        """Restore state on startup."""
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if state and state.state not in ("unknown", "unavailable"):
            value = int(float(state.state))
            self.coordinator.update_config(CONF_PRIORITY, value)
            _LOGGER.debug(f"Restored priority for {self.coordinator.device_name}: {value}")
    
    @property
    def native_value(self) -> float:
        """Return the current priority."""
        return self.coordinator.device_config.get(CONF_PRIORITY, 5)
    
    async def async_set_native_value(self, value: float) -> None:
        """Set the priority."""
        self.coordinator.update_config(CONF_PRIORITY, int(value))
        _LOGGER.info(f"Updated priority for {self.coordinator.device_name} to {int(value)}")
        self.async_write_ha_state()


class DeviceMinOnTimeNumber(CoordinatorEntity, NumberEntity, RestoreEntity):
    """Minimum on time number for device."""
    
    _attr_has_entity_name = True
    _attr_name = "Min On Time"
    _attr_entity_category = EntityCategory.CONFIG
    
    def __init__(self, coordinator: DeviceCoordinator) -> None:
        """Initialize the number."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_min_on_time"
        self._attr_native_min_value = 0
        self._attr_native_max_value = 1440  # 24 hours in minutes
        self._attr_native_step = 1
        self._attr_native_unit_of_measurement = "min"
        
        # Link to device
        device_name = coordinator.device_name
        device_type = coordinator.device_config.get(CONF_TYPE, "Unknown")
        normalized_name = normalize_device_name(device_name)
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{coordinator.config_entry.entry_id}_{normalized_name}")},
        }
    
    async def async_added_to_hass(self) -> None:
        """Restore state on startup."""
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if state and state.state not in ("unknown", "unavailable"):
            value = int(float(state.state))
            self.coordinator.update_config(CONF_MIN_ON_TIME, value)
            _LOGGER.debug(f"Restored min on time for {self.coordinator.device_name}: {value}")
    
    @property
    def native_value(self) -> float:
        """Return the current min on time."""
        return self.coordinator.device_config.get(CONF_MIN_ON_TIME, 0)
    
    async def async_set_native_value(self, value: float) -> None:
        """Set the min on time."""
        self.coordinator.update_config(CONF_MIN_ON_TIME, int(value))
        _LOGGER.info(f"Updated min on time for {self.coordinator.device_name} to {int(value)} min")
        self.async_write_ha_state()


class DeviceMinOffTimeNumber(CoordinatorEntity, NumberEntity, RestoreEntity):
    """Minimum off time number for device."""
    
    _attr_has_entity_name = True
    _attr_name = "Min Off Time"
    _attr_entity_category = EntityCategory.CONFIG
    
    def __init__(self, coordinator: DeviceCoordinator) -> None:
        """Initialize the number."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_min_off_time"
        self._attr_native_min_value = 0
        self._attr_native_max_value = 1440  # 24 hours in minutes
        self._attr_native_step = 1
        self._attr_native_unit_of_measurement = "min"
        
        # Link to device
        device_name = coordinator.device_name
        device_type = coordinator.device_config.get(CONF_TYPE, "Unknown")
        normalized_name = normalize_device_name(device_name)
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{coordinator.config_entry.entry_id}_{normalized_name}")},
        }
    
    async def async_added_to_hass(self) -> None:
        """Restore state on startup."""
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if state and state.state not in ("unknown", "unavailable"):
            value = int(float(state.state))
            self.coordinator.update_config(CONF_MIN_OFF_TIME, value)
            _LOGGER.debug(f"Restored min off time for {self.coordinator.device_name}: {value}")
    
    @property
    def native_value(self) -> float:
        """Return the current min off time."""
        return self.coordinator.device_config.get(CONF_MIN_OFF_TIME, 0)
    
    async def async_set_native_value(self, value: float) -> None:
        """Set the min off time."""
        self.coordinator.update_config(CONF_MIN_OFF_TIME, int(value))
        _LOGGER.info(f"Updated min off time for {self.coordinator.device_name} to {int(value)} min")
        self.async_write_ha_state()


class DeviceTargetNumber(CoordinatorEntity, NumberEntity):
    """Target value number for numeric devices."""
    
    _attr_has_entity_name = True
    _attr_name = "Target Value"
    
    def __init__(self, coordinator: DeviceCoordinator, target: Dict[str, Any]) -> None:
        """Initialize the number."""
        super().__init__(coordinator)
        self._target = target
        self._numeric_entity_id = target[CONF_NUMERIC_ENTITY_ID]
        self._activated_value = target[CONF_ACTIVATED_VALUE]
        self._deactivated_value = target[CONF_DEACTIVATED_VALUE]
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{self._numeric_entity_id}_target"
        self._attr_native_min_value = min(self._activated_value, self._deactivated_value)
        self._attr_native_max_value = max(self._activated_value, self._deactivated_value)
        
        # Link to device
        device_name = coordinator.device_name
        device_type = coordinator.device_config.get(CONF_TYPE, "Unknown")
        normalized_name = normalize_device_name(device_name)
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{coordinator.config_entry.entry_id}_{normalized_name}")},
        }
    
    @property
    def native_value(self) -> float:
        """Return the current value."""
        state = self.hass.states.get(self._numeric_entity_id)
        return float(state.state) if state and state.state not in ['unknown', 'unavailable'] else 0.0
    
    async def async_set_native_value(self, value: float) -> None:
        """Set the value."""
        await self.hass.services.async_call(
            "number", "set_value",
            {"entity_id": self._numeric_entity_id, "value": value}
        )
        self.async_write_ha_state()
