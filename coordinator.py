"""Coordinator for PV Optimizer integration."""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import entity_registry as er

from .const import (
    DOMAIN,
    CONF_SURPLUS_SENSOR_ENTITY_ID,
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
    CONF_MEASURED_POWER_ENTITY_ID,
    CONF_POWER_THRESHOLD,
    CONF_INVERT_SWITCH,
    TYPE_SWITCH,
    TYPE_NUMERIC,
    ATTR_PVO_LAST_TARGET_STATE,
    ATTR_IS_LOCKED,
    ATTR_MEASURED_POWER_AVG,
)

_LOGGER = logging.getLogger(__name__)


class PVOptimizerCoordinator(DataUpdateCoordinator):
    """Coordinator for PV Optimizer."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
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

    async def _async_update_data(self) -> Dict[str, Any]:
        """Fetch data for the optimization cycle."""
        # Step 1: Data Aggregation - Gather current states and data for all devices
        # This solves the problem of needing up-to-date information on device status, power consumption, and timestamps for locking logic.
        await self._aggregate_device_data()

        # Step 2: Calculate Power Budget - Determine available power for optimization
        # This solves the problem of computing the total power available by combining PV surplus and currently managed power.
        power_budget = await self._calculate_power_budget()

        # Step 3: Ideal State Calculation - Use knapsack algorithm to find optimal device states per priority
        # This solves the problem of maximizing power utilization while respecting priority and budget constraints.
        ideal_on_list = await self._calculate_ideal_state(power_budget)

        # Step 4: State Synchronization - Apply the ideal states to devices
        # This solves the problem of ensuring devices are turned on/off according to the optimization without violating locks.
        await self._synchronize_states(ideal_on_list)

        # Return data for sensors (e.g., power budget, surplus avg)
        surplus_avg = await self._get_averaged_surplus()
        return {
            "power_budget": power_budget,
            "surplus_avg": surplus_avg,
            "ideal_on_list": ideal_on_list,
        }

    async def _aggregate_device_data(self) -> None:
        """Aggregate data for each device: measured_power_avg, is_locked, pvo_last_target_state."""
        # For each device, read current state, last change timestamp, and averaged power
        # This updates the device_states cache with necessary info for locking and power calculations.
        for device in self.devices:
            if not device.get(CONF_OPTIMIZATION_ENABLED, True):
                continue
            device_id = device[CONF_NAME]
            # Read current state (on/off for switches, value for numeric)
            # Calculate averaged power over sliding window
            # Determine if locked based on min times and manual interventions
            # Update device_states[device_id] with: state, last_change, measured_power_avg, is_locked, pvo_last_target_state

    async def _calculate_power_budget(self) -> float:
        """Calculate the total available power budget."""
        # Read averaged PV surplus
        surplus_avg = await self._get_averaged_surplus()
        # Sum power of currently ON and managed devices that are not locked
        running_manageable_power = 0.0
        for device in self.devices:
            if not device.get(CONF_OPTIMIZATION_ENABLED, True):
                continue
            device_id = device[CONF_NAME]
            state_info = self.device_states.get(device_id, {})
            if state_info.get("is_on") and not state_info.get(ATTR_IS_LOCKED, False):
                running_manageable_power += device[CONF_POWER]
        # Budget = surplus + running_manageable_power
        return surplus_avg + running_manageable_power

    async def _calculate_ideal_state(self, power_budget: float) -> List[str]:
        """Calculate the ideal list of devices to turn on using knapsack per priority."""
        ideal_on_list = []
        remaining_budget = power_budget
        # Sort devices by priority (1 highest)
        sorted_devices = sorted(self.devices, key=lambda d: d[CONF_PRIORITY])
        current_priority = None
        priority_group = []
        for device in sorted_devices:
            if device[CONF_PRIORITY] != current_priority:
                # Process previous priority group
                if priority_group:
                    selected = self._knapsack_select(priority_group, remaining_budget)
                    ideal_on_list.extend(selected)
                    remaining_budget -= sum(d[CONF_POWER] for d in selected if d in selected)
                current_priority = device[CONF_PRIORITY]
                priority_group = [device]
            else:
                priority_group.append(device)
        # Process last group
        if priority_group:
            selected = self._knapsack_select(priority_group, remaining_budget)
            ideal_on_list.extend(selected)
        return ideal_on_list

    def _knapsack_select(self, devices: List[Dict], budget: float) -> List[str]:
        """Select subset of devices that maximize power without exceeding budget."""
        # Simple greedy: sort by power descending, add if fits
        # For full knapsack, use DP, but greedy suffices for now
        devices.sort(key=lambda d: d[CONF_POWER], reverse=True)
        selected = []
        for device in devices:
            if device[CONF_POWER] <= budget and not self.device_states.get(device[CONF_NAME], {}).get(ATTR_IS_LOCKED, False):
                selected.append(device[CONF_NAME])
                budget -= device[CONF_POWER]
        return selected

    async def _synchronize_states(self, ideal_on_list: List[str]) -> None:
        """Turn devices on/off based on ideal list."""
        for device in self.devices:
            device_id = device[CONF_NAME]
            should_be_on = device_id in ideal_on_list
            state_info = self.device_states.get(device_id, {})
            currently_on = state_info.get("is_on", False)
            if should_be_on and not currently_on and not state_info.get(ATTR_IS_LOCKED, False):
                # Turn on
                await self._activate_device(device)
                # Update pvo_last_target_state to True
            elif not should_be_on and currently_on and not state_info.get(ATTR_IS_LOCKED, False):
                # Turn off
                await self._deactivate_device(device)
                # Update pvo_last_target_state to False

    async def _activate_device(self, device: Dict) -> None:
        """Activate a device based on its type."""
        if device[CONF_TYPE] == TYPE_SWITCH:
            # Set switch to on (consider invert_switch)
            pass
        elif device[CONF_TYPE] == TYPE_NUMERIC:
            # Set numeric targets to activated_value
            pass

    async def _deactivate_device(self, device: Dict) -> None:
        """Deactivate a device based on its type."""
        if device[CONF_TYPE] == TYPE_SWITCH:
            # Set switch to off (consider invert_switch)
            pass
        elif device[CONF_TYPE] == TYPE_NUMERIC:
            # Set numeric targets to deactivated_value
            pass

    async def _get_averaged_surplus(self) -> float:
        """Get averaged PV surplus over sliding window."""
        # Use history stats or similar to average the surplus sensor
        # For now, return current value as placeholder
        surplus_entity = self.global_config[CONF_SURPLUS_SENSOR_ENTITY_ID]
        state = self.hass.states.get(surplus_entity)
        return float(state.state) if state else 0.0
