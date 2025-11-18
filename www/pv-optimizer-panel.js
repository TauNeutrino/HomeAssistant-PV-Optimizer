/**
 * PV Optimizer Panel for Home Assistant
 * 
 * This panel provides a user interface for managing the PV Optimizer integration.
 * It uses Home Assistant's native dialog system and form selectors for optimal
 * compatibility and user experience.
 * 
 * Features:
 * - Global configuration management
 * - Device management (add, edit, delete)
 * - Native HA dialogs and selectors
 * - Full dark mode support
 * - Real-time device status monitoring
 */

class PvOptimizerPanel extends HTMLElement {
  /**
   * Constructor - Initialize component state
   */
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    
    // State management
    this._config = null;              // Configuration from backend
    this._error = null;               // Error message if any
    this._loading = true;             // Loading state
  }

  /**
   * Setter for hass object (Home Assistant connection)
   * Called by HA when the hass object is available or updated
   */
  set hass(hass) {
    this._hass = hass;
    
    // Load configuration on first hass assignment
    if (!this._config) {
      this._getConfigWithRetry();
    }
    
    this.render();
  }

  /**
   * Getter for hass object
   */
  get hass() {
    return this._hass;
  }

  /**
   * Setter for panel configuration
   * Called by HA with panel-specific configuration
   */
  set panel(panel) {
    this._panel = panel;
  }

  /**
   * Lifecycle method - called when element is added to DOM
   */
  connectedCallback() {
    this.render();
  }

  /**
   * Load configuration from backend with retry logic
   * Retries up to 3 times with exponential backoff
   * 
   * @param {number} retryCount - Current retry attempt (0-based)
   */
  async _getConfigWithRetry(retryCount = 0) {
    // Check WebSocket connection availability
    if (!this._hass?.connection) {
      this._error = 'WebSocket connection not available';
      this._loading = false;
      this.render();
      return;
    }

    try {
      // Set loading state and clear errors
      this._loading = true;
      this._error = null;
      this.render();

      // Small delay to ensure WebSocket is ready
      await new Promise(resolve => setTimeout(resolve, 500));

      // Fetch configuration via WebSocket
      const response = await this._hass.callWS({
        type: 'pv_optimizer/config',
      });
      
      // Update state with received configuration
      this._config = response;
      this._loading = false;
      this._error = null;
      this.render();
      
    } catch (error) {
      console.error('Failed to get config:', error);
      
      // Retry logic with exponential backoff
      if (retryCount < 3) {
        const delay = Math.pow(2, retryCount) * 1000; // 1s, 2s, 4s
        setTimeout(() => this._getConfigWithRetry(retryCount + 1), delay);
      } else {
        // Max retries reached - show error
        this._error = `Failed to load configuration: ${error.message}`;
        this._loading = false;
        this.render();
      }
    }
  }

  /**
   * Show Home Assistant's native dialog for editing global configuration
   * Uses HA's form dialog with native selectors
   */
  _showEditGlobalDialog() {
    const globalConfig = this._config?.global_config || {};
    
    // Define form schema using HA's selector system
    const schema = [
      {
        name: 'surplus_sensor_entity_id',
        required: true,
        selector: {
          entity: {
            domain: 'sensor',
            device_class: 'power',
          }
        }
      },
      {
        name: 'sliding_window_size',
        required: true,
        default: 5,
        selector: {
          number: {
            min: 1,
            max: 60,
            unit_of_measurement: 'minutes',
          }
        }
      },
      {
        name: 'optimization_cycle_time',
        required: true,
        default: 60,
        selector: {
          number: {
            min: 10,
            max: 300,
            unit_of_measurement: 'seconds',
          }
        }
      }
    ];

    // Fire event to show HA's native form dialog
    this._showFormDialog({
      title: 'Edit Global Configuration',
      schema: schema,
      data: globalConfig,
      computeLabel: (schema) => {
        // Generate user-friendly labels
        const labels = {
          'surplus_sensor_entity_id': 'PV Surplus Sensor',
          'sliding_window_size': 'Sliding Window Size',
          'optimization_cycle_time': 'Optimization Cycle Time',
        };
        return labels[schema.name] || schema.name;
      },
      computeHelper: (schema) => {
        // Generate helpful descriptions
        const helpers = {
          'surplus_sensor_entity_id': 'The sensor that provides PV surplus/deficit values (negative = surplus)',
          'sliding_window_size': 'Time window for averaging power measurements to smooth fluctuations',
          'optimization_cycle_time': 'How often the optimization algorithm runs',
        };
        return helpers[schema.name];
      },
      submit: async (data) => {
        await this._saveGlobalConfig(data);
      }
    });
  }

  /**
   * Show Home Assistant's native dialog for adding/editing a device
   * 
   * @param {Object} deviceData - Existing device data (null for new device)
   */
  _showDeviceDialog(deviceData = null) {
    const isEdit = !!deviceData;
    const device = isEdit ? deviceData.config : {
      name: '',
      type: 'switch',
      priority: 5,
      power: 0,
      optimization_enabled: true,
      switch_entity_id: '',
      invert_switch: false,
      measured_power_entity_id: '',
      power_threshold: 100,
      min_on_time: 0,
      min_off_time: 0,
      numeric_targets: [],
    };

    // Define form schema - will be dynamically updated based on device type
    let schema = [
      {
        name: 'name',
        required: true,
        disabled: isEdit, // Name cannot be changed when editing
        selector: { text: {} }
      },
      {
        name: 'type',
        required: true,
        selector: {
          select: {
            options: [
              { value: 'switch', label: 'Switch (On/Off Control)' },
              { value: 'numeric', label: 'Numeric (Value Adjustment)' }
            ]
          }
        }
      },
      {
        name: 'priority',
        required: true,
        selector: {
          number: {
            min: 1,
            max: 10,
            mode: 'box',
          }
        }
      },
      {
        name: 'power',
        required: true,
        selector: {
          number: {
            min: 0,
            step: 0.1,
            unit_of_measurement: 'W',
            mode: 'box',
          }
        }
      },
      {
        name: 'optimization_enabled',
        selector: { boolean: {} }
      },
    ];

    // Add type-specific fields
    if (device.type === 'switch') {
      schema.push(
        {
          name: 'switch_entity_id',
          required: true,
          selector: {
            entity: {
              domain: 'switch',
            }
          }
        },
        {
          name: 'invert_switch',
          selector: { boolean: {} }
        }
      );
    } else if (device.type === 'numeric') {
      // For numeric devices, we'll handle targets separately
      // as they require a more complex UI (multiple targets)
      schema.push({
        name: 'numeric_targets_info',
        selector: { 
          text: { 
            disabled: true,
            type: 'text',
          } 
        }
      });
    }

    // Add common optional fields
    schema.push(
      {
        name: 'measured_power_entity_id',
        selector: {
          entity: {
            domain: 'sensor',
            device_class: 'power',
          }
        }
      },
      {
        name: 'power_threshold',
        selector: {
          number: {
            min: 0,
            step: 0.1,
            unit_of_measurement: 'W',
            mode: 'box',
          }
        }
      },
      {
        name: 'min_on_time',
        selector: {
          number: {
            min: 0,
            unit_of_measurement: 'minutes',
            mode: 'box',
          }
        }
      },
      {
        name: 'min_off_time',
        selector: {
          number: {
            min: 0,
            unit_of_measurement: 'minutes',
            mode: 'box',
          }
        }
      }
    );

    // Show the form dialog
    this._showFormDialog({
      title: isEdit ? `Edit Device: ${device.name}` : 'Add New Device',
      schema: schema,
      data: device,
      computeLabel: (schema) => {
        const labels = {
          'name': 'Device Name',
          'type': 'Device Type',
          'priority': 'Priority',
          'power': 'Nominal Power',
          'optimization_enabled': 'Optimization Enabled',
          'switch_entity_id': 'Switch Entity',
          'invert_switch': 'Invert Switch Logic',
          'numeric_targets_info': 'Numeric Targets',
          'measured_power_entity_id': 'Measured Power Sensor',
          'power_threshold': 'Power Threshold',
          'min_on_time': 'Minimum On Time',
          'min_off_time': 'Minimum Off Time',
        };
        return labels[schema.name] || schema.name;
      },
      computeHelper: (schema) => {
        const helpers = {
          'name': 'A unique name for this device',
          'type': 'Switch: On/Off control | Numeric: Value adjustment',
          'priority': '1 = highest priority (activated first), 10 = lowest priority',
          'power': "The device's nominal power consumption in Watts",
          'optimization_enabled': 'Whether this device should be managed by the optimizer',
          'switch_entity_id': 'The switch entity to control',
          'invert_switch': 'Turn OFF to activate device, ON to deactivate (for normally-closed switches)',
          'numeric_targets_info': 'Note: Numeric targets must be configured via YAML for now. This will be improved in a future version.',
          'measured_power_entity_id': 'Optional: Sensor providing actual power consumption (overrides nominal power)',
          'power_threshold': 'Power threshold in Watts to determine if device is ON (when using measured power)',
          'min_on_time': 'Device must stay on for at least this duration (prevents short-cycling)',
          'min_off_time': 'Device must stay off for at least this duration (prevents short-cycling)',
        };
        return helpers[schema.name];
      },
      submit: async (data) => {
        // Preserve numeric_targets if editing
        if (isEdit && device.numeric_targets) {
          data.numeric_targets = device.numeric_targets;
        }
        
        // Remove info field (not actual config)
        delete data.numeric_targets_info;
        
        if (isEdit) {
          await this._updateDevice(device.name, data);
        } else {
          await this._addDevice(data);
        }
      }
    });
  }

  /**
   * Helper function to show HA's native form dialog
   * This uses Home Assistant's event system to display forms
   * 
   * @param {Object} options - Dialog configuration
   * @param {string} options.title - Dialog title
   * @param {Array} options.schema - Form schema (HA selector format)
   * @param {Object} options.data - Initial form data
   * @param {Function} options.computeLabel - Function to compute field labels
   * @param {Function} options.computeHelper - Function to compute helper text
   * @param {Function} options.submit - Callback when form is submitted
   */
  _showFormDialog({ title, schema, data, computeLabel, computeHelper, submit }) {
    // Fire custom event that HA listens for
    const event = new CustomEvent('show-dialog', {
      detail: {
        dialogTag: 'ha-form-dialog',
        dialogImport: () => import('https://www.home-assistant.io/static/frontend/2024.11.0/chunk.78cbf8d77f5b0ea11db6.js'),
        dialogParams: {
          title: title,
          schema: schema,
          data: data,
          computeLabel: computeLabel,
          computeHelper: computeHelper,
          submit: submit,
        },
      },
      bubbles: true,
      composed: true,
    });
    
    this.dispatchEvent(event);
  }

  /**
   * Save global configuration to backend
   * 
   * @param {Object} config - Global configuration object
   */
  async _saveGlobalConfig(config) {
    try {
      await this._hass.callWS({
        type: 'pv_optimizer/set_config',
        data: config,
      });
      
      // Reload configuration from backend
      await this._getConfigWithRetry();
      
      // Show success toast
      this._showToast('Global configuration saved successfully');
    } catch (error) {
      console.error('Failed to save global config:', error);
      this._showToast(`Failed to save: ${error.message}`);
    }
  }

  /**
   * Add a new device via backend API
   * 
   * @param {Object} deviceConfig - Device configuration object
   */
  async _addDevice(deviceConfig) {
    try {
      await this._hass.callWS({
        type: 'pv_optimizer/add_device',
        device: deviceConfig,
      });
      
      // Reload configuration
      await this._getConfigWithRetry();
      
      // Show success toast
      this._showToast('Device added successfully');
    } catch (error) {
      console.error('Failed to add device:', error);
      this._showToast(`Failed to add device: ${error.message}`);
    }
  }

  /**
   * Update an existing device via backend API
   * 
   * @param {string} deviceName - Name of device to update
   * @param {Object} deviceConfig - New device configuration
   */
  async _updateDevice(deviceName, deviceConfig) {
    try {
      await this._hass.callWS({
        type: 'pv_optimizer/update_device',
        device_name: deviceName,
        device: deviceConfig,
      });
      
      // Reload configuration
      await this._getConfigWithRetry();
      
      // Show success toast
      this._showToast('Device updated successfully');
    } catch (error) {
      console.error('Failed to update device:', error);
      this._showToast(`Failed to update device: ${error.message}`);
    }
  }

  /**
   * Delete a device via backend API
   * Asks for user confirmation before deleting
   * 
   * @param {string} deviceName - Name of device to delete
   */
  async _deleteDevice(deviceName) {
    // Confirm deletion
    if (!confirm(`Are you sure you want to delete device "${deviceName}"?`)) {
      return;
    }
    
    try {
      await this._hass.callWS({
        type: 'pv_optimizer/delete_device',
        device_name: deviceName,
      });
      
      // Reload configuration
      await this._getConfigWithRetry();
      
      // Show success toast
      this._showToast('Device deleted successfully');
    } catch (error) {
      console.error('Failed to delete device:', error);
      this._showToast(`Failed to delete device: ${error.message}`);
    }
  }

  /**
   * Show a toast notification using HA's notification system
   * 
   * @param {string} message - Message to display
   */
  _showToast(message) {
    const event = new CustomEvent('hass-notification', {
      detail: { message },
      bubbles: true,
      composed: true,
    });
    this.dispatchEvent(event);
  }

  /**
   * Main render function - updates the Shadow DOM with current state
   * Called whenever state changes
   */
  render() {
    if (!this.shadowRoot) return;

    // Define CSS styles (using HA CSS variables for theme support)
    const styles = `
      <style>
        /* Base host styles */
        :host {
          display: block;
          padding: 16px;
          background-color: var(--primary-background-color);
        }

        /* Header styling */
        .header {
          font-size: 24px;
          font-weight: 500;
          margin-bottom: 24px;
          color: var(--primary-text-color);
          display: flex;
          align-items: center;
          gap: 12px;
        }

        /* Card container (uses HA card styling) */
        .card {
          background-color: var(--ha-card-background, var(--card-background-color, white));
          border-radius: var(--ha-card-border-radius, 12px);
          box-shadow: var(--ha-card-box-shadow, 0 2px 4px rgba(0,0,0,0.1));
          padding: 20px;
          margin-bottom: 20px;
        }

        /* Card header with action buttons */
        .card-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 16px;
          font-size: 18px;
          font-weight: 600;
          color: var(--primary-text-color);
        }

        /* Card content area */
        .card-content {
          color: var(--primary-text-color);
        }

        /* Configuration group (label + value pair) */
        .config-group {
          margin-bottom: 16px;
        }

        .config-label {
          font-weight: 500;
          margin-bottom: 4px;
          font-size: 14px;
        }

        .config-value {
          padding: 8px 12px;
          background-color: var(--secondary-background-color);
          border-radius: 4px;
          font-family: monospace;
          font-size: 13px;
        }

        /* Button styling (HA theme colors) */
        button {
          background-color: var(--primary-color);
          color: white;
          border: none;
          padding: 8px 16px;
          border-radius: 4px;
          cursor: pointer;
          font-size: 14px;
          font-weight: 500;
          transition: all 0.2s;
        }

        button:hover {
          background-color: var(--primary-color-dark, #0288d1);
        }

        button.danger {
          background-color: var(--error-color, #f44336);
        }

        button.danger:hover {
          background-color: #d32f2f;
        }

        /* Device list grid */
        .device-list {
          display: grid;
          gap: 12px;
        }

        /* Individual device card */
        .device-card {
          background-color: var(--card-background-color);
          border: 1px solid var(--divider-color);
          border-left: 4px solid var(--primary-color);
          border-radius: 8px;
          padding: 16px;
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
        }

        .device-info {
          flex: 1;
        }

        .device-name {
          font-size: 16px;
          font-weight: 500;
          margin-bottom: 8px;
        }

        /* Device details grid */
        .device-details {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
          gap: 8px;
          font-size: 13px;
          color: var(--secondary-text-color);
        }

        /* Device action buttons */
        .device-actions {
          display: flex;
          gap: 8px;
        }

        /* Empty state when no devices configured */
        .empty-state {
          text-align: center;
          padding: 40px 20px;
          color: var(--secondary-text-color);
        }

        /* Error message styling */
        .error {
          color: var(--error-color);
          background-color: rgba(244, 67, 54, 0.1);
          padding: 12px;
          border-radius: 4px;
          margin: 8px 0;
          border-left: 4px solid var(--error-color);
        }

        /* Loading state styling */
        .loading {
          text-align: center;
          padding: 20px;
          color: var(--secondary-text-color);
        }
      </style>
    `;

    // Render error state
    if (this._error) {
      this.shadowRoot.innerHTML = `
        ${styles}
        <div class="header">⚡ PV Optimizer</div>
        <div class="card">
          <div class="error">
            <strong>Error:</strong> ${this._error}
            <div><button onclick="location.reload()" style="margin-top: 12px;">Refresh Page</button></div>
          </div>
        </div>
      `;
      return;
    }

    // Render loading state
    if (this._loading) {
      this.shadowRoot.innerHTML = `
        ${styles}
        <div class="header">⚡ PV Optimizer</div>
        <div class="card">
          <div class="loading">Loading configuration...</div>
        </div>
      `;
      return;
    }

    // Extract configuration data
    const globalConfig = this._config?.global_config || {};
    const devices = this._config?.devices || [];

    // Render main content
    this.shadowRoot.innerHTML = `
      ${styles}
      <div class="header">⚡ PV Optimizer</div>
      
      ${this._renderGlobalConfig(globalConfig)}
      ${this._renderDeviceList(devices)}
    `;

    // Attach event listeners to buttons
    this._attachEventListeners();
  }

  /**
   * Render the global configuration card
   * 
   * @param {Object} globalConfig - Global configuration object
   * @returns {string} HTML string for global config card
   */
  _renderGlobalConfig(globalConfig) {
    return `
      <div class="card">
        <div class="card-header">
          <span>Global Configuration</span>
          <button id="edit-global-btn">✏️ Edit</button>
        </div>
        <div class="card-content">
          <div class="config-group">
            <div class="config-label">PV Surplus Sensor</div>
            <div class="config-value">${globalConfig.surplus_sensor_entity_id || 'Not configured'}</div>
          </div>
          <div class="config-group">
            <div class="config-label">Sliding Window Size</div>
            <div class="config-value">${globalConfig.sliding_window_size || 5} minutes</div>
          </div>
          <div class="config-group">
            <div class="config-label">Optimization Cycle Time</div>
            <div class="config-value">${globalConfig.optimization_cycle_time || 60} seconds</div>
          </div>
        </div>
      </div>
    `;
  }

  /**
   * Render the device list card
   * 
   * @param {Array} devices - Array of device objects
   * @returns {string} HTML string for device list card
   */
  _renderDeviceList(devices) {
    return `
      <div class="card">
        <div class="card-header">
          <span>Devices (${devices.length})</span>
          <button id="add-device-btn">➕ Add Device</button>
        </div>
        <div class="card-content">
          ${devices.length === 0 ? `
            <div class="empty-state">
              <div style="font-size: 48px; margin-bottom: 16px;">📱</div>
              <div>No devices configured yet</div>
              <div style="margin-top: 8px; font-size: 14px;">
                Click "Add Device" to configure your first controllable device
              </div>
            </div>
          ` : `
            <div class="device-list">
              ${devices.map(device => this._renderDeviceCard(device)).join('')}
            </div>
          `}
        </div>
      </div>
    `;
  }

  /**
   * Render a single device card
   * 
   * @param {Object} deviceData - Device data object (contains config and state)
   * @returns {string} HTML string for device card
   */
  _renderDeviceCard(deviceData) {
    const device = deviceData.config;
    const state = deviceData.state || {};
    
    // Status indicator based on optimization enabled/disabled
    const statusIcon = device.optimization_enabled ? '🟢' : '🔴';
    
    // Escape device name for use in onclick attributes
    const escapedName = device.name.replace(/'/g, "\\'");
    
    return `
      <div class="device-card">
        <div class="device-info">
          <div class="device-name">
            ${statusIcon} ${device.name}
          </div>
          <div class="device-details">
            <div><strong>Type:</strong> ${device.type}</div>
            <div><strong>Priority:</strong> ${device.priority}</div>
            <div><strong>Power:</strong> ${device.power}W</div>
            <div><strong>Status:</strong> ${state.is_on ? 'ON' : 'OFF'}</div>
            <div><strong>Locked:</strong> ${state.is_locked ? 'Yes' : 'No'}</div>
            ${state.measured_power_avg ? `
              <div><strong>Measured:</strong> ${state.measured_power_avg.toFixed(1)}W</div>
            ` : ''}
          </div>
        </div>
        <div class="device-actions">
          <button class="edit-device-btn" data-device-name="${escapedName}">✏️ Edit</button>
          <button class="danger delete-device-btn" data-device-name="${escapedName}">🗑️ Delete</button>
        </div>
      </div>
    `;
  }

  /**
   * Attach event listeners to interactive elements
   * This must be called after render() to ensure elements exist
   */
  _attachEventListeners() {
    // Global config edit button
    const editGlobalBtn = this.shadowRoot.querySelector('#edit-global-btn');
    if (editGlobalBtn) {
      editGlobalBtn.addEventListener('click', () => this._showEditGlobalDialog());
    }

    // Add device button
    const addDeviceBtn = this.shadowRoot.querySelector('#add-device-btn');
    if (addDeviceBtn) {
      addDeviceBtn.addEventListener('click', () => this._showDeviceDialog());
    }

    // Edit device buttons (one per device)
    const editButtons = this.shadowRoot.querySelectorAll('.edit-device-btn');
    editButtons.forEach(btn => {
      btn.addEventListener('click', (e) => {
        const deviceName = e.target.dataset.deviceName;
        const deviceData = this._config.devices.find(d => d.config.name === deviceName);
        if (deviceData) {
          this._showDeviceDialog(deviceData);
        }
      });
    });

    // Delete device buttons (one per device)
    const deleteButtons = this.shadowRoot.querySelectorAll('.delete-device-btn');
    deleteButtons.forEach(btn => {
      btn.addEventListener('click', (e) => {
        const deviceName = e.target.dataset.deviceName;
        this._deleteDevice(deviceName);
      });
    });
  }
}

// Register the custom element
customElements.define('pv-optimizer-panel', PvOptimizerPanel);
