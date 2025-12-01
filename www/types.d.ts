/**
 * TypeScript Type Definitions for PV Optimizer Integration
 * 
 * These types define the data structures used throughout the PV Optimizer
 * frontend, ensuring type safety and better IDE support.
 */

/**
 * Global configuration for the PV Optimizer service
 */
interface GlobalConfig {
    surplus_sensor_entity_id: string;
    invert_surplus_value: boolean;
    sliding_window_size: number;
    optimization_cycle_time: number;
}

/**
 * Real-time optimizer statistics shown in System Overview
 */
interface OptimizerStats {
    /** Current instantaneous surplus (W) */
    surplus_current: number;
    /** Averaged surplus over sliding window (W) */
    surplus_average: number;
    /** Total rated power of devices currently ON (W) */
    power_rated_total: number;
    /** Total measured power of devices currently ON (W) */
    power_measured_total: number;
    /** Additional surplus for simulation mode (W) */
    surplus_offset: number;
}

/**
 * Runtime state of a managed device
 */
interface DeviceState {
    /** Whether the device is currently on */
    is_on: boolean;
    /** Current measured power (W) */
    power_measured: number;
    /** Averaged measured power (W) */
    power_measured_average: number;
    /** Whether device is locked (manual or timing) */
    is_locked: boolean;
    /** Whether device is locked due to min on/off time */
    is_locked_timing: boolean;
    /** Whether device is locked due to manual override */
    is_locked_manual: boolean;
    /** Whether device entity is available */
    is_available: boolean;
    /** Home Assistant device registry ID */
    device_id: string;
    /** Last target state set by optimizer */
    pvo_last_target_state: boolean | null;
    /** Last state update timestamp */
    last_update?: Date;
}

/**
 * Configuration for a managed device
 */
interface DeviceConfig {
    /** Device display name */
    name: string;
    /** Device type */
    type: 'switch' | 'numeric';
    /** Rated power consumption (W) */
    power: number;
    /** Optimization priority (1-10, lower = higher priority) */
    priority: number;
    /** Whether optimization is enabled for this device */
    optimization_enabled: boolean;
    /** Whether device participates in simulation */
    simulation_active: boolean;
    /** Minimum on time (minutes) */
    min_on_time?: number;
    /** Minimum off time (minutes) */
    min_off_time?: number;
    /** Switch entity ID (for switch devices) */
    switch_entity_id?: string;
    /** Numeric targets (for numeric devices) */
    numeric_targets?: NumericTarget[];
    /** Measured power sensor entity ID */
    measured_power_entity_id?: string;
    /** Power threshold for detection (W) */
    power_threshold?: number;
}

/**
 * Numeric device target configuration
 */
interface NumericTarget {
    /** Number/input_number entity ID */
    numeric_entity_id: string;
    /** Value when device is activated */
    activated_value: number;
    /** Value when device is deactivated */
    deactivated_value: number;
}

/**
 * Complete device data (config + state)
 */
interface DeviceData {
    config: DeviceConfig;
    state: DeviceState;
}

/**
 * Complete PV Optimizer configuration from WebSocket
 */
interface PVOptimizerConfig {
    /** Integration version */
    version: string;
    /** Global configuration */
    global_config: GlobalConfig;
    /** Array of managed devices */
    devices: DeviceData[];
    /** Current optimizer statistics */
    optimizer_stats: OptimizerStats;
}

/**
 * Historical statistics (Statistics tab)
 */
interface Statistics {
    /** Period covered by statistics (hours) */
    period_hours: number;
    /** Number of snapshots analyzed */
    snapshots_count: number;
    /** Average surplus over period (W) */
    avg_surplus: number;
    /** Minimum surplus recorded (W) */
    min_surplus: number;
    /** Maximum surplus recorded (W) */
    max_surplus: number;
    /** Average power budget (W) */
    avg_budget: number;
    /** Utilization rate (%) */
    utilization_rate: number;
    /** Most active devices during period */
    most_active_devices: ActiveDeviceStats[];
}

/**
 * Statistics for individual device activity
 */
interface ActiveDeviceStats {
    /** Device name */
    name: string;
    /** Number of times device was on */
    on_count: number;
    /** Percentage of time device was on */
    on_percentage: number;
}

/**
 * Single historical snapshot (for Charts tab)
 */
interface HistorySnapshot {
    /** Snapshot timestamp (ISO format) */
    timestamp: string;
    /** Current surplus at snapshot (W) */
    surplus_current: number;
    /** Averaged surplus at snapshot (W) */
    surplus_average: number;
    /** Real power budget at snapshot (W) */
    budget_real: number;
    /** Simulation power budget at snapshot (W) */
    budget_simulation: number;
    /** Total measured power at snapshot (W) */
    power_measured_total: number;
    /** Devices active at snapshot */
    active_devices: ActiveDevice[];
}

/**
 * Active device in a snapshot
 */
interface ActiveDevice {
    /** Device name */
    name: string;
    /** Measured power (W) */
    power: number;
}

/**
 * ApexCharts series data format
 */
interface ChartSeries {
    /** Series name */
    name: string;
    /** Data points [timestamp (ms), value] */
    data: Array<[number, number]>;
}

/**
 * History data response from WebSocket
 */
interface HistoryData {
    /** Array of historical snapshots */
    snapshots: HistorySnapshot[];
    /** Total number of snapshots */
    count: number;
}

/**
 * WebSocket command for resetting device
 */
interface ResetDeviceCommand {
    type: 'pv_optimizer/reset_device';
    device_name: string;
}

/**
 * WebSocket command for setting simulation offset
 */
interface SetSimulationOffsetCommand {
    type: 'pv_optimizer/set_simulation_offset';
    offset: number;
}

/**
 * WebSocket command for updating device config
 */
interface UpdateDeviceConfigCommand {
    type: 'pv_optimizer/update_device_config';
    device_name: string;
    updates: Partial<DeviceConfig>;
}

/**
 * WebSocket command for getting history
 */
interface GetHistoryCommand {
    type: 'pv_optimizer/history';
    hours?: number;
}

/**
 * WebSocket command for getting statistics
 */
interface GetStatisticsCommand {
    type: 'pv_optimizer/statistics';
}

// Export all types for use in JavaScript with JSDoc
export type {
    GlobalConfig,
    OptimizerStats,
    DeviceState,
    DeviceConfig,
    NumericTarget,
    DeviceData,
    PVOptimizerConfig,
    Statistics,
    ActiveDeviceStats,
    HistorySnapshot,
    ActiveDevice,
    ChartSeries,
    HistoryData,
    ResetDeviceCommand,
    SetSimulationOffsetCommand,
    UpdateDeviceConfigCommand,
    GetHistoryCommand,
    GetStatisticsCommand,
};
