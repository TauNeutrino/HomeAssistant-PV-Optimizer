"""
Button Entities for PV Optimizer Integration.

This module creates button entities for devices to allow resetting internal state.
"""

import logging
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN, normalize_device_name
from .coordinators import DeviceCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up buttons for PV Optimizer."""
    entry_type = config_entry.data.get("entry_type")
    
    if entry_type == "device":
        coordinator: DeviceCoordinator = hass.data[DOMAIN][config_entry.entry_id]
        async_add_entities([DeviceResetButton(coordinator)])


class DeviceResetButton(CoordinatorEntity, ButtonEntity):
    """Button to reset device target state."""

    _attr_has_entity_name = True
    _attr_name = "Reset Target State"
    _attr_icon = "mdi:restore"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: DeviceCoordinator) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_reset_target_state"
        
        # Link to device
        device_name = coordinator.device_name
        normalized_name = normalize_device_name(device_name)
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{coordinator.config_entry.entry_id}_{normalized_name}")},
        }

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.coordinator.reset_target_state()
