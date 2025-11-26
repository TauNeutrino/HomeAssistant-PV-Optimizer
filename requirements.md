# Requirement-Documentation: PV Optimizer

This document outlines the functional requirements for a software system designed to optimize the self-consumption of solar power within a smart home environment. The system's goal is to intelligently activate and deactivate electrical appliances (or change values of control mechanisms) based on the amount of surplus photovoltaic (PV) power available.

## 1. High-Level Goal

The primary objective is to maximize the use of self-generated solar energy by automatically running appliances when there is a power surplus (i.e., when more power is being generated than consumed, which would otherwise be fed into the grid). This reduces reliance on grid power and lowers energy costs.

The secondary goal is ease of use. Therefore all configuration options have to be available in a nice graphical user interface. Configuration options as well as the implications of selecting certain options have to be explained to the user directly at interface level. The interface has to be well structured into configuration topics.
For easy accessability, the PV Optimizer interface shall be linked directly on the left sidebar (like the "browser mod" integration)

## 2. Core Concepts

- **PV Surplus:** The foundational metric for all decisions. It is defined as the net power flow at the grid connection point. A negative value indicates a surplus (power is being exported to the grid), and a positive value indicates a deficit (power is being imported from the grid). The system should aim to keep this value as close to zero as possible from the grid's perspective.
- **Controllable Device:** Any appliance that the system can turn on or off or change its value. Each device has a specific set of configuration parameters.
- **Prioritization:** Devices are assigned a priority level. Higher-priority devices (lower priority number) should be activated before lower-priority devices.
- **Power Budget:** The total amount of power available for consumption at any given time. This is calculated from the current PV surplus plus the power already being consumed by devices under the system's control.
- **Optimization Cycle:** The system operates in discrete cycles, triggered at a regular time interval (e.g., every minute). In each cycle, it evaluates the current power situation and determines the optimal set of devices that should be running.

## 3. System & Device Configuration

The system provides two complementary interfaces for configuration:

### 3.1. Initial Setup (Config Flow)

When first adding the integration:
1. Navigate to **Settings → Devices & Services → Add Integration**
2. Search for "PV Optimizer"
3. Configure the global parameters:
   - **`surplus_sensor_entity_id`**: The primary sensor entity that provides the PV surplus value
   - **`sliding_window_size`**: The size of the sliding window in minutes for averaging the surplus power
   - **`optimization_cycle_time`**: The frequency in seconds at which the optimization algorithm runs

### 3.2. Device Management (Options Flow)

Device configuration (add, edit, delete) is handled through the integration's **Options Flow**:

**Access via Integration Page:**
- Settings → Devices & Services → PV Optimizer → **Configure**
- Menu-based navigation with native Home Assistant forms

**Access via Sidebar Panel:**
- Click "PV Optimizer" in sidebar
- Click **"Open Configuration"** button
- Automatically navigates to options flow

The options flow provides:
- Global configuration editing
- Device list (view/edit/delete existing devices)
- Add Switch Device (separate form optimized for switches)
- Add Numeric Device (separate form optimized for numeric controls)

### 3.3. Device Configuration Parameters

Each device requires the following configuration parameters:

-   **`name`**: A human-readable name for the device (e.g., "Hot water optimization").
-   **`priority`**: A numerical value indicating its activation priority (e.g., 1-10, where 1 is the highest).
-   **`power`**: The nominal power consumption of the device in Watts. This is used for budget calculations.
-   **`type`**: The control mechanism for the device. This determines which other parameters are required.
    -   If `type` is **`switch`**:
        -   **`switch_entity_id`**: The entity ID of the switch to be controlled.
    -   If `type` is **`numeric`**:
        -   **`numeric_targets`**: A list of objects, where each object defines an entity to control and its target values. Each object must contain:
            -   `numeric_entity_id`: The entity ID of the number or input_number to be set.
            -   `activated_value`: The value to set when the device is activated by the optimizer.
            -   `deactivated_value`: The value to set when the device is deactivated.
-   **`min_on_time`** (optional): The minimum duration (in minutes) the device must remain on after being activated, to prevent short-cycling.
-   **`min_off_time`** (optional): The minimum duration (in minutes) the device must remain off after being deactivated, to prevent short-cycling.
-   **`optimization_enabled`**: A master boolean flag to determine if the device should be considered by the optimizer at all.
-   `measured_power_entity_id`: A sensor that provides the real-time power consumption of the device.
-   **`power_threshold`** (optional): A threshold in Watts, used with `power_sensor_entity_id`. If the measured power is above this threshold, the device is considered "ON". Defaults to 100W.
-   **`invert_switch`** (optional): A boolean flag. If `true`, the system will turn the switch `off` to activate the device and `on` to deactivate it.

Internally, the system will use a class-based approach, with a base class for all devices and specialized subclasses for `switch` and `numeric` types to ensure clean and maintainable logic.

## 4. Functional Requirements (Core Logic)

The core logic runs in a loop triggered at the `optimization_cycle_time` frequency.

### 4.1. Data Aggregation

- At the start of each cycle, the system must discover and load the configuration for all `automation_enabled` devices.
- It must read the current state (on/off) of each device and the timestamp of its last change.
- It must read the current values of the dynamic configuration entities (see section 5.3) for each device.

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


### 5.2. Appliance Monitoring Entities
For each configured appliance, a dedicated device (e.g., "PVO Hot Water Heater") shall be created, linked to the controller. Each appliance device will have the following entities for **monitoring**:
- A sensor for its locked status.
- A sensor for its measured power.
- A sensor for the last target state set by the optimizer.
- A sensor indicating its current contribution to the power budget.

### 5.3. Dynamic Configuration Entities
To allow for real-time adjustments from the UI, the following parameters will be exposed as entities on each appliance's device card. The optimizer will use the current state of these entities for its calculations, overriding the initial values set in the configuration flow.

- **`Priority`**: A `number` entity to dynamically change the device's priority.
- **`Optimization Enabled`**: A `switch` entity to enable or disable the device from being considered by the optimizer.
- **`Minimum On Time`**: A `number` entity to adjust the `min_on_time`.
- **`Minimum Off Time`**: A `number` entity to adjust the `min_off_time`.

## 6. Advanced Features

### 6.1. Simulation Mode
To allow users to test configuration changes without affecting real devices, a "Simulation Mode" is available.
- **Global Simulation**: The system calculates a parallel "simulation budget" and "simulation ideal list".
- **Device Simulation**: Each device has a `simulation_active` flag.
    - If `true`, the device participates in the simulation calculation.
    - Simulation ignores manual locks (assumes the optimizer has full control).
- **Surplus Offset**: The simulation can run with a virtual offset to the surplus (e.g., "what if I had 500W more surplus?").

### 6.2. Invert Surplus
A global configuration option `invert_surplus_value` allows handling surplus sensors that report positive values for export (instead of the default negative).

### 6.3. Manual Control
Each device has a dedicated "Manual Control" switch entity that allows forcing the device state, which is useful for testing and overrides.

### 6.4. Detailed Monitoring
The system provides granular feedback on why a device is locked:
- **Timing Lock**: Locked due to minimum on/off time constraints.
- **Manual Lock**: Locked due to user intervention (state mismatch with optimizer target).

