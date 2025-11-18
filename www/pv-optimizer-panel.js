
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
    this._checkWebSocket();
    this.render();
  }

  get hass() {
    return this._hass;
  }

  set panel(panel) {
    this._panel = panel;
    this.render();
  }

  async connectedCallback() {
    this.render();
    await this._getConfigWithRetry();
  }

  _checkWebSocket() {
    if (this._hass && !this._hass.connection) {
      this._error = 'WebSocket connection not available. Please ensure Home Assistant is properly connected.';
      this._loading = false;
      this.render();
      return false;
    }
    return true;
  }

  async _getConfigWithRetry(retryCount = 0) {
    if (!this._hass || !this._checkWebSocket()) {
      return;
    }

    try {
      this._loading = true;
      this._error = null;
      this.render();

      // Wait a bit for WebSocket connection to establish
      await new Promise(resolve => setTimeout(resolve, 1000));

      const response = await this._hass.callWS({
        type: 'pv_optimizer/config',
      });
      
      this._config = response;
      this._loading = false;
      this._error = null;
      this.render();
      
    } catch (error) {
      console.error('Failed to get config:', error);
      
      // Retry up to 3 times with increasing delays
      if (retryCount < 3) {
        const delay = Math.pow(2, retryCount) * 1000; // 1s, 2s, 4s
        setTimeout(() => this._getConfigWithRetry(retryCount + 1), delay);
      } else {
        this._error = `Failed to load configuration: ${error.message || 'Connection error'}`;
        this._loading = false;
        this.render();
      }
    }
  }

  _formatConfigValue(value) {
    if (value === null || value === undefined) {
      return 'Not configured';
    }
    return String(value);
  }

  render() {
    if (!this.shadowRoot) return;

    const hasConnection = this._checkWebSocket();
    const loading = this._loading && hasConnection;
    const error = this._error;
    const config = this._config || {};
    const globalConfig = config.global_config || {};
    const devices = config.devices || [];

    const surplusSensor = this._formatConfigValue(globalConfig.surplus_sensor_entity_id);
    const slidingWindow = this._formatConfigValue(globalConfig.sliding_window_size);
    const cycleTime = this._formatConfigValue(globalConfig.optimization_cycle_time);

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          padding: 16px;
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
        }

        .card {
          background-color: var(--ha-card-background, var(--card-background-color, white));
          border-radius: var(--ha-card-border-radius, 4px);
          box-shadow: var(--ha-card-box-shadow, 0px 2px 1px -1px rgba(0, 0, 0, 0.2), 0px 1px 1px 0px rgba(0, 0, 0, 0.14), 0px 1px 3px 0px rgba(0, 0, 0, 0.12));
          padding: 16px;
          margin-bottom: 16px;
        }

        .card-header {
          font-size: 1.2em;
          font-weight: bold;
          margin-bottom: 16px;
          color: var(--primary-text-color);
        }

        .form-group {
          margin-bottom: 16px;
        }

        label {
          display: block;
          margin-bottom: 8px;
          color: var(--primary-text-color);
          font-weight: 500;
        }

        .value {
          padding: 8px 12px;
          background-color: var(--secondary-background-color, #f5f5f5);
          border-radius: 4px;
          color: var(--primary-text-color, #000);
          font-family: monospace;
        }

        .error {
          color: var(--error-color, #f44336);
          background-color: rgba(244, 67, 54, 0.1);
          padding: 12px;
          border-radius: 4px;
          margin: 8px 0;
          border-left: 4px solid var(--error-color, #f44336);
        }

        .loading {
          color: var(--secondary-text-color, #666);
          font-style: italic;
        }

        .success {
          color: var(--success-color, #4caf50);
        }

        .refresh-button {
          background-color: var(--primary-color, #2196f3);
          color: white;
          border: none;
          padding: 8px 16px;
          border-radius: 4px;
          cursor: pointer;
          margin-top: 8px;
        }

        .refresh-button:hover {
          background-color: var(--primary-color-dark, #1976d2);
        }

        .status-indicator {
          width: 12px;
          height: 12px;
          border-radius: 50%;
          display: inline-block;
          margin-right: 8px;
        }

        .status-connected {
          background-color: var(--success-color, #4caf50);
        }

        .status-disconnected {
          background-color: var(--error-color, #f44336);
        }

        .status-loading {
          background-color: var(--warning-color, #ff9800);
          animation: pulse 1.5s infinite;
        }

        .device-card {
          background-color: var(--secondary-background-color, #f0f0f0);
          border-left: 4px solid var(--primary-color, #03a9f4);
          padding: 12px;
          margin-top: 12px;
          border-radius: 4px;
        }

        .device-card h3 {
          margin-top: 0;
          margin-bottom: 8px;
          color: var(--primary-text-color);
        }

        .device-card p {
          margin: 4px 0;
          color: var(--secondary-text-color);
        }

        @keyframes pulse {
          0% { opacity: 1; }
          50% { opacity: 0.5; }
          100% { opacity: 1; }
        }
      </style>
      
      <div class="card">
        <div class="card-header">
          <span class="status-indicator ${error ? 'status-disconnected' : (loading ? 'status-loading' : 'status-connected')}"></span>
          PV Optimizer Configuration
        </div>
        
        ${error ? `
          <div class="error">
            <strong>Connection Error:</strong><br>
            ${error}<br>
            <button class="refresh-button" onclick="location.reload()">Refresh Page</button>
          </div>
        ` : loading ? `
          <div class="loading">🔄 Loading configuration...</div>
        ` : config ? `
          <div class="success">✅ Connected to Home Assistant</div>
          
          <div class="form-group">
            <label for="surplus-sensor">PV Surplus Sensor</label>
            <div class="value" id="surplus-sensor">${surplusSensor}</div>
          </div>
          
          <div class="form-group">
            <label for="sliding-window">Sliding Window Size (minutes)</label>
            <div class="value" id="sliding-window">${slidingWindow}</div>
          </div>
          
          <div class="form-group">
            <label for="cycle-time">Optimization Cycle Time (seconds)</label>
            <div class="value" id="cycle-time">${cycleTime}</div>
          </div>
        ` : `
          <div class="error">
            <strong>No configuration data received</strong><br>
            The PV Optimizer integration may not be properly configured.
          </div>
        `}
      </div>
      
      <div class="card">
        <div class="card-header">Device Status</div>
        ${loading ? `
          <div class="loading">Loading device information...</div>
        ` : error ? `
          <div class="error">Cannot display device status due to connection issues.</div>
        ` : devices.length > 0 ? `
          <div class="success">Device monitoring is active</div>
          <div style="margin-top: 12px;">
            <p><strong>Total Devices:</strong> ${devices.length}</p>
            ${devices.map(device => `
              <div class="device-card">
                <h3>${device.config.name}</h3>
                <p><strong>Type:</strong> ${device.config.type}</p>
                <p><strong>Priority:</strong> ${device.config.priority}</p>
                <p><strong>Optimization Enabled:</strong> ${device.config.optimization_enabled ? 'Yes' : 'No'}</p>
                <p><strong>Current State:</strong> ${device.state.is_on ? 'On' : 'Off'}</p>
                <p><strong>Measured Power Avg:</strong> ${device.state.measured_power_avg ? device.state.measured_power_avg.toFixed(2) + ' W' : 'N/A'}</p>
                <p><strong>Locked:</strong> ${device.state.is_locked ? 'Yes' : 'No'}</p>
              </div>
            `).join('')}
          </div>
        ` : `
          <div class="error">No devices configured for PV Optimizer.</div>
        `}
      </div>
    `;
  }
}

customElements.define('pv-optimizer-panel', PvOptimizerPanel);
