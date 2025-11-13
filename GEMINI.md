# PV Optimizer Integration

This Home Assistant integration optimizes the use of self-generated PV power by controlling various devices based on the available surplus power.

## Configuration

To use this integration, you need to configure it directly in the Home Assistant UI.

Configurables:
  - PV Surplus Sensor
  - Polling Frequency (seconds)
  - Devices (Simple Switches)
    - Name
    - Switch entity 
    - Power Sensor entity
    - Priority
    - Nominal Power
    - Power On Threshold
    - Min On Duration
    - Min Off Duration
  - Devices (Numeric Devices)
    - Name
    - Power Sensor entity
    - Priority
    - Nominal Power
    - Power On Threshold
    - Min On Duration
    - Min Off Duration
    - List of Numeric Parameters with the following parameters
      - Numeric EntityID
      - On Value
      - Off Value

### Main Configuration

| Key                 | Type    | Required | Description                               |
| ------------------- | ------- | -------- | ----------------------------------------- |
| `pv_surplus_sensor` | string  | yes      | The entity ID of your PV surplus sensor.  |
| `polling_frequency` | integer | yes      | The frequency in seconds to run the polling. |
| `devices`           | list    | yes      | A list of devices to be controlled.       |

### Device Configuration

| Key                 | Type    | Required | Default | Description                                                                                               |
| ------------------- | ------- | -------- | ------- | --------------------------------------------------------------------------------------------------------- |
| `name`              | string  | yes      |         | A unique name for the device.                                                                             |
| `nominal_power`              | string  | yes      |         | The nominal power consumption in watts for the device.                                                                             |
| `switch_entity_id`         | string  | yes      |         | The entity ID of the switch to control.                                                                   |
| `power_sensor_entity_id`      | string  | no      |         | The entity ID of the power sensor for the device.                                                         |
| `priority`          | integer | no       | 10      | The priority of the device. Lower numbers have higher priority.                                           |
| `power_threshold`   | integer | no       | 100     | The power consumption in watts above which the device is considered to be "on".                           |
| `duration_on`       | integer | no       | 10      | The minimum time in minutes the device should be on before it can be switched off.                        |
| `duration_off`      | integer | no       | 10      | The minimum time in minutes the device should be off before it can be switched on.                        |
| `invert_switch`     | boolean | no       | false   | Set to `true` if the switch is inverted (e.g., `on` means the device is off).                             |
| `numeric_parameters`     | list | no       | false   | If set, the device is considered a numeric device that (instead of beeing a swiched on and off) gets set different values for configured parameters.        |
## User Interface

The Devices are shown in Home Assistant on the integration page.
For each device the following sections are produced:

  - Device Info
  - Control Elements
  - Sensors
  - Configurations
  - Diagnostics
  - Activities