# Changelog - PV Optimizer Custom Integration

## Version 1.1.0 (2025-11-20) - Simulation Feature 🧪

### 🎉 Major New Feature: Simulation Mode

#### What's New

**Parallel Simulation Optimization**
- ✅ Run real and simulation optimizations simultaneously
- ✅ Test device configurations without physical control
- ✅ Compare real vs simulation results side-by-side
- ✅ Independent enable switches for optimization and simulation

**New Switch Entity per Device**
- `switch.pvo_{device}_simulation_active` - Mark device for simulation
- Independent from `optimization_enabled` (both can be active)
- Default: `False` for backward compatibility

**New Sensors**
- `sensor.pv_optimizer_simulation_power_budget` - Budget for simulation
- `sensor.pv_optimizer_simulation_ideal_devices` - List of devices in simulation ideal state
- `sensor.pv_optimizer_real_ideal_devices` - List of devices in real ideal state

**Enhanced Frontend Panel**
- Two new cards: "Real Optimization" and "Simulation" results
- Toggle button to switch between separate cards and comparison table
- Comparison table shows side-by-side device status (Real vs Simulation)
- Visual indicators for simulation-active devices (🧪 icon)
- Summary statistics (device count, total power, budget usage)

#### How It Works

**Separate Budget Calculation (Option A from requirements)**
- Real optimization: PV surplus + power from real running devices
- Simulation: PV surplus + power from simulation running devices
- Clean separation ensures realistic comparison

**Independent Device Control (Option B from requirements)**
- Devices can have both `optimization_enabled` AND `simulation_active`
- Real optimization physically controls devices
- Simulation calculates ideal state but NEVER controls devices
- Perfect for "what-if" scenarios

**Frontend Display (Option C from requirements)**
- Default: Separate cards for Real and Simulation results
- Toggle: Comparison table showing all devices side-by-side
- Easy visual comparison of optimization strategies

#### Use Cases

**Testing New Devices**
```
Scenario: Want to test if adding a washing machine is beneficial

Steps:
1. Add device "Washing Machine" with simulation_active=True
2. Observe simulation results over time
3. Compare with real optimization
4. Decide if device should be added to real optimization
```

**Configuration Tuning**
```
Scenario: Optimize priorities without affecting real devices

Steps:
1. Duplicate device with simulation_active=True
2. Try different priority values
3. Compare simulation vs real results
4. Apply best configuration to real device
```

**Budget Analysis**
```
Scenario: Understand impact of additional loads

Steps:
1. Mark all new/planned devices as simulation_active
2. Monitor simulation power budget usage
3. Identify peak demand scenarios
4. Optimize device scheduling
```

#### Technical Implementation

**Backend Changes**
- `coordinator.py`: Parallel optimization loops (real + simulation)
- `config_flow.py`: Added `simulation_active` checkbox to device forms
- `switch.py`: New `PVOptimizerSimulationSwitch` entity class
- `sensor.py`: New sensors for simulation results
- `const.py`: New constant `CONF_SIMULATION_ACTIVE`

**Frontend Changes**
- `pv-optimizer-panel.js`: 
  - New `_renderIdealDevicesCard()` method
  - New `_renderComparisonTable()` method
  - Toggle state management
  - Sensor data fetching from Home Assistant states

**Data Flow**
```
1. Coordinator runs two optimizations:
   - Real: filters devices with optimization_enabled=True
   - Simulation: filters devices with simulation_active=True

2. Separate budget calculations:
   - Real budget: surplus + real running devices
   - Sim budget: surplus + sim running devices

3. Knapsack algorithm runs twice:
   - Real ideal_on_list → physical control
   - Sim ideal_on_list → display only

4. Results stored in coordinator.data:
   - ideal_on_list (real)
   - simulation_ideal_on_list (new)
   - power_budget (real)
   - simulation_power_budget (new)

5. Frontend fetches sensor states and displays
```

#### Backward Compatibility

✅ **Fully Compatible**
- Existing devices continue working without changes
- `simulation_active` defaults to `False` for all devices
- No configuration migration required
- Existing entities remain unchanged
- Only new entities are added per device

#### Configuration Example

**Edit Existing Device**
```
Settings → Devices & Services → PV Optimizer → Configure
→ Manage Devices → Device List → Select Device → Edit

New Options:
☐ Optimization Enabled  (existing - controls real optimization)
☐ Simulation Active     (NEW - controls simulation)
```

**Add New Simulation-Only Device**
```
→ Manage Devices → Add Switch Device

Device Configuration:
- Name: Test Water Heater
- Priority: 1
- Power: 2000W
- ☐ Optimization Enabled  (disabled - not in real optimization)
- ✓ Simulation Active     (enabled - simulation only)
```

#### Screenshots & Examples

**Panel with Separate Cards**
```
┌─────────────────────────────────────┐
│ Real Optimization                   │
│ ⚡ 3 devices | 4300W / 5000W        │
│ ✅ Hot Water Heater (2000W)        │
│ ✅ Heat Pump (2300W)                │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│ Simulation                          │
│ 🧪 2 devices | 2800W / 5000W        │
│ ✅ Washing Machine (800W)           │
│ ✅ Dryer (2000W)                    │
└─────────────────────────────────────┘
```

**Comparison Table View**
```
Device              | Power | Real | Simulation
--------------------|-------|------|------------
Hot Water Heater    | 2000W | ✅   | ❌
Heat Pump           | 2300W | ✅   | ❌
Washing Machine     | 800W  | ❌   | ✅
Dryer               | 2000W | ❌   | ✅
```

#### Known Limitations

- Simulation assumes devices would respond if controlled (may differ from reality)
- Simulation doesn't account for device startup delays
- Lock states affect both real and simulation equally

#### Future Enhancements

- [ ] Historical simulation data tracking
- [ ] Export simulation results as CSV
- [ ] Simulation scheduling (run at specific times)
- [ ] "Promote to real" button (convert simulation device to real)
- [ ] Advanced simulation: weather forecasts, price signals

---

## Version 1.0.0 (2025-11-18) - Production Release 🎉

[Previous changelog entries remain unchanged...]
