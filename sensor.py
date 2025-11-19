"""
Sensor Entities for PV Optimizer Integration

This module creates sensor entities for monitoring the optimization system
and individual device states.

Purpose:
--------
Provide comprehensive monitoring capabilities through Home Assistant's
sensor entities, enabling:
1. System-wide monitoring (power budget, surplus)
2. Per-device monitoring (lock status, power, targets)
3. Configuration visibility (window size, cycle time)
4. Historical data tracking

Sensor Categories:
-----------------
1. Controller Sensors (Global):
   - Power Budget: Total available power for optimization
   - Averaged Surplus: Smoothed PV surplus over sliding window
   - Current Surplus: Real-time surplus (sign-corrected)
   - Sliding Window Size: Configuration value
   - Cycle Time: Configuration value

2. Device Sensors (Per-Device):
   - Locked: Whether device is locked in current state
   - Measured Power Avg: Averaged power consumption
   - Last Target State: Last state set by optimizer
   - Contribution to Budget: Power contributed when running

Architecture:
------------
All sensors extend CoordinatorEntity to:
- Automatically update when coordinator refreshes
- Access coordinator data efficiently
- Link to appropriate parent device
- Maintain consistent state

Data Flow:
---------
1. Coordinator runs optimization cycle
2. Coordinator updates self.data dict with results
3. Coordinator updates self.device_states with device info
4. CoordinatorEntity triggers entity updates
5. Sensors read from coordinator data
6. Home Assistant displays updated values

Benefits:
--------
- Real-time monitoring without polling
- Historical data via recorder integration
- Ability to create dashboards and automations
- Debugging and tuning visibility
- Performance analysis

Design Pattern:
--------------
Uses Template Method pattern with base classes providing
common structure while allowing customization of:
- Data source (coordinator.data vs coordinator.device_states)
- State calculation
- Attributes assignment
- Device linkage
"""

import logging
from typing import Any, Dict, Optional

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    CONF_NAME,
    CONF_SURPLUS_SENSOR_ENTITY_ID,
    CONF_INVERT_SURPLUS_VALUE,
    CONF_SLIDING_WINDOW_SIZE,
    CONF_OPTIMIZATION_CYCLE_TIME,
    ATTR_IS_LOCKED,
    ATTR_MEASURED_POWER_AVG,
    ATTR_PVO_LAST_TARGET_STATE,
    normalize_device_name,
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
    entities.append(PVOptimizerControllerSensor(coordinator, "power_budget", "Power Budget", "W", 1))
    entities.append(PVOptimizerControllerSensor(coordinator, "surplus_avg", "Averaged Surplus", "W", 1))
    entities.append(PVOptimizerCurrentSurplusSensor(coordinator))
    entities.append(PVOptimizerConfigSensor(coordinator, "sliding_window", "Sliding Window Size", "min"))
    entities.append(PVOptimizerConfigSensor(coordinator, "cycle_time", "Optimization Cycle Time", "s"))

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

    def __init__(self, coordinator: PVOptimizerCoordinator, data_key: str, name: str, unit: Optional[str], decimals: Optional[int] = None) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._data_key = data_key
        self._decimals = decimals
        self._attr_name = f"PV Optimizer {name}"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{data_key}"
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = SensorDeviceClass.POWER if unit == "W" else None
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_entity_registry_enabled_default = True
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.config_entry.entry_id)},
            "name": "PV Optimizer Controller",
            "manufacturer": "Custom",
            "model": "PV Optimizer",
        }

    @property
    def state(self) -> Any:
        """Return the state of the sensor."""
        if self.coordinator.data is None:
            return 0
        value = self.coordinator.data.get(self._data_key, 0)
        if self._decimals is not None and value is not None:
            return round(value, self._decimals)
        return value


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
        self._attr_entity_registry_enabled_default = True
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


class PVOptimizerCurrentSurplusSensor(CoordinatorEntity, SensorEntity):
    """Sensor for current surplus value (sign-corrected)."""

    def __init__(self, coordinator: PVOptimizerCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_name = "PV Optimizer Current Surplus"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_current_surplus"
        self._attr_native_unit_of_measurement = "W"
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_entity_registry_enabled_default = True
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.config_entry.entry_id)},
            "name": "PV Optimizer Controller",
            "manufacturer": "Custom",
            "model": "PV Optimizer",
        }

    @property
    def state(self) -> Any:
        """Return the current surplus value (sign-corrected)."""
        surplus_entity = self.coordinator.global_config.get(CONF_SURPLUS_SENSOR_ENTITY_ID)
        if not surplus_entity:
            return 0
        
        state = self.hass.states.get(surplus_entity)
        if not state or state.state in ['unknown', 'unavailable']:
            return 0
        
        try:
            value = float(state.state)
            # Apply inversion if configured
            if self.coordinator.global_config.get(CONF_INVERT_SURPLUS_VALUE, False):
                value = value * -1
            return round(value, 1)
        except (ValueError, TypeError):
            return 0


class PVOptimizerConfigSensor(CoordinatorEntity, SensorEntity):
    """Read-only sensor for global configuration values."""

    def __init__(self, coordinator: PVOptimizerCoordinator, config_key: str, name: str, unit: str) -> None:
        """Initialize the config sensor."""
        super().__init__(coordinator)
        self._config_key = config_key
        self._attr_name = f"PV Optimizer {name}"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{config_key}"
        self._attr_native_unit_of_measurement = unit
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_entity_registry_enabled_default = True
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.config_entry.entry_id)},
            "name": "PV Optimizer Controller",
            "manufacturer": "Custom",
            "model": "PV Optimizer",
        }

    @property
    def state(self) -> Any:
        """Return the configuration value."""
        if self._config_key == "sliding_window":
            return self.coordinator.global_config.get(CONF_SLIDING_WINDOW_SIZE, 5)
        elif self._config_key == "cycle_time":
            return self.coordinator.global_config.get(CONF_OPTIMIZATION_CYCLE_TIME, 60)
        return None
