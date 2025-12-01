"""
Test configuration and fixtures for PV Optimizer tests.
"""
import pytest
from unittest.mock import Mock, AsyncMock, MagicMock
from datetime import datetime, timedelta
import zoneinfo

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util


@pytest.fixture
def mock_hass():
    """Return a mocked Home Assistant instance."""
    hass = Mock(spec=HomeAssistant)
    hass.states = Mock()
    hass.states.get = Mock(return_value=None)
    hass.config_entries = Mock()
    hass.data = {}
    return hass


@pytest.fixture
def mock_surplus_sensor_state():
    """Return a mocked surplus sensor state."""
    state = Mock()
    state.state = "-500.0"  # Negative = grid export (surplus)
    state.last_updated = dt_util.now()
    return state


@pytest.fixture
def sample_device_config():
    """Return sample device configuration."""
    return {
        "name": "TestDevice",
        "type": "switch",
        "power": 400,
        "priority": 5,
        "switch_entity_id": "switch.test_device",
        "optimization_enabled": True,
        "simulation_active": True,
        "min_on_time": 0,
        "min_off_time": 0,
    }


@pytest.fixture
def sample_device_states():
    """Return sample device states dictionary."""
    return {
        "Device1": {
            "is_on": True,
            "power_measured": 380.0,
            "power_measured_average": 390.0,
            "is_locked": False,
            "is_locked_timing": False,
            "is_locked_manual": False,
            "is_available": True,
            "device_id": "device1_id",
            "pvo_last_target_state": True,
        },
        "Device2": {
            "is_on": False,
            "power_measured": 0.0,
            "power_measured_average": 0.0,
            "is_locked": False,
            "is_locked_timing": False,
            "is_locked_manual": False,
            "is_available": True,
            "device_id": "device2_id",
            "pvo_last_target_state": False,
        },
        "Device3": {
            "is_on": True,
            "power_measured": 950.0,
            "power_measured_average": 945.0,
            "is_locked": False,
            "is_locked_timing": False,
            "is_locked_manual": False,
            "is_available": True,
            "device_id": "device3_id",
            "pvo_last_target_state": True,
        },
    }


@pytest.fixture
def sample_optimizer_stats():
    """Return sample optimizer statistics."""
    return {
        "surplus_current": 500.0,
        "surplus_average": 480.0,
        "power_rated_total": 1330.0,  # Device1 + Device3 (both ON)
        "power_measured_total": 1330.0,
        "surplus_offset": 0.0,
    }


@pytest.fixture
def sample_history_snapshot():
    """Return sample history snapshot."""
    return {
        "timestamp": dt_util.now().isoformat(),
        "surplus_current": 500.0,
        "surplus_average": 480.0,
        "budget_real": 480.0,
        "budget_simulation": 480.0,
        "power_measured_total": 1330.0,
        "active_devices": [
            {"name": "Device1", "power": 380.0},
            {"name": "Device3", "power": 950.0},
        ],
    }
