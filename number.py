"""
Number Entities for PV Optimizer Integration

This module creates number entities that allow users to:
1. Control numeric device targets (for numeric-type devices)
2. Dynamically adjust device configuration (priority, min times)

Purpose:
--------
Provide interactive controls for both device operation and configuration
through Home Assistant's native number entity interface.

Entity Types Created:
--------------------
1. Numeric Target Controls (PVOptimizerNumber):
   - For numeric-type devices only
   - One number entity per configured target
   - Allows manual adjustment of target entity values
   - Example: Adjust heat pump temperature setpoint manually

2. Dynamic Configuration Numbers:
   - Priority (PVOptimizerPriorityNumber): Adjust device priority (1-10)
   - Min On Time (PVOptimizerMinOnTimeNumber): Adjust minimum on time
   - Min Off Time (PVOptimizerMinOffTimeNumber): Adjust minimum off time
   - Created for ALL devices (both switch and numeric types)
   - Changes persist to config entry and apply immediately

Architecture:
------------
All number entities extend CoordinatorEntity to:
- Receive updates when coordinator refreshes
- Link to parent device in device registry
- Maintain consistent state across entities

Dynamic Configuration Pattern:
-----------------------------
The dynamic configuration numbers (priority, min times) solve the problem
of allowing runtime adjustments without requiring integration reload.

Flow:
1. User adjusts number via UI
2. async_set_native_value() called
3. Value stored in coordinator.devices list
4. Config entry updated with new data
5. Changes take effect in next optimization cycle
6. No reload needed (unlike options flow changes)

Benefits:
- Immediate feedback
- No service interruption
- Easy experimentation with settings
- Fine-tuning without UI navigation

Device Linking:
--------------
All entities include device_info to link them to their parent device,
enabling proper organization in the device UI.
"""

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
    normalize_device_name,
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

    _attr_has_entity_name = True
    _attr_translation_key = "target_value"

    def __init__(self, coordinator: PVOptimizerCoordinator, device: Dict[str, Any], target: Dict[str, Any]) -> None:
        """Initialize the number."""
        super().__init__(coordinator)
        self._device = device
        self._target = target
        self._device_name = device[CONF_NAME]
        self._numeric_entity_id = target[CONF_NUMERIC_ENTITY_ID]
        self._activated_value = target[CONF_ACTIVATED_VALUE]
        self._deactivated_value = target[CONF_DEACTIVATED_VALUE]
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{self._device_name}_{self._numeric_entity_id}"
        self._attr_entity_registry_enabled_default = True
        # Get device type for model
        device_type = self._device.get("type", "Unknown")
        
        normalized_name = normalize_device_name(self._device_name)
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{coordinator.config_entry.entry_id}_{normalized_name}")},
            "name": f"PVO {self._device_name}",
            "manufacturer": "PV Optimizer",
            "model": f"{device_type.capitalize()} Device",
        }
        # Set min/max based on activated/deactivated values
        self._attr_min_value = min(self._activated_value, self._deactivated_value)
        self._attr_max_value = max(self._activated_value, self._deactivated_value)

    @property
    def native_value(self) -> float:
        """Return the current value."""
        state = self.hass.states.get(self._numeric_entity_id)
        return float(state.state) if state else 0.0

    async def async_set_native_value(self, value: float) -> None:
        """Set the value."""
        # This is for manual control; the coordinator handles optimization
        # But we can allow manual override
        await self.hass.services.async_call(
            "number", "set_value",
            {"entity_id": self._numeric_entity_id, "value": value}
        )
        # Force immediate state update in UI
        self.async_write_ha_state()
        # Trigger immediate optimization cycle
        await self.coordinator.async_request_refresh()


class PVOptimizerPriorityNumber(CoordinatorEntity, NumberEntity):
    """Dynamic config number for device priority - dynamic config entity."""

    _attr_has_entity_name = True
    _attr_translation_key = "priority"

    def __init__(self, coordinator: PVOptimizerCoordinator, device_name: str) -> None:
        """Initialize the priority number."""
        super().__init__(coordinator)
        self._device_name = device_name
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{device_name}_priority"
        self._attr_entity_registry_enabled_default = True
        self._attr_min_value = 1
        self._attr_max_value = 10
        self._attr_step = 1
        # Get device type for model
        device_type = "Unknown"
        for device in coordinator.devices:
            if device[CONF_NAME] == device_name:
                device_type = device.get("type", "Unknown")
                break
        
        normalized_name = normalize_device_name(device_name)
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{coordinator.config_entry.entry_id}_{normalized_name}")},
            "name": f"PVO {device_name}",
            "manufacturer": "PV Optimizer",
            "model": f"{device_type.capitalize()} Device",
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
                
                # Force immediate state update in UI
                self.async_write_ha_state()
                # Trigger immediate optimization cycle
                await self.coordinator.async_request_refresh()
                break


class PVOptimizerMinOnTimeNumber(CoordinatorEntity, NumberEntity):
    """Dynamic config number for minimum on time - dynamic config entity."""

    _attr_has_entity_name = True
    _attr_translation_key = "min_on_time"

    def __init__(self, coordinator: PVOptimizerCoordinator, device_name: str) -> None:
        """Initialize the min on time number."""
        super().__init__(coordinator)
        self._device_name = device_name
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{device_name}_min_on_time"
        self._attr_entity_registry_enabled_default = True
        self._attr_min_value = 0
        self._attr_max_value = 1440  # 24 hours in minutes
        self._attr_step = 1
        self._attr_unit_of_measurement = "min"
        # Get device type for model
        device_type = "Unknown"
        for device in coordinator.devices:
            if device[CONF_NAME] == device_name:
                device_type = device.get("type", "Unknown")
                break
        
        normalized_name = normalize_device_name(device_name)
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{coordinator.config_entry.entry_id}_{normalized_name}")},
            "name": f"PVO {device_name}",
            "manufacturer": "PV Optimizer",
            "model": f"{device_type.capitalize()} Device",
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
                
                # Force immediate state update in UI
                self.async_write_ha_state()
                # Trigger immediate optimization cycle
                await self.coordinator.async_request_refresh()
                break


class PVOptimizerMinOffTimeNumber(CoordinatorEntity, NumberEntity):
    """Dynamic config number for minimum off time - dynamic config entity."""

    _attr_has_entity_name = True
    _attr_translation_key = "min_off_time"

    def __init__(self, coordinator: PVOptimizerCoordinator, device_name: str) -> None:
        """Initialize the min off time number."""
        super().__init__(coordinator)
        self._device_name = device_name
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{device_name}_min_off_time"
        self._attr_entity_registry_enabled_default = True
        self._attr_min_value = 0
        self._attr_max_value = 1440  # 24 hours in minutes
        self._attr_step = 1
        self._attr_unit_of_measurement = "min"
        # Get device type for model
        device_type = "Unknown"
        for device in coordinator.devices:
            if device[CONF_NAME] == device_name:
                device_type = device.get("type", "Unknown")
                break
        
        normalized_name = normalize_device_name(device_name)
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{coordinator.config_entry.entry_id}_{normalized_name}")},
            "name": f"PVO {device_name}",
            "manufacturer": "PV Optimizer",
            "model": f"{device_type.capitalize()} Device",
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
                
                # Force immediate state update in UI
                self.async_write_ha_state()
                # Trigger immediate optimization cycle
                await self.coordinator.async_request_refresh()
                break
