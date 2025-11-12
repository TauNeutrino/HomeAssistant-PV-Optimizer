import logging
from datetime import timedelta, datetime
from itertools import chain, combinations
import math

from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.const import SERVICE_TURN_ON, SERVICE_TURN_OFF, STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.util import dt as dt_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

def find_best_combination(devices, budget):
    """
    Find the combination of devices that maximizes power usage without exceeding the budget.
    This is a variation of the 0/1 knapsack problem.
    """
    if not devices or budget <= 0:
        return []

    # Sort devices by power to potentially find a good fit faster, though not strictly necessary for correctness
    devices.sort(key=lambda x: x['power'], reverse=True)
    
    best_combo = []
    best_power = 0

    # We can iterate through all possible subset sizes
    for i in range(1, len(devices) + 1):
        # And all combinations of that size
        for combo in combinations(devices, i):
            current_power = sum(d['power'] for d in combo)
            if best_power < current_power <= budget:
                best_power = current_power
                best_combo = [d['name'] for d in combo]
    
    _LOGGER.debug(f"Found best combination for budget {budget}W: {best_combo} using {best_power}W")
    return best_combo


class PvoCoordinator(DataUpdateCoordinator):
    """PV Optimizer Coordinator."""

    def __init__(self, hass: HomeAssistant, entry):
        """Initialize the coordinator."""
        _LOGGER.info("Initializing PV Optimizer Coordinator")
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=1),  # Run every minute like the automation
        )
        self.config_entry = entry
        # This set will store the entity_ids of switches that we have turned on.
        # This is how we know a device is "managed" by the optimizer.
        self._managed_switches = set()

    async def _async_update_data(self):
        """This is the main optimization logic, translated from the YAML automation."""
        _LOGGER.info("--- PV Optimizer Cycle Start ---")

        # =================================================================================
        # SECTION 1: DATA GATHERING & PRE-PROCESSING
        # =================================================================================
        _LOGGER.debug("SECTION 1: Gathering device data")

        # Get the configured devices from the options flow
        configured_devices = self.config_entry.options.get("devices", [])
        # Get the main switch state for each device (the one that enables/disables automation for it)
        optimizer_switches = {
            f"pvo_{d.get('name', '').lower().replace(' ', '_')}": d.get('name')
            for d in configured_devices
        }
        
        consumers_config = []
        for device_conf in configured_devices:
            device_name = device_conf.get("name")
            switch_entity_id = device_conf.get("switch_entity_id")

            # Check if the automation is enabled for this device
            pvo_switch_unique_id = f"pvo_{device_name.lower().replace(' ', '_')}"
            # The entity_id of our own switch is based on its unique_id
            pvo_switch_entity_id = self.hass.data[DOMAIN].get(pvo_switch_unique_id)
            
            is_automation_enabled = False
            if pvo_switch_entity_id:
                pvo_switch_state = self.hass.states.get(pvo_switch_entity_id)
                if pvo_switch_state:
                    is_automation_enabled = (pvo_switch_state.state == STATE_ON)

            if not is_automation_enabled:
                _LOGGER.debug(f"Device '{device_name}' is disabled by its optimizer switch, skipping.")
                continue

            if not switch_entity_id:
                _LOGGER.warning(f"Device '{device_name}' has no switch entity configured, skipping.")
                continue

            switch_state = self.hass.states.get(switch_entity_id)
            if not switch_state:
                _LOGGER.warning(f"Switch entity '{switch_entity_id}' for device '{device_name}' not found, skipping.")
                continue

            is_on = (switch_state.state == STATE_ON)
            
            # Check for manual override: if the switch is on but not in our managed set, it was turned on manually.
            if is_on and switch_entity_id not in self._managed_switches:
                _LOGGER.info(f"Device '{device_name}' ({switch_entity_id}) was turned on manually. It will not be turned off by the optimizer.")

            # A device is managed if we turned it on, or if it was turned on manually.
            # We only turn off devices that we ourselves have turned on.
            is_managed_by_us = switch_entity_id in self._managed_switches

            # Check if the device is "locked" by min_on_time or min_off_time
            is_locked = False
            now = dt_util.utcnow()
            last_changed_minutes = (now - switch_state.last_changed).total_seconds() / 60
            
            min_on_time = device_conf.get("min_on_time", 0)
            min_off_time = device_conf.get("min_off_time", 0)

            if is_on and min_on_time > 0 and last_changed_minutes < min_on_time:
                is_locked = True
                _LOGGER.debug(f"Device '{device_name}' is ON and locked for another {min_on_time - last_changed_minutes:.1f} minutes.")
            elif not is_on and min_off_time > 0 and last_changed_minutes < min_off_time:
                is_locked = True
                _LOGGER.debug(f"Device '{device_name}' is OFF and locked for another {min_off_time - last_changed_minutes:.1f} minutes.")

            consumers_config.append({
                "name": device_name,
                "priority": device_conf.get("priority", 10),
                "power": device_conf.get("power", 0),
                "switch_entity_id": switch_entity_id,
                "is_on": is_on,
                "is_managed_by_us": is_managed_by_us,
                "is_locked": is_locked,
            })
        
        _LOGGER.debug(f"Processed consumers_config: {consumers_config}")

        # =================================================================================
        # SECTION 2: BUDGET-BERECHNUNG
        # =================================================================================
        _LOGGER.debug("SECTION 2: Calculating power budget")
        
        pv_surplus_sensor = self.config_entry.options.get("pv_surplus_sensor")
        if not pv_surplus_sensor:
            _LOGGER.error("PV surplus sensor not configured. Aborting cycle.")
            return

        surplus_state = self.hass.states.get(pv_surplus_sensor)
        if not surplus_state or surplus_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            _LOGGER.warning(f"PV surplus sensor '{pv_surplus_sensor}' is unavailable. Aborting cycle.")
            return
        
        try:
            # IMPORTANT: Based on the automation logic, we assume the surplus sensor
            # provides a NEGATIVE value for surplus power (e.g., -500W means 500W is being fed to the grid).
            surplus_power = float(surplus_state.state)
            _LOGGER.info(f"Current PV surplus sensor value: {surplus_power}W")
        except (ValueError, TypeError):
            _LOGGER.error(f"Could not parse state '{surplus_state.state}' of PV surplus sensor. Aborting cycle.")
            return

        # Calculate power of devices that are on and managed/locked
        running_managed_power = sum(c['power'] for c in consumers_config if c['is_on'] and (c['is_managed_by_us'] or c['is_locked']))
        _LOGGER.debug(f"Power of running managed/locked devices: {running_managed_power}W")

        # The total power budget we can distribute among all managed devices
        power_budget = -surplus_power + running_managed_power
        _LOGGER.info(f"Total power budget for this cycle: {power_budget}W")

        # =================================================================================
        # SECTION 3: BERECHNUNG DES IDEALZUSTANDS
        # =================================================================================
        _LOGGER.debug("SECTION 3: Calculating ideal state")

        ideal_on_list = []
        
        # First, add all devices that are ON and LOCKED. Their state is non-negotiable.
        for c in consumers_config:
            if c['is_on'] and c['is_locked']:
                ideal_on_list.append(c['name'])
        
        _LOGGER.debug(f"Devices that are ON and LOCKED (must stay on): {ideal_on_list}")

        # The remaining budget is the total budget minus the power of these locked-on devices.
        power_of_locked_on = sum(c['power'] for c in consumers_config if c['name'] in ideal_on_list)
        remaining_power = power_budget - power_of_locked_on
        _LOGGER.debug(f"Power of locked-on devices: {power_of_locked_on}W. Remaining budget: {remaining_power}W")

        # Iterate through priorities from 1 to 10
        for prio in range(1, 11):
            if remaining_power <= 0:
                break # No budget left

            # Get candidate devices for this priority level that are not already locked-on
            candidates = [c for c in consumers_config if c['priority'] == prio and c['name'] not in ideal_on_list]
            if not candidates:
                continue
            
            _LOGGER.debug(f"Finding best combination for priority {prio} with budget {remaining_power}W. Candidates: {[c['name'] for c in candidates]}")
            
            # Find the best combination of devices for the current priority
            best_combination_for_prio = find_best_combination(candidates, remaining_power)

            if best_combination_for_prio:
                ideal_on_list.extend(best_combination_for_prio)
                power_of_best_combo = sum(c['power'] for c in candidates if c['name'] in best_combination_for_prio)
                remaining_power -= power_of_best_combo
                _LOGGER.debug(f"Added {best_combination_for_prio} to ideal ON list. Consumed {power_of_best_combo}W. Remaining budget: {remaining_power}W")

        _LOGGER.info(f"Ideal state calculated. Devices that should be ON: {ideal_on_list}")

        # =================================================================================
        # SECTION 4: SYNCHRONISIERUNG
        # =================================================================================
        _LOGGER.debug("SECTION 4: Synchronizing device states")

        for c in consumers_config:
            should_be_on = c['name'] in ideal_on_list
            entity_id = c['switch_entity_id']

            # --- TURN ON ---
            # Turn on if it should be on, is not already on, and is not locked in the OFF state.
            if should_be_on and not c['is_on'] and not c['is_locked']:
                _LOGGER.info(f"Turning ON '{c['name']}' ({entity_id}). Reason: Should be ON and is not.")
                await self.hass.services.async_call('switch', SERVICE_TURN_ON, {'entity_id': entity_id}, blocking=True)
                self._managed_switches.add(entity_id) # Mark as managed by us

            # --- TURN OFF ---
            # Turn off if it should be off, is currently on, is managed by us, and is not locked in the ON state.
            elif not should_be_on and c['is_on'] and c['is_managed_by_us'] and not c['is_locked']:
                _LOGGER.info(f"Turning OFF '{c['name']}' ({entity_id}). Reason: Should be OFF, is ON, is managed by us, and not locked.")
                await self.hass.services.async_call('switch', SERVICE_TURN_OFF, {'entity_id': entity_id}, blocking=True)
                self._managed_switches.discard(entity_id) # Unmark as managed
        
        _LOGGER.info("--- PV Optimizer Cycle End ---")
