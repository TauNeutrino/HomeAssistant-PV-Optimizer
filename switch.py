"""
Switch Entities for PV Optimizer Integration - Multi-Config-Entry Architecture

This module creates switch entities for device entries only:
- Manual Control Switch (for switch-type devices)
- Optimization Enabled Switch (all devices)
- Simulation Active Switch (all devices)
"""

import logging
from typing import Any, Dict, Optional

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    DOMAIN,
    CONF_NAME,
    CONF_TYPE,
    CONF_SWITCH_ENTITY_ID,
    CONF_INVERT_SWITCH,
    TYPE_SWITCH,
    CONF_OPTIMIZATION_ENABLED,
    CONF_SIMULATION_ACTIVE,
    CONF_NUMERIC_TARGETS,
    TYPE_NUMERIC,
    CONF_NUMERIC_ENTITY_ID,
    CONF_ACTIVATED_VALUE,
    CONF_DEACTIVATED_VALUE,
    normalize_device_name,
)
from .coordinators import DeviceCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches for PV Optimizer device."""
    coordinator: DeviceCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    device_config = config_entry.data.get("device_config", {})
    device_type = device_config.get(CONF_TYPE)
    
    entities = []
    
    # Manual control switch (for ALL device types)
    entities.append(DeviceManualSwitch(coordinator))
    
    # Optimization enabled switch (all devices)
    entities.append(DeviceOptimizationSwitch(coordinator))
    
    # Simulation active switch (all devices)
    entities.append(DeviceSimulationSwitch(coordinator))
    
    async_add_entities(entities)


class DeviceManualSwitch(CoordinatorEntity, SwitchEntity):
    """Manual control switch for both switch-type and numeric-type devices."""
    
    _attr_has_entity_name = True
    _attr_translation_key = "manual_control"
    
    def __init__(self, coordinator: DeviceCoordinator) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        device_config = coordinator.device_config
        self._device_type = device_config.get(CONF_TYPE)
        
        # Switch specific config
        self._switch_entity_id = device_config.get(CONF_SWITCH_ENTITY_ID)
        self._invert = device_config.get(CONF_INVERT_SWITCH, False)
        
        # Numeric specific config
        self._numeric_targets = device_config.get(CONF_NUMERIC_TARGETS, [])
        
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_manual_control"
        
        # Link to device
        device_name = coordinator.device_name
        normalized_name = normalize_device_name(device_name)
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{coordinator.config_entry.entry_id}_{normalized_name}")},
        }
    
    @property
    def is_on(self) -> bool:
        """Return true if the device is effectively 'on'."""
        if self._device_type == TYPE_SWITCH:
            if not self._switch_entity_id:
                return False
            state = self.hass.states.get(self._switch_entity_id)
            if state:
                on_state = state.state == "on"
                return not on_state if self._invert else on_state
            return False
            
        elif self._device_type == TYPE_NUMERIC:
            # For numeric devices, consider it ON if ANY target matches its activated value
            for target in self._numeric_targets:
                entity_id = target[CONF_NUMERIC_ENTITY_ID]
                state = self.hass.states.get(entity_id)
                if state and state.state not in ['unknown', 'unavailable']:
                    try:
                        current_value = float(state.state)
                        if current_value == target[CONF_ACTIVATED_VALUE]:
                            return True
                    except (ValueError, TypeError):
                        continue
            return False
            
        return False
    
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        if self._device_type == TYPE_SWITCH:
            target_state = "off" if self._invert else "on"
            await self.hass.services.async_call(
                "switch", "turn_on" if target_state == "on" else "turn_off",
                {"entity_id": self._switch_entity_id}
            )
            
        elif self._device_type == TYPE_NUMERIC:
            # Set all numeric targets to their activated values
            for target in self._numeric_targets:
                entity_id = target[CONF_NUMERIC_ENTITY_ID]
                value = target[CONF_ACTIVATED_VALUE]
                await self.hass.services.async_call(
                    "number", "set_value",
                    {"entity_id": entity_id, "value": value}
                )
    
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        if self._device_type == TYPE_SWITCH:
            target_state = "on" if self._invert else "off"
            await self.hass.services.async_call(
                "switch", "turn_on" if target_state == "on" else "turn_off",
                {"entity_id": self._switch_entity_id}
            )
            
        elif self._device_type == TYPE_NUMERIC:
            # Set all numeric targets to their deactivated values
            for target in self._numeric_targets:
                entity_id = target[CONF_NUMERIC_ENTITY_ID]
                value = target[CONF_DEACTIVATED_VALUE]
                await self.hass.services.async_call(
                    "number", "set_value",
                    {"entity_id": entity_id, "value": value}
                )


class DeviceOptimizationSwitch(CoordinatorEntity, SwitchEntity, RestoreEntity):
    """Optimization enabled switch for device."""
    
    _attr_has_entity_name = True
    _attr_translation_key = "optimization_enabled"
    
    def __init__(self, coordinator: DeviceCoordinator) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_optimization_enabled"
        
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
            value = state.state == "on"
            self.coordinator.update_config(CONF_OPTIMIZATION_ENABLED, value)
            _LOGGER.debug(f"Restored optimization enabled for {self.coordinator.device_name}: {value}")
    
    @property
    def is_on(self) -> bool:
        """Return true if optimization is enabled."""
        return self.coordinator.device_config.get(CONF_OPTIMIZATION_ENABLED, True)
    
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable optimization."""
        self.coordinator.update_config(CONF_OPTIMIZATION_ENABLED, True)
        _LOGGER.info(f"Enabled optimization for device: {self.coordinator.device_name}")
        self.async_write_ha_state()
    
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable optimization."""
        self.coordinator.update_config(CONF_OPTIMIZATION_ENABLED, False)
        _LOGGER.info(f"Disabled optimization for device: {self.coordinator.device_name}")
        self.async_write_ha_state()


class DeviceSimulationSwitch(CoordinatorEntity, SwitchEntity, RestoreEntity):
    """Simulation active switch for device."""
    
    _attr_has_entity_name = True
    _attr_translation_key = "simulation_active"
    
    def __init__(self, coordinator: DeviceCoordinator) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_simulation_active"
        
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
            value = state.state == "on"
            self.coordinator.update_config(CONF_SIMULATION_ACTIVE, value)
            _LOGGER.debug(f"Restored simulation active for {self.coordinator.device_name}: {value}")
    
    @property
    def is_on(self) -> bool:
        """Return true if simulation is active."""
        return self.coordinator.device_config.get(CONF_SIMULATION_ACTIVE, False)
    
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable simulation."""
        self.coordinator.update_config(CONF_SIMULATION_ACTIVE, True)
        _LOGGER.info(f"Enabled simulation for device: {self.coordinator.device_name}")
        self.async_write_ha_state()
    
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable simulation."""
        self.coordinator.update_config(CONF_SIMULATION_ACTIVE, False)
        _LOGGER.info(f"Disabled simulation for device: {self.coordinator.device_name}")
        self.async_write_ha_state()
