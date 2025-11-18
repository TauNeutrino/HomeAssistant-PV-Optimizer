# Changelog - PV Optimizer Custom Integration

## Version 0.2.0 (2025-11-18)

### ✨ Major Features

#### Device Management UI
- **Complete UI Redesign**: Modern, responsive interface with Material Design principles
- **Add Devices**: Full-featured form to add new controllable devices via UI
- **Edit Devices**: Modify existing device configurations without YAML editing
- **Delete Devices**: Remove devices with confirmation dialog
- **Real-time Status**: Live device status display with power measurements and lock status

#### Enhanced WebSocket API
- **New Commands**:
  - `pv_optimizer/add_device` - Add new devices programmatically
  - `pv_optimizer/update_device` - Update existing device configuration
  - `pv_optimizer/delete_device` - Remove devices
  - `pv_optimizer/get_available_entities` - Get list of available Home Assistant entities
- **Validation**: Server-side validation for device configurations
- **Error Handling**: Comprehensive error messages for invalid configurations

#### UI/UX Improvements
- **Modal Dialogs**: Clean modal interfaces for editing configurations
- **Form Validation**: Client-side and server-side input validation
- **Visual Feedback**: Success/error messages with animations
- **Empty States**: Helpful messages when no devices are configured
- **Responsive Design**: Works on desktop and mobile devices
- **Status Indicators**: Visual indicators for connection status and device states

#### Device Configuration
- **Switch Devices**: 
  - Entity selection
  - Invert switch logic option
  - Power threshold configuration
- **Numeric Devices**: 
  - Multiple numeric targets per device
  - Dynamic target addition/removal in UI
  - Individual activated/deactivated values per target
- **Common Settings**:
  - Priority (1-10)
  - Nominal power consumption
  - Minimum on/off times
  - Measured power sensor
  - Optimization enable/disable toggle

### 🔧 Technical Improvements

- **Validation Layer**: Duplicate name detection, required field validation
- **Auto-reload**: Integration automatically reloads when devices are added/modified
- **Error Recovery**: Better error handling and user feedback
- **Type Safety**: Improved type checking in WebSocket handlers

### 📚 Documentation

- German translations added (`de.json`)
- Comprehensive inline help text in forms
- This changelog document

### 🎯 Requirements Compliance

This update addresses the following requirements from the specification:
- ✅ **Requirement 3.1**: Global configuration now editable via UI
- ✅ **Requirement 3.2**: Full device management (add, edit, remove) via UI
- ✅ **Requirement 2**: Improved ease of use with graphical interface
- ✅ **Requirement 2**: Configuration options explained directly in interface

### 🚀 Upgrade Notes

**From 0.1.0 to 0.2.0**:
1. Backup your existing device configurations from `config_entry.data`
2. Update the integration files
3. Restart Home Assistant
4. Navigate to the PV Optimizer panel in the sidebar
5. Your existing devices should still be present
6. You can now manage devices through the UI instead of config flow

### ⚠️ Breaking Changes

None. This update is backward compatible with existing configurations.

### 🐛 Known Issues

- Device entity auto-complete could be improved with dropdown selectors
- Bulk operations (enable/disable multiple devices) not yet implemented
- No import/export functionality for device configurations

### 📝 Future Improvements (Planned)

Phase 2:
- Fix timestamp tracking for accurate min on/off time enforcement
- Implement power threshold usage in device state detection
- Global config live editing (currently requires restart)

Phase 3:
- Real-time power flow visualization
- Historical optimization data and graphs
- Device templates for common appliances
- Import/export device configurations
- Bulk device operations

---

## Version 0.1.0 (Initial Release)

### Features

- PV surplus-based device optimization
- Priority-based device selection (knapsack algorithm)
- Device locking (min on/off times, manual intervention detection)
- Switch and numeric device types
- Sliding window power averaging
- Entity-based monitoring (sensors for each device)
- Dynamic configuration entities (priority, min times, optimization toggle)
- WebSocket API for configuration retrieval
- Basic panel interface (read-only)
