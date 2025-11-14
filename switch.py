"""Switch platform for PV Überschuss Optimizer."""
from homeassistant.components.switch import SwitchEntity
from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import const


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the switch platform."""
    coordinator = hass.data[const.DOMAIN][entry.entry_id]

    @callback
    def _add_switches():
        async_add_entities([PvoDeviceSwitch(coordinator, device) for device in coordinator.devices])
    coordinator.register_add_entities_callback(_add_switches)


class PvoDeviceSwitch(CoordinatorEntity, SwitchEntity):
    """Representation of a PVO-controlled device switch."""

    def __init__(self, coordinator, pvo_device):
        """Initialize the switch."""
        super().__init__(coordinator)
        self.pvo_device = pvo_device
        self._device_name = pvo_device.name
        device_unique_id = f"pvo_device_{self._device_name.lower().replace(' ', '_')}"
        self._attr_device_info = DeviceInfo(
            identifiers={(const.DOMAIN, device_unique_id)},
            # The name attribute is not needed here as it will be inherited from the device.
            # name=f"PVO {self._device_name}",
            manufacturer="PV Optimizer",
            via_device=(const.DOMAIN, "controller"),
        )
        # The switch itself should be for enabling/disabling automation
        self._attr_name = f"PVO {self._device_name} Automation"
        self._attr_unique_id = f"pvo_{self._device_name.lower().replace(' ', '_')}_automation"

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        await super().async_added_to_hass()
        # Store the entity_id in hass.data for the coordinator to find
        if self.unique_id: # This check is not strictly necessary as unique_id is always set.
            self.hass.data[const.DOMAIN][self.unique_id] = self.entity_id

    @property
    def is_on(self):
        """Return true if the switch is on."""
        # The state is managed in the PVOptimizerDevice object
        return self.pvo_device.is_automation_enabled

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        self.pvo_device.is_automation_enabled = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        self.pvo_device.is_automation_enabled = False
        self.async_write_ha_state()