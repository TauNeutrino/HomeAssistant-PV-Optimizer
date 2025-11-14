"""The PV Optimizer Coordinator."""
from __future__ import annotations

import logging
from datetime import timedelta, datetime
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.entity import Entity # noqa: F401
from . import const

_LOGGER = logging.getLogger(__name__)

class PVOptimizerDevice:
    """A class to represent a single device controlled by the optimizer."""

    def __init__(self, hass: HomeAssistant, config: dict):
        self.hass = hass
        self.name = config.get(const.CONF_NAME)
        self.switch_entity_id = config.get(const.CONF_SWITCH_ENTITY_ID)
        self.power_sensor_entity_id = config.get(const.CONF_POWER_SENSOR_ENTITY_ID)
        self.priority = config.get(const.CONF_PRIORITY, const.DEFAULT_PRIORITY)
        self.nominal_power = config.get(const.CONF_NOMINAL_POWER)
        self.power_threshold = config.get(const.CONF_POWER_THRESHOLD, const.DEFAULT_POWER_THRESHOLD)
        self.duration_on = timedelta(minutes=config.get(const.CONF_DURATION_ON, const.DEFAULT_DURATION_ON))
        self.duration_off = timedelta(minutes=config.get(const.CONF_DURATION_OFF, const.DEFAULT_DURATION_OFF))
        self.invert_switch = config.get(const.CONF_INVERT_SWITCH, const.DEFAULT_INVERT_SWITCH)
        self.is_automation_enabled = True  # Default to enabled
        
        self.is_on = False
        self.is_locked = False
        self.should_be_on = False
        self.last_changed: datetime | None = None
        self.power_consumption = 0

    def update_state(self):
        """Update the state of the device."""
        switch_state = self.hass.states.get(self.switch_entity_id)
        if not switch_state:
            _LOGGER.warning("Switch entity not found: %s", self.switch_entity_id)
            return

        # Update power consumption
        self.power_consumption = 0
        if self.power_sensor_entity_id:
            power_state = self.hass.states.get(self.power_sensor_entity_id)
            if power_state and power_state.state not in ["unknown", "unavailable"]:
                try:
                    self.power_consumption = float(power_state.state)
                except (ValueError, TypeError):
                    _LOGGER.warning("Could not parse power sensor state for %s", self.name)
            else:
                _LOGGER.debug("Power sensor not available for %s", self.name)

        # Update is_on state
        current_is_on = False
        if self.power_sensor_entity_id:
            current_is_on = self.power_consumption > self.power_threshold
        else:
            current_is_on = switch_state.state == "on"
            if self.invert_switch:
                current_is_on = not current_is_on

        if self.is_on != current_is_on:
            _LOGGER.debug("Device %s changed state from %s to %s", self.name, self.is_on, current_is_on)
            self.last_changed = datetime.now()

        self.is_on = current_is_on

        # Update is_locked state
        if self.last_changed:
            time_since_change = datetime.now() - self.last_changed
            if self.is_on and self.duration_on > time_since_change:
                self.is_locked = True
            elif not self.is_on and self.duration_off > time_since_change:
                self.is_locked = True
            else:
                self.is_locked = False
        else:
            self.is_locked = False
        
        # If no power sensor, use nominal power when on
        if not self.power_sensor_entity_id:
            if self.is_on:
                self.power_consumption = self.nominal_power

class PVOptimizerCoordinator(DataUpdateCoordinator):
    """The PV Optimizer coordinator."""

    def __init__(self, hass: HomeAssistant, config: dict):
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=const.DOMAIN,
            update_interval=timedelta(seconds=config.get(const.CONF_POLLING_FREQUENCY, 60)),
        )
        self.pv_surplus_sensor = config.get(const.CONF_PV_SURPLUS_SENSOR)
        self._config = config
        self.devices: list[PVOptimizerDevice] = []
        self._async_add_entities_callbacks = []

    def register_add_entities_callback(self, async_add_entities):
        """Register a callback to add entities."""
        self._async_add_entities_callbacks.append(async_add_entities)

    async def async_initialize_devices_and_refresh(self):
        """Initialize devices and perform the first refresh."""
        _LOGGER.debug("Initializing PV Optimizer devices.")
        
        # Create device instances
        self.devices = [PVOptimizerDevice(self.hass, device_config) for device_config in self._config.get(const.CONF_DEVICES, [])]

        # Create entities for all platforms
        from .switch import PvoDeviceSwitch
        from .binary_sensor import PvoDeviceIsOnSensor, PvoDeviceIsLockedSensor, PvoDeviceShouldBeOnSensor
        from .sensor import PvoDevicePowerSensor, PvoDevicePrioritySensor

        for callback in self._async_add_entities_callbacks:
            callback()

        await self.async_config_entry_first_refresh()
    async def _async_update_data(self):
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        _LOGGER.debug("Starting PV Optimizer update cycle")

        # 1. Data Collection
        for device in self.devices:
            device.update_state()

        surplus_state = self.hass.states.get(self.pv_surplus_sensor)
        if not surplus_state or surplus_state.state in ["unknown", "unavailable"]:
            _LOGGER.warning("PV surplus sensor not available.")
            return self.data # Return old data if sensor is not available

        try:
            surplus_power = -float(surplus_state.state)
        except (ValueError, TypeError):
            _LOGGER.error("Could not parse PV surplus sensor state.")
            return self.data

        # 2. Budget Calculation
        running_managed_power = sum(d.power_consumption for d in self.devices if d.is_on and not d.is_locked)
        power_budget = surplus_power + running_managed_power
        _LOGGER.debug("Power budget: %s W", power_budget)

        # 3. Ideal State Calculation (Knapsack problem)
        
        # Devices that must be on because they are locked in 'on' state
        ideal_on_devices = {d for d in self.devices if d.is_on and d.is_locked}
        
        remaining_budget = power_budget - sum(d.power_consumption for d in ideal_on_devices)

        # Sort devices by priority
        sorted_devices = sorted([d for d in self.devices if d not in ideal_on_devices], key=lambda x: x.priority)

        # This is a simplified greedy approach. A full knapsack implementation is more complex.
        # For each priority, find the best combination of devices.
        for priority in sorted(list(set(d.priority for d in sorted_devices))):
            candidates = [d for d in sorted_devices if d.priority == priority]
            
            # Simple greedy choice: add devices if they fit in the budget
            for candidate in candidates:
                if remaining_budget >= candidate.nominal_power:
                    ideal_on_devices.add(candidate)
                    remaining_budget -= candidate.nominal_power

        for device in self.devices:
            device.should_be_on = device in ideal_on_devices

        # 4. Synchronization
        for device in self.devices:
            if device.is_automation_enabled and device.should_be_on and not device.is_on and not device.is_locked:
                _LOGGER.info("Turning on %s", device.name)
                await self.hass.services.async_call(
                    "switch",
                    "turn_on" if not device.invert_switch else "turn_off",
                    {"entity_id": device.switch_entity_id},
                    blocking=True
                )
            elif device.is_automation_enabled and not device.should_be_on and device.is_on and not device.is_locked:
                _LOGGER.info("Turning off %s", device.name)
                await self.hass.services.async_call(
                    "switch",
                    "turn_off" if not device.invert_switch else "turn_on",
                    {"entity_id": device.switch_entity_id},
                    blocking=True
                )

        # 5. Return data
        return {
            "devices": {
                device.name: {
                    "is_on": device.is_on,
                    "is_locked": device.is_locked,
                    "should_be_on": device.should_be_on,
                    "power_consumption": device.power_consumption,
                    "priority": device.priority,
                }
                for device in self.devices
            },
            "surplus_power": surplus_power,
            "power_budget": power_budget,
        }