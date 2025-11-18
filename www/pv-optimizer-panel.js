/**
 * PV Optimizer Panel for Home Assistant
 * 
 * This panel provides a user interface for managing the PV Optimizer integration.
 * It triggers config flows for device management, providing native HA dialogs with
 * proper focus handling and all native selectors.
 * 
 * Features:
 * - Global configuration management via config flow
 * - Device management (add, edit, delete) via service calls and config flow
 * - Native HA dialogs with proper focus handling
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
   */
  set hass(hass) {
    this._hass = hass;
    
    // Load configuration on first hass assignment
    if (!this._config) {
      this._getConfigWithRetry();
    }
    
    this.render();
  }

  get hass() {
    return this._hass;
  }

  set panel(panel) {
    this._panel = panel;
  }

  connectedCallback() {
    this.render();
  }

  /**
   * Load configuration from backend with retry logic
   */
  async _getConfigWithRetry(retryCount = 0) {
    if (!this._hass?.connection) {
      this._error = 'WebSocket connection not available';
      this._loading = false;
      this.render();
      return;
    }

    try {
      this._loading = true;
      this._error = null;
      this.render();

      await new Promise(resolve => setTimeout(resolve, 500));

      const response = await this._hass.callWS({
        type: 'pv_optimizer/config',
      });
      
      this._config = response;
      this._loading = false;
      this._error = null;
      this.render();
      
    } catch (error) {
      console.error('Failed to get config:', error);
      
      if (retryCount < 3) {
        const delay = Math.pow(2, retryCount) * 1000;
        setTimeout(() => this._getConfigWithRetry(retryCount + 1), delay);
      } else {
        this._error = `Failed to load configuration: ${error.message}`;
        this._loading = false;
        this.render();
      }
    }
  }

  /**
   * Open options flow for global configuration
   * This uses HA's native config flow system
   */
  _editGlobalConfig() {
    // Find the config entry for PV Optimizer
    const entries = Object.values(this._hass.config_entries || {});
    const entry = entries.find(e => e.domain === 'pv_optimizer');
    
    if (entry) {
      // Navigate to options flow
      window.history.pushState(null, '', `/config/integrations/integration/pv_optimizer`);
      const event = new CustomEvent('location-changed');
      window.dispatchEvent(event);
    } else {
      this._showToast('Integration entry not found');
    }
  }

  /**
   * Start a service call-based flow for adding devices
   * Uses HA service calls with data forms
   */
  async _addDevice() {
    this._showToast('Use the WebSocket API to add devices. UI form coming in a future version.');
    // TODO: In future, trigger a custom config flow for device addition
  }

  /**
   * Edit device via service call
   */
  async _editDevice(deviceName) {
    this._showToast('Use the WebSocket API to edit devices. UI form coming in a future version.');
    // TODO: In future, trigger a custom config flow for device editing
  }

  /**
   * Delete a device
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
   * Main render function
   */
  render() {
    if (!this.shadowRoot) return;

    // CSS styles
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

        .info-box {
          background-color: var(--info-color, #2196f3);
          color: white;
          padding: 12px;
          border-radius: 4px;
          margin-bottom: 16px;
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
    const devices = this._config?.devices || {};

    // Render main content
    this.shadowRoot.innerHTML = `
      ${styles}
      <div class="header">⚡ PV Optimizer</div>
      
      <div class="info-box">
        ℹ️ <strong>Note:</strong> Device management UI is under development. Currently, devices must be added via the WebSocket API or YAML configuration. You can edit global settings and delete devices from this panel.
      </div>
      
      ${this._renderGlobalConfig(globalConfig)}
      ${this._renderDeviceList(devices)}
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
          <button id="edit-global-btn">⚙️ Configure Integration</button>
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
    const deviceArray = devices.devices || [];
    
    return `
      <div class="card">
        <div class="card-header">
          <span>Devices (${deviceArray.length})</span>
        </div>
        <div class="card-content">
          ${deviceArray.length === 0 ? `
            <div class="empty-state">
              <div style="font-size: 48px; margin-bottom: 16px;">📱</div>
              <div>No devices configured yet</div>
              <div style="margin-top: 8px; font-size: 14px;">
                Add devices via the WebSocket API or YAML configuration
              </div>
            </div>
          ` : `
            <div class="device-list">
              ${deviceArray.map(device => this._renderDeviceCard(device)).join('')}
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
          <button class="danger delete-device-btn" data-device-name="${escapedName}">🗑️ Delete</button>
        </div>
      </div>
    `;
  }

  /**
   * Attach event listeners
   */
  _attachEventListeners() {
    // Global config edit button
    const editGlobalBtn = this.shadowRoot.querySelector('#edit-global-btn');
    if (editGlobalBtn) {
      editGlobalBtn.addEventListener('click', () => this._editGlobalConfig());
    }

    // Delete device buttons
    const deleteButtons = this.shadowRoot.querySelectorAll('.delete-device-btn');
    deleteButtons.forEach(btn => {
      btn.addEventListener('click', (e) => {
        const deviceName = e.target.dataset.deviceName;
        this._deleteDevice(deviceName);
      });
    });
  }
}

// Register custom element
customElements.define('pv-optimizer-panel', PvOptimizerPanel);
