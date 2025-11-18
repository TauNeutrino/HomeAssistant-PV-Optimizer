/**
 * PV Optimizer Panel for Home Assistant
 * 
 * This panel provides quick access to device status and shortcuts to
 * the configuration options flow for device management.
 * 
 * All configuration (global settings and device management) is handled
 * through Home Assistant's native config flow system for proper focus
 * handling and native UI components.
 */

class PvOptimizerPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    
    this._config = null;
    this._error = null;
    this._loading = true;
  }

  set hass(hass) {
    this._hass = hass;
    
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
   * Navigate to integration options flow
   */
  _openOptionsFlow() {
    // Find PV Optimizer config entry
    const configEntries = Object.values(this._hass.config_entries || {});
    const entry = configEntries.find(e => e.domain === 'pv_optimizer');
    
    if (entry) {
      // Navigate to integration page which will show option button
      window.history.pushState(null, '', `/config/integrations/integration/pv_optimizer`);
      const event = new CustomEvent('location-changed');
      window.dispatchEvent(event);
    }
  }

  render() {
    if (!this.shadowRoot) return;

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
          padding: 10px 20px;
          border-radius: 4px;
          cursor: pointer;
          font-size: 14px;
          font-weight: 500;
          transition: all 0.2s;
        }

        button:hover {
          background-color: var(--primary-color-dark, #0288d1);
          transform: translateY(-1px);
          box-shadow: 0 2px 8px rgba(0,0,0,0.2);
        }

        button.large {
          padding: 16px 32px;
          font-size: 16px;
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
          background-color: rgba(3, 169, 244, 0.1);
          border-left: 4px solid var(--info-color, #2196f3);
          padding: 16px;
          border-radius: 4px;
          margin-bottom: 20px;
        }

        .info-title {
          font-weight: 600;
          margin-bottom: 8px;
          color: var(--primary-text-color);
        }

        .info-text {
          color: var(--secondary-text-color);
          font-size: 14px;
          line-height: 1.5;
        }

        .config-button-container {
          text-align: center;
          padding: 32px 20px;
        }
      </style>
    `;

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

    if (this._loading) {
      this.shadowRoot.innerHTML = `
        ${styles}
        <div class="header">⚡ PV Optimizer</div>
        <div class="card">
          <div class="loading">⏳ Loading configuration...</div>
        </div>
      `;
      return;
    }

    const globalConfig = this._config?.global_config || {};
    const devices = this._config?.devices || [];

    this.shadowRoot.innerHTML = `
      ${styles}
      <div class="header">⚡ PV Optimizer</div>
      
      <div class="info-box">
        <div class="info-title">ℹ️ Configuration via Options Flow</div>
        <div class="info-text">
          All configuration (global settings and device management) is now handled through 
          Home Assistant's native configuration interface. Click the button below to access 
          the configuration menu with proper native dialogs, entity selectors, and focus handling.
        </div>
      </div>

      <div class="card">
        <div class="config-button-container">
          <button class="large" id="open-config-btn">
            ⚙️ Open Configuration
          </button>
          <div style="margin-top: 12px; color: var(--secondary-text-color); font-size: 14px;">
            Configure global settings • Manage devices • Add/Edit/Delete
          </div>
        </div>
      </div>
      
      ${this._renderGlobalConfig(globalConfig)}
      ${this._renderDeviceList(devices)}
    `;

    this._attachEventListeners();
  }

  _renderGlobalConfig(globalConfig) {
    return `
      <div class="card">
        <div class="card-header">
          <span>📊 Global Configuration</span>
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

  _renderDeviceList(devices) {
    return `
      <div class="card">
        <div class="card-header">
          <span>📱 Devices (${devices.length})</span>
        </div>
        <div class="card-content">
          ${devices.length === 0 ? `
            <div class="empty-state">
              <div style="font-size: 48px; margin-bottom: 16px;">📱</div>
              <div style="font-weight: 500; margin-bottom: 8px;">No devices configured yet</div>
              <div style="font-size: 14px; margin-bottom: 16px;">
                Click "Open Configuration" above to add your first device
              </div>
              <button onclick="this.getRootNode().host._openOptionsFlow()">
                ➕ Add First Device
              </button>
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

  _renderDeviceCard(deviceData) {
    const device = deviceData.config;
    const state = deviceData.state || {};
    
    return `
      <div class="device-card">
        <div class="device-name">
          ${device.optimization_enabled ? '🟢' : '🔴'} ${device.name}
        </div>
        <div class="device-details">
          <div><strong>Type:</strong> ${device.type}</div>
          <div><strong>Priority:</strong> ${device.priority}</div>
          <div><strong>Power:</strong> ${device.power}W</div>
          <div><strong>Status:</strong> ${state.is_on ? '✅ ON' : '⭕ OFF'}</div>
          <div><strong>Locked:</strong> ${state.is_locked ? '🔒 Yes' : '🔓 No'}</div>
          ${state.measured_power_avg ? `
            <div><strong>Measured:</strong> ⚡ ${state.measured_power_avg.toFixed(1)}W</div>
          ` : ''}
        </div>
      </div>
    `;
  }

  _attachEventListeners() {
    const openConfigBtn = this.shadowRoot.querySelector('#open-config-btn');
    if (openConfigBtn) {
      openConfigBtn.addEventListener('click', () => this._openOptionsFlow());
    }
  }
}

customElements.define('pv-optimizer-panel', PvOptimizerPanel);
