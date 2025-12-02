"""
Constants for PV Optimizer Integration

This module defines all constants used throughout the PV Optimizer integration.
It includes configuration keys, device types, attribute names, and utility functions.

Organization:
------------
1. Domain and UI Constants: Integration identifier and panel configuration
2. Utility Functions: Helper functions for name normalization
3. Global Configuration Keys: Settings that apply to the entire optimization system
4. Device Configuration Keys: Per-device settings
5. Device Types: Types of controllable devices
6. Attributes: Custom attributes added to entities
"""

import re

# ============================================================================
# DOMAIN AND UI CONSTANTS
# ============================================================================

# Integration domain identifier - used throughout Home Assistant to identify this integration
# This appears in entity IDs (e.g., sensor.pv_optimizer_*), service calls, and event names
DOMAIN = "pv_optimizer"

# Frontend panel configuration
# The panel provides a UI interface accessible from the Home Assistant sidebar
FRONTEND_URL = "/pv_optimizer-panel.js"  # URL path to serve the JavaScript panel
PANEL_TITLE = "PV Optimizer"              # Title displayed in sidebar
PANEL_ICON = "mdi:solar-power"            # Material Design Icon shown in sidebar
PANEL_URL = "pv-optimizer"                # URL path for the panel (e.g., /pv-optimizer)


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def normalize_device_name(name: str) -> str:
    """
    Normalize device name to a safe identifier (entity_id format).
    
    This function converts user-provided device names into safe identifiers that
    can be used in entity IDs and device identifiers. It ensures compatibility
    with Home Assistant's naming requirements.
    
    Functionality Achieved:
    ----------------------
    1. Converts to lowercase for consistency
    2. Replaces spaces and special characters with underscores
    3. Removes leading/trailing underscores
    4. Collapses multiple consecutive underscores into single underscore
    
    Transformation Examples:
    -----------------------
    "Hot Water Heater" -> "hot_water_heater"
    "Heizstab (Küche)!" -> "heizstab_kuche"
    "  Test__Device  " -> "test_device"
    "123-Test Device" -> "123_test_device"
    
    Use Cases:
    ----------
    - Creating device identifiers for device registry
    - Generating unique entity IDs
    - Ensuring cross-platform compatibility
    
    Args:
        name: User-provided device name (can contain any characters)
    
    Returns:
        str: Normalized name safe for use in entity IDs and identifiers
    """
    # Convert to lowercase for consistency
    name = name.lower()
    
    # Replace spaces and special characters with underscores
    # Pattern [^a-z0-9_]+ matches one or more characters that are NOT:
    # - lowercase letters (a-z)
    # - digits (0-9)
    # - underscores (_)
    name = re.sub(r'[^a-z0-9_]+', '_', name)
    
    # Remove leading/trailing underscores
    # Example: "_test_device_" becomes "test_device"
    name = name.strip('_')
    
    # Replace multiple consecutive underscores with single underscore
    # Example: "test__device" becomes "test_device"
    name = re.sub(r'_+', '_', name)
    
    return name


# ============================================================================
# DEVICE COLORS
# ============================================================================
# Predefined color palette for device visualization
# These colors are used consistently across charts, power bars, and device cards

DEVICE_COLORS = [
    '#4CAF50',  # Green
    '#2196F3',  # Blue
    '#FFC107',  # Amber
    '#9C27B0',  # Purple
    '#F44336',  # Red
    '#00BCD4',  # Cyan
    '#FF9800',  # Orange
    '#795548',  # Brown
    '#607D8B',  # Blue Grey
    '#E91E63'   # Pink
]


# ============================================================================
# DEVICE COLORS
# ============================================================================
# Predefined color palette for device visualization
# These colors are used consistently across charts, power bars, and device cards

DEVICE_COLORS = [
    '#4CAF50',  # Green
    '#2196F3',  # Blue
    '#FFC107',  # Amber
    '#9C27B0',  # Purple
    '#F44336',  # Red
    '#00BCD4',  # Cyan
    '#FF9800',  # Orange
    '#795548',  # Brown
    '#607D8B',  # Blue Grey
    '#E91E63'   # Pink
]


# ============================================================================
# GLOBAL CONFIGURATION CONSTANTS
# ============================================================================
# These settings apply to the entire PV Optimizer system and are configured
# during initial setup (config flow) or via options flow.

# PV Surplus Sensor
# The entity ID of the sensor that provides the current power surplus/deficit
# - Negative values typically indicate surplus (exporting to grid)
# - Positive values indicate deficit (importing from grid)
# Example: "sensor.grid_power" or "sensor.inverter_surplus"
CONF_SURPLUS_SENSOR_ENTITY_ID = "surplus_sensor_entity_id"

# Invert Surplus Value
# Boolean flag to invert the sign of the surplus sensor reading
# Use this when your sensor reports the opposite sign (e.g., positive = surplus)
# - True: Multiply sensor value by -1
# - False: Use sensor value as-is
CONF_INVERT_SURPLUS_VALUE = "invert_surplus_value"

# Sliding Window Size
# Time window (in minutes) for averaging power measurements
# This smooths out brief fluctuations and prevents optimization based on spikes
# - Smaller values (1-3 min): More responsive but less stable
# - Medium values (5-10 min): Good balance (recommended)
# - Larger values (15+ min): Very stable but slower to react
# Default: 5 minutes
CONF_SLIDING_WINDOW_SIZE = "sliding_window_size"

# Optimization Cycle Time
# How frequently (in seconds) the optimization algorithm runs
# - Shorter cycles (30-45s): More responsive but higher CPU usage
# - Standard cycles (60s): Good balance (recommended)
# - Longer cycles (120s+): Lower overhead but slower optimization
# Default: 60 seconds
CONF_OPTIMIZATION_CYCLE_TIME = "optimization_cycle_time"


# ============================================================================
# DEVICE CONFIGURATION CONSTANTS
# ============================================================================
# These settings are configured per device and define how each device operates
# within the optimization system.

# Basic Device Properties
CONF_NAME = "name"              # Human-readable device name (e.g., "Hot Water Heater")
CONF_PRIORITY = "priority"      # Priority level (1-10, where 1 is highest priority)
CONF_POWER = "power"            # Nominal power consumption in Watts
CONF_TYPE = "type"              # Device type: "switch" or "numeric"

# Switch Device Configuration
# For devices controlled by a simple on/off switch entity
CONF_SWITCH_ENTITY_ID = "switch_entity_id"  # Entity ID of the switch to control
CONF_INVERT_SWITCH = "invert_switch"        # If True, "off" means activated

# Numeric Device Configuration
# For devices controlled by setting numeric values (e.g., temperature setpoints)
CONF_NUMERIC_TARGETS = "numeric_targets"    # List of numeric entities to control
CONF_NUMERIC_ENTITY_ID = "numeric_entity_id"  # Entity ID of number/input_number
CONF_ACTIVATED_VALUE = "activated_value"    # Value when device is activated
CONF_DEACTIVATED_VALUE = "deactivated_value"  # Value when device is deactivated

# Device Timing Controls
# These prevent short-cycling and respect device operational constraints
CONF_MIN_ON_TIME = "min_on_time"    # Minimum minutes device must stay ON
CONF_MIN_OFF_TIME = "min_off_time"  # Minimum minutes device must stay OFF

# Optimization Control
# Master switch to enable/disable optimization for this device
CONF_OPTIMIZATION_ENABLED = "optimization_enabled"

# Simulation Control (NEW)
# Boolean flag to mark device for simulation mode
# When True: Device participates in simulation calculations but is NOT physically controlled
# When False: Device only participates in real optimization (if optimization_enabled)
# Both can be True simultaneously for testing/comparison scenarios
# Default: False (backward compatibility)
CONF_SIMULATION_ACTIVE = "simulation_active"

# Power Measurement
# Optional sensor for measuring actual device power consumption
CONF_MEASURED_POWER_ENTITY_ID = "measured_power_entity_id"
# Threshold in Watts to determine if device is ON (when using power sensor)
CONF_POWER_THRESHOLD = "power_threshold"

# Device Color
# Hex color code for consistent visualization across UI elements
CONF_DEVICE_COLOR = "device_color"

# Device Color
# Hex color code for consistent visualization across UI elements
CONF_DEVICE_COLOR = "device_color"


# ============================================================================
# DEVICE TYPE CONSTANTS
# ============================================================================
# Defines the types of devices that can be controlled

# Switch-type device: Controlled by turning a switch on/off
# - Simple binary control (on/off)
# - Examples: Water heater, washing machine, dryer
TYPE_SWITCH = "switch"

# Numeric-type device: Controlled by setting numeric values
# - Can adjust multiple numeric entities (up to 5 targets)
# - Examples: Heat pump temperature setpoints, HVAC settings
TYPE_NUMERIC = "numeric"


# ============================================================================
# CUSTOM ATTRIBUTE CONSTANTS
# ============================================================================
# These attributes are added to entities to provide additional state information

# Last Target State
# Records the last state the optimizer intended for this device
# Used to detect manual interventions (user overrides)
ATTR_PVO_LAST_TARGET_STATE = "pvo_last_target_state"

# Lock Status
# Indicates whether the device is currently locked in its state
# A locked device cannot be controlled by the optimizer until the lock expires
# Reasons for locking:
# - Minimum ON time not yet elapsed
# - Minimum OFF time not yet elapsed
# - Manual intervention detected
ATTR_IS_LOCKED = "is_locked"

# Measured Power Average
# The averaged power consumption over the sliding window
# This smoothed value is used for budget calculations
ATTR_POWER_MEASURED_AVERAGE = "power_measured_average"
