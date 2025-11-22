"""
Sensor Entities for PV Optimizer Integration - Multi-Config-Entry Architecture

This module creates sensors for both service and device entries:
- Service Entry: Global sensors (power budget, surplus, ideal device lists)
- Device Entry: Device-specific sensors (locked status, power, target state)
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
    ATTR_IS_LOCKED,
    ATTR_MEASURED_POWER_AVG,
    ATTR_PVO_LAST_TARGET_STATE,
    normalize_device_name,
)
from .coordinators import ServiceCoordinator, DeviceCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors for PV Optimizer."""
    entry_type = config_entry.data.get("entry_type")
    
    if entry_type == "service":
        # Service entry → create global sensors
        await _async_setup_service_sensors(hass, config_entry, async_add_entities)
    else:
        # Device entry → create device sensors
        await _async_setup_device_sensors(hass, config_entry, async_add_entities)


async def _async_setup_service_sensors(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up service sensors (global sensors)."""
    coordinator: ServiceCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    entities = [
        ServicePowerBudgetSensor(coordinator),
        ServiceSurplusAvgSensor(coordinator),
        ServiceSimulationBudgetSensor(coordinator),
        ServiceRealIdealDevicesSensor(coordinator),
        ServiceSimulationIdealDevicesSensor(coordinator),
    ]
    
    async_add_entities(entities)


async def _async_setup_device_sensors(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up device sensors."""
    coordinator: DeviceCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    entities = [
        DeviceLockedSensor(coordinator),
        DevicePowerSensor(coordinator),
        DeviceTargetStateSensor(coordinator),
    ]
    
    async_add_entities(entities)


# ============================================================================
# SERVICE SENSORS (Global)
# ============================================================================

class ServicePowerBudgetSensor(CoordinatorEntity, SensorEntity):
    """Power budget sensor for service."""
    
    _attr_has_entity_name = True
    _attr_translation_key = "power_budget"
    
    def __init__(self, coordinator: ServiceCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_power_budget"
        self._attr_native_unit_of_measurement = "W"
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_device_info = {
            "identifiers": {(DOMAIN, "service")},
            "name": "PV Optimizer",
            "manufacturer": "PV Optimizer",
            "model": "Service",
        }
    
    @property
    def native_value(self) -> float:
        """Return the power budget."""
        if self.coordinator.data:
            return round(self.coordinator.data.get("power_budget", 0), 1)
        return 0


class ServiceSurplusAvgSensor(CoordinatorEntity, SensorEntity):
    """Surplus average sensor for service."""
    
    _attr_has_entity_name = True
    _attr_translation_key = "surplus_avg"
    
    def __init__(self, coordinator: ServiceCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_surplus_avg"
        self._attr_native_unit_of_measurement = "W"
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_device_info = {
            "identifiers": {(DOMAIN, "service")},
        }
    
    @property
    def native_value(self) -> float:
        """Return the surplus average."""
        if self.coordinator.data:
            return round(self.coordinator.data.get("surplus_avg", 0), 1)
        return 0


class ServiceSimulationBudgetSensor(CoordinatorEntity, SensorEntity):
    """Simulation power budget sensor for service."""
    
    _attr_has_entity_name = True
    _attr_translation_key = "simulation_power_budget"
    
    def __init__(self, coordinator: ServiceCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_simulation_power_budget"
        self._attr_native_unit_of_measurement = "W"
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_device_info = {
            "identifiers": {(DOMAIN, "service")},
        }
    
    @property
    def native_value(self) -> float:
        """Return the simulation power budget."""
        if self.coordinator.data:
            return round(self.coordinator.data.get("simulation_power_budget", 0), 1)
        return 0


class ServiceRealIdealDevicesSensor(CoordinatorEntity, SensorEntity):
    """Real ideal devices list sensor for service."""
    
    _attr_has_entity_name = True
    _attr_translation_key = "real_ideal_devices"
    
    def __init__(self, coordinator: ServiceCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_real_ideal_devices"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, "service")},
        }
    
    @property
    def native_value(self) -> str:
        """Return the real ideal devices list."""
        if self.coordinator.data:
            devices = self.coordinator.data.get("ideal_on_list", [])
            return ", ".join(devices) if devices else "None"
        return "None"


class ServiceSimulationIdealDevicesSensor(CoordinatorEntity, SensorEntity):
    """Simulation ideal devices list sensor for service."""
    
    _attr_has_entity_name = True
    _attr_translation_key = "simulation_ideal_devices"
    
    def __init__(self, coordinator: ServiceCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_simulation_ideal_devices"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, "service")},
        }
    
    @property
    def native_value(self) -> str:
        """Return the simulation ideal devices list."""
        if self.coordinator.data:
            devices = self.coordinator.data.get("simulation_ideal_on_list", [])
            return ", ".join(devices) if devices else "None"
        return "None"


# ============================================================================
# DEVICE SENSORS (Per-Device)
# ============================================================================

class DeviceLockedSensor(CoordinatorEntity, SensorEntity):
    """Device locked status sensor."""
    
    _attr_has_entity_name = True
    _attr_translation_key = "is_locked"
    
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
    def native_value(self) -> bool:
        """Return the locked status."""
        if self.coordinator.data:
            return self.coordinator.data.get(ATTR_IS_LOCKED, False)
        return False
    
    @property
    def icon(self) -> str:
        """Return the icon."""
        return "mdi:lock" if self.native_value else "mdi:lock-open"


class DevicePowerSensor(CoordinatorEntity, SensorEntity):
    """Device measured power sensor."""
    
    _attr_has_entity_name = True
    _attr_translation_key = "measured_power_avg"
    
    def __init__(self, coordinator: DeviceCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_measured_power_avg"
        self._attr_native_unit_of_measurement = "W"
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT
        
        # Link to device
        device_name = coordinator.device_name
        normalized_name = normalize_device_name(device_name)
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{coordinator.config_entry.entry_id}_{normalized_name}")},
        }
    
    @property
    def native_value(self) -> float:
        """Return the measured power."""
        if self.coordinator.data:
            return round(self.coordinator.data.get(ATTR_MEASURED_POWER_AVG, 0), 1)
        return 0


class DeviceTargetStateSensor(CoordinatorEntity, SensorEntity):
    """Device target state sensor."""
    
    _attr_has_entity_name = True
    _attr_translation_key = "last_target_state"
    
    def __init__(self, coordinator: DeviceCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_last_target_state"
        
        # Link to device
        device_name = coordinator.device_name
        normalized_name = normalize_device_name(device_name)
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{coordinator.config_entry.entry_id}_{normalized_name}")},
        }
    
    @property
    def native_value(self) -> str:
        """Return the target state."""
        if self.coordinator.data:
            state = self.coordinator.data.get(ATTR_PVO_LAST_TARGET_STATE)
            if state is None:
                return "Unknown"
            return "On" if state else "Off"
        return "Unknown"
    
    @property
    def icon(self) -> str:
        """Return the icon."""
        value = self.native_value
        if value == "On":
            return "mdi:power-plug"
        elif value == "Off":
            return "mdi:power-plug-off"
        return "mdi:help-circle"
