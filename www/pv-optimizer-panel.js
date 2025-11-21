import "https://unpkg.com/wired-card@2.1.0/lib/wired-card.js?module";
import {
  LitElement,
  html,
  css,
} from "https://unpkg.com/lit-element@2.4.0/lit-element.js?module";

/**
 * PV Optimizer Panel with Simulation Support
 * 
 * UPDATED: Added simulation results display
 * - Shows real optimization results
 * - Shows simulation results
 * - Toggle between separate view and comparison table
 */
class PvOptimizerPanel extends LitElement {
  static get properties() {
    return {
      hass: { type: Object },
      narrow: { type: Boolean },
      _config: { type: Object, state: true },
      _loading: { type: Boolean, state: true },
      _error: { type: String, state: true },
      _showComparison: { type: Boolean, state: true },  // NEW: Toggle for comparison view
      _lastUpdateTimestamp: { type: Object, state: true },
      _elapsedSeconds: { type: Number, state: true },
    };
  }

  constructor() {
    super();
    this._config = null;
    this._loading = true;
    this._error = null;
    this._refreshInterval = null;
    this._showComparison = false;  // Start with separate cards view
    this._secondInterval = null;
    this._lastUpdateTimestamp = null;
    this._elapsedSeconds = null;
  }

  connectedCallback() {
    super.connectedCallback();
    this._fetchConfig();

    // Auto-refresh every 30 seconds
    this._refreshInterval = setInterval(() => {
      this._fetchConfig();
    }, 30000);

    // Update elapsed time every second
    this._secondInterval = setInterval(() => {
      this._updateElapsedTime();
    }, 1000);
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    if (this._refreshInterval) {
      clearInterval(this._refreshInterval);
      this._refreshInterval = null;
    }
    if (this._secondInterval) {
      clearInterval(this._secondInterval);
      this._secondInterval = null;
    }
  }

  _updateElapsedTime() {
    if (this._lastUpdateTimestamp) {
      this._elapsedSeconds = Math.floor((new Date() - this._lastUpdateTimestamp) / 1000);
    }
  }

  updated(changedProperties) {
    if (changedProperties.has("hass") && this.hass && !this._config) {
      this._fetchConfig();
    }
  }

  async _fetchConfig() {
    if (!this.hass) {
      return;
    }

    if (!this.hass.connection) {
      this._error = "WebSocket connection not available";
      this._loading = false;
      return;
    }

    try {
      this._loading = true;
      this._error = null;

      const response = await this.hass.callWS({
        type: "pv_optimizer/config",
      });

      this._config = response;
      if (response?.optimizer_stats?.last_update_timestamp) {
        this._lastUpdateTimestamp = new Date(response.optimizer_stats.last_update_timestamp);
        this._updateElapsedTime();
      } else {
        this._lastUpdateTimestamp = null;
      }
      this._loading = false;
      this._error = null;
    } catch (error) {
      console.error("PV Optimizer: Failed to get config:", error);
      this._error = `Failed to load configuration: ${error.message}`;
      this._loading = false;
    }
  }

  _openConfiguration() {
    // Navigate to integration configuration
    window.history.pushState(
      null,
      "",
      "/config/integrations/integration/pv_optimizer"
    );
    window.dispatchEvent(new Event("location-changed"));
  }

  _toggleComparison() {
    this._showComparison = !this._showComparison;
  }

  /**
   * Get ideal device list from Home Assistant state
   * NEW: Helper to fetch sensor data
   */
  _getIdealDevices(sensorName) {
    if (!this.hass) return [];

    const entity = this.hass.states[`sensor.pv_optimizer_${sensorName}`];
    if (!entity) return [];

    return entity.attributes.device_details || [];
  }

  _getPowerBudget(key) {
    if (!this.hass) return 0;

    const sensorName = key === 'real' ? 'power_budget' : 'simulation_power_budget';
    const entity = this.hass.states[`sensor.pv_optimizer_${sensorName}`];
    if (!entity) return 0;

    return parseFloat(entity.state) || 0;
  }

  _renderStatusCard() {
    const ready = !this._loading && !this._error && this._config;

    return html`
      <div class="header">
      <div class="name">PV Optimizer</div>
      <div class="header-right">
        <ha-button
          appearance="filled"
          @click=${this._openConfiguration}
        >
          <ha-icon slot="icon" .icon=${"mdi:cog"}></ha-icon>
          Open Configuration
        </ha-button>
        ${ready
        ? html`
              <ha-icon
                class="icon"
                .icon=${"mdi:check-circle-outline"}
                style="color: var(--success-color, green);"
              ></ha-icon>
            `
        : html`
              <ha-icon
                class="icon"
                .icon=${"mdi:alert-circle-outline"}
                style="color: var(--error-color, red);"
              ></ha-icon>
            `}
        </div>
      </div>
    `;
  }

  _renderErrorCard() {
    return html`
      <ha-card outlined>
        <div class="card-content">
          <ha-alert alert-type="error">
            ${this._error}
            <ha-button
              slot="action"
              appearance="plain"
              @click=${() => this._fetchConfig()}
            >
              Retry
            </ha-button>
          </ha-alert>
        </div>
      </ha-card>
    `;
  }

  _renderGlobalConfigCard() {
    if (!this._config?.global_config) {
      return html``;
    }

    const stats = this._config.optimizer_stats;

    return html`
      <ha-card outlined>
        <h1 class="card-header">Global Configuration</h1>
        <div class="card-content">
          ${stats ? html`
            <div class="config-group">
              <div class="config-label">Current Surplus</div>
              <div class="config-value">${stats.current_surplus.toFixed(2)} W</div>
            </div>
            <div class="config-group">
              <div class="config-label">Averaged Surplus</div>
              <div class="config-value">${stats.averaged_surplus.toFixed(2)} W</div>
            </div>
            <div class="config-group">
              <div class="config-label">Potential Power of Switched-On Devices</div>
              <div class="config-value">${stats.potential_power_on_devices.toFixed(2)} W</div>
            </div>
            <div class="config-group">
              <div class="config-label">Measured Power of Switched-On Devices</div>
              <div class="config-value">${stats.measured_power_on_devices.toFixed(2)} W</div>
            </div>
            <div class="config-group">
              <div class="config-label">Last Update Timestamp</div>
              <div class="config-value">${this._lastUpdateTimestamp ? this._lastUpdateTimestamp.toLocaleString() : 'N/A'}</div>
            </div>
            <div class="config-group">
              <div class="config-label">Elapsed Time Since Last Update</div>
              <div class="config-value">${this._elapsedSeconds !== null ? `${this._elapsedSeconds} s` : 'N/A'}</div>
            </div>
          ` : html`
            <div class="loading">⏳ Loading stats...</div>
          `}
        </div>
      </ha-card>
    `;
  }

  /**
   * NEW: Render ideal devices list (real or simulation)
   */
  _renderIdealDevicesCard(title, sensorKey, icon, color) {
    const devices = this._getIdealDevices(sensorKey);
    const budget = this._getPowerBudget(sensorKey === 'real_ideal_devices' ? 'real' : 'simulation');
    const totalPower = devices.reduce((sum, d) => sum + (d.power || 0), 0);

    return html`
      <ha-card outlined>
        <h1 class="card-header" style="border-left: 4px solid ${color};">
          <ha-icon .icon=${icon} style="color: ${color}; margin-right: 8px;"></ha-icon>
          ${title}
        </h1>
        <div class="card-content">
          ${devices.length === 0
        ? html`
                <div class="empty-state">
                  <div style="font-size: 32px; margin-bottom: 12px;">📊</div>
                  <div>No devices in ideal ${title.toLowerCase()} state</div>
                </div>
              `
        : html`
                <div class="ideal-summary">
                  <div class="summary-item">
                    <div class="summary-label">Devices Active</div>
                    <div class="summary-value">${devices.length}</div>
                  </div>
                  <div class="summary-item">
                    <div class="summary-label">Total Power</div>
                    <div class="summary-value">${totalPower.toFixed(0)}W</div>
                  </div>
                  <div class="summary-item">
                    <div class="summary-label">Budget Available</div>
                    <div class="summary-value">${budget.toFixed(0)}W</div>
                  </div>
                  <div class="summary-item">
                    <div class="summary-label">Budget Used</div>
                    <div class="summary-value">${((totalPower / budget) * 100).toFixed(0)}%</div>
                  </div>
                </div>
                
                <div class="device-list">
                  ${devices.map((device) => this._renderIdealDeviceRow(device))}
                </div>
              `}
        </div>
      </ha-card>
    `;
  }

  _renderIdealDeviceRow(device) {
    return html`
      <div class="ideal-device-row">
        <div class="device-info">
          <div class="device-name">✅ ${device.name}</div>
          <div class="device-meta">
            Priority ${device.priority} • ${device.type}
          </div>
        </div>
        <div class="device-power">⚡ ${device.power}W</div>
      </div>
    `;
  }

  /**
   * NEW: Render comparison table
   */
  _renderComparisonTable() {
    const realDevices = this._getIdealDevices('real_ideal_devices');
    const simDevices = this._getIdealDevices('simulation_ideal_devices');

    // Get all unique device names
    const allDeviceNames = new Set([
      ...realDevices.map(d => d.name),
      ...simDevices.map(d => d.name)
    ]);

    const realBudget = this._getPowerBudget('real');
    const simBudget = this._getPowerBudget('simulation');

    return html`
      <ha-card outlined>
        <h1 class="card-header">
          <ha-icon .icon=${"mdi:table-compare"} style="margin-right: 8px;"></ha-icon>
          Real vs Simulation Comparison
        </h1>
        <div class="card-content">
          <div class="comparison-summary">
            <div class="comparison-col">
              <div class="comparison-title">Real Optimization</div>
              <div class="comparison-stat">
                ${realDevices.length} devices | 
                ${realDevices.reduce((s, d) => s + d.power, 0)}W / ${realBudget.toFixed(0)}W
              </div>
            </div>
            <div class="comparison-col">
              <div class="comparison-title">Simulation</div>
              <div class="comparison-stat">
                ${simDevices.length} devices | 
                ${simDevices.reduce((s, d) => s + d.power, 0)}W / ${simBudget.toFixed(0)}W
              </div>
            </div>
          </div>

          <table class="comparison-table">
            <thead>
              <tr>
                <th>Device</th>
                <th>Power</th>
                <th>Real</th>
                <th>Simulation</th>
              </tr>
            </thead>
            <tbody>
              ${Array.from(allDeviceNames).map(name => {
      const realDevice = realDevices.find(d => d.name === name);
      const simDevice = simDevices.find(d => d.name === name);
      const inReal = !!realDevice;
      const inSim = !!simDevice;
      const power = (realDevice || simDevice)?.power || 0;

      return html`
                  <tr>
                    <td class="device-name-col">${name}</td>
                    <td>${power}W</td>
                    <td class="status-col">
                      ${inReal ? html`<span class="status-badge active">✅ Active</span>` : html`<span class="status-badge inactive">⭕ Inactive</span>`}
                    </td>
                    <td class="status-col">
                      ${inSim ? html`<span class="status-badge active">✅ Active</span>` : html`<span class="status-badge inactive">⭕ Inactive</span>`}
                    </td>
                  </tr>
                `;
    })}
            </tbody>
          </table>
        </div>
      </ha-card>
    `;
  }

  _renderDeviceCard(deviceData) {
    const device = deviceData.config;
    const state = deviceData.state || {};

    const statusIcon = device.optimization_enabled ? "🟢" : "🔴";
    const simIcon = device.simulation_active ? "🧪" : "";
    const statusText = state.is_on ? "✅ ON" : "⭕ OFF";
    const lockIcon = state.is_locked ? "🔒" : "🔓";

    return html`
      <div class="device-card">
        <div class="device-name">${statusIcon} ${simIcon} ${device.name}</div>
        <div class="device-details">
          <div><strong>Type:</strong> ${device.type}</div>
          <div><strong>Priority:</strong> ${device.priority}</div>
          <div><strong>Power:</strong> ${device.power}W</div>
          <div><strong>Status:</strong> ${statusText}</div>
          <div><strong>Locked:</strong> ${lockIcon} ${state.is_locked ? "Yes" : "No"}</div>
          ${device.optimization_enabled ? html`<div><strong>Real Opt:</strong> ✅ Enabled</div>` : ''}
          ${device.simulation_active ? html`<div><strong>Simulation:</strong> 🧪 Active</div>` : ''}
          ${state.measured_power_avg
        ? html`
                <div>
                  <strong>Measured:</strong> ⚡
                  ${state.measured_power_avg.toFixed(1)}W
                </div>
              `
        : ""}
        </div>
      </div>
    `;
  }

  _renderDevicesCard() {
    const devices = this._config?.devices || [];

    return html`
      <ha-card outlined>
        <h1 class="card-header">Devices (${devices.length})</h1>
        <div class="card-content">
          ${devices.length === 0
        ? html`
                <div class="empty-state">
                  <div style="font-size: 48px; margin-bottom: 16px;">📱</div>
                  <div style="font-weight: 500; margin-bottom: 8px;">
                    No devices configured yet
                  </div>
                  <div style="font-size: 14px; margin-bottom: 16px;">
                    Click "Open Configuration" above to add your first device
                  </div>
                </div>
              `
        : html`
                <div class="device-list">
                  ${devices.map((device) => this._renderDeviceCard(device))}
                </div>
              `}
          </div>
        </ha-card>
      `;
  }

  render() {
    if (this._loading && !this._config) {
      return html`
        <ha-card outlined>
          <div class="card-content">
            <div class="loading">⏳ Loading configuration...</div>
          </div>
        </ha-card>
      `;
    }

    return html`
      ${this._renderStatusCard()} 
      ${this._renderGlobalConfigCard()}
      
      <!-- NEW: Toggle button for comparison view -->
      <div class="toggle-container">
        <ha-button @click=${this._toggleComparison}>
          <ha-icon 
            slot="icon" 
            .icon=${this._showComparison ? "mdi:view-split-vertical" : "mdi:table-compare"}
          ></ha-icon>
          ${this._showComparison ? "Show Separate Cards" : "Show Comparison Table"}
        </ha-button>
      </div>

      <!-- NEW: Conditional rendering based on view mode -->
      ${this._showComparison
        ? html`${this._renderComparisonTable()}`
        : html`
            ${this._renderIdealDevicesCard(
          "Real Optimization",
          "real_ideal_devices",
          "mdi:lightning-bolt",
          "var(--success-color, #4caf50)"
        )}
            ${this._renderIdealDevicesCard(
          "Simulation",
          "simulation_ideal_devices",
          "mdi:test-tube",
          "var(--info-color, #2196f3)"
        )}
          `}

      ${this._renderDevicesCard()}

      ${this._error ? this._renderErrorCard() : ""}
    `;
  }

  static get styles() {
    return css`
      :host {
        display: block;
        padding: 16px;
        background-color: var(--primary-background-color);
      }

      .header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 12px 16px;
        background-color: var(--app-header-background-color, var(--primary-color));
        color: var(--app-header-text-color, white);
        margin: -16px -16px 16px -16px;
        --md-sys-color-primary: var(--app-header-text-color, white);
      }

      .header .name {
        font-size: 24px;
        font-weight: 400;
      }
      
      .header-right {
        display: flex;
        align-items: center;
        gap: 16px;
      }

      .card-container {
        display: flex;
        flex-wrap: wrap;
        justify-content: center;
        gap: 16px;
      }

      ha-card {
        flex: 0 1 auto;
        min-width: 350px;
        max-width: 500px;
        border-radius: var(--ha-card-border-radius, 8px);
      }

      .card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 16px;
        font-size: 18px;
        font-weight: 600;
        gap: 16px;
      }

      .card-header .name {
        flex: 1;
      }

      .card-header .icon {
        display: flex;
      }

      .card-content {
        padding: 16px;
      }

      .config-button-container {
        display: none;
      }

      .toggle-container {
        text-align: center;
        margin: 0 16px;
      }

      .config-group {
        margin-bottom: 16px;
      }

      .config-group:last-child {
        margin-bottom: 0;
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

      /* NEW: Ideal devices card styles */
      .ideal-summary {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
        gap: 12px;
        margin-bottom: 16px;
        padding: 16px;
        background-color: var(--secondary-background-color);
        border-radius: 8px;
      }

      .summary-item {
        text-align: center;
      }

      .summary-label {
        font-size: 12px;
        color: var(--secondary-text-color);
        margin-bottom: 4px;
      }

      .summary-value {
        font-size: 20px;
        font-weight: 600;
        color: var(--primary-text-color);
      }

      .ideal-device-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 12px;
        margin-bottom: 8px;
        background-color: var(--secondary-background-color);
        border-radius: 4px;
        border-left: 3px solid var(--primary-color);
      }

      .device-info {
        flex: 1;
      }

      .device-name {
        font-weight: 500;
        margin-bottom: 4px;
      }

      .device-meta {
        font-size: 12px;
        color: var(--secondary-text-color);
      }

      .device-power {
        font-weight: 600;
        font-size: 16px;
        color: var(--primary-color);
      }

      /* NEW: Comparison table styles */
      .comparison-summary {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 16px;
        margin-bottom: 16px;
        padding: 16px;
        background-color: var(--secondary-background-color);
        border-radius: 8px;
      }

      .comparison-col {
        text-align: center;
      }

      .comparison-title {
        font-weight: 600;
        margin-bottom: 8px;
        font-size: 16px;
      }

      .comparison-stat {
        font-size: 14px;
        color: var(--secondary-text-color);
      }

      .comparison-table {
        width: 100%;
        border-collapse: collapse;
      }

      .comparison-table thead {
        background-color: var(--secondary-background-color);
      }

      .comparison-table th {
        padding: 12px;
        text-align: left;
        font-weight: 600;
        border-bottom: 2px solid var(--divider-color);
      }

      .comparison-table td {
        padding: 12px;
        border-bottom: 1px solid var(--divider-color);
      }

      .device-name-col {
        font-weight: 500;
      }

      .status-col {
        text-align: center;
      }

      .status-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: 500;
      }

      .status-badge.active {
        background-color: rgba(76, 175, 80, 0.2);
        color: var(--success-color, #4caf50);
      }

      .status-badge.inactive {
        background-color: rgba(158, 158, 158, 0.2);
        color: var(--secondary-text-color);
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

      .loading {
        text-align: center;
        padding: 20px;
        color: var(--secondary-text-color);
      }

      ha-alert {
        display: block;
        margin-bottom: 16px;
      }

      ha-button {
        --md-sys-color-primary: var(--primary-color);
      }

      ha-icon {
        display: flex;
      }

      @media all and (max-width: 820px) {
        :host {
          padding: 8px;
        }
        .header {
            margin: -8px -8px 8px -8px;
            padding: 8px;
            font-size: 20px;
        }
        .card-container {
          gap: 8px;
        }
        ha-card {
          margin: 0;
        }

        .device-details {
          grid-template-columns: 1fr;
        }

        .ideal-summary {
          grid-template-columns: repeat(2, 1fr);
        }

        .comparison-summary {
          grid-template-columns: 1fr;
        }

        .comparison-table {
          font-size: 12px;
        }

        .comparison-table th,
        .comparison-table td {
          padding: 8px 4px;
        }
      }
    `;
  }
}

// Register the custom element
window.customElements.define("pv-optimizer-panel", PvOptimizerPanel);
