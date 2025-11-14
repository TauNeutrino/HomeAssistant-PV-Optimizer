"""Sensor platform for PV Optimizer."""
from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.const import UnitOfPower

from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    @callback
    def _add_sensors():
        # This is the main controller device
        controller_device_info = DeviceInfo(
            identifiers={(DOMAIN, "controller")},
            name="PV Optimizer Controller",
            manufacturer="PV Optimizer",
            model="Controller",
        )

        sensors = [
            PvoSurplusSensor(coordinator, controller_device_info),
            PvoPowerBudgetSensor(coordinator, controller_device_info),
            PvoAddedPowerSensor(coordinator, controller_device_info),
        ]

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

            sensors.extend([
                PvoDevicePowerSensor(coordinator, device_config, appliance_device_info),
                PvoDevicePrioritySensor(coordinator, device_config, appliance_device_info),
            ])
        async_add_entities(sensors)
    coordinator.register_add_entities_callback(_add_sensors)


class PvoBaseSensor(CoordinatorEntity, SensorEntity):
    """Base class for PV Optimizer sensors."""

    def __init__(self, coordinator):
        """Initialize the sensor."""
        super().__init__(coordinator)


class PvoSurplusSensor(PvoBaseSensor):
    """Representation of the PV Surplus Sensor."""

    def __init__(self, coordinator, device_info):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_device_info = device_info
        self._attr_name = "PV Optimizer Surplus"
        self._attr_unique_id = "pvo_surplus_power"
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_icon = "mdi:solar-power"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if self.coordinator.data and "surplus_power" in self.coordinator.data:
            return self.coordinator.data["surplus_power"]
        return None


class PvoPowerBudgetSensor(PvoBaseSensor):
    """Representation of the Power Budget Sensor."""

    def __init__(self, coordinator, device_info):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_device_info = device_info
        self._attr_name = "PV Optimizer Power Budget"
        self._attr_unique_id = "pvo_power_budget"
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_icon = "mdi:calculator"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if self.coordinator.data and "power_budget" in self.coordinator.data:
            return self.coordinator.data["power_budget"]
        return None


class PvoAddedPowerSensor(PvoBaseSensor):
    """Representation of the Added Power Sensor."""

    def __init__(self, coordinator, device_info):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_device_info = device_info
        self._attr_name = "PV Optimizer Added Power"
        self._attr_unique_id = "pvo_added_power"
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_icon = "mdi:power-plug"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if self.coordinator.data and "power_budget" in self.coordinator.data and "surplus_power" in self.coordinator.data:
            return self.coordinator.data["power_budget"] - self.coordinator.data["surplus_power"]
        return None


class PvoDeviceSensor(PvoBaseSensor):
    """Base class for appliance-specific sensors."""
    def __init__(self, coordinator, device_config, device_info):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_device_info = device_info
        self._device_name = device_config.name

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if self.coordinator.data and self._device_name in self.coordinator.data.get("devices", {}):
            return self.coordinator.data["devices"][self._device_name].get(self.entity_description.key)
        return None


class PvoDevicePowerSensor(PvoDeviceSensor):
    """Representation of a PVO-controlled device's power sensor."""

    def __init__(self, coordinator, device_config, device_info):
        """Initialize the sensor."""
        self.entity_description = SensorEntityDescription(
            key="power_consumption",
            native_unit_of_measurement=UnitOfPower.WATT,
        )
        super().__init__(coordinator, device_config, device_info)
        self._attr_name = f"PVO {self._device_name} Power"
        self._attr_unique_id = f"pvo_{self._device_name.lower().replace(' ', '_')}_power"


class PvoDevicePrioritySensor(PvoDeviceSensor):
    """Representation of a PVO-controlled device's priority sensor."""

    def __init__(self, coordinator, device_config, device_info):
        """Initialize the sensor."""
        self.entity_description = SensorEntityDescription(
            key="priority",
        )
        super().__init__(coordinator, device_config, device_info)
        self._attr_name = f"PVO {self._device_name} Priority"
        self._attr_unique_id = f"pvo_{self._device_name.lower().replace(' ', '_')}_priority"
