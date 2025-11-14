"""Binary sensor platform for PV Optimizer."""
from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorEntityDescription
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the binary sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    @callback
    def _add_binary_sensors():
        binary_sensors = []

        # This is the main controller device
        controller_device_info = DeviceInfo(
            identifiers={(DOMAIN, "controller")},
            name="PV Optimizer Controller",
            manufacturer="PV Optimizer",
        )

        for device_config in coordinator.devices:
            device_name = device_config.name
            device_unique_id = f"pvo_device_{device_name.lower().replace(' ', '_')}"

            # Each appliance gets its own device entry
            appliance_device_info = DeviceInfo(
                identifiers={(DOMAIN, device_unique_id)},
                name=f"PVO {device_name}",
                manufacturer="PV Optimizer",
                model="Managed Load",
                via_device=(DOMAIN, "controller"), # Linked to the main controller
            )

            binary_sensors.extend([
                PvoDeviceIsOnSensor(coordinator, device_config, appliance_device_info),
                PvoDeviceIsLockedSensor(coordinator, device_config, appliance_device_info),
                PvoDeviceShouldBeOnSensor(coordinator, device_config, appliance_device_info),
            ])
        async_add_entities(binary_sensors)
    coordinator.register_add_entities_callback(_add_binary_sensors)


class PvoDeviceBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Base class for PV Optimizer binary sensors."""

    def __init__(self, coordinator, device_config, device_info):
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._device_name = device_config.name
        self._attr_device_info = device_info

    @property
    def is_on(self):
        """Return the state of the sensor."""
        if self.coordinator.data and self._device_name in self.coordinator.data.get("devices", {}):
            return self.coordinator.data["devices"][self._device_name].get(self.entity_description.key)
        return None


class PvoDeviceIsOnSensor(PvoDeviceBinarySensor):
    """Representation of whether the appliance switch is physically on."""
    def __init__(self, coordinator, device_config, device_info):
        self.entity_description = BinarySensorEntityDescription(key="is_on")
        super().__init__(coordinator, device_config, device_info)
        self._attr_name = f"PVO {self._device_name} Is On"
        self._attr_unique_id = f"pvo_{self._device_name.lower().replace(' ', '_')}_is_on"


class PvoDeviceIsLockedSensor(PvoDeviceBinarySensor):
    """Representation of whether the appliance is locked by min_on/off_time."""
    def __init__(self, coordinator, device_config, device_info):
        self.entity_description = BinarySensorEntityDescription(key="is_locked")
        super().__init__(coordinator, device_config, device_info)
        self._attr_name = f"PVO {self._device_name} Is Locked"
        self._attr_unique_id = f"pvo_{self._device_name.lower().replace(' ', '_')}_is_locked"


class PvoDeviceShouldBeOnSensor(PvoDeviceBinarySensor):
    """Representation of whether the appliance should be on according to the optimizer."""
    def __init__(self, coordinator, device_config, device_info):
        self.entity_description = BinarySensorEntityDescription(key="should_be_on")
        super().__init__(coordinator, device_config, device_info)
        self._attr_name = f"PVO {self._device_name} Should Be On"
        self._attr_unique_id = f"pvo_{self._device_name.lower().replace(' ', '_')}_should_be_on"
