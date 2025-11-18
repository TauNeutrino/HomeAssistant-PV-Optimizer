"""Switches for PV Optimizer integration."""
import logging
from typing import Any, Dict, Optional

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    CONF_NAME,
    CONF_TYPE,
    CONF_SWITCH_ENTITY_ID,
    CONF_INVERT_SWITCH,
    TYPE_SWITCH,
    CONF_OPTIMIZATION_ENABLED,
)
from .coordinator import PVOptimizerCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches for PV Optimizer."""
    coordinator: PVOptimizerCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = []

    # Create switches for switch-type devices
    for device in coordinator.devices:
        if device[CONF_TYPE] == TYPE_SWITCH:
            entities.append(PVOptimizerSwitch(coordinator, device))

    # Create optimization enabled switches for all devices - dynamic config entities
    for device in coordinator.devices:
        device_name = device[CONF_NAME]
        entities.append(PVOptimizerOptimizationSwitch(coordinator, device_name))

    async_add_entities(entities)


class PVOptimizerSwitch(CoordinatorEntity, SwitchEntity):
    """Switch for PV Optimizer appliance."""

    def __init__(self, coordinator: PVOptimizerCoordinator, device: Dict[str, Any]) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._device = device
        self._device_name = device[CONF_NAME]
        self._switch_entity_id = device.get(CONF_SWITCH_ENTITY_ID)
        self._invert = device.get(CONF_INVERT_SWITCH, False)
        self._attr_name = f"PVO {self._device_name}"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{self._device_name}_switch"
        # Get device type for model
        device_type = self._device.get("type", "Unknown")
        
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{coordinator.config_entry.entry_id}_{self._device_name}")},
            "name": f"PVO {self._device_name}",
            "manufacturer": "PV Optimizer",
            "model": f"{device_type.capitalize()} Device",
        }

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        if not self._switch_entity_id:
            return False
        state = self.hass.states.get(self._switch_entity_id)
        if state:
            on_state = state.state == "on"
            return not on_state if self._invert else on_state
        return False

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        # This is for manual control; the coordinator handles optimization
        # But we can allow manual override
        target_state = "off" if self._invert else "on"
        await self.hass.services.async_call(
            "switch", "turn_on" if target_state == "on" else "turn_off",
            {"entity_id": self._switch_entity_id}
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        target_state = "on" if self._invert else "off"
        await self.hass.services.async_call(
            "switch", "turn_on" if target_state == "on" else "turn_off",
            {"entity_id": self._switch_entity_id}
        )


class PVOptimizerOptimizationSwitch(CoordinatorEntity, SwitchEntity):
    """Switch for enabling/disabling optimization for a device - dynamic config entity."""

    def __init__(self, coordinator: PVOptimizerCoordinator, device_name: str) -> None:
        """Initialize the optimization switch."""
        super().__init__(coordinator)
        self._device_name = device_name
        self._attr_name = f"PVO {device_name} Optimization Enabled"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{device_name}_optimization_enabled"
        # Get device type for model
        device_type = "Unknown"
        for device in coordinator.devices:
            if device[CONF_NAME] == device_name:
                device_type = device.get("type", "Unknown")
                break
        
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{coordinator.config_entry.entry_id}_{device_name}")},
            "name": f"PVO {device_name}",
            "manufacturer": "PV Optimizer",
            "model": f"{device_type.capitalize()} Device",
        }

    @property
    def is_on(self) -> bool:
        """Return true if optimization is enabled for this device."""
        # This solves the problem of allowing dynamic configuration of optimization enabled/disabled
        # by reading from the device config stored in the coordinator
        for device in self.coordinator.devices:
            if device[CONF_NAME] == self._device_name:
                return device.get(CONF_OPTIMIZATION_ENABLED, True)
        return True  # Default to enabled

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable optimization for this device."""
        # This solves the problem of dynamically updating device configuration
        # by modifying the config stored in the coordinator and config entry
        for i, device in enumerate(self.coordinator.devices):
            if device[CONF_NAME] == self._device_name:
                self.coordinator.devices[i][CONF_OPTIMIZATION_ENABLED] = True
                # Update config entry data
                config_data = dict(self.coordinator.config_entry.data)
                config_data["devices"] = self.coordinator.devices
                self.hass.config_entries.async_update_entry(self.coordinator.config_entry, data=config_data)
                _LOGGER.info(f"Enabled optimization for device: {self._device_name}")
                break

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable optimization for this device."""
        # This solves the problem of dynamically disabling optimization for a device
        for i, device in enumerate(self.coordinator.devices):
            if device[CONF_NAME] == self._device_name:
                self.coordinator.devices[i][CONF_OPTIMIZATION_ENABLED] = False
                # Update config entry data
                config_data = dict(self.coordinator.config_entry.data)
                config_data["devices"] = self.coordinator.devices
                self.hass.config_entries.async_update_entry(self.coordinator.config_entry, data=config_data)
                _LOGGER.info(f"Disabled optimization for device: {self._device_name}")
                break
