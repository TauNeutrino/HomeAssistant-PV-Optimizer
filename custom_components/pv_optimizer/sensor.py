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
from homeassistant.helpers.entity import EntityCategory

from .const import (
    DOMAIN,
    CONF_NAME,
    ATTR_IS_LOCKED,
    ATTR_POWER_MEASURED_AVERAGE,
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
        DevicePowerSensor(coordinator),
        DeviceTargetStateSensor(coordinator),
        DeviceConfigurationSensor(coordinator),  # Shows all config including targets
    ]
    
    async_add_entities(entities)


# ============================================================================
# SERVICE SENSORS (Global)
# ============================================================================

class ServicePowerBudgetSensor(CoordinatorEntity, SensorEntity):
    """Power budget sensor for service."""
    
    _attr_has_entity_name = True
    _attr_name = "Power Budget"
    
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
    _attr_name = "Surplus Avg"
    
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
    _attr_name = "Simulation Power Budget"
    
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
    _attr_name = "Real Ideal Devices"
    
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
    
    @property
    def extra_state_attributes(self) -> dict:
        """Return device details for frontend display."""
        if not self.coordinator.data:
            return {"device_details": []}
        
        device_list = self.coordinator.data.get("ideal_on_list", [])
        device_details = []
        
        for device_name in device_list:
            coordinator = self.coordinator.device_coordinators.get(device_name)
            if coordinator:
                config = coordinator.device_config
                measured_power = coordinator.data.get("measured_power", 0) if coordinator.data else 0
                device_details.append({
                    "name": device_name,
                    "power": config.get("power", 0),
                    "measured_power": measured_power,
                    "priority": config.get("priority", 5),
                })
        
        return {"device_details": device_details}


class ServiceSimulationIdealDevicesSensor(CoordinatorEntity, SensorEntity):
    """Simulation ideal devices list sensor for service."""
    
    _attr_has_entity_name = True
    _attr_name = "Simulation Ideal Devices"
    
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
    
    @property
    def extra_state_attributes(self) -> dict:
        """Return device details for frontend display."""
        if not self.coordinator.data:
            return {"device_details": []}
        
        device_list = self.coordinator.data.get("simulation_ideal_on_list", [])
        device_details = []
        
        for device_name in device_list:
            coordinator = self.coordinator.device_coordinators.get(device_name)
            if coordinator:
                config = coordinator.device_config
                measured_power = coordinator.data.get("measured_power", 0) if coordinator.data else 0
                device_details.append({
                    "name": device_name,
                    "power": config.get("power", 0),
                    "measured_power": measured_power,
                    "priority": config.get("priority", 5),
                })
        
        return {"device_details": device_details}


# ============================================================================
# DEVICE SENSORS (Per-Device)
# ============================================================================

class DevicePowerSensor(CoordinatorEntity, SensorEntity):
    """Device measured power sensor."""
    
    _attr_has_entity_name = True
    _attr_name = "Measured Power Avg"
    
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
            return round(self.coordinator.data.get(ATTR_POWER_MEASURED_AVERAGE, 0), 1)
        return 0


class DeviceTargetStateSensor(CoordinatorEntity, SensorEntity):
    """Device target state sensor."""
    
    _attr_has_entity_name = True
    _attr_name = "Last Target State"
    
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


class DeviceConfigurationSensor(CoordinatorEntity, SensorEntity):
    """Device configuration summary sensor."""
    
    _attr_has_entity_name = True
    _attr_name = "Configuration"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    
    def __init__(self, coordinator: DeviceCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_configuration"
        
        # Link to device
        device_name = coordinator.device_name
        normalized_name = normalize_device_name(device_name)
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{coordinator.config_entry.entry_id}_{normalized_name}")},
        }
    
    @property
    def native_value(self) -> str:
        """Return configuration summary."""
        config = self.coordinator.device_config
        device_type = config.get("type", "unknown")
        
        if device_type == "switch":
            entity = config.get("switch_entity_id", "N/A")
            invert = "Yes" if config.get("invert_switch", False) else "No"
            return f"Type: Switch | Entity: {entity} | Invert: {invert}"
        elif device_type == "numeric":
            target_count = len(config.get("numeric_targets", []))
            return f"Type: Numeric | Targets: {target_count}"
        return f"Type: {device_type}"
    
    @property
    def extra_state_attributes(self) -> dict:
        """Return additional configuration details."""
        config = self.coordinator.device_config
        attrs = {
            "device_type": config.get("type"),
            "priority": config.get("priority"),
            "nominal_power": config.get("power"),
            "min_on_time": config.get("min_on_time", 0),
            "min_off_time": config.get("min_off_time", 0),
            "optimization_enabled": config.get("optimization_enabled", True),
            "simulation_active": config.get("simulation_active", False),
            # Dynamic state
            "is_locked": self.coordinator.device_state.get("is_locked", False),
            "is_locked_timing": self.coordinator.device_state.get("is_locked_timing", False),
            "is_locked_manual": self.coordinator.device_state.get("is_locked_manual", False),
        }
        
        # Add type-specific attributes
        if config.get("type") == "switch":
            attrs["switch_entity_id"] = config.get("switch_entity_id")
            attrs["invert_switch"] = config.get("invert_switch", False)
        elif config.get("type") == "numeric":
            targets = config.get("numeric_targets", [])
            attrs["numeric_targets_count"] = len(targets)
            for i, target in enumerate(targets):
                attrs[f"target_{i+1}_entity"] = target.get("numeric_entity_id")
                attrs[f"target_{i+1}_on_value"] = target.get("activated_value")
                attrs[f"target_{i+1}_off_value"] = target.get("deactivated_value")
        
        if config.get("measured_power_entity_id"):
            attrs["power_sensor"] = config.get("measured_power_entity_id")
            attrs["power_threshold"] = config.get("power_threshold", 100)
        
        return attrs
    
    @property
    def icon(self) -> str:
        """Return the icon."""
        return "mdi:cog"
