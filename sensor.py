"""
Sensor Entities for PV Optimizer Integration

UPDATED: Added sensors for simulation results
- simulation_power_budget: Budget available for simulation
- simulation_ideal_devices: List of devices in simulation ideal state
- real_ideal_devices: List of devices in real ideal state (for comparison)
"""

import logging
from typing import Any, Dict, List, Optional

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

    # Controller sensors (existing)
    entities.append(PVOptimizerControllerSensor(coordinator, "power_budget", "power_budget", "W", 1))
    entities.append(PVOptimizerControllerSensor(coordinator, "surplus_avg", "surplus_avg", "W", 1))
    entities.append(PVOptimizerCurrentSurplusSensor(coordinator))
    entities.append(PVOptimizerConfigSensor(coordinator, "sliding_window", "sliding_window", "min"))
    entities.append(PVOptimizerConfigSensor(coordinator, "cycle_time", "cycle_time", "s"))

    # NEW: Simulation sensors
    entities.append(PVOptimizerControllerSensor(coordinator, "simulation_power_budget", "simulation_power_budget", "W", 1))
    entities.append(PVOptimizerIdealDevicesListSensor(coordinator, "ideal_on_list", "real_ideal_devices"))
    entities.append(PVOptimizerIdealDevicesListSensor(coordinator, "simulation_ideal_on_list", "simulation_ideal_devices"))

    # Appliance sensors (existing) - monitoring entities
    for device in coordinator.devices:
        device_name = device[CONF_NAME]
        entities.append(PVOptimizerApplianceSensor(coordinator, device_name, ATTR_IS_LOCKED, "is_locked", None))
        entities.append(PVOptimizerApplianceSensor(coordinator, device_name, ATTR_MEASURED_POWER_AVG, "measured_power_avg", "W"))
        entities.append(PVOptimizerApplianceSensor(coordinator, device_name, ATTR_PVO_LAST_TARGET_STATE, "last_target_state", None))
        entities.append(PVOptimizerApplianceSensor(coordinator, device_name, "contribution_to_budget", "contribution_to_budget", "W"))

    async_add_entities(entities)


class PVOptimizerControllerSensor(CoordinatorEntity, SensorEntity):
    """Sensor for PV Optimizer controller."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: PVOptimizerCoordinator, data_key: str, translation_key: str, unit: Optional[str], decimals: Optional[int] = None) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._data_key = data_key
        self._decimals = decimals
        self._attr_translation_key = translation_key
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


class PVOptimizerIdealDevicesListSensor(CoordinatorEntity, SensorEntity):
    """
    Sensor for displaying ideal device lists (real or simulation).
    
    Purpose:
    -------
    Provides a sensor that shows which devices are in the ideal ON state.
    The list of device names is stored as an attribute for frontend display.
    The sensor state shows the count of devices.
    
    NEW: Created for simulation feature to display both real and simulation results.
    """

    _attr_has_entity_name = True

    def __init__(self, coordinator: PVOptimizerCoordinator, data_key: str, translation_key: str) -> None:
        """Initialize the ideal devices list sensor."""
        super().__init__(coordinator)
        self._data_key = data_key
        self._attr_translation_key = translation_key
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{data_key}_list"
        self._attr_icon = "mdi:format-list-checks"
        self._attr_entity_registry_enabled_default = True
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.config_entry.entry_id)},
            "name": "PV Optimizer Controller",
            "manufacturer": "Custom",
            "model": "PV Optimizer",
        }

    @property
    def state(self) -> int:
        """Return the count of devices in the ideal list."""
        if self.coordinator.data is None:
            return 0
        ideal_list = self.coordinator.data.get(self._data_key, [])
        return len(ideal_list)

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return the list of device names as attributes."""
        if self.coordinator.data is None:
            return {"devices": []}
        
        ideal_list = self.coordinator.data.get(self._data_key, [])
        
        # Get detailed device info for frontend display
        device_details = []
        for device_name in ideal_list:
            # Find device config
            device_config = next(
                (d for d in self.coordinator.devices if d[CONF_NAME] == device_name),
                None
            )
            if device_config:
                device_details.append({
                    "name": device_name,
                    "power": device_config.get("power", 0),
                    "priority": device_config.get("priority", 5),
                    "type": device_config.get("type", "unknown"),
                })
        
        return {
            "devices": ideal_list,  # Simple list for backwards compatibility
            "device_details": device_details,  # Detailed info for frontend
            "total_power": sum(d["power"] for d in device_details),
        }


class PVOptimizerApplianceSensor(CoordinatorEntity, SensorEntity):
    """Sensor for PV Optimizer appliance."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: PVOptimizerCoordinator, device_name: str, data_key: str, translation_key: str, unit: Optional[str]) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._device_name = device_name
        self._data_key = data_key
        self._attr_translation_key = translation_key
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
            if device_data.get("is_on") and not device_data.get(ATTR_IS_LOCKED, False):
                return device_data.get(ATTR_MEASURED_POWER_AVG, 0)
            return 0
        return None


class PVOptimizerCurrentSurplusSensor(CoordinatorEntity, SensorEntity):
    """Sensor for current surplus value (sign-corrected)."""

    _attr_has_entity_name = True
    _attr_translation_key = "current_surplus"

    def __init__(self, coordinator: PVOptimizerCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
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

    _attr_has_entity_name = True

    def __init__(self, coordinator: PVOptimizerCoordinator, config_key: str, translation_key: str, unit: str) -> None:
        """Initialize the config sensor."""
        super().__init__(coordinator)
        self._config_key = config_key
        self._attr_translation_key = translation_key
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
