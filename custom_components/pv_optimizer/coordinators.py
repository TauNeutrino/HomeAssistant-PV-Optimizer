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
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.storage import Store
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
    CONF_DEVICE_COLOR,
    TYPE_SWITCH,
    TYPE_NUMERIC,
    ATTR_PVO_LAST_TARGET_STATE,
    ATTR_IS_LOCKED,
    ATTR_POWER_MEASURED_AVERAGE,
    normalize_device_name,
    DEVICE_COLORS,
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
        # Create a copy to ensure we don't modify config_entry.data in place
        # This ensures async_update_entry detects changes correctly
        device_config = dict(device_config)
        device_name = device_config.get(CONF_NAME, "Unknown")
        
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{device_name}",
            update_interval=timedelta(seconds=10),  # Device state updates every 10s
        )
        self.config_entry = config_entry
        self.device_config = device_config
        self.device_name = device_name
        self.device_id = None  # Will be populated on first update
        
        # Backwards compatibility: Assign random color if not present
        if CONF_DEVICE_COLOR not in self.device_config:
            import random
            self.device_config[CONF_DEVICE_COLOR] = random.choice(DEVICE_COLORS)
            # Update config entry with the new color
            new_data = dict(config_entry.data)
            new_data["device_config"] = self.device_config
            hass.config_entries.async_update_entry(config_entry, data=new_data)
        
        # Device instance for state reading/control
        self.device_instance: Optional[PVDevice] = None
        
        # Device state cache
        self.device_state: Dict[str, Any] = {}
        self.state_changes: Dict[str, datetime] = {}
        
        # Tracking for locking logic
        self.last_switch_time: Optional[datetime] = None
        self.is_fault_locked: bool = False
        
        # Service coordinator reference (set during registration)
        self.service_coordinator: Optional["ServiceCoordinator"] = None
        
        # State change listeners
        self._unsub_listeners: List = []
        
        # Persistence
        self._store = Store(hass, 1, f"pv_optimizer_device_{config_entry.entry_id}_{normalize_device_name(device_name)}")
        
    def set_fault_lock(self, lock_status: bool):
        """Set or clear the fault lock on the device."""
        _LOGGER.debug(f"Setting fault lock for {self.device_name} to {lock_status}")
        self.is_fault_locked = lock_status
        # Request an immediate refresh to update entities
        self.hass.async_create_task(self.async_request_refresh())

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass, set up state listeners."""
        await super().async_added_to_hass()
        
        device_type = self.device_config.get(CONF_TYPE)
        entities_to_monitor = []
        
        # 1. Switch entity (for switch-type devices)
        if device_type == TYPE_SWITCH:
            switch_entity = self.device_config.get(CONF_SWITCH_ENTITY_ID)
            if switch_entity:
                entities_to_monitor.append(switch_entity)
        
        # 2. Numeric target entities (for numeric-type devices)
        elif device_type == TYPE_NUMERIC:
            numeric_targets = self.device_config.get(CONF_NUMERIC_TARGETS, [])
            for target in numeric_targets:
                numeric_entity = target.get(CONF_NUMERIC_ENTITY_ID)
                if numeric_entity:
                    entities_to_monitor.append(numeric_entity)
        
        # 3. Power sensor (for all device types)
        power_sensor = self.device_config.get(CONF_MEASURED_POWER_ENTITY_ID)
        if power_sensor:
            entities_to_monitor.append(power_sensor)
        
        # Set up listeners for all entities
        for entity_id in entities_to_monitor:
            self._unsub_listeners.append(
                self.hass.helpers.event.async_track_state_change_event(
                    entity_id,
                    self._handle_state_change
                )
            )

            _LOGGER.debug(f"{self.device_name}: Listening to {entity_id} state changes")
            
        # Restore state
        await self._async_load_state()
            
        # Retrieve device ID from registry
        dev_reg = dr.async_get(self.hass)
        normalized_name = normalize_device_name(self.device_name)
        device = dev_reg.async_get_device(identifiers={(DOMAIN, f"{self.config_entry.entry_id}_{normalized_name}")})
        if device:
            self.device_id = device.id
        else:
            self.device_id = None
    
    async def async_will_remove_from_hass(self) -> None:
        """Clean up listeners when coordinator is removed."""
        for unsub in self._unsub_listeners:
            unsub()
        self._unsub_listeners.clear()
        await super().async_will_remove_from_hass()
    
    def _handle_state_change(self, event) -> None:
        """Handle state change events for monitored entities."""
        old_state = event.data.get("old_state")
        new_state = event.data.get("new_state")
        
        if old_state is None or new_state is None:
            return
        
        if old_state.state == new_state.state:
            return
        
        _LOGGER.debug(
            f"{self.device_name}: State change detected - "
            f"{event.data.get('entity_id')}: {old_state.state} → {new_state.state}"
        )
        
        # Trigger immediate coordinator update
        self.hass.async_create_task(self.async_request_refresh())

    async def _async_update_data(self) -> Dict[str, Any]:
        """Update device state."""
        # Create device instance if needed
        if self.device_instance is None:
            # Pass coordinator to device instance
            self.device_instance = create_device(self.hass, self.device_config, self)
        
        if self.device_instance is None:
            _LOGGER.warning(f"Failed to create device instance for {self.device_name}")
            return {}
        
        now = dt_util.now()
        
        # Get current state
        is_on = self.device_instance.is_on()
        is_off = self.device_instance.is_off()
        is_indeterminate = not is_on and not is_off
        
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
        locked_timing, locked_manual, lock_reason = self._get_lock_status(is_on, is_indeterminate)
        is_locked = locked_timing or locked_manual
        
        # Check availability of underlying entities
        is_available = self._check_availability()

        # Retry device_id lookup if it's None (race condition handling)
        if self.device_id is None:
            dev_reg = dr.async_get(self.hass)
            normalized_name = normalize_device_name(self.device_name)
            identifier = (DOMAIN, f"{self.config_entry.entry_id}_{normalized_name}")
            
            _LOGGER.debug(
                "Attempting device_id lookup for %s with identifier %s",
                self.device_name,
                identifier
            )
            
            device_entry = dev_reg.async_get_device(identifiers={identifier})
            if device_entry:
                self.device_id = device_entry.id
                _LOGGER.info("Found device_id %s for %s", self.device_id, self.device_name)
            else:
                _LOGGER.debug(
                    "Device not found for %s. Available devices for this entry: %s",
                    self.device_name,
                    [
                        (dev.name, dev.identifiers)
                        for dev in dev_reg.devices.values()
                        if self.config_entry.entry_id in dev.config_entries
                    ]
                )
        
        # Behavior Refinement: If optimization is disabled, device is ON (via optimizer), 
        # and locks are clear -> Turn OFF
        optimization_enabled = self.device_config.get("optimization_enabled", True)
        last_target = self.device_state.get(ATTR_PVO_LAST_TARGET_STATE)
        
        if not optimization_enabled and is_on and last_target is True and not is_locked:
             _LOGGER.info(f"{self.device_name}: Optimization disabled and locks cleared. Turning OFF device.")
             if self.device_instance:
                 # We need to schedule this task to avoid blocking the update
                 self.hass.async_create_task(self.device_instance.deactivate())
                 # Update local state immediately for responsiveness
                 is_on = False
                 self.device_state[ATTR_PVO_LAST_TARGET_STATE] = False
                 self.last_switch_time = now
                 # Recalculate lock status with new state (though likely irrelevant as it's off)
                 locked_timing, locked_manual, lock_reason = self._get_lock_status(is_on, is_indeterminate)
                 is_locked = locked_timing or locked_manual

        # Update state cache
        self.device_state = {
            "is_on": is_on,
            ATTR_POWER_MEASURED_AVERAGE: measured_power_avg,
            "power_measured": self._get_current_power(),
            ATTR_IS_LOCKED: is_locked,
            "is_locked_timing": locked_timing,
            "is_locked_manual": locked_manual,
            "is_fault_locked": self.is_fault_locked,
            "lock_reason": lock_reason,
            "is_available": is_available,
            "device_id": getattr(self, "device_id", None),
            ATTR_PVO_LAST_TARGET_STATE: self.device_state.get(ATTR_PVO_LAST_TARGET_STATE, is_on),
            "last_update": now,
        }
        
        return self.device_state
        
    def _check_availability(self) -> bool:
        """Check if underlying entities are available."""
        device_type = self.device_config.get(CONF_TYPE)
        entities_to_check = []
        
        # 1. Switch entity
        if device_type == TYPE_SWITCH:
            switch_entity = self.device_config.get(CONF_SWITCH_ENTITY_ID)
            if switch_entity:
                entities_to_check.append(switch_entity)
        
        # 2. Numeric target entities
        elif device_type == TYPE_NUMERIC:
            numeric_targets = self.device_config.get(CONF_NUMERIC_TARGETS, [])
            for target in numeric_targets:
                numeric_entity = target.get(CONF_NUMERIC_ENTITY_ID)
                if numeric_entity:
                    entities_to_check.append(numeric_entity)
        
        # 3. Power sensor
        power_sensor = self.device_config.get(CONF_MEASURED_POWER_ENTITY_ID)
        if power_sensor:
            entities_to_check.append(power_sensor)
            
        # Check all entities
        for entity_id in entities_to_check:
            state = self.hass.states.get(entity_id)
            if state is None or state.state in ["unavailable", "unknown"]:
                _LOGGER.debug(f"{self.device_name}: Entity {entity_id} is unavailable/unknown")
                return False
                
        return True

    def _get_current_power(self) -> float:
        """Get current power consumption."""
        power_sensor = self.device_config.get(CONF_MEASURED_POWER_ENTITY_ID)
        if not power_sensor:
            return self.device_config.get(CONF_POWER, 0.0)
            
        state = self.hass.states.get(power_sensor)
        return float(state.state) if state and state.state not in ['unknown', 'unavailable'] else 0.0

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

    def _get_lock_status(self, current_state: bool, is_indeterminate: bool = False) -> tuple[bool, bool, str]:
        """
        Determine if device is locked.
        Returns (locked_timing, locked_manual, lock_reason).
        """
        now = dt_util.now()
        config = self.device_config
        lock_reason = ""
        
        # 1. Timing Lock (Min On/Off Time)
        locked_timing = False
        # Check if we have a last switch time
        if hasattr(self, 'last_switch_time') and self.last_switch_time:
            elapsed = (now - self.last_switch_time).total_seconds() / 60.0
            if current_state:
                # Currently ON -> Check Min On Time
                min_on = config.get(CONF_MIN_ON_TIME, 0)
                if min_on > 0 and elapsed < min_on:
                    locked_timing = True
                    remaining = min_on - elapsed
                    lock_reason = f"Minimum on time: {remaining:.1f} min remaining"
            else:
                # Currently OFF -> Check Min Off Time
                min_off = config.get(CONF_MIN_OFF_TIME, 0)
                if min_off > 0 and elapsed < min_off:
                    locked_timing = True
                    remaining = min_off - elapsed
                    lock_reason = f"Minimum off time: {remaining:.1f} min remaining"
        
        # 2. Manual Lock (User Intervention) & Fault Lock
        locked_manual = False
        if self.is_fault_locked:
            locked_manual = True
            lock_reason = "Device Fault - Failed to set value"

        last_target = self.device_state.get(ATTR_PVO_LAST_TARGET_STATE)
        
        # Only lock if we have a known last target state that differs from current
        # If last_target is None (after reset or initial state), don't lock - allow optimizer to take control
        if is_indeterminate:
            locked_manual = True
            # Get detailed state information for numeric devices
            if self.device_instance:
                details = self.device_instance.get_state_details()
                # get_state_details already includes header, so use it directly
                lock_reason = details
                _LOGGER.debug(f"{self.device_name}: Manual lock detected - {lock_reason}")
            else:
                lock_reason = "Manual Override - Device state manually changed"
        elif last_target is not None and current_state != last_target:
            locked_manual = True
            expected_state = "ON" if last_target else "OFF"
            actual_state = "ON" if current_state else "OFF"  
            lock_reason = f"Manual Override\nExpected: {expected_state}\nActual: {actual_state}"
            _LOGGER.debug(f"{self.device_name}: Manual lock detected - {lock_reason}")
        elif last_target is None:
            _LOGGER.debug(f"{self.device_name}: No last target state (None) - allowing optimizer control")
            
        return locked_timing, locked_manual, lock_reason

    async def async_update_device_config(self, updates: Dict[str, Any]) -> None:
        """Update device configuration and persist to config entry."""
        # Check for specific transitions before updating config
        if "optimization_enabled" in updates and updates["optimization_enabled"] is False:
            # Optimization being disabled
            last_target = self.device_state.get(ATTR_PVO_LAST_TARGET_STATE)
            is_locked_manual = self.device_state.get("is_locked_manual", False)
            
            if last_target is True and not is_locked_manual:
                # Check timing lock
                is_on = self.device_instance.is_on() if self.device_instance else False
                is_off = self.device_instance.is_off() if self.device_instance else True
                is_indeterminate = not is_on and not is_off
                locked_timing, _, _ = self._get_lock_status(is_on, is_indeterminate)
                
                if not locked_timing:
                    _LOGGER.info(f"{self.device_name}: Optimization disabled. Turning OFF device immediately.")
                    if self.device_instance:
                        await self.device_instance.deactivate()
                        self.device_state[ATTR_PVO_LAST_TARGET_STATE] = False
                        self.device_state[ATTR_PVO_LAST_TARGET_STATE] = False
                        self.last_switch_time = dt_util.now()
                        await self._async_save_state()
                else:
                    _LOGGER.info(f"{self.device_name}: Optimization disabled, but timing lock active. Will turn off when lock expires.")

        self.device_config.update(updates)
        
        # Update config entry
        new_data = dict(self.config_entry.data)
        new_data["device_config"] = self.device_config
        
        self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)
        _LOGGER.info(f"Updated config for device {self.device_name}: {updates}")
        
        # Trigger refresh
        await self.async_request_refresh()
        
        # Trigger service optimization if needed
        if self.service_coordinator:
            await self.service_coordinator.async_request_refresh()

    def update_config(self, key: str, value: Any) -> None:
        """Update device configuration in memory."""
        self.device_config[key] = value

    async def activate(self) -> None:
        """Activate the device."""
        if self.device_instance:
            await self.device_instance.activate()
            self.device_state[ATTR_PVO_LAST_TARGET_STATE] = True
            self.last_switch_time = dt_util.now() # PVO initiated switch

    async def deactivate(self) -> None:
        """Deactivate the device."""
        if self.device_instance:
            await self.device_instance.deactivate()
            self.device_state[ATTR_PVO_LAST_TARGET_STATE] = False
            self.last_switch_time = dt_util.now() # PVO initiated switch

    async def reset_target_state(self) -> None:
        """Reset the last target state to None."""
        # Clear any fault lock
        self.is_fault_locked = False

        # Check if device is in an indeterminate state (neither ON nor OFF)
        # This happens for numeric devices when manually set to a value that matches neither target
        is_on = self.device_instance.is_on() if self.device_instance else False
        is_off = self.device_instance.is_off() if self.device_instance else False
        is_indeterminate = not is_on and not is_off


        if is_indeterminate and self.device_instance:
            _LOGGER.info(f"Resetting indeterminate device {self.device_name} to deactivated state to clear manual lock")
            await self.device_instance.deactivate()
            self.device_state[ATTR_PVO_LAST_TARGET_STATE] = False
        else:
            self.device_state[ATTR_PVO_LAST_TARGET_STATE] = None
            
        await self._async_save_state()
        _LOGGER.info(f"Reset target state for device: {self.device_name}")
        
        # Refresh this device coordinator first to recalculate lock status
        await self.async_request_refresh()
        
        # Then trigger optimization cycle on service coordinator
        if self.service_coordinator:
            _LOGGER.info(f"Triggering optimization after reset for device: {self.device_name}")
            await self.service_coordinator.async_request_refresh()

    async def _async_load_state(self) -> None:
        """Load persisted state."""
        try:
            data = await self._store.async_load()
            if data:
                self.device_state[ATTR_PVO_LAST_TARGET_STATE] = data.get("last_target_state")
                self.is_fault_locked = data.get("is_fault_locked", False)
                if data.get("last_switch_time"):
                    self.last_switch_time = dt_util.parse_datetime(data["last_switch_time"])
                _LOGGER.info(f"Restored state for {self.device_name}: target={self.device_state.get(ATTR_PVO_LAST_TARGET_STATE)}, last_switch={self.last_switch_time}")
        except Exception as e:
            _LOGGER.error(f"Failed to load state for {self.device_name}: {e}")

    async def _async_save_state(self) -> None:
        """Save state to persistence."""
        try:
            data = {
                "last_target_state": self.device_state.get(ATTR_PVO_LAST_TARGET_STATE),
                "last_switch_time": self.last_switch_time.isoformat() if self.last_switch_time else None,
                "is_fault_locked": self.is_fault_locked,
            }
            await self._store.async_save(data)
        except Exception as e:
            _LOGGER.error(f"Failed to save state for {self.device_name}: {e}")


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
        
        # Simulation specific
        self.simulation_surplus_offset: float = 0.0
        
        # State change listeners
        self._unsub_listeners: List = []
    
    async def async_added_to_hass(self) -> None:
        """When coordinator is added to hass, set up state listeners."""
        await super().async_added_to_hass()
        
        # Listen to surplus sensor changes to trigger immediate optimization
        surplus_sensor = self.global_config.get(CONF_SURPLUS_SENSOR_ENTITY_ID)
        if surplus_sensor:
            self._unsub_listeners.append(
                self.hass.helpers.event.async_track_state_change_event(
                    surplus_sensor,
                    self._handle_surplus_change
                )
            )
            _LOGGER.debug(f"ServiceCoordinator: Listening to {surplus_sensor} state changes")
    
    async def async_will_remove_from_hass(self) -> None:
        """Clean up listeners when coordinator is removed."""
        for unsub in self._unsub_listeners:
            unsub()
        self._unsub_listeners.clear()
        await super().async_will_remove_from_hass()
    
    def _handle_surplus_change(self, event) -> None:
        """Handle surplus sensor state changes."""
        old_state = event.data.get("old_state")
        new_state = event.data.get("new_state")
        
        if old_state is None or new_state is None:
            return
        
        if old_state.state == new_state.state:
            return
        
        _LOGGER.debug(
            f"ServiceCoordinator: Surplus change detected - "
            f"{old_state.state} → {new_state.state}"
        )
        
        # Trigger immediate optimization cycle
        self.hass.async_create_task(self.async_request_refresh())

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
        _LOGGER.debug("⚡ Bolt: Starting performance measurement for optimization cycle.")
        start_time = time.time()
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
        real_ideal_list = await self._calculate_ideal_state(real_power_budget, real_devices, ignore_manual_lock=False)
        await self._synchronize_states(real_ideal_list, real_devices)
        
        # Calculate averaged surplus first (needed for logging and return data)
        surplus_avg = await self._get_averaged_surplus()
        surplus_current = self._get_current_surplus()
        
        # Run simulation optimization
        sim_devices = [
            (name, state) for name, state in device_states.items()
            if self._get_device_config(name).get(CONF_SIMULATION_ACTIVE, False)
        ]
        sim_power_budget = await self._calculate_power_budget(sim_devices, surplus_offset=self.simulation_surplus_offset)
        # SIMULATION IGNORES MANUAL LOCKS
        sim_ideal_list = await self._calculate_ideal_state(sim_power_budget, sim_devices, ignore_manual_lock=True)
        
        _LOGGER.warning(
            f"Optimization cycle debug:\n"
            f"  Offset: {self.simulation_surplus_offset}\n"
            f"  Sim Budget: {sim_power_budget}\n"
            f"  Surplus Avg: {surplus_avg}"
        )
        
        _LOGGER.info(
            f"Optimization cycle completed.\n"
            f"  Real: Budget={real_power_budget:.2f}W, Ideal devices={real_ideal_list}\n"
            f"  Simulation: Budget={sim_power_budget:.2f}W, Ideal devices={sim_ideal_list}"
        )
        
        # Calculate totals
        power_measured_total = sum(
            state.get("power_measured", 0) 
            for state in device_states.values() 
            if state.get("is_on")
        )
        
        power_rated_total = sum(
            self._get_device_config(name).get(CONF_POWER, 0)
            for name, state in device_states.items()
            if state.get("is_on")
        )

        _LOGGER.warning(f"DEBUG TOTALS: Measured={power_measured_total}, Rated={power_rated_total}")
        _LOGGER.warning(f"DEBUG DEVICE STATES: {device_states}")

        end_time = time.time()
        execution_time = (end_time - start_time) * 1000  # in milliseconds
        _LOGGER.info(f"⚡ Bolt: Optimization cycle finished in {execution_time:.2f}ms.")
        # Return data for sensors
        return {
            "optimizer_stats": {
                "surplus_current": surplus_current,
                "surplus_average": surplus_avg,
                "budget_real": real_power_budget,
                "budget_simulation": sim_power_budget,
                "power_measured_total": power_measured_total,
                "power_rated_total": power_rated_total,
                "surplus_offset": self.simulation_surplus_offset,
            },
            "devices_state": device_states,
            # Legacy keys for backward compatibility (optional, but good for safety)
            "power_budget": real_power_budget,
            "surplus_avg": surplus_avg,
            "ideal_on_list": real_ideal_list,
            "simulation_power_budget": sim_power_budget,
            "simulation_ideal_on_list": sim_ideal_list,
            "simulation_surplus_offset": self.simulation_surplus_offset,
            "last_update_timestamp": dt_util.now(),
        }

    def _get_device_config(self, device_name: str) -> Dict[str, Any]:
        """Get device config from coordinator."""
        coordinator = self.device_coordinators.get(device_name)
        return coordinator.device_config if coordinator else {}

    async def _calculate_power_budget(self, devices: List[tuple[str, Dict[str, Any]]], surplus_offset: float = 0.0) -> float:
        """Calculate available power budget."""
        surplus_avg = await self._get_averaged_surplus()
        
        # Apply offset (for simulation)
        surplus_avg += surplus_offset
        
        running_manageable_power = 0.0
        for device_name, state in devices:
            if state.get("is_on") and not state.get(ATTR_IS_LOCKED, False):
                config = self._get_device_config(device_name)
                power = state.get(ATTR_POWER_MEASURED_AVERAGE, config.get(CONF_POWER, 0.0))
                running_manageable_power += power
        
        budget = surplus_avg + running_manageable_power
        _LOGGER.warning(f"Budget Calc: Surplus={surplus_avg:.2f}W (Offset={surplus_offset:.2f}W), Running={running_manageable_power:.2f}W, Total={budget:.2f}W")
        return budget


    def set_simulation_surplus_offset(self, offset: float) -> None:
        """Set the surplus offset for simulation."""
        self.simulation_surplus_offset = float(offset)
        _LOGGER.info(f"Set simulation surplus offset to {offset}W")
        # Trigger update
        self.async_set_updated_data(self.data)
        self.hass.async_create_task(self.async_request_refresh())

    async def _calculate_ideal_state(self, power_budget: float, devices: List[tuple[str, Dict[str, Any]]], ignore_manual_lock: bool = False) -> List[str]:
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
        
        _LOGGER.debug(f"Calculating ideal state. Budget={power_budget:.2f}W, Priorities={list(devices_by_priority.keys())}, IgnoreManual={ignore_manual_lock}")
        
        # Process priorities
        for priority in sorted(devices_by_priority.keys()):
            priority_devices = devices_by_priority[priority]
            selected = self._knapsack_select(priority_devices, remaining_budget, ignore_manual_lock)
            ideal_on_list.extend(selected)
            
            # Update budget
            for device_name in selected:
                _, _, config = next(d for d in priority_devices if d[0] == device_name)
                power = config.get(CONF_POWER, 0)
                remaining_budget -= power
                _LOGGER.debug(f"Selected {device_name} (Prio {priority}, {power}W). Remaining Budget={remaining_budget:.2f}W")
        
        return ideal_on_list

    def _knapsack_select(self, devices: List[tuple[str, Dict[str, Any], Dict[str, Any]]], budget: float, ignore_manual_lock: bool = False) -> List[str]:
        """Select devices via greedy knapsack."""
        # Filter locked devices
        available = []
        for name, state, config in devices:
            # Determine if locked based on mode
            is_locked = False
            if ignore_manual_lock:
                # Simulation: Only respect timing locks
                if state.get("is_locked_timing", False):
                    is_locked = True
                    _LOGGER.debug(f"Skipping {name}: Timing Locked")
            else:
                # Real: Respect all locks (legacy ATTR_IS_LOCKED covers both)
                if state.get(ATTR_IS_LOCKED, False):
                    is_locked = True
                    _LOGGER.debug(f"Skipping {name}: Locked")
            
            if not is_locked:
                available.append((name, state, config))
        
        # Sort by power descending
        available.sort(key=lambda d: d[2].get(CONF_POWER, 0), reverse=True)
        
        selected = []
        for device_name, state, config in available:
            power = config.get(CONF_POWER, 0)
            if power <= budget:
                selected.append(device_name)
                budget -= power
            else:
                _LOGGER.debug(f"Skipping {device_name}: Power {power}W > Budget {budget:.2f}W")
        
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
                
                # Verify switch was successful
                await self._verify_switch(coordinator, device_name, expected_state=True)
                
            elif not should_be_on and currently_on and not is_locked:
                await coordinator.deactivate()
                _LOGGER.info(f"Deactivated device: {device_name}")
                
                # Verify switch was successful
                await self._verify_switch(coordinator, device_name, expected_state=False)

    async def _verify_switch(self, coordinator: "DeviceCoordinator", device_name: str, expected_state: bool) -> None:
        """Verify that a device switch was successful."""
        import asyncio
        
        # Wait for device to respond
        await asyncio.sleep(3)
        
        # Re-read device state
        if coordinator.device_instance:
            actual_state = coordinator.device_instance.is_on()
            
            if actual_state != expected_state:
                _LOGGER.warning(
                    f"Switch verification failed for {device_name}: "
                    f"Expected {expected_state}, got {actual_state}. "
                    f"Clearing last_target_state to allow retry."
                )
                # Clear last_target_state to prevent lock and allow retry
                coordinator.device_state[ATTR_PVO_LAST_TARGET_STATE] = None
                coordinator.async_set_updated_data(coordinator.device_state)
            else:
                _LOGGER.debug(f"Switch verification successful for {device_name}: state is {actual_state}")

    def _get_current_surplus(self) -> float:
        """Get current instantaneous PV surplus."""
        surplus_entity = self.global_config.get(CONF_SURPLUS_SENSOR_ENTITY_ID)
        if not surplus_entity:
            return 0.0
        
        state = self.hass.states.get(surplus_entity)
        current = float(state.state) if state and state.state not in ['unknown', 'unavailable'] else 0.0
        
        # Requirements state Negative = Surplus.
        # We invert by default so that internal logic sees Positive = Surplus.
        current = current * -1
        
        # Configured inversion (flip it back if user wants)
        if self.global_config.get(CONF_INVERT_SURPLUS_VALUE, False):
            current = current * -1
            
        return current

    async def _get_averaged_surplus(self) -> float:
        """Get averaged PV surplus."""
        surplus_entity = self.global_config.get(CONF_SURPLUS_SENSOR_ENTITY_ID)
        if not surplus_entity:
            return 0.0
        
        # Requirements state Negative = Surplus.
        # We invert by default so that internal logic sees Positive = Surplus.
        # If user checks "Invert Surplus", we invert AGAIN (effectively keeping original sign).
        invert_config = self.global_config.get(CONF_INVERT_SURPLUS_VALUE, False)
        
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
                
                # Default inversion (Negative -> Positive)
                avg = avg * -1
                
                # Configured inversion (flip it back if user wants)
                if invert_config:
                    avg = avg * -1
                    
                return avg
        except Exception as e:
            _LOGGER.warning(f"Failed to get averaged surplus: {e}")
        
        # Fallback
        state = self.hass.states.get(surplus_entity)
        current = float(state.state) if state and state.state not in ['unknown', 'unavailable'] else 0.0
        
        # Default inversion (Negative -> Positive)
        current = current * -1
        
        # Configured inversion
        if invert_config:
            current = current * -1
            
        return current
