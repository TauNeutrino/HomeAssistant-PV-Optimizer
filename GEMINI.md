# Requirement-Documentation: PV Optimizer

This document outlines the functional requirements for a software system designed to optimize the self-consumption of solar power within a smart home environment. The system's goal is to intelligently activate and deactivate electrical appliances (or change values of control mechanisms) based on the amount of surplus photovoltaic (PV) power available.

## 1. High-Level Goal

The primary objective is to maximize the use of self-generated solar energy by automatically running appliances when there is a power surplus (i.e., when more power is being generated than consumed, which would otherwise be fed into the grid). This reduces reliance on grid power and lowers energy costs.

## 2. Core Concepts

- **PV Surplus:** The foundational metric for all decisions. It is defined as the net power flow at the grid connection point. A negative value indicates a surplus (power is being exported to the grid), and a positive value indicates a deficit (power is being imported from the grid). The system should aim to keep this value as close to zero as possible from the grid's perspective.
- **Controllable Device:** Any appliance that the system can turn on or off or change its value. Each device has a specific set of configuration parameters.
- **Prioritization:** Devices are assigned a priority level. Higher-priority devices (lower priority number) should be activated before lower-priority devices.
- **Power Budget:** The total amount of power available for consumption at any given time. This is calculated from the current PV surplus plus the power already being consumed by devices under the system's control.
- **Optimization Cycle:** The system operates in discrete cycles, triggered at a regular time interval (e.g., every minute). In each cycle, it evaluates the current power situation and determines the optimal set of devices that should be running.

## 3. System & Device Configuration

The system must be configurable through the Home Assistant graphical user interface (Config Flow).

### 3.1. General Configuration

**`surplus_sensor_entity_id`**: A global setting must define the primary sensor entity that provides the PV surplus value. But this system should use a time-averaged (sliding window) value of this sensor to smooth out brief fluctuations. 

**`sliding_window_size`**: The sliding window size shall be configurable (# of minutes)

**`optimization_cycle_time`**: A second global setting has to define the optimization cycle (# of seconds) that provides the running frequency of the algorithms.

### 3.2. Device Configuration

The UI must allow users to add, edit, and remove controllable devices. Each device has the following configuration parameters:

- **`name`**: A human-readable name for the device (e.g., "Hot water optimization").
- **`priority`**: A numerical value indicating its activation priority (e.g., 1-10, where 1 is the highest).
- **`power`**: The nominal power consumption of the device in Watts. This can be used for budget calculations.
- **`type`**: The control mechanism for the device. This determines which other parameters are required.
    - If `type` is **`switch`**:
        - **`switch_entity_id`**: The entity ID of the switch to be controlled.
    - If `type` is **`numeric`**:
        - **`numeric_targets`**: A list of objects, where each object defines an entity to control and its target values. Each object must contain:
            - `numeric_entity_id`: The entity ID of the number or input_number to be set.
            - `activated_value`: The value to set when the device is activated by the optimizer.
            - `deactivated_value`: The value to set when the device is deactivated.
- **`min_on_time`** (optional): The minimum duration (in minutes) the device must remain on after being activated, to prevent short-cycling.
- **`min_off_time`** (optional): The minimum duration (in minutes) the device must remain off after being deactivated, to prevent short-cycling.
- **`optimization_enabled`**: A master boolean flag to determine if the device should be considered by the optimizer at all.
- `measured_power_entity_id`: A sensor that provides the real-time power consumption of the device.
 - **`power_threshold`** (optional): A threshold in Watts, used with `power_sensor_entity_id`. If the measured power is above this threshold, the device is considered "ON". Defaults to 100W.
- **`invert_switch`** (optional): A boolean flag. If `true`, the system will turn the switch `off` to activate the device and `on` to deactivate it.

## 4. Functional Requirements (Core Logic)

The core logic runs in a loop triggered at the `optimization_cycle_time` frequency.

### 4.1. Data Aggregation

- At the start of each cycle, the system must discover and load the configuration for all `automation_enabled` devices.
- It must read the current state (on/off) of each device and the timestamp of its last change.

#### 4.2. Device Data

The following data is aquired or generated for each device:

- `measured_power_avg`: Sensor providing the averaged power consumption of the device for the last # of minutes (definde by `sliding_window_size`).
- `is_locked`: info if the device state may changed or not.
- `pvo_last_target_state`: holds the last state the device was set to by the optimizer.


### 4.2.1. Device Locking

- The system must determine if a device is "locked" in its current state.
- A device is **locked** if it is currently on and its `min_on_time` has not yet elapsed.
- A device is **locked** if it is currently off and its `min_off_time` has not yet elapsed.
- A device is **locked** if `pvo__last_target_state` is not the current state of the device (meaning a manual intervention by the user happend).
- Locked devices cannot have their state changed during the current cycle.

### 4.3. Power Budget Calculation

1.  Read the current (averaged) PV surplus.
2.  Calculate the `running_manageable_power`: the sum of the power consumption of all devices that are currently **ON** and **managed by the optimizer** and not locked.
3.  The `total_available_power` (the "budget") is the sum of the PV surplus and the `running_manageable_power`.

### 4.4. Ideal State Calculation

This is the central optimization step. The system must determine the "ideal" set of devices that should be running to best utilize the `total_available_power`.

1.  **Initialize Ideal List:** Start with an empty list of devices that should be on. 
2.  **Iterate Through Priorities:** Process devices in order of priority, from highest (1) to lowest (10).
3.  **Select Best Combination:** For each priority level, consider all devices that are not locked. Find the combination of these devices that:
    - Maximizes power consumption.
    - Does **not** exceed the remaining `total_available_power`.
    - This is a variation of the "knapsack problem" for each priority level.
4.  **Update Budget:** Add the selected devices to the ideal list and subtract their combined power from the `total_available_power`.
5.  **Repeat:** Continue to the next priority level with the reduced budget.

### 4.5. State Synchronization
- Compare the calculated "ideal list" with the actual state of the devices.
- For each device:
    - **Turn ON:** If the device is in the ideal list, is currently OFF, the system shall activate it.
    - **Turn OFF:** If the device is NOT in the ideal list, is currently ON, is managed by the optimizer, the system shall deactivate it.


## 5. Monitoring & Statistics

- The integration should expose its internal state for debugging and monitoring purposes by using the logging mechanism of HOME Asistant.
- This includes but is not limited to:
    - The calculated power budget.
    - The list of all configured devices with their current parameters (priority, power, state, locked status, etc.).
    - The final "ideal on list" calculated in the cycle.

## 5. Entity & State Model

The integration shall create a clear entity model in Home Assistant for monitoring and control.

### 5.1. Controller Device
A central "PV Optimizer Controller" device shall be created to group global sensors.


### 5.2. Appliance Devices
For each configured appliance, a dedicated device (e.g., "PVO Hot Water Heater") shall be created, linked to the controller. Each appliance device will have the following entities:

