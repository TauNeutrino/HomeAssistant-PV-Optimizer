"""
Binary Sensor Entities for PV Optimizer Integration.

This module creates binary sensors for device lock status:
- Timing Lock: Locked due to min on/off time
- Manual Lock: Locked due to user intervention
"""

import logging
from typing import Any, Dict, Optional

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import EntityCategory

from .const import (
    DOMAIN,
    ATTR_IS_LOCKED,
    normalize_device_name,
)
from .coordinators import DeviceCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensors for PV Optimizer."""
    entry_type = config_entry.data.get("entry_type")
    
    if entry_type == "device":
        # Device entry → create device binary sensors
        await _async_setup_device_binary_sensors(hass, config_entry, async_add_entities)


async def _async_setup_device_binary_sensors(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up device binary sensors."""
    coordinator: DeviceCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    entities = [
        DeviceLockedBinarySensor(coordinator),
        DeviceTimingLockBinarySensor(coordinator),
        DeviceManualLockBinarySensor(coordinator),
    ]
    
    async_add_entities(entities)


class DeviceLockedBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor for overall lock status."""
    
    _attr_has_entity_name = True
    _attr_translation_key = "is_locked"
    _attr_name = "Locked"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    
    def __init__(self, coordinator: DeviceCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_is_locked"
        
        # Link to device
        device_name = coordinator.device_name
        normalized_name = normalize_device_name(device_name)
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{coordinator.config_entry.entry_id}_{normalized_name}")},
        }
    
    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        if self.coordinator.data:
            return self.coordinator.data.get(ATTR_IS_LOCKED, False)
        return False
    
    @property
    def icon(self) -> str:
        """Return the icon."""
        return "mdi:lock" if self.is_on else "mdi:lock-open"


class DeviceTimingLockBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor for timing lock status."""
    
    _attr_has_entity_name = True
    _attr_translation_key = "timing_lock"
    _attr_name = "Timing Lock"  # Explicit name fallback
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    
    def __init__(self, coordinator: DeviceCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_timing_lock"
        
        # Link to device
        device_name = coordinator.device_name
        normalized_name = normalize_device_name(device_name)
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{coordinator.config_entry.entry_id}_{normalized_name}")},
        }
    
    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        if self.coordinator.data:
            return self.coordinator.data.get("is_locked_timing", False)
        return False
    
    @property
    def icon(self) -> str:
        """Return the icon."""
        return "mdi:timer-lock" if self.is_on else "mdi:timer-outline"


class DeviceManualLockBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor for manual lock status."""
    
    _attr_has_entity_name = True
    _attr_translation_key = "manual_lock"
    _attr_name = "Manual Lock"  # Explicit name fallback
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    
    def __init__(self, coordinator: DeviceCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_manual_lock"
        
        # Link to device
        device_name = coordinator.device_name
        normalized_name = normalize_device_name(device_name)
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{coordinator.config_entry.entry_id}_{normalized_name}")},
        }
    
    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        if self.coordinator.data:
            return self.coordinator.data.get("is_locked_manual", False)
        return False
    
    @property
    def icon(self) -> str:
        """Return the icon."""
        return "mdi:account-lock" if self.is_on else "mdi:account"
