"""
History Tracker for PV Optimizer Integration

This module tracks historical optimization data at 5-minute intervals for
visualization and statistics.

Purpose:
- Store time-series data of surplus, power budget, and device states
- Enable historical charts and statistics calculations
- Use Home Assistant's built-in storage mechanisms

Storage Strategy:
- 5-minute snapshots stored as sensor state attributes
- Leverages Home Assistant's recorder for persistence
- Automatic cleanup of data older than configured retention period
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any

from homeassistant.util import dt as dt_util
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
STORAGE_KEY = "pv_optimizer_history"
SNAPSHOT_INTERVAL = timedelta(minutes=5)
DEFAULT_RETENTION_DAYS = 7


class HistoryTracker:
    """Track and store historical optimization data."""

    def __init__(self, hass: HomeAssistant, config_entry):
        """Initialize the history tracker."""
        self.hass = hass
        self.config_entry = config_entry
        self._store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}_{config_entry.entry_id}")
        self._snapshots: List[Dict[str, Any]] = []
        self._unsub_interval = None
        
    async def async_setup(self):
        """Set up the history tracker."""
        # Load existing snapshots from storage
        data = await self._store.async_load()
        if data:
            self._snapshots = data.get("snapshots", [])
            _LOGGER.info("Loaded %d historical snapshots", len(self._snapshots))
        
        # Start periodic snapshot collection
        self._unsub_interval = async_track_time_interval(
            self.hass,
            self._async_take_snapshot,
            SNAPSHOT_INTERVAL
        )
        
        _LOGGER.info("History tracker initialized with %d-minute intervals", SNAPSHOT_INTERVAL.total_seconds() / 60)
        
    async def async_stop(self):
        """Stop the history tracker."""
        if self._unsub_interval:
            self._unsub_interval()
        await self._async_save()
        
    @callback
    async def _async_take_snapshot(self, now):
        """Take a snapshot of current optimization state."""
        try:
            # Get global coordinator data
            # In __init__.py: hass.data[DOMAIN][entry.entry_id] = coordinator
            global_coordinator = self.hass.data.get("pv_optimizer", {}).get(
                self.config_entry.entry_id
            )
            
            if not global_coordinator:
                _LOGGER.debug("Global coordinator not available for snapshot")
                return
                
            stats = global_coordinator.data.get("optimizer_stats", {})
            devices_state = global_coordinator.data.get("devices_state", {})
            
            # Build snapshot
            snapshot = {
                "timestamp": now.isoformat(),
                "current_surplus": stats.get("current_surplus", 0),
                "averaged_surplus": stats.get("averaged_surplus", 0),
                "power_budget": stats.get("power_budget", 0),
                "measured_power_on_devices": stats.get("measured_power_on_devices", 0),
                "active_devices": []
            }
            
            # Collect active device data for stacked charts
            for device_name, device_data in devices_state.items():
                if device_data.get("is_on"):
                    snapshot["active_devices"].append({
                        "name": device_name,
                        "measured_power": device_data.get("measured_power_avg", device_data.get("power", 0)),
                        "priority": device_data.get("priority", 10)
                    })
            
            # Add snapshot to history
            self._snapshots.append(snapshot)
            
            # Cleanup old snapshots
            await self._async_cleanup_old_data()
            
            # Save periodically (every hour to avoid excessive writes)
            if len(self._snapshots) % 12 == 0:  # Every 12 snapshots = 1 hour
                await self._async_save()
                
            _LOGGER.debug("Snapshot taken: %d active devices, surplus: %.0fW", 
                         len(snapshot["active_devices"]), snapshot["current_surplus"])
                         
        except Exception as err:
            _LOGGER.error("Error taking snapshot: %s", err)
    
    async def _async_cleanup_old_data(self):
        """Remove snapshots older than retention period."""
        retention_days = self.config_entry.options.get("history_retention_days", DEFAULT_RETENTION_DAYS)
        # Use timezone-aware current time
        cutoff = dt_util.now() - timedelta(days=retention_days)
        
        original_count = len(self._snapshots)
        # Ensure stored timestamps are parsed as aware datetimes
        self._snapshots = [
            s for s in self._snapshots
            if dt_util.parse_datetime(s["timestamp"]) > cutoff
        ]
        
        removed = original_count - len(self._snapshots)
        if removed > 0:
            _LOGGER.debug("Removed %d old snapshots (retention: %d days)", removed, retention_days)
    
    async def _async_save(self):
        """Save snapshots to storage."""
        try:
            await self._store.async_save({"snapshots": self._snapshots})
            _LOGGER.debug("Saved %d snapshots to storage", len(self._snapshots))
        except Exception as err:
            _LOGGER.error("Error saving snapshots: %s", err)
    
    def get_snapshots(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get snapshots for the specified time range."""
        # Use timezone-aware current time
        cutoff = dt_util.now() - timedelta(hours=hours)
        return [
            s for s in self._snapshots
            if dt_util.parse_datetime(s["timestamp"]) > cutoff
        ]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Calculate statistics from historical data."""
        if not self._snapshots:
            return {}
        
        # Calculate metrics from last 24 hours
        recent_snapshots = self.get_snapshots(24)
        
        if not recent_snapshots:
            return {}
        
        # Total optimization events (device state changes)
        total_events = sum(len(s["active_devices"]) for s in recent_snapshots)
        
        # Average surplus utilization
        total_surplus = sum(s["current_surplus"] for s in recent_snapshots)
        total_used = sum(s["measured_power_on_devices"] for s in recent_snapshots)
        utilization_rate = (total_used / total_surplus * 100) if total_surplus > 0 else 0
        
        # Most active device
        device_counts = {}
        for snapshot in recent_snapshots:
            for device in snapshot["active_devices"]:
                device_counts[device["name"]] = device_counts.get(device["name"], 0) + 1
        
        most_active_device = max(device_counts.items(), key=lambda x: x[1])[0] if device_counts else "None"
        
        # Peak optimization time (hour with most active devices)
        hour_activity = {}
        for snapshot in recent_snapshots:
            # Parse timestamp as aware datetime
            dt = dt_util.parse_datetime(snapshot["timestamp"])
            # Use local hour for user-friendly display
            hour = dt_util.as_local(dt).hour
            hour_activity[hour] = hour_activity.get(hour, 0) + len(snapshot["active_devices"])
        
        peak_hour = max(hour_activity.items(), key=lambda x: x[1])[0] if hour_activity else 0
        
        return {
            "total_events": total_events,
            "utilization_rate": round(utilization_rate, 1),
            "most_active_device": most_active_device,
            "peak_hour": peak_hour,
            "snapshots_count": len(recent_snapshots)
        }
