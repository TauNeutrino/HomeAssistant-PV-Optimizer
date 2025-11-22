"""
Coordinators for PV Optimizer Integration - Multi-Config-Entry Architecture

This module defines two coordinator classes that work together to support the new
architecture where each device has its own config entry:

1. ServiceCoordinator: Manages global config and orchestrates optimization across all devices
2. DeviceCoordinator: Manages individual device state and entities

Architecture:
------------
Service Entry (entry_type="service")
  └── ServiceCoordinator
       ├── Global sensors (power budget, surplus)
       └── Orchestrates optimization across all device coordinators

Device Entry (entry_type="device") 
  └── DeviceCoordinator
       ├── Device entities (switches, numbers, sensors)
       └── Registers with service coordinator
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import entity_registry as er
from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.history import get_significant_states
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    CONF_SURPLUS_SENSOR_ENTITY_ID,
    CONF_INVERT_SURPLUS_VALUE,
    CONF_SLIDING_WINDOW_SIZE,
    CONF_OPTIMIZATION_CYCLE_TIME,
    CONF_NAME,
    CONF_PRIORITY,
    CONF_POWER,
    CONF_TYPE,
    CONF_SWITCH_ENTITY_ID,
    CONF_NUMERIC_TARGETS,
    CONF_NUMERIC_ENTITY_ID,
    CONF_ACTIVATED_VALUE,
    CONF_DEACTIVATED_VALUE,
    CONF_MIN_ON_TIME,
    CONF_MIN_OFF_TIME,
    CONF_OPTIMIZATION_ENABLED,
    CONF_SIMULATION_ACTIVE,
    CONF_MEASURED_POWER_ENTITY_ID,
    CONF_POWER_THRESHOLD,
    CONF_INVERT_SWITCH,
    TYPE_SWITCH,
    TYPE_NUMERIC,
    ATTR_PVO_LAST_TARGET_STATE,
    ATTR_IS_LOCKED,
    ATTR_MEASURED_POWER_AVG,
)
from .device import create_device, PVDevice

_LOGGER = logging.getLogger(__name__)


class DeviceCoordinator(DataUpdateCoordinator):
    """
    Coordinator for a single PV Optimizer device.
    
    Responsibilities:
    ----------------
    - Manage device state (on/off, power, lock status)
    - Provide device entities (switches, numbers, sensors)
    - Register with service coordinator for optimization
    - Track device state changes and min on/off times
    """

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the device coordinator."""
        device_config = config_entry.data.get("device_config", {})
        device_name = device_config.get(CONF_NAME, "Unknown")
        
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{device_name}",
            update_interval=timedelta(seconds=30),  # Device state updates every 30s
        )
        self.config_entry = config_entry
        self.device_config = device_config
        self.device_name = device_name
        
        # Device instance for state reading/control
        self.device_instance: Optional[PVDevice] = None
        
        # Device state cache
        self.device_state: Dict[str, Any] = {}
        self.state_changes: Dict[str, datetime] = {}
        
        # Service coordinator reference
 (set during registration)
        self.service_coordinator: Optional["ServiceCoordinator"] = None

    async def _async_update_data(self) -> Dict[str, Any]:
        """Update device state."""
        # Create device instance if needed
        if self.device_instance is None:
            self.device_instance = create_device(self.hass, self.device_config)
        
        if self.device_instance is None:
            _LOGGER.warning(f"Failed to create device instance for {self.device_name}")
            return {}
        
        now = dt_util.now()
        
        # Get current state
        is_on = self.device_instance.is_on()
        
        # Track state changes
        previous_state = self.device_state.get("is_on")
        if previous_state is not None and previous_state != is_on:
            if is_on:
                self.state_changes["last_on_time"] = now
            else:
                self.state_changes["last_off_time"] = now
            _LOGGER.info(f"Device {self.device_name} state changed to {'ON' if is_on else 'OFF'}")
        
        # Get service coordinator global config for averaging window
        global_config = {}
        if self.service_coordinator:
            global_config = self.service_coordinator.global_config
        
        # Calculate averaged power
        measured_power_avg = await self._get_averaged_power(now, global_config)
        
        # Determine lock status
        is_locked = self._is_device_locked(is_on, now)
        
        # Update state cache
        self.device_state = {
            "is_on": is_on,
            "measured_power_avg": measured_power_avg,
            ATTR_IS_LOCKED: is_locked,
            ATTR_PVO_LAST_TARGET_STATE: self.device_state.get(ATTR_PVO_LAST_TARGET_STATE, is_on),
            "last_update": now,
        }
        
        return self.device_state

    async def _get_averaged_power(self, now: datetime, global_config: Dict[str, Any]) -> float:
        """Get averaged power consumption over sliding window."""
        power_sensor = self.device_config.get(CONF_MEASURED_POWER_ENTITY_ID)
        if not power_sensor:
            return self.device_config.get(CONF_POWER, 0.0)
        
        window_minutes = global_config.get(CONF_SLIDING_WINDOW_SIZE, 5)
        start_time = now - timedelta(minutes=window_minutes)
        
        try:
            history = await get_instance(self.hass).async_add_executor_job(
                get_significant_states, self.hass, start_time, now, [power_sensor]
            )
            if power_sensor in history and history[power_sensor]:
                values = [float(state.state) for state in history[power_sensor] 
                         if state.state not in ['unknown', 'unavailable']]
                return sum(values) / len(values) if values else 0.0
        except Exception as e:
            _LOGGER.warning(f"Failed to get averaged power for {self.device_name}: {e}")
        
        # Fallback
        state = self.hass.states.get(power_sensor)
        return float(state.state) if state and state.state not in ['unknown', 'unavailable'] else 0.0

    def _is_device_locked(self, is_on: bool, now: datetime) -> bool:
        """Determine if device is locked in its current state."""
        # Check minimum on time
        if is_on:
            min_on_minutes = self.device_config.get(CONF_MIN_ON_TIME, 0)
            if min_on_minutes > 0:
                last_on_time = self.state_changes.get("last_on_time")
                if last_on_time:
                    time_on = (now - last_on_time).total_seconds() / 60
                    if time_on < min_on_minutes:
                        return True
        
        # Check minimum off time
        if not is_on:
            min_off_minutes = self.device_config.get(CONF_MIN_OFF_TIME, 0)
            if min_off_minutes > 0:
                last_off_time = self.state_changes.get("last_off_time")
                if last_off_time:
                    time_off = (now - last_off_time).total_seconds() / 60
                    if time_off < min_off_minutes:
                        return True
        
        # Check for manual intervention
        last_target = self.device_state.get(ATTR_PVO_LAST_TARGET_STATE)
        if last_target is not None and last_target != is_on:
            return True
        
        return False

    def update_config(self, key: str, value: Any) -> None:
        """Update device configuration in memory."""
        self.device_config[key] = value

    async def activate(self) -> None:
        """Activate the device."""
        if self.device_instance:
            await self.device_instance.activate()
            self.device_state[ATTR_PVO_LAST_TARGET_STATE] = True

    async def deactivate(self) -> None:
        """Deactivate the device."""
        if self.device_instance:
            await self.device_instance.deactivate()
            self.device_state[ATTR_PVO_LAST_TARGET_STATE] = False


class ServiceCoordinator(DataUpdateCoordinator):
    """
    Service coordinator for PV Optimizer.
    
    Responsibilities:
    ----------------
    - Manage global configuration (surplus sensor, cycle time, etc.)
    - Discover and register device coordinators
    - Run optimization algorithm across all devices
    - Provide global sensors (power budget, surplus, etc.)
    - Orchestrate device activation/deactivation
    """

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the service coordinator."""
        global_config = config_entry.data.get("global", {})
        
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=global_config.get(CONF_OPTIMIZATION_CYCLE_TIME, 60)),
        )
        self.config_entry = config_entry
        self.global_config = global_config
        
        # Registry of device coordinators
        self.device_coordinators: Dict[str, DeviceCoordinator] = {}

    def register_device_coordinator(self, device_coordinator: DeviceCoordinator) -> None:
        """Register a device coordinator for optimization."""
        device_name = device_coordinator.device_name
        self.device_coordinators[device_name] = device_coordinator
        device_coordinator.service_coordinator = self
        _LOGGER.info(f"Registered device coordinator: {device_name}")

    def unregister_device_coordinator(self, device_name: str) -> None:
        """Unregister a device coordinator."""
        if device_name in self.device_coordinators:
            del self.device_coordinators[device_name]
            _LOGGER.info(f"Unregistered device coordinator: {device_name}")

    async def async_set_config(self, data: Dict[str, Any]) -> None:
        """Update global configuration."""
        self.global_config.update(data)
        new_data = dict(self.config_entry.data)
        new_data["global"] = self.global_config
        self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)
        self.async_set_update_interval(timedelta(seconds=self.global_config[CONF_OPTIMIZATION_CYCLE_TIME]))

    async def _async_update_data(self) -> Dict[str, Any]:
        """
        Run optimization cycle across all registered devices.
        
        Returns global data for sensors.
        """
        # Collect device states from all device coordinators
        device_states = {}
        for device_name, coordinator in self.device_coordinators.items():
            if coordinator.data:
                device_states[device_name] = coordinator.data
            else:
                _LOGGER.warning(f"No data from device coordinator: {device_name}")
        
        # Run real optimization
        real_devices = [
            (name, state) for name, state in device_states.items()
            if self._get_device_config(name).get(CONF_OPTIMIZATION_ENABLED, True)
        ]
        real_power_budget = await self._calculate_power_budget(real_devices)
        real_ideal_list = await self._calculate_ideal_state(real_power_budget, real_devices)
        await self._synchronize_states(real_ideal_list, real_devices)
        
        # Run simulation optimization
        sim_devices = [
            (name, state) for name, state in device_states.items()
            if self._get_device_config(name).get(CONF_SIMULATION_ACTIVE, False)
        ]
        sim_power_budget = await self._calculate_power_budget(sim_devices)
        sim_ideal_list = await self._calculate_ideal_state(sim_power_budget, sim_devices)
        
        _LOGGER.info(
            f"Optimization cycle completed.\n"
            f"  Real: Budget={real_power_budget:.2f}W, Ideal devices={real_ideal_list}\n"
            f"  Simulation: Budget={sim_power_budget:.2f}W, Ideal devices={sim_ideal_list}"
        )
        
        # Return data for sensors
        surplus_avg = await self._get_averaged_surplus()
        
        return {
            "power_budget": max(0.0, real_power_budget),
            "surplus_avg": max(0.0, surplus_avg),
            "ideal_on_list": real_ideal_list,
            "simulation_power_budget": max(0.0, sim_power_budget),
            "simulation_ideal_on_list": sim_ideal_list,
            "last_update_timestamp": dt_util.now(),
        }

    def _get_device_config(self, device_name: str) -> Dict[str, Any]:
        """Get device config from coordinator."""
        coordinator = self.device_coordinators.get(device_name)
        return coordinator.device_config if coordinator else {}

    async def _calculate_power_budget(self, devices: List[tuple[str, Dict[str, Any]]]) -> float:
        """Calculate available power budget."""
        surplus_avg = await self._get_averaged_surplus()
        
        running_manageable_power = 0.0
        for device_name, state in devices:
            if state.get("is_on") and not state.get(ATTR_IS_LOCKED, False):
                config = self._get_device_config(device_name)
                power = state.get(ATTR_MEASURED_POWER_AVG, config.get(CONF_POWER, 0.0))
                running_manageable_power += power
        
        budget = surplus_avg + running_manageable_power
        _LOGGER.debug(f"Power budget: {surplus_avg:.2f}W surplus + {running_manageable_power:.2f}W running = {budget:.2f}W")
        return budget

    async def _calculate_ideal_state(self, power_budget: float, devices: List[tuple[str, Dict[str, Any]]]) -> List[str]:
        """Calculate ideal list of devices to turn on."""
        ideal_on_list = []
        remaining_budget = power_budget
        
        # Group by priority
        devices_by_priority = {}
        for device_name, state in devices:
            config = self._get_device_config(device_name)
            priority = config.get(CONF_PRIORITY, 5)
            if priority not in devices_by_priority:
                devices_by_priority[priority] = []
            devices_by_priority[priority].append((device_name, state, config))
        
        # Process priorities
        for priority in sorted(devices_by_priority.keys()):
            priority_devices = devices_by_priority[priority]
            selected = self._knapsack_select(priority_devices, remaining_budget)
            ideal_on_list.extend(selected)
            
            # Update budget
            for device_name in selected:
                _, _, config = next(d for d in priority_devices if d[0] == device_name)
                remaining_budget -= config.get(CONF_POWER, 0)
        
        return ideal_on_list

    def _knapsack_select(self, devices: List[tuple[str, Dict[str, Any], Dict[str, Any]]], budget: float) -> List[str]:
        """Select devices via greedy knapsack."""
        available = [(name, state, config) for name, state, config in devices 
                     if not state.get(ATTR_IS_LOCKED, False)]
        
        # Sort by power descending
        available.sort(key=lambda d: d[2].get(CONF_POWER, 0), reverse=True)
        
        selected = []
        for device_name, state, config in available:
            power = config.get(CONF_POWER, 0)
            if power <= budget:
                selected.append(device_name)
                budget -= power
        
        return selected

    async def _synchronize_states(self, ideal_on_list: List[str], devices: List[tuple[str, Dict[str, Any]]]) -> None:
        """Synchronize device states with ideal list."""
        for device_name, state in devices:
            coordinator = self.device_coordinators.get(device_name)
            if not coordinator:
                continue
            
            should_be_on = device_name in ideal_on_list
            currently_on = state.get("is_on", False)
            is_locked = state.get(ATTR_IS_LOCKED, False)
            
            if should_be_on and not currently_on and not is_locked:
                await coordinator.activate()
                _LOGGER.info(f"Activated device: {device_name}")
            elif not should_be_on and currently_on and not is_locked:
                await coordinator.deactivate()
                _LOGGER.info(f"Deactivated device: {device_name}")

    async def _get_averaged_surplus(self) -> float:
        """Get averaged PV surplus."""
        surplus_entity = self.global_config.get(CONF_SURPLUS_SENSOR_ENTITY_ID)
        if not surplus_entity:
            return 0.0
        
        invert_value = self.global_config.get(CONF_INVERT_SURPLUS_VALUE, False)
        window_minutes = self.global_config.get(CONF_SLIDING_WINDOW_SIZE, 5)
        now = dt_util.now()
        start_time = now - timedelta(minutes=window_minutes)
        
        try:
            history = await get_instance(self.hass).async_add_executor_job(
                get_significant_states, self.hass, start_time, now, [surplus_entity]
            )
            if surplus_entity in history and history[surplus_entity]:
                values = [float(state.state) for state in history[surplus_entity] 
                         if state.state not in ['unknown', 'unavailable']]
                avg = sum(values) / len(values) if values else 0.0
                if invert_value:
                    avg = avg * -1
                return avg
        except Exception as e:
            _LOGGER.warning(f"Failed to get averaged surplus: {e}")
        
        # Fallback
        state = self.hass.states.get(surplus_entity)
        current = float(state.state) if state and state.state not in ['unknown', 'unavailable'] else 0.0
        if invert_value:
            current = current * -1
        return current
