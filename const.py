"""Constants for the PV Optimizer integration."""

# The domain of the integration, used as a unique identifier in Home Assistant.
DOMAIN = "pv_optimizer"
# Configuration keys
CONF_DEVICES = "devices"
CONF_PV_SURPLUS_SENSOR = "pv_surplus_sensor"
CONF_POLLING_FREQUENCY = "polling_frequency"

# Device configuration keys
CONF_NAME = "name"
CONF_NOMINAL_POWER = "nominal_power"
CONF_SWITCH_ENTITY_ID = "switch_entity_id"
CONF_POWER_SENSOR_ENTITY_ID = "power_sensor_entity_id"
CONF_PRIORITY = "priority"
CONF_POWER_THRESHOLD = "power_threshold"
CONF_DURATION_ON = "duration_on"
CONF_DURATION_OFF = "duration_off"
CONF_INVERT_SWITCH = "invert_switch"
CONF_NUMERIC_PARAMETERS = "numeric_parameters"

# Default values for device configuration
DEFAULT_PRIORITY = 10
DEFAULT_POWER_THRESHOLD = 100
DEFAULT_DURATION_ON = 10
DEFAULT_DURATION_OFF = 10
DEFAULT_INVERT_SWITCH = False
DEFAULT_NUMERIC_PARAMETERS = False

# Attributes
ATTR_STATUS = "status"
ATTR_POWER_CONSUMPTION = "power_consumption"
ATTR_PRIORITY = "priority"
ATTR_IS_ON = "is_on"

# Services
SERVICE_ACTIVATE = "activate"
SERVICE_DEACTIVATE = "deactivate"
SERVICE_SET_PRIORITY = "set_priority"

# PVO Device States
PVO_STATE_IDLE = "idle"
PVO_STATE_ACTIVE = "active"
PVO_STATE_WAITING_FOR_DURATION = "waiting_for_duration"
PVO_STATE_DISABLED = "disabled"
