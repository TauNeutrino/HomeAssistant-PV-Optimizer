"""Device classes for PV Optimizer integration."""
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
    """Base class for PV Optimizer devices."""

    def __init__(self, hass: HomeAssistant, device_config: Dict[str, Any]) -> None:
        """Initialize the device."""
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
    def get_power_consumption(self) -> float:
        """Return the current power consumption of the device."""
        pass


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
        """Return True if any of the numeric targets is at activated value or power threshold exceeded."""
        # This solves the problem of determining if a numeric device is 'on' based on target values
        # or measured power when available
        
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
        
        # Fallback to checking numeric targets
        for target in self.numeric_targets:
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

    def get_power_consumption(self) -> float:
        """Return power consumption - for numeric devices, this is typically from a separate sensor."""
        # This solves the problem of getting power data for numeric-controlled devices
        # Implementation would read from measured_power_entity_id if configured
        # For now, return nominal power or 0 if no sensor
        return self.config.get("power", 0.0)


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
