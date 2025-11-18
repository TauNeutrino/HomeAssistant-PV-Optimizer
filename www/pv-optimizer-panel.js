/**
 * PV Optimizer Panel for Home Assistant
 * 
 * This panel provides a user interface for managing the PV Optimizer integration.
 * Uses custom dialogs with proper focus management and HA styling.
 * 
 * Features:
 * - Global configuration management
 * - Device management (add, edit, delete)
 * - Proper dialog focus handling (no cursor blinking)
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
    this._showingGlobalDialog = false;  // Is global config dialog open?
    this._showingDeviceDialog = false;  // Is device dialog open?
    this._editingDevice = null;       // Device being edited (null for add)
    this._dialogData = {};            // Current dialog form data
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
   * Show dialog for editing global configuration
   */
  _showGlobalDialog() {
    const globalConfig = this._config?.global_config || {};
    this._dialogData = { ...globalConfig };
    this._showingGlobalDialog = true;
    this.render();
    
    // Focus first input after render
    setTimeout(() => {
      const firstInput = this.shadowRoot.querySelector('.dialog input, .dialog select');
      if (firstInput) firstInput.focus();
    }, 100);
  }

  /**
   * Show dialog for adding/editing a device
   * 
   * @param {Object} deviceData - Existing device data (null for new device)
   */
  _showDeviceDialog(deviceData = null) {
    this._editingDevice = deviceData;
    this._dialogData = deviceData ? { ...deviceData.config } : {
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
    this._showingDeviceDialog = true;
    this.render();
    
    // Focus first input after render
    setTimeout(() => {
      const firstInput = this.shadowRoot.querySelector('.dialog input:not([readonly]), .dialog select');
      if (firstInput) firstInput.focus();
    }, 100);
  }

  /**
   * Close all dialogs
   */
  _closeDialog() {
    this._showingGlobalDialog = false;
    this._showingDeviceDialog = false;
    this._editingDevice = null;
    this._dialogData = {};
    this.render();
  }

  /**
   * Handle form input change
   * @param {string} field - Field name
   * @param {any} value - New value
   */
  _updateDialogData(field, value) {
    this._dialogData[field] = value;
    // Re-render if type changes (shows different fields)
    if (field === 'type') {
      this.render();
    }
  }

  /**
   * Save global configuration to backend
   */
  async _saveGlobalConfig() {
    try {
      await this._hass.callWS({
        type: 'pv_optimizer/set_config',
        data: this._dialogData,
      });
      
      this._closeDialog();
      await this._getConfigWithRetry();
      this._showToast('Global configuration saved successfully');
    } catch (error) {
      console.error('Failed to save global config:', error);
      this._showToast(`Failed to save: ${error.message}`);
    }
  }

  /**
   * Add or update device
   */
  async _saveDevice() {
    const isEdit = !!this._editingDevice;
    
    try {
      if (isEdit) {
        await this._hass.callWS({
          type: 'pv_optimizer/update_device',
          device_name: this._editingDevice.config.name,
          device: this._dialogData,
        });
        this._showToast('Device updated successfully');
      } else {
        await this._hass.callWS({
          type: 'pv_optimizer/add_device',
          device: this._dialogData,
        });
        this._showToast('Device added successfully');
      }
      
      this._closeDialog();
      await this._getConfigWithRetry();
    } catch (error) {
      console.error('Failed to save device:', error);
      this._showToast(`Failed to save device: ${error.message}`);
    }
  }

  /**
   * Delete a device
   * @param {string} deviceName - Name of device to delete
   */
  async _deleteDevice(deviceName) {
    if (!confirm(`Are you sure you want to delete device "${deviceName}"?`)) {
      return;
    }
    
    try {
      await this._hass.callWS({
        type: 'pv_optimizer/delete_device',
        device_name: deviceName,
      });
      
      await this._getConfigWithRetry();
      this._showToast('Device deleted successfully');
    } catch (error) {
      console.error('Failed to delete device:', error);
      this._showToast(`Failed to delete device: ${error.message}`);
    }
  }

  /**
   * Show a toast notification
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
   * Get list of entities for domain
   * @param {string} domain - Entity domain (e.g., 'switch', 'sensor')
   * @returns {Array} List of entities
   */
  _getEntities(domain) {
    if (!this._hass?.states) return [];
    
    return Object.keys(this._hass.states)
      .filter(entity_id => entity_id.startsWith(domain + '.'))
      .sort();
  }

  /**
   * Main render function - updates the Shadow DOM with current state
   */
  render() {
    if (!this.shadowRoot) return;

    // CSS styles with HA variables for theme support
    const styles = `
      <style>
        :host {
          display: block;
          padding: 16px;
          background-color: var(--primary-background-color);
        }

        .header {
          font-size: 24px;
          font-weight: 500;
          margin-bottom: 24px;
          color: var(--primary-text-color);
        }

        .card {
          background-color: var(--ha-card-background, var(--card-background-color, white));
          border-radius: var(--ha-card-border-radius, 12px);
          box-shadow: var(--ha-card-box-shadow, 0 2px 4px rgba(0,0,0,0.1));
          padding: 20px;
          margin-bottom: 20px;
        }

        .card-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 16px;
          font-size: 18px;
          font-weight: 600;
          color: var(--primary-text-color);
        }

        .card-content {
          color: var(--primary-text-color);
        }

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

        button.secondary {
          background-color: var(--secondary-text-color);
        }

        .device-list {
          display: grid;
          gap: 12px;
        }

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

        .device-details {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
          gap: 8px;
          font-size: 13px;
          color: var(--secondary-text-color);
        }

        .device-actions {
          display: flex;
          gap: 8px;
        }

        .empty-state {
          text-align: center;
          padding: 40px 20px;
          color: var(--secondary-text-color);
        }

        .error {
          color: var(--error-color);
          background-color: rgba(244, 67, 54, 0.1);
          padding: 12px;
          border-radius: 4px;
          margin: 8px 0;
          border-left: 4px solid var(--error-color);
        }

        .loading {
          text-align: center;
          padding: 20px;
          color: var(--secondary-text-color);
        }

        /* Dialog styles */
        .dialog-overlay {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background-color: rgba(0, 0, 0, 0.5);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 1000;
        }

        .dialog {
          background-color: var(--ha-card-background, var(--card-background-color, white));
          border-radius: 8px;
          padding: 24px;
          max-width: 600px;
          width: calc(100% - 32px);
          max-height: 90vh;
          overflow-y: auto;
          box-shadow: 0 8px 32px rgba(0,0,0,0.3);
        }

        .dialog-header {
          font-size: 20px;
          font-weight: 600;
          margin-bottom: 20px;
          color: var(--primary-text-color);
        }

        .dialog-content {
          color: var(--primary-text-color);
        }

        .dialog-actions {
          display: flex;
          justify-content: flex-end;
          gap: 12px;
          margin-top: 20px;
          padding-top: 20px;
          border-top: 1px solid var(--divider-color);
        }

        .form-group {
          margin-bottom: 16px;
        }

        label {
          display: block;
          margin-bottom: 6px;
          color: var(--primary-text-color);
          font-weight: 500;
          font-size: 14px;
        }

        input[type="text"],
        input[type="number"],
        select {
          width: 100%;
          padding: 10px;
          border: 1px solid var(--divider-color);
          border-radius: 4px;
          background-color: var(--primary-background-color);
          color: var(--primary-text-color);
          font-size: 14px;
          box-sizing: border-box;
        }

        input[type="text"]:focus,
        input[type="number"]:focus,
        select:focus {
          outline: none;
          border-color: var(--primary-color);
          box-shadow: 0 0 0 2px rgba(var(--rgb-primary-color, 3, 169, 244), 0.2);
        }

        input[readonly] {
          opacity: 0.6;
          cursor: not-allowed;
        }

        input[type="checkbox"] {
          width: 18px;
          height: 18px;
          margin-right: 8px;
        }

        .checkbox-group {
          display: flex;
          align-items: center;
          margin-bottom: 16px;
        }

        .checkbox-group label {
          margin-bottom: 0;
          cursor: pointer;
        }

        .help-text {
          font-size: 12px;
          color: var(--secondary-text-color);
          margin-top: 4px;
          font-style: italic;
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

    const globalConfig = this._config?.global_config || {};
    const devices = this._config?.devices || [];

    // Render main content
    this.shadowRoot.innerHTML = `
      ${styles}
      <div class="header">⚡ PV Optimizer</div>
      
      ${this._renderGlobalConfig(globalConfig)}
      ${this._renderDeviceList(devices)}
      ${this._showingGlobalDialog ? this._renderGlobalDialog() : ''}
      ${this._showingDeviceDialog ? this._renderDeviceDialog() : ''}
    `;

    this._attachEventListeners();
  }

  /**
   * Render global configuration card
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
   * Render device list card
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
   * Render single device card
   */
  _renderDeviceCard(deviceData) {
    const device = deviceData.config;
    const state = deviceData.state || {};
    const escapedName = device.name.replace(/'/g, "\\'");
    
    return `
      <div class="device-card">
        <div class="device-info">
          <div class="device-name">
            ${device.optimization_enabled ? '🟢' : '🔴'} ${device.name}
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
   * Render global configuration dialog
   */
  _renderGlobalDialog() {
    const data = this._dialogData;
    const sensors = this._getEntities('sensor');
    
    return `
      <div class="dialog-overlay" id="dialog-overlay">
        <div class="dialog" id="dialog">
          <div class="dialog-header">Edit Global Configuration</div>
          <div class="dialog-content">
            <div class="form-group">
              <label>PV Surplus Sensor *</label>
              <select id="surplus_sensor">
                <option value="">Select sensor...</option>
                ${sensors.map(entity => `
                  <option value="${entity}" ${entity === data.surplus_sensor_entity_id ? 'selected' : ''}>
                    ${entity}
                  </option>
                `).join('')}
              </select>
              <div class="help-text">Sensor providing PV surplus/deficit (negative = surplus)</div>
            </div>
            
            <div class="form-group">
              <label>Sliding Window Size (minutes) *</label>
              <input type="number" id="sliding_window" value="${data.sliding_window_size || 5}" 
                     min="1" max="60" required>
              <div class="help-text">Time window for averaging power measurements</div>
            </div>
            
            <div class="form-group">
              <label>Optimization Cycle Time (seconds) *</label>
              <input type="number" id="cycle_time" value="${data.optimization_cycle_time || 60}" 
                     min="10" max="300" required>
              <div class="help-text">How often the optimizer runs</div>
            </div>
          </div>
          <div class="dialog-actions">
            <button class="secondary" id="dialog-cancel">Cancel</button>
            <button id="dialog-save">Save</button>
          </div>
        </div>
      </div>
    `;
  }

  /**
   * Render device dialog (add/edit)
   */
  _renderDeviceDialog() {
    const isEdit = !!this._editingDevice;
    const data = this._dialogData;
    const switches = this._getEntities('switch');
    const sensors = this._getEntities('sensor');
    const numbers = this._getEntities('number').concat(this._getEntities('input_number'));
    
    return `
      <div class="dialog-overlay" id="dialog-overlay">
        <div class="dialog" id="dialog">
          <div class="dialog-header">${isEdit ? `Edit: ${data.name}` : 'Add New Device'}</div>
          <div class="dialog-content">
            <div class="form-group">
              <label>Device Name *</label>
              <input type="text" id="device_name" value="${data.name}" 
                     ${isEdit ? 'readonly' : ''} required>
              <div class="help-text">A unique name for this device</div>
            </div>

            <div class="form-group">
              <label>Device Type *</label>
              <select id="device_type">
                <option value="switch" ${data.type === 'switch' ? 'selected' : ''}>Switch (On/Off Control)</option>
                <option value="numeric" ${data.type === 'numeric' ? 'selected' : ''}>Numeric (Value Adjustment)</option>
              </select>
              <div class="help-text">Switch: direct on/off | Numeric: adjust values</div>
            </div>

            <div class="form-group">
              <label>Priority * (1=highest, 10=lowest)</label>
              <input type="number" id="priority" value="${data.priority}" min="1" max="10" required>
            </div>

            <div class="form-group">
              <label>Nominal Power (W) *</label>
              <input type="number" id="power" value="${data.power}" min="0" step="0.1" required>
            </div>

            <div class="checkbox-group">
              <input type="checkbox" id="optimization_enabled" ${data.optimization_enabled ? 'checked' : ''}>
              <label>Optimization Enabled</label>
            </div>

            <div id="switch-fields" style="display: ${data.type === 'switch' ? 'block' : 'none'};">
              <div class="form-group">
                <label>Switch Entity *</label>
                <select id="switch_entity">
                  <option value="">Select switch...</option>
                  ${switches.map(entity => `
                    <option value="${entity}" ${entity === data.switch_entity_id ? 'selected' : ''}>
                      ${entity}
                    </option>
                  `).join('')}
                </select>
              </div>
              
              <div class="checkbox-group">
                <input type="checkbox" id="invert_switch" ${data.invert_switch ? 'checked' : ''}>
                <label>Invert Switch Logic (OFF = activate)</label>
              </div>
            </div>

            <div id="numeric-fields" style="display: ${data.type === 'numeric' ? 'block' : 'none'};">
              <div class="help-text" style="padding: 12px; background-color: var(--warning-color, #ff9800); color: white; border-radius: 4px;">
                ⚠️ Numeric targets must be configured via YAML. This will be improved in a future version.
              </div>
            </div>

            <div class="form-group">
              <label>Measured Power Sensor (optional)</label>
              <select id="measured_power">
                <option value="">None</option>
                ${sensors.map(entity => `
                  <option value="${entity}" ${entity === data.measured_power_entity_id ? 'selected' : ''}>
                    ${entity}
                  </option>
                `).join('')}
              </select>
              <div class="help-text">Optional sensor for actual power consumption</div>
            </div>

            <div class="form-group">
              <label>Power Threshold (W)</label>
              <input type="number" id="power_threshold" value="${data.power_threshold || 100}" 
                     min="0" step="0.1">
              <div class="help-text">Threshold to determine if device is ON</div>
            </div>

            <div class="form-group">
              <label>Minimum On Time (minutes)</label>
              <input type="number" id="min_on_time" value="${data.min_on_time || 0}" min="0">
              <div class="help-text">Device must stay on at least this long</div>
            </div>

            <div class="form-group">
              <label>Minimum Off Time (minutes)</label>
              <input type="number" id="min_off_time" value="${data.min_off_time || 0}" min="0">
              <div class="help-text">Device must stay off at least this long</div>
            </div>
          </div>
          <div class="dialog-actions">
            <button class="secondary" id="dialog-cancel">Cancel</button>
            <button id="dialog-save">${isEdit ? 'Update' : 'Add'} Device</button>
          </div>
        </div>
      </div>
    `;
  }

  /**
   * Attach event listeners to interactive elements
   */
  _attachEventListeners() {
    // Global config edit button
    const editGlobalBtn = this.shadowRoot.querySelector('#edit-global-btn');
    if (editGlobalBtn) {
      editGlobalBtn.addEventListener('click', () => this._showGlobalDialog());
    }

    // Add device button
    const addDeviceBtn = this.shadowRoot.querySelector('#add-device-btn');
    if (addDeviceBtn) {
      addDeviceBtn.addEventListener('click', () => this._showDeviceDialog());
    }

    // Edit device buttons
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

    // Delete device buttons
    const deleteButtons = this.shadowRoot.querySelectorAll('.delete-device-btn');
    deleteButtons.forEach(btn => {
      btn.addEventListener('click', (e) => {
        const deviceName = e.target.dataset.deviceName;
        this._deleteDevice(deviceName);
      });
    });

    // Dialog event listeners
    this._attachDialogListeners();
  }

  /**
   * Attach dialog-specific event listeners
   */
  _attachDialogListeners() {
    // Dialog overlay click (close on background click)
    const dialogOverlay = this.shadowRoot.querySelector('#dialog-overlay');
    if (dialogOverlay) {
      dialogOverlay.addEventListener('click', (e) => {
        if (e.target === dialogOverlay) {
          this._closeDialog();
        }
      });
    }

    // Dialog content click (prevent closing)
    const dialog = this.shadowRoot.querySelector('#dialog');
    if (dialog) {
      dialog.addEventListener('click', (e) => {
        e.stopPropagation();
      });
    }

    // Cancel button
    const cancelBtn = this.shadowRoot.querySelector('#dialog-cancel');
    if (cancelBtn) {
      cancelBtn.addEventListener('click', () => this._closeDialog());
    }

    // Save button
    const saveBtn = this.shadowRoot.querySelector('#dialog-save');
    if (saveBtn) {
      saveBtn.addEventListener('click', () => {
        if (this._showingGlobalDialog) {
          this._saveGlobalFromDialog();
        } else if (this._showingDeviceDialog) {
          this._saveDeviceFromDialog();
        }
      });
    }

    // Type change for device dialog
    const typeSelect = this.shadowRoot.querySelector('#device_type');
    if (typeSelect) {
      typeSelect.addEventListener('change', (e) => {
        this._dialogData.type = e.target.value;
        this.render();
      });
    }

    // ESC key to close dialog
    const handleEsc = (e) => {
      if (e.key === 'Escape' && (this._showingGlobalDialog || this._showingDeviceDialog)) {
        this._closeDialog();
      }
    };
    document.addEventListener('keydown', handleEsc);
  }

  /**
   * Save global config from dialog inputs
   */
  _saveGlobalFromDialog() {
    this._dialogData.surplus_sensor_entity_id = this.shadowRoot.querySelector('#surplus_sensor').value;
    this._dialogData.sliding_window_size = parseInt(this.shadowRoot.querySelector('#sliding_window').value);
    this._dialogData.optimization_cycle_time = parseInt(this.shadowRoot.querySelector('#cycle_time').value);
    this._saveGlobalConfig();
  }

  /**
   * Save device from dialog inputs
   */
  _saveDeviceFromDialog() {
    this._dialogData.name = this.shadowRoot.querySelector('#device_name').value;
    this._dialogData.type = this.shadowRoot.querySelector('#device_type').value;
    this._dialogData.priority = parseInt(this.shadowRoot.querySelector('#priority').value);
    this._dialogData.power = parseFloat(this.shadowRoot.querySelector('#power').value);
    this._dialogData.optimization_enabled = this.shadowRoot.querySelector('#optimization_enabled').checked;
    this._dialogData.measured_power_entity_id = this.shadowRoot.querySelector('#measured_power').value || null;
    this._dialogData.power_threshold = parseFloat(this.shadowRoot.querySelector('#power_threshold').value);
    this._dialogData.min_on_time = parseInt(this.shadowRoot.querySelector('#min_on_time').value);
    this._dialogData.min_off_time = parseInt(this.shadowRoot.querySelector('#min_off_time').value);
    
    if (this._dialogData.type === 'switch') {
      this._dialogData.switch_entity_id = this.shadowRoot.querySelector('#switch_entity').value;
      this._dialogData.invert_switch = this.shadowRoot.querySelector('#invert_switch').checked;
    }
    
    this._saveDevice();
  }
}

// Register custom element
customElements.define('pv-optimizer-panel', PvOptimizerPanel);
