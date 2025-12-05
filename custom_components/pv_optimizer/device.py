"""
Device Classes for PV Optimizer Integration

This module implements the device abstraction layer, providing a unified
interface for controlling different types of devices (switch-based and
numeric-based).

Purpose:
--------
Abstract the differences between device types behind a common interface,
allowing the coordinator to control any device type uniformly without
knowing the implementation details.

Architecture:
------------
Uses the Strategy Pattern with an abstract base class and concrete
implementations for each device type.

Class Hierarchy:
---------------
PVDevice (Abstract Base Class)
├── SwitchDevice: Controls ON/OFF devices via switch entities
└── NumericDevice: Controls devices by setting numeric values

Design Benefits:
---------------
1. Polymorphism: Coordinator treats all devices uniformly
2. Extensibility: Easy to add new device types
3. Encapsulation: Device-specific logic hidden from coordinator
4. Testability: Each device type can be tested independently

Device Types Explained:
----------------------
1. Switch Device:
   - Controls a switch entity (on/off)
   - Example: Hot water heater, washing machine
   - Activation: Turn switch ON
   - Deactivation: Turn switch OFF
   - Optional invert logic for reversed switches

2. Numeric Device:
   - Controls one or more numeric entities (set values)
   - Example: Heat pump temperature setpoints
   - Activation: Set numeric entities to "activated" values
   - Deactivation: Set numeric entities to "deactivated" values
   - Supports up to 5 numeric targets per device

Common Functionality:
--------------------
All devices support:
- Power threshold-based state detection
- Integration with measured power sensors
- Abstracted activation/deactivation
- Uniform state checking (is_on)
- Power consumption reporting

Factory Pattern:
---------------
The create_device() factory function instantiates the appropriate
device subclass based on configuration, simplifying device creation
in the coordinator.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_TYPE,
    CONF_SWITCH_ENTITY_ID,
    CONF_INVERT_SWITCH,
    CONF_NUMERIC_TARGETS,
    CONF_NUMERIC_ENTITY_ID,
    CONF_ACTIVATED_VALUE,
    CONF_DEACTIVATED_VALUE,
    CONF_MEASURED_POWER_ENTITY_ID,
    CONF_POWER_THRESHOLD,
    TYPE_SWITCH,
    TYPE_NUMERIC,
)

_LOGGER = logging.getLogger(__name__)


class PVDevice(ABC):
    """
    Abstract base class for PV Optimizer devices.
    
    Defines the interface that all device types must implement,
    ensuring uniform control from the coordinator regardless of
    the underlying device type.
    
    This abstraction solves the problem of controlling heterogeneous
    devices (switches, numeric controls, etc.) through a single,
    consistent interface.
    
    Required Methods (must be implemented by subclasses):
    ----------------------------------------------------
    - activate(): Turn device on or set to activated values
    - deactivate(): Turn device off or set to deactivated values
    - is_on(): Determine if device is currently active
    - get_power_consumption(): Report current power usage
    
    Common Functionality (provided by base class):
    ----------------------------------------------
    - Configuration storage
    - Home Assistant integration
    - Entity registry access
    """

    def __init__(self, hass: HomeAssistant, device_config: Dict[str, Any]) -> None:
        """
        Initialize the device base class.
        
        Stores common configuration and references needed by all
        device types.
        
        Args:
            hass: Home Assistant instance for service calls and state access
            device_config: Device configuration dict with type-specific settings
        """
        self.hass = hass
        self.config = device_config
        self.name = device_config["name"]
        self.entity_registry = er.async_get(hass)

    @abstractmethod
    async def activate(self) -> None:
        """Activate the device (turn on or set to activated value)."""
        pass

    @abstractmethod
    async def deactivate(self) -> None:
        """Deactivate the device (turn off or set to deactivated value)."""
        pass

    @abstractmethod
    def is_on(self) -> bool:
        """Return True if the device is currently on/active."""
        pass

    @abstractmethod
    def is_off(self) -> bool:
        """Return True if the device is currently off/inactive."""
        pass

    @abstractmethod
    def get_power_consumption(self) -> float:
        """Return the current power consumption of the device."""
        pass

    def get_state_details(self) -> str:
        """Return details about the current state (useful for debugging indeterminate states)."""
        return ""


class SwitchDevice(PVDevice):
    """Device that controls a switch entity."""

    def __init__(self, hass: HomeAssistant, device_config: Dict[str, Any]) -> None:
        """Initialize the switch device."""
        super().__init__(hass, device_config)
        self.switch_entity_id = device_config[CONF_SWITCH_ENTITY_ID]
        self.invert = device_config.get(CONF_INVERT_SWITCH, False)

    async def activate(self) -> None:
        """Activate the switch device."""
        # This solves the problem of handling inverted switches where 'off' means activated
        target_state = "off" if self.invert else "on"
        await self.hass.services.async_call(
            "switch", f"turn_{target_state}",
            {"entity_id": self.switch_entity_id}
        )
        _LOGGER.debug(f"Activated switch device {self.name}: set {self.switch_entity_id} to {target_state}")

    async def deactivate(self) -> None:
        """Deactivate the switch device."""
        # This solves the problem of handling inverted switches where 'on' means deactivated
        target_state = "on" if self.invert else "off"
        await self.hass.services.async_call(
            "switch", f"turn_{target_state}",
            {"entity_id": self.switch_entity_id}
        )
        _LOGGER.debug(f"Deactivated switch device {self.name}: set {self.switch_entity_id} to {target_state}")

    def is_on(self) -> bool:
        """Return True if the switch is on (considering invert flag and power threshold)."""
        # This solves the problem of correctly determining device state with potential inversion
        # and using power threshold when a power sensor is available
        
        # First check if we have a power sensor and should use power threshold
        power_sensor = self.config.get(CONF_MEASURED_POWER_ENTITY_ID)
        power_threshold = self.config.get(CONF_POWER_THRESHOLD, 100)
        
        if power_sensor:
            power_state = self.hass.states.get(power_sensor)
            if power_state and power_state.state not in ['unknown', 'unavailable']:
                try:
                    current_power = float(power_state.state)
                    is_on_by_power = current_power > power_threshold
                    _LOGGER.debug(f"Device {self.name} power-based state: {current_power}W > {power_threshold}W = {is_on_by_power}")
                    return is_on_by_power
                except (ValueError, TypeError):
                    _LOGGER.warning(f"Could not parse power value for {self.name}: {power_state.state}")
        
        # Fallback to switch state
        state = self.hass.states.get(self.switch_entity_id)
        if state is None:
            return False
        on_state = state.state == "on"
        return not on_state if self.invert else on_state

    def is_off(self) -> bool:
        """Return True if the switch is off."""
        return not self.is_on()

    def get_power_consumption(self) -> float:
        """Return power consumption - for switches, this is typically from a separate sensor."""
        # This solves the problem of getting power data for switch-controlled devices
        # Implementation would read from measured_power_entity_id if configured
        # For now, return nominal power or 0 if no sensor
        return self.config.get("power", 0.0)


class NumericDevice(PVDevice):
    """Device that controls numeric entities (number/input_number)."""

    def __init__(self, hass: HomeAssistant, device_config: Dict[str, Any]) -> None:
        """Initialize the numeric device."""
        super().__init__(hass, device_config)
        self.numeric_targets = device_config[CONF_NUMERIC_TARGETS]

    async def activate(self) -> None:
        """Activate the numeric device by setting targets to activated values."""
        # This solves the problem of controlling multiple numeric entities for one device
        for target in self.numeric_targets:
            entity_id = target[CONF_NUMERIC_ENTITY_ID]
            value = target[CONF_ACTIVATED_VALUE]
            await self.hass.services.async_call(
                "number", "set_value",
                {"entity_id": entity_id, "value": value}
            )
            _LOGGER.debug(f"Activated numeric device {self.name}: set {entity_id} to {value}")

    async def deactivate(self) -> None:
        """Deactivate the numeric device by setting targets to deactivated values."""
        # This solves the problem of resetting multiple numeric entities when deactivating
        for target in self.numeric_targets:
            entity_id = target[CONF_NUMERIC_ENTITY_ID]
            value = target[CONF_DEACTIVATED_VALUE]
            await self.hass.services.async_call(
                "number", "set_value",
                {"entity_id": entity_id, "value": value}
            )
            _LOGGER.debug(f"Deactivated numeric device {self.name}: set {entity_id} to {value}")

    def is_on(self) -> bool:
        """Return True ONLY if ALL numeric targets match the activated value."""
        # Strict check: All targets must match activated_value
        for target in self.numeric_targets:
            entity_id = target[CONF_NUMERIC_ENTITY_ID]
            state = self.hass.states.get(entity_id)
            
            if not state or state.state in ['unknown', 'unavailable']:
                return False
                
            try:
                current_value = float(state.state)
                # Use a small epsilon for float comparison if needed, but exact match is usually fine for setpoints
                if current_value != target[CONF_ACTIVATED_VALUE]:
                    return False
            except (ValueError, TypeError):
                return False
                
        return True

    def is_off(self) -> bool:
        """Return True ONLY if ALL numeric targets match the deactivated value."""
        # Strict check: All targets must match deactivated_value
        for target in self.numeric_targets:
            entity_id = target[CONF_NUMERIC_ENTITY_ID]
            state = self.hass.states.get(entity_id)
            
            if not state or state.state in ['unknown', 'unavailable']:
                return False
                
            try:
                current_value = float(state.state)
                if current_value != target[CONF_DEACTIVATED_VALUE]:
                    return False
            except (ValueError, TypeError):
                return False
                
        return True

    def get_power_consumption(self) -> float:
        """Return power consumption - for numeric devices, this is typically from a separate sensor."""
        # This solves the problem of getting power data for numeric-controlled devices
        # Implementation would read from measured_power_entity_id if configured
        # For now, return nominal power or 0 if no sensor
        return self.config.get("power", 0.0)

    def get_state_details(self) -> str:
        """Return details about current numeric values - only showing mismatches."""
        details = []
        for target in self.numeric_targets:
            entity_id = target[CONF_NUMERIC_ENTITY_ID]
            state = self.hass.states.get(entity_id)
            if not state:
                continue
                
            try:
                current = float(state.state)
            except (ValueError, TypeError):
                continue
                
            active = target[CONF_ACTIVATED_VALUE]
            inactive = target[CONF_DEACTIVATED_VALUE]
            
            # Only include if current value doesn't match either target
            if current != active and current != inactive:
                # Extract friendly name from entity_id (e.g., "temperature" from "number.device_temperature")
                entity_name = entity_id.split('.')[-1].replace('_', ' ').title()
                details.append(f"• {entity_name}: {current} (needs {active} or {inactive})")
                
        if not details:
            return "All values match expected states"
        
        # Format with header and bullet points
        return "Manual Override - Custom Values Set:\n" + "\n".join(details)


def create_device(hass: HomeAssistant, device_config: Dict[str, Any]) -> Optional[PVDevice]:
    """Factory function to create the appropriate device instance."""
    # This solves the problem of instantiating the correct device subclass based on type
    device_type = device_config.get(CONF_TYPE)
    if device_type == TYPE_SWITCH:
        return SwitchDevice(hass, device_config)
    elif device_type == TYPE_NUMERIC:
        return NumericDevice(hass, device_config)
    else:
        _LOGGER.error(f"Unknown device type: {device_type}")
        return None
