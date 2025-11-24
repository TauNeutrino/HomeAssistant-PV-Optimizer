import {
  LitElement,
  html,
  css,
} from "https://unpkg.com/lit-element@2.4.0/lit-element.js?module";

/**
 * PV Optimizer Panel
 * 
 * A modern, Home Assistant native interface for the PV Optimizer integration.
 * Features:
 * - Real-time status monitoring
 * - Global configuration statistics
 * - Comparison view (Real vs Simulation)
 * - Device management list
 */
class PvOptimizerPanel extends LitElement {
  static get properties() {
    return {
      hass: { type: Object },
      narrow: { type: Boolean },
      _config: { type: Object, state: true },
      _loading: { type: Boolean, state: true },
      _error: { type: String, state: true },
      _showComparison: { type: Boolean, state: true },
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
    this._showComparison = false;
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
    if (!this.hass) return;

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
    } catch (error) {
      console.error("PV Optimizer: Failed to get config:", error);
      this._error = `Failed to load configuration: ${error.message}`;
      this._loading = false;
    }
  }

  _openConfiguration() {
    window.history.pushState(null, "", "/config/integrations/integration/pv_optimizer");
    window.dispatchEvent(new Event("location-changed"));
  }

  _toggleComparison() {
    this._showComparison = !this._showComparison;
  }

  _getIdealDevices(sensorName) {
    if (!this.hass) return [];
    const entity = this.hass.states[`sensor.pv_optimizer_${sensorName}`];
    return entity?.attributes?.device_details || [];
  }

  _getPowerBudget(key) {
    if (!this.hass) return 0;
    const sensorName = key === 'real' ? 'power_budget' : 'simulation_power_budget';
    const entity = this.hass.states[`sensor.pv_optimizer_${sensorName}`];
    return parseFloat(entity?.state) || 0;
  }

  _renderHeader() {
    const ready = !this._loading && !this._error && this._config;

    return html`
      <div class="header">
        <div class="header-content">
          <div class="title">
            ${this.narrow ? html`
              <ha-menu-button
                .hass=${this.hass}
                .narrow=${this.narrow}
              ></ha-menu-button>
            ` : ""}
            <div style="display: flex; align-items: center;">
              <ha-icon icon="mdi:solar-power" style="margin-right: 10px;"></ha-icon>
              PV Optimizer
              ${this._config?.version ? html`<span class="version">v${this._config.version}</span>` : ""}
            </div>
          </div>
          <div class="actions">
            <ha-button @click=${this._openConfiguration} outlined style="--mdc-theme-primary: var(--app-header-text-color, white); border-color: rgba(255,255,255,0.5);">
              <ha-icon slot="icon" icon="mdi:cog"></ha-icon>
              Configuration
            </ha-button>
            <div class="status-indicator ${ready ? 'ready' : 'error'}" style="background: rgba(255,255,255,0.1); color: inherit;">
              <ha-icon icon=${ready ? "mdi:check-circle" : "mdi:alert-circle"}></ha-icon>
              ${ready ? "System Ready" : "System Issue"}
            </div>
          </div>
        </div>
      </div>
    `;
  }

  _renderErrorCard() {
    return html`
      <ha-alert alert-type="error" title="Error Loading Configuration">
        ${this._error}
        <ha-button slot="action" @click=${() => this._fetchConfig()}>Retry</ha-button>
      </ha-alert>
    `;
  }

  _renderGlobalConfigCard() {
    if (!this._config?.global_config) return html``;

    const stats = this._config.optimizer_stats;
    if (!stats) return html`<div class="loading">Loading statistics...</div>`;

    const items = [
      { label: "Current Surplus", value: `${(stats.current_surplus).toFixed(0)} W`, icon: "mdi:flash" },
      { label: "Avg Surplus", value: `${stats.averaged_surplus.toFixed(0)} W`, icon: "mdi:chart-bell-curve-cumulative" },
      { label: "Potential Load", value: `${stats.potential_power_on_devices.toFixed(0)} W`, icon: "mdi:lightning-bolt-outline" },
      { label: "Active Load", value: `${stats.measured_power_on_devices.toFixed(0)} W`, icon: "mdi:lightning-bolt" },
      { label: "Last Update", value: this._lastUpdateTimestamp ? this._lastUpdateTimestamp.toLocaleTimeString() : 'N/A', icon: "mdi:clock-outline" },
      { label: "Age", value: this._elapsedSeconds !== null ? `${this._elapsedSeconds}s` : 'N/A', icon: "mdi:timer-outline" },
    ];

    return html`
      <ha-card class="stats-card">
        <h1 class="card-header">
          <ha-icon icon="mdi:chart-dashboard"></ha-icon>
          System Overview
        </h1>
        <div class="stats-grid">
          ${items.map(item => html`
            <div class="stat-item">
              <div class="stat-icon"><ha-icon icon=${item.icon}></ha-icon></div>
              <div class="stat-content">
                <div class="stat-value">${item.value}</div>
                <div class="stat-label">${item.label}</div>
              </div>
            </div>
          `)}
        </div>
      </ha-card>
    `;
  }

  _renderIdealDevicesCard(title, sensorKey, icon, colorVar) {
    const devices = this._getIdealDevices(sensorKey);
    const budget = this._getPowerBudget(sensorKey === 'real_ideal_devices' ? 'real' : 'simulation');
    const totalPower = devices.reduce((sum, d) => sum + (d.power || 0), 0);
    const usagePercent = budget > 0 ? Math.min((totalPower / budget) * 100, 100) : 0;

    return html`
      <ha-card class="ideal-card">
        <h1 class="card-header" style="color: var(${colorVar})">
          <ha-icon icon=${icon}></ha-icon>
          ${title}
        </h1>
        <div class="card-content">
          <div class="budget-bar">
            <div class="budget-info">
              <span>Usage: ${totalPower.toFixed(0)}W</span>
              <span>Budget: ${budget.toFixed(0)}W</span>
            </div>
            <div class="progress-track">
              <div class="progress-fill" style="width: ${usagePercent}%; background-color: var(${colorVar})"></div>
            </div>
          </div>

          ${devices.length === 0
        ? html`<div class="empty-state">No active devices</div>`
        : html`
                <div class="device-list-compact">
                  ${devices.map(device => html`
                    <div class="device-row">
                      <div class="device-main">
                        <span class="device-name">${device.name}</span>
                        <span class="device-meta">Prio ${device.priority}</span>
                      </div>
                      <div class="device-power">${device.power} W</div>
                    </div>
                  `)}
                </div>
              `}
        </div>
      </ha-card>
    `;
  }

  _renderComparisonTable() {
    const realDevices = this._getIdealDevices('real_ideal_devices');
    const simDevices = this._getIdealDevices('simulation_ideal_devices');
    const allNames = new Set([...realDevices.map(d => d.name), ...simDevices.map(d => d.name)]);

    return html`
      <ha-card class="comparison-card">
        <h1 class="card-header">
          <ha-icon icon="mdi:compare"></ha-icon>
          Optimization Comparison
        </h1>
        <div class="table-container">
          <table>
            <thead>
              <tr>
                <th>Device</th>
                <th class="text-right">Power</th>
                <th class="text-center">Real</th>
                <th class="text-center">Sim</th>
              </tr>
            </thead>
            <tbody>
              ${Array.from(allNames).map(name => {
      const real = realDevices.find(d => d.name === name);
      const sim = simDevices.find(d => d.name === name);
      const power = (real || sim)?.power || 0;

      return html`
                  <tr>
                    <td class="fw-500">${name}</td>
                    <td class="text-right">${power} W</td>
                    <td class="text-center">
                      ${real
          ? html`<ha-icon icon="mdi:check-circle" class="success-text"></ha-icon>`
          : html`<ha-icon icon="mdi:circle-outline" class="disabled-text"></ha-icon>`}
                    </td>
                    <td class="text-center">
                      ${sim
          ? html`<ha-icon icon="mdi:check-circle" class="info-text"></ha-icon>`
          : html`<ha-icon icon="mdi:circle-outline" class="disabled-text"></ha-icon>`}
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
    const isOn = state.is_on;
    const isLocked = state.is_locked;

    return html`
      <ha-card class="device-card ${isOn ? 'active' : ''}">
        <div class="device-header">
          <div class="device-title">
            <ha-icon icon=${isOn ? "mdi:power-plug" : "mdi:power-plug-off"} class="device-icon"></ha-icon>
            ${device.name}
          </div>
          ${isLocked ? html`<ha-icon icon="mdi:lock" title="Locked"></ha-icon>` : ''}
        </div>
        
        <div class="device-body">
          <div class="chip-container">
            <span class="chip type">${device.type}</span>
            <span class="chip priority">Prio ${device.priority}</span>
          </div>
          
          <div class="device-stats">
            <div class="stat">
              <span class="label">Rated</span>
              <span class="value">${device.power} W</span>
            </div>
            ${state.measured_power_avg ? html`
              <div class="stat">
                <span class="label">Measured</span>
                <span class="value">${state.measured_power_avg.toFixed(0)} W</span>
              </div>
            ` : ''}
          </div>
        </div>

        <div class="device-footer">
          <div class="status-badges">
            ${device.optimization_enabled ? html`<span class="badge success">Auto</span>` : html`<span class="badge warning">Manual</span>`}
            ${device.simulation_active ? html`<span class="badge info">Sim</span>` : ''}
          </div>
        </div>
      </ha-card>
    `;
  }

  render() {
    if (this._loading && !this._config) {
      return html`<div class="loading-screen"><ha-circular-progress active></ha-circular-progress></div>`;
    }

    return html`
      ${this._renderHeader()}
      
      ${this._error ? this._renderErrorCard() : ""}

      <div class="dashboard-grid">
        <div class="main-column">
          ${this._renderGlobalConfigCard()}
          
          <div class="view-toggle">
            <ha-button @click=${this._toggleComparison}>
              <ha-icon slot="icon" icon=${this._showComparison ? "mdi:view-dashboard" : "mdi:table-large"}></ha-icon>
              ${this._showComparison ? "View Cards" : "View Comparison"}
            </ha-button>
          </div>

          ${this._showComparison
        ? this._renderComparisonTable()
        : html`
                <div class="dual-grid">
                  ${this._renderIdealDevicesCard("Real Optimization", "real_ideal_devices", "mdi:lightning-bolt", "--success-color")}
                  ${this._renderIdealDevicesCard("Simulation", "simulation_ideal_devices", "mdi:flask", "--info-color")}
                </div>
              `}
        </div>

        <div class="devices-column">
          <h2 class="section-title">Managed Devices</h2>
          <div class="devices-grid">
            ${this._config?.devices?.map(d => this._renderDeviceCard(d))}
          </div>
        </div>
      </div>
    `;
  }

  static get styles() {
    return css`
      :host {
        display: block;
        padding: 16px;
        --ha-card-border-radius: 12px;
        --success-color: var(--success-color, #4caf50);
        --info-color: var(--info-color, #2196f3);
        --warning-color: var(--warning-color, #ff9800);
        --error-color: var(--error-color, #f44336);
      }

      /* Layout */
      .dashboard-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
        gap: 24px;
        margin-top: 24px;
        align-items: start;
      }

      .main-column {
        display: flex;
        flex-direction: column;
        gap: 24px;
      }

      .dual-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 16px;
      }

      .devices-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
        gap: 16px;
      }

      /* Header */
      .header {
        background-color: var(--app-header-background-color, var(--primary-color));
        color: var(--app-header-text-color, white);
        padding: 10px 16px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.14);
      }
      .header-content {
        display: flex;
        justify-content: space-between;
        align-items: center;
        max-width: 1200px;
        margin: 0 auto;
        height: 44px; /* Standard HA header height */
      }
      .title {
        font-size: 20px;
        font-weight: 400;
        display: flex;
        align-items: center;
        gap: 12px;
      }
      .version {
        font-size: 12px;
        opacity: 0.8;
        margin-left: 8px;
        font-weight: normal;
        background: rgba(255, 255, 255, 0.2);
        padding: 2px 6px;
        border-radius: 4px;
      }
      .actions {
        display: flex;
        gap: 12px;
        align-items: center;
      }
      .status-indicator {
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 14px;
        font-weight: 500;
        padding: 6px 12px;
        border-radius: 16px;
        background: var(--secondary-background-color);
      }
      .status-indicator.ready { color: var(--success-color); }
      .status-indicator.error { color: var(--error-color); }

      /* Cards */
      ha-card {
        display: flex;
        flex-direction: column;
        background: var(--ha-card-background, var(--card-background-color, white));
        border: 1px solid var(--divider-color, #e0e0e0);
        transition: all 0.3s ease;
      }
      
      /* Only stretch cards in grids where they share a row */
      .dual-grid ha-card,
      .devices-grid ha-card {
        height: 100%;
      }

      .card-header {
        padding: 16px;
        margin: 0;
        font-size: 18px;
        font-weight: 500;
        display: flex;
        align-items: center;
        gap: 10px;
        color: var(--primary-text-color);
      }
      .card-content {
        padding: 16px;
        flex: 1;
      }

      /* Stats Grid */
      .stats-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
        gap: 16px;
        padding: 16px;
      }
      .stat-item {
        display: flex;
        align-items: center;
        gap: 12px;
      }
      .stat-icon {
        background: var(--secondary-background-color);
        padding: 8px;
        border-radius: 50%;
        color: var(--primary-color);
      }
      .stat-value {
        font-size: 18px;
        font-weight: 600;
        color: var(--primary-text-color);
      }
      .stat-label {
        font-size: 12px;
        color: var(--secondary-text-color);
      }

      /* Comparison Table */
      .table-container {
        overflow-x: auto;
        padding: 0 16px 16px;
      }
      table {
        width: 100%;
        border-collapse: collapse;
      }
      th {
        text-align: left;
        padding: 12px 8px;
        border-bottom: 2px solid var(--divider-color);
        color: var(--secondary-text-color);
        font-weight: 500;
        font-size: 13px;
      }
      td {
        padding: 12px 8px;
        border-bottom: 1px solid var(--divider-color);
        color: var(--primary-text-color);
        font-size: 14px;
      }
      .text-right { text-align: right; }
      .text-center { text-align: center; }
      .success-text { color: var(--success-color); }
      .info-text { color: var(--info-color); }
      .disabled-text { color: var(--disabled-text-color); }

      /* Device Cards */
      .device-card {
        padding: 16px;
        border-left: 1px solid var(--divider-color);
      }
      .device-card.active {
        border-left-color: var(--primary-color);
      }
      .device-header {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        margin-bottom: 12px;
      }
      .device-title {
        font-weight: 500;
        display: flex;
        align-items: center;
        gap: 8px;
      }
      .device-body {
        margin-bottom: 12px;
      }
      .chip-container {
        display: flex;
        gap: 8px;
        margin-bottom: 8px;
      }
      .chip {
        font-size: 11px;
        padding: 2px 8px;
        border-radius: 10px;
        background: var(--secondary-background-color);
        color: var(--secondary-text-color);
      }
      .device-stats {
        display: flex;
        justify-content: space-between;
        font-size: 13px;
      }
      .status-badges {
        display: flex;
        gap: 8px;
      }
      .badge {
        font-size: 11px;
        padding: 2px 6px;
        border-radius: 4px;
        font-weight: 500;
      }
      .badge.success { background: rgba(76, 175, 80, 0.15); color: var(--success-color); }
      .badge.warning { background: rgba(255, 152, 0, 0.15); color: var(--warning-color); }
      .badge.info { background: rgba(33, 150, 243, 0.15); color: var(--info-color); }

      /* Progress Bar */
      .budget-bar {
        margin-bottom: 16px;
      }
      .budget-info {
        display: flex;
        justify-content: space-between;
        font-size: 12px;
        margin-bottom: 4px;
        color: var(--secondary-text-color);
      }
      .progress-track {
        height: 8px;
        background: var(--secondary-background-color);
        border-radius: 4px;
        overflow: hidden;
      }
      .progress-fill {
        height: 100%;
        transition: width 0.5s ease;
      }

      /* Utilities */
      .view-toggle {
        margin: 16px 0;
        text-align: center;
      }
      .section-title {
        font-size: 20px;
        font-weight: 400;
        margin-bottom: 16px;
        color: var(--primary-text-color);
      }
      .loading-screen {
        display: flex;
        justify-content: center;
        padding: 40px;
      }
      
      /* Responsive */
      @media (max-width: 600px) {
        .dual-grid { grid-template-columns: 1fr; }
        .header-content { flex-direction: column; align-items: flex-start; }
        .actions { width: 100%; justify-content: space-between; }
      }
    `;
  }
}

window.customElements.define("pv-optimizer-panel", PvOptimizerPanel);
