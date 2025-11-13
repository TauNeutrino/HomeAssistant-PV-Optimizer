"""Switch platform for PV Überschuss Optimizer."""
from homeassistant.components.switch import SwitchEntity
from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the switch platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    @callback
    def _add_switches():
        async_add_entities([PvoDeviceSwitch(coordinator, device) for device in coordinator.devices])
    coordinator.register_add_entities_callback(_add_switches)


class PvoDeviceSwitch(CoordinatorEntity, SwitchEntity):
    """Representation of a PVO-controlled device switch."""

    def __init__(self, coordinator, device_info):
        """Initialize the switch."""
        super().__init__(coordinator)
        self.device_info = device_info
        self._device_name = device_info.name
        self._attr_name = f"PVO {self._device_name}"
        device_unique_id = f"pvo_device_{self._device_name.lower().replace(' ', '_')}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_unique_id)},
            # The name attribute is not needed here as it will be inherited from the device.
            # name=f"PVO {self._device_name}",
            # manufacturer="PV Optimizer",
            # via_device=(DOMAIN, "controller"),
        )
        # The switch itself should be for enabling/disabling automation
        self._attr_name = f"PVO {self._device_name} Automation"
        self._attr_unique_id = f"pvo_{self._device_name.lower().replace(' ', '_')}"
        # This switch will represent if the automation is enabled for this device
        self._attr_is_on = True # Default to enabled

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        await super().async_added_to_hass()
        # Store the entity_id in hass.data for the coordinator to find
        if self.unique_id:
            self.hass.data[DOMAIN][self.unique_id] = self.entity_id

    @property
    def is_on(self):
        """Return true if the switch is on."""
        # Here you would manage the state of whether this device is managed
        return self._attr_is_on

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        self._attr_is_on = False
        self.async_write_ha_state()