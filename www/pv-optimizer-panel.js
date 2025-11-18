/**
 * PV Optimizer Panel for Home Assistant
 * 
 * Minimal panel that shows device status and provides access to config flow.
 * Based on browser_mod patterns for proper button handling without flicker.
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
   * Navigate to integration config page
   * Opens the options flow directly
   */
  _openOptionsFlow() {
    // Navigate to the integration's config entry page
    this._hass.callService("browser_mod", "navigate", {
      path: "/config/integrations/integration/pv_optimizer"
    }).catch(() => {
      // Fallback: use direct navigation
      window.history.pushState(null, '', '/config/integrations/integration/pv_optimizer');
      window.dispatchEvent(new CustomEvent('location-changed', {
        bubbles: true,
        composed: true
      }));
    });
  }

  render() {
    if (!this.shadowRoot) return;

    const styles = `
      <style>
        :host {
          display: block;
          padding: 0;
          background-color: var(--primary-background-color);
        }

        ha-card {
          margin: 16px;
        }

        .card-header {
          font-size: 18px;
          font-weight: 600;
          padding: 16px;
        }

        .card-content {
          padding: 16px;
        }

        .config-group {
          margin-bottom: 16px;
        }

        .config-label {
          font-weight: 500;
          margin-bottom: 4px;
          font-size: 14px;
          color: var(--secondary-text-color);
        }

        .config-value {
          padding: 8px 12px;
          background-color: var(--secondary-background-color);
          border-radius: 4px;
          font-family: monospace;
          font-size: 13px;
        }

        .device-list {
          display: grid;
          gap: 12px;
        }

        .device-card {
          background-color: var(--secondary-background-color);
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
        }

        .loading {
          text-align: center;
          padding: 20px;
          color: var(--secondary-text-color);
        }

        .config-button-container {
          text-align: center;
          padding: 32px 20px;
        }

        ha-alert {
          display: block;
          margin-bottom: 16px;
        }

        /* Ensure ha-button doesn't flicker */
        ha-button {
          --md-sys-color-primary: var(--primary-color);
        }
      </style>
    `;

    if (this._error) {
      this.shadowRoot.innerHTML = `
        ${styles}
        <ha-card outlined header="PV Optimizer">
          <div class="card-content">
            <ha-alert alert-type="error">
              ${this._error}
              <ha-button slot="action" onclick="location.reload()">Refresh</ha-button>
            </ha-alert>
          </div>
        </ha-card>
      `;
      return;
    }

    if (this._loading) {
      this.shadowRoot.innerHTML = `
        ${styles}
        <ha-card outlined header="PV Optimizer">
          <div class="card-content">
            <div class="loading">⏳ Loading configuration...</div>
          </div>
        </ha-card>
      `;
      return;
    }

    const globalConfig = this._config?.global_config || {};
    const devices = this._config?.devices || [];

    this.shadowRoot.innerHTML = `
      ${styles}
      
      <ha-card outlined header="PV Optimizer">
        <div class="card-content">
          <ha-alert alert-type="info" title="Configuration">
            All settings are managed through the integration's options flow.
            Click the button below to access device management and global settings.
          </ha-alert>
        </div>
        
        <div class="card-content">
          <div class="config-button-container">
            <ha-button
              id="open-config-btn"
              appearance="filled"
            >
              <ha-icon slot="start" icon="mdi:cog"></ha-icon>
              Open Configuration
            </ha-button>
          </div>
        </div>
      </ha-card>

      <ha-card outlined header="Global Configuration">
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
      </ha-card>

      <ha-card outlined header="Devices (${devices.length})">
        <div class="card-content">
          ${devices.length === 0 ? `
            <div class="empty-state">
              <div style="font-size: 48px; margin-bottom: 16px;">📱</div>
              <div style="font-weight: 500; margin-bottom: 8px;">No devices configured yet</div>
              <div style="font-size: 14px; margin-bottom: 16px;">
                Click "Open Configuration" above to add your first device
              </div>
            </div>
          ` : `
            <div class="device-list">
              ${devices.map(device => this._renderDeviceCard(device)).join('')}
            </div>
          `}
        </div>
      </ha-card>
    `;

    this._attachEventListeners();
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
      // Use proper addEventListener (not onclick) to avoid focus issues
      openConfigBtn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        this._openOptionsFlow();
      });
    }
  }
}

customElements.define('pv-optimizer-panel', PvOptimizerPanel);
