"""
Coordinator for PV Optimizer Integration

UPDATED: Added parallel simulation optimization
- Runs separate optimization for simulation-marked devices
- No physical control for simulation devices
- Separate budget calculation for simulation
- Results available via coordinator.data for frontend display
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
    CONF_SIMULATION_ACTIVE,  # NEW
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


class PVOptimizerCoordinator(DataUpdateCoordinator):
    """
    Coordinator for PV Optimizer - manages optimization cycles.
    
    UPDATED: Now runs two parallel optimizations:
    1. Real Optimization: For devices with optimization_enabled=True
    2. Simulation: For devices with simulation_active=True
    
    Key Differences:
    ---------------
    - Real: Calculates budget from real devices, synchronizes states
    - Simulation: Calculates separate budget, NO state synchronization
    - Both use same knapsack algorithm for fair comparison
    """

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the PV Optimizer coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=config_entry.data["global"][CONF_OPTIMIZATION_CYCLE_TIME]),
        )
        self.config_entry = config_entry
        self.devices = config_entry.data.get("devices", [])
        self.global_config = config_entry.data.get("global", {})
        self.entity_registry = er.async_get(hass)
        self.device_states = {}  # Cache for device states and timestamps
        self.device_instances = {}  # Cache for device class instances
        self.device_state_changes = {}  # Track actual state change timestamps

    async def async_set_config(self, data: Dict[str, Any]) -> None:
        """Set the global configuration."""
        self.global_config.update(data)
        new_data = dict(self.config_entry.data)
        new_data["global"] = self.global_config
        self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)
        self.async_set_update_interval(timedelta(seconds=self.global_config[CONF_OPTIMIZATION_CYCLE_TIME]))

    async def _async_update_data(self) -> Dict[str, Any]:
        """
        Fetch data for the optimization cycle.
        
        UPDATED: Now runs two parallel optimizations:
        1. Real optimization (existing logic)
        2. Simulation optimization (new logic, no state sync)
        """
        # Step 1: Data Aggregation - Gather current states for ALL devices
        await self._aggregate_device_data()

        # ============================================
        # REAL OPTIMIZATION (existing logic)
        # ============================================
        
        # Filter devices for real optimization
        real_devices = [d for d in self.devices if d.get(CONF_OPTIMIZATION_ENABLED, True)]
        
        # Calculate power budget for real optimization
        real_power_budget = await self._calculate_power_budget(real_devices, "real")
        
        # Calculate ideal state for real optimization
        real_ideal_list = await self._calculate_ideal_state(real_power_budget, real_devices)
        
        # Synchronize states (ONLY for real optimization)
        await self._synchronize_states(real_ideal_list, real_devices)

        # ============================================
        # SIMULATION OPTIMIZATION (new logic)
        # ============================================
        
        # Filter devices for simulation
        sim_devices = [d for d in self.devices if d.get(CONF_SIMULATION_ACTIVE, False)]
        
        # Calculate power budget for simulation (separate calculation)
        sim_power_budget = await self._calculate_power_budget(sim_devices, "simulation")
        
        # Calculate ideal state for simulation
        sim_ideal_list = await self._calculate_ideal_state(sim_power_budget, sim_devices)
        
        # IMPORTANT: NO _synchronize_states for simulation!
        # Simulation devices are never physically controlled

        # ============================================
        # LOGGING & RETURN DATA
        # ============================================

        _LOGGER.info(
            f"Optimization cycle completed.\n"
            f"  Real: Budget={real_power_budget:.2f}W, Ideal devices={real_ideal_list}\n"
            f"  Simulation: Budget={sim_power_budget:.2f}W, Ideal devices={sim_ideal_list}"
        )

        # Detailed device status logging
        device_status = []
        for device_config in self.devices:
            device_name = device_config[CONF_NAME]
            state_info = self.device_states.get(device_name, {})
            device_status.append({
                "name": device_name,
                "is_on": state_info.get("is_on", False),
                "locked": state_info.get(ATTR_IS_LOCKED, False),
                "power": state_info.get(ATTR_MEASURED_POWER_AVG, 0),
                "priority": device_config.get(CONF_PRIORITY, 5),
                "opt_enabled": device_config.get(CONF_OPTIMIZATION_ENABLED, True),
                "sim_active": device_config.get(CONF_SIMULATION_ACTIVE, False),
            })
        _LOGGER.debug(f"Device status summary: {device_status}")

        # Return data for sensors
        surplus_avg = await self._get_averaged_surplus()
        return {
            # Real optimization data (existing)
            "power_budget": real_power_budget,
            "surplus_avg": surplus_avg,
            "ideal_on_list": real_ideal_list,
            
            # Simulation data (NEW)
            "simulation_power_budget": sim_power_budget,
            "simulation_ideal_on_list": sim_ideal_list,
        }

    async def _aggregate_device_data(self) -> None:
        """
        Aggregate data for each device: measured_power_avg, is_locked, pvo_last_target_state.
        
        NOTE: This aggregates data for ALL devices (real + simulation) since simulation
        devices also need state tracking for realistic budget calculations.
        """
        now = dt_util.now()
        for device_config in self.devices:
            # Aggregate data for ALL devices, not just optimization_enabled
            # This ensures simulation devices also have realistic state data
            device_name = device_config[CONF_NAME]

            # Create or get device instance
            if device_name not in self.device_instances:
                self.device_instances[device_name] = create_device(self.hass, device_config)
            device = self.device_instances[device_name]

            if device is None:
                continue

            # Get current state
            is_on = device.is_on()

            # Track state changes with accurate timestamps
            previous_state = self.device_states.get(device_name, {}).get("is_on")
            if previous_state is not None and previous_state != is_on:
                # State changed - record the timestamp
                if device_name not in self.device_state_changes:
                    self.device_state_changes[device_name] = {}
                
                if is_on:
                    self.device_state_changes[device_name]["last_on_time"] = now
                else:
                    self.device_state_changes[device_name]["last_off_time"] = now
                
                _LOGGER.info(f"Device {device_name} state changed to {'ON' if is_on else 'OFF'} at {now}")

            # Calculate averaged power over sliding window
            measured_power_avg = await self._get_averaged_power(device_config, now)

            # Determine if locked based on min times and manual interventions
            is_locked = await self._is_device_locked(device_config, device, is_on, now)

            # Get last target state from previous cycle
            last_target_state = self.device_states.get(device_name, {}).get(ATTR_PVO_LAST_TARGET_STATE, is_on)

            # Update device_states cache
            self.device_states[device_name] = {
                "is_on": is_on,
                "measured_power_avg": measured_power_avg,
                ATTR_IS_LOCKED: is_locked,
                ATTR_PVO_LAST_TARGET_STATE: last_target_state,
                "last_update": now,
            }

    async def _get_averaged_power(self, device_config: Dict[str, Any], now: datetime) -> float:
        """Get averaged power consumption over sliding window."""
        power_sensor = device_config.get(CONF_MEASURED_POWER_ENTITY_ID)
        if not power_sensor:
            return device_config.get(CONF_POWER, 0.0)  # Fallback to nominal power

        window_minutes = self.global_config[CONF_SLIDING_WINDOW_SIZE]
        start_time = now - timedelta(minutes=window_minutes)

        try:
            # Use recorder history to get averaged power
            history = await get_instance(self.hass).async_add_executor_job(
                get_significant_states, self.hass, start_time, now, [power_sensor]
            )
            if power_sensor in history and history[power_sensor]:
                values = [float(state.state) for state in history[power_sensor] if state.state not in ['unknown', 'unavailable']]
                return sum(values) / len(values) if values else 0.0
        except Exception as e:
            _LOGGER.warning(f"Failed to get averaged power for {device_config[CONF_NAME]}: {e}")

        # Fallback to current state
        state = self.hass.states.get(power_sensor)
        return float(state.state) if state and state.state not in ['unknown', 'unavailable'] else 0.0

    async def _is_device_locked(self, device_config: Dict[str, Any], device: PVDevice, is_on: bool, now: datetime) -> bool:
        """Determine if a device is locked in its current state."""
        device_name = device_config[CONF_NAME]
        state_info = self.device_states.get(device_name, {})
        state_changes = self.device_state_changes.get(device_name, {})

        # Check minimum on time
        if is_on:
            min_on_minutes = device_config.get(CONF_MIN_ON_TIME)
            if min_on_minutes and min_on_minutes > 0:
                last_on_time = state_changes.get("last_on_time")
                if last_on_time:
                    time_on = (now - last_on_time).total_seconds() / 60
                    if time_on < min_on_minutes:
                        _LOGGER.debug(f"Device {device_name} locked ON: {time_on:.1f}/{min_on_minutes} min")
                        return True

        # Check minimum off time
        elif not is_on:
            min_off_minutes = device_config.get(CONF_MIN_OFF_TIME)
            if min_off_minutes and min_off_minutes > 0:
                last_off_time = state_changes.get("last_off_time")
                if last_off_time:
                    time_off = (now - last_off_time).total_seconds() / 60
                    if time_off < min_off_minutes:
                        _LOGGER.debug(f"Device {device_name} locked OFF: {time_off:.1f}/{min_off_minutes} min")
                        return True

        # Check for manual intervention
        last_target = state_info.get(ATTR_PVO_LAST_TARGET_STATE)
        if last_target is not None and last_target != is_on:
            _LOGGER.debug(f"Device {device_name} locked: manual intervention detected (target={last_target}, actual={is_on})")
            return True

        return False

    async def _calculate_power_budget(self, devices: List[Dict[str, Any]], mode: str) -> float:
        """
        Calculate the total available power budget.
        
        UPDATED: Now accepts a filtered device list and mode identifier.
        
        Args:
            devices: List of devices to consider (real or simulation)
            mode: "real" or "simulation" for logging purposes
        
        Budget Calculation (Answer to Question 1: Option A):
        ----------------------------------------------------
        - Real: PV surplus + power from running real optimization devices
        - Simulation: PV surplus + power from running simulation devices
        - Separate budgets ensure clean separation between real and simulation
        """
        surplus_avg = await self._get_averaged_surplus()

        running_manageable_power = 0.0
        for device_config in devices:
            device_name = device_config[CONF_NAME]
            state_info = self.device_states.get(device_name, {})
            
            # Only count devices that are:
            # 1. Currently ON
            # 2. Not locked (manageable)
            if state_info.get("is_on") and not state_info.get(ATTR_IS_LOCKED, False):
                power = state_info.get(ATTR_MEASURED_POWER_AVG, device_config.get(CONF_POWER, 0.0))
                running_manageable_power += power

        budget = surplus_avg + running_manageable_power
        _LOGGER.debug(
            f"Calculated {mode} power budget: {surplus_avg:.2f}W surplus + "
            f"{running_manageable_power:.2f}W running = {budget:.2f}W"
        )
        return budget

    async def _calculate_ideal_state(self, power_budget: float, devices: List[Dict[str, Any]]) -> List[str]:
        """
        Calculate the ideal list of devices to turn on using knapsack per priority.
        
        UPDATED: Now accepts a filtered device list (real or simulation).
        """
        ideal_on_list = []
        remaining_budget = power_budget

        # Group devices by priority
        devices_by_priority = {}
        for device_config in devices:
            priority = device_config[CONF_PRIORITY]
            if priority not in devices_by_priority:
                devices_by_priority[priority] = []
            devices_by_priority[priority].append(device_config)

        # Process priorities from highest (1) to lowest
        for priority in sorted(devices_by_priority.keys()):
            priority_devices = devices_by_priority[priority]
            selected = self._knapsack_select(priority_devices, remaining_budget)
            ideal_on_list.extend(selected)

            # Update remaining budget
            for device_name in selected:
                device_config = next(d for d in priority_devices if d[CONF_NAME] == device_name)
                power = device_config[CONF_POWER]
                remaining_budget -= power

        _LOGGER.debug(f"Ideal state calculated: {ideal_on_list} with remaining budget {remaining_budget:.2f}W")
        return ideal_on_list

    def _knapsack_select(self, devices: List[Dict], budget: float) -> List[str]:
        """Select subset of devices that maximize power without exceeding budget."""
        available_devices = [
            d for d in devices
            if not self.device_states.get(d[CONF_NAME], {}).get(ATTR_IS_LOCKED, False)
        ]

        # Sort by power descending for greedy selection
        available_devices.sort(key=lambda d: d[CONF_POWER], reverse=True)

        selected = []
        for device in available_devices:
            power = device[CONF_POWER]
            if power <= budget:
                selected.append(device[CONF_NAME])
                budget -= power

        return selected

    async def _synchronize_states(self, ideal_on_list: List[str], devices: List[Dict[str, Any]]) -> None:
        """
        Turn devices on/off based on ideal list.
        
        UPDATED: Now accepts a device list to only sync specified devices.
        This ensures simulation devices are never physically controlled.
        """
        for device_config in devices:
            device_name = device_config[CONF_NAME]
            device = self.device_instances.get(device_name)
            if device is None:
                continue

            should_be_on = device_name in ideal_on_list
            state_info = self.device_states.get(device_name, {})
            currently_on = state_info.get("is_on", False)
            is_locked = state_info.get(ATTR_IS_LOCKED, False)

            if should_be_on and not currently_on and not is_locked:
                # Activate device
                await device.activate()
                # Update last target state
                self.device_states[device_name][ATTR_PVO_LAST_TARGET_STATE] = True
                _LOGGER.info(f"Activated device: {device_name}")

            elif not should_be_on and currently_on and not is_locked:
                # Deactivate device
                await device.deactivate()
                # Update last target state
                self.device_states[device_name][ATTR_PVO_LAST_TARGET_STATE] = False
                _LOGGER.info(f"Deactivated device: {device_name}")

    async def _get_averaged_surplus(self) -> float:
        """Get averaged PV surplus over sliding window."""
        surplus_entity = self.global_config[CONF_SURPLUS_SENSOR_ENTITY_ID]
        invert_value = self.global_config.get(CONF_INVERT_SURPLUS_VALUE, False)
        window_minutes = self.global_config[CONF_SLIDING_WINDOW_SIZE]
        now = datetime.now()
        start_time = now - timedelta(minutes=window_minutes)

        try:
            # Use recorder history to get averaged surplus
            history = await get_instance(self.hass).async_add_executor_job(
                get_significant_states, self.hass, start_time, now, [surplus_entity]
            )
            if surplus_entity in history and history[surplus_entity]:
                values = [float(state.state) for state in history[surplus_entity] if state.state not in ['unknown', 'unavailable']]
                avg = sum(values) / len(values) if values else 0.0
                # Apply inversion if configured
                if invert_value:
                    avg = avg * -1
                _LOGGER.debug(f"Averaged surplus over {window_minutes}min: {avg:.2f}W (inverted: {invert_value})")
                return avg
        except Exception as e:
            _LOGGER.warning(f"Failed to get averaged surplus: {e}")

        # Fallback to current state
        state = self.hass.states.get(surplus_entity)
        current = float(state.state) if state and state.state not in ['unknown', 'unavailable'] else 0.0
        # Apply inversion if configured
        if invert_value:
            current = current * -1
        _LOGGER.debug(f"Using current surplus (fallback): {current:.2f}W (inverted: {invert_value})")
        return current
