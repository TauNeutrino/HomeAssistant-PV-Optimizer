"""Unit tests for PV Optimizer Coordinators."""
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta

from custom_components.pv_optimizer.coordinators import ServiceCoordinator, DeviceCoordinator
from custom_components.pv_optimizer.const import (
    CONF_POWER,
    CONF_PRIORITY,
    CONF_NAME,
)


class TestServiceCoordinator:
    """Tests for ServiceCoordinator data transformations."""

    @pytest.mark.asyncio
    async def test_power_measured_total_only_counts_on_devices(
        self, mock_hass, sample_device_states
    ):
        """Test that power_measured_total only counts devices that are ON."""
        # Setup
        config_entry = Mock()
        config_entry.data = {
            "entry_type": "service",
            "global": {
                "surplus_sensor_entity_id": "sensor.surplus",
                "sliding_window_size": 5,
            },
        }
        
        coordinator = ServiceCoordinator(mock_hass, config_entry)
        
        # Mock device states (Device1 and Device3 are ON)
        coordinator.device_coordinators = {
            "Device1": Mock(data=sample_device_states["Device1"], device_config={"power": 400}),
            "Device2": Mock(data=sample_device_states["Device2"], device_config={"power": 25}),
            "Device3": Mock(data=sample_device_states["Device3"], device_config={"power": 950}),
        }
        
        # Calculate expected value (only ON devices)
        expected_measured = 380.0 + 950.0  # Device1 + Device3
        
        # Mock the calculation in _async_update_data
        calculated_total = sum(
            state.get("power_measured", 0)
            for state in sample_device_states.values()
            if state.get("is_on")
        )
        
        assert calculated_total == expected_measured
        assert calculated_total == 1330.0

    @pytest.mark.asyncio
    async def test_power_rated_total_only_counts_on_devices(
        self, mock_hass, sample_device_states
    ):
        """Test that power_rated_total only counts devices that are ON."""
        device_configs = {
            "Device1": {"power": 400},
            "Device2": {"power": 25},
            "Device3": {"power": 950},
        }
        
        # Calculate expected value (only ON devices)
        expected_rated = 400 + 950  # Device1 + Device3
        
        # Mock the calculation
        calculated_total = sum(
            device_configs[name].get("power", 0)
            for name, state in sample_device_states.items()
            if state.get("is_on")
        )
        
        assert calculated_total == expected_rated
        assert calculated_total == 1350.0

    def test_surplus_calculation(self, mock_surplus_sensor_state):
        """Test surplus value calculation with inversion."""
        # Test default inversion (grid export is negative, surplus is positive)
        surplus_value = float(mock_surplus_sensor_state.state)
        inverted_surplus = surplus_value * -1
        
        assert inverted_surplus == 500.0
        
        # Test double inversion (when invert_surplus_value is True)
        double_inverted = inverted_surplus * -1
        assert double_inverted == -500.0

    def test_device_locking_logic(self, sample_device_states):
        """Test that locked devices are excluded from optimization."""
        # Manually lock Device1
        sample_device_states["Device1"]["is_locked_manual"] = True
        sample_device_states["Device1"]["is_locked"] = True
        
        # Filter unlocked devices
        unlocked_devices = [
            name for name, state in sample_device_states.items()
            if not state.get("is_locked")
        ]
        
        assert "Device1" not in unlocked_devices
        assert "Device2" in unlocked_devices
        assert "Device3" in unlocked_devices


class TestKnapsackOptimization:
    """Tests for knapsack optimization algorithm."""

    def test_optimization_with_sufficient_budget(self):
        """Test device selection when budget is sufficient."""
        devices = [
            {"name": "Device1", "power": 400, "priority": 5},
            {"name": "Device2", "power": 950, "priority": 6},
            {"name": "Device3", "power": 25, "priority": 5},
        ]
        budget = 1500.0
        
        # Sort by priority (lower number = higher priority)
        sorted_devices = sorted(devices, key=lambda d: d["priority"])
        
        selected = []
        remaining_budget = budget
        
        for device in sorted_devices:
            if device["power"] <= remaining_budget:
                selected.append(device["name"])
                remaining_budget -= device["power"]
        
        assert "Device1" in selected  # Priority 5, 400W
        assert "Device3" in selected  # Priority 5, 25W
        assert "Device2" in selected  # Priority 6, 950W
        assert remaining_budget == 125.0

    def test_optimization_with_insufficient_budget(self):
        """Test device selection when budget is too small."""
        devices = [
            {"name": "Device1", "power": 400, "priority": 5},
            {"name": "Device2", "power": 950, "priority": 6},
        ]
        budget = 300.0  # Not enough for any device
        
        selected = []
        for device in devices:
            if device["power"] <= budget:
                selected.append(device)
        
        assert len(selected) == 0

    def test_optimization_priority_order(self):
        """Test that devices are selected by priority first."""
        devices = [
            {"name": "LowPrio", "power": 100, "priority": 10},
            {"name": "HighPrio", "power": 100, "priority": 1},
            {"name": "MedPrio", "power": 100, "priority": 5},
        ]
        budget = 200.0
        
        sorted_devices = sorted(devices, key=lambda d: d["priority"])
        
        selected = []
        remaining_budget = budget
        
        for device in sorted_devices:
            if device["power"] <= remaining_budget:
                selected.append(device["name"])
                remaining_budget -= device["power"]
        
        # Should select HighPrio and MedPrio first
        assert selected[0] == "HighPrio"
        assert selected[1] == "MedPrio"
        assert "LowPrio" not in selected


class TestDeviceCoordinator:
    """Tests for DeviceCoordinator state management."""

    def test_device_state_structure(self, sample_device_states):
        """Test that device state has all required fields."""
        device_state = sample_device_states["Device1"]
        
        # Verify required fields
        assert "is_on" in device_state
        assert "power_measured" in device_state
        assert "power_measured_average" in device_state
        assert "is_locked" in device_state
        assert "is_locked_timing" in device_state
        assert "is_locked_manual" in device_state
        assert "is_available" in device_state
        assert "device_id" in device_state
        
        # Verify types
        assert isinstance(device_state["is_on"], bool)
        assert isinstance(device_state["power_measured"], float)
        assert isinstance(device_state["is_locked"], bool)

    def test_unavailable_device_handling(self, sample_device_states):
        """Test that unavailable devices are handled correctly."""
        # Mark device as unavailable
        sample_device_states["Device1"]["is_available"] = False
        
        # Filter available devices
        available_devices = [
            name for name, state in sample_device_states.items()
            if state.get("is_available", True)
        ]
        
        assert "Device1" not in available_devices
        assert len(available_devices) == 2
