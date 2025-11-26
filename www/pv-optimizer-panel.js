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

  async _handleResetDevice(device) {
    if (!confirm(`Reset target state for ${device.name}? This will clear the manual lock.`)) return;

    try {
      await this.hass.callWS({
        type: "pv_optimizer/reset_device",
        device_name: device.name
      });
      // Refresh config to update UI
      await this._fetchConfig();
    } catch (err) {
      this._error = `Failed to reset device: ${err.message}`;
    }
  }

  async _handleSimulationOffsetChange(e) {
    const offset = parseFloat(e.target.value);
    if (isNaN(offset)) return;

    try {
      await this.hass.callWS({
        type: "pv_optimizer/set_simulation_offset",
        offset: offset
      });
      // Refresh config to update UI
      await this._fetchConfig();
    } catch (err) {
      this._error = `Failed to set offset: ${err.message}`;
    }
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
    if (changedProperties.has("hass")) {
      // Initial load
      if (this.hass && !this._config) {
        this._fetchConfig();
      }

      // Reactive update: Check if power budget sensor updated
      // This signals that an optimization cycle just finished
      const oldHass = changedProperties.get("hass");
      if (oldHass && this.hass) {
        const entityId = "sensor.pv_optimizer_power_budget";
        const oldState = oldHass.states[entityId];
        const newState = this.hass.states[entityId];

        if (oldState !== newState && newState) {
          // Sensor changed (state or attributes/timestamp)
          // Trigger refresh to get full config/stats
          // Debounce slightly to allow other sensors to settle if needed
          if (this._debounceFetch) clearTimeout(this._debounceFetch);
          this._debounceFetch = setTimeout(() => {
            console.log("PV Optimizer: Power budget updated, refreshing config...");
            this._fetchConfig();
          }, 500);
        }
      }
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

      console.log("PV Optimizer Config Response:", response);
      console.log("Devices array:", response?.devices);
      console.log("Number of devices:", response?.devices?.length);

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

  _findEntityByTranslationKey(translationKey) {
    if (!this.hass) return null;
    // Search for entity with matching unique_id pattern
    for (const entityId in this.hass.states) {
      if (entityId.startsWith('sensor.pv_optimizer_')) {
        const entity = this.hass.states[entityId];
        // Check if the entity's unique_id ends with our translation key
        const state = entity;
        // Match by checking if entity ID contains key parts
        if (translationKey === 'simulation_ideal_devices' &&
          (entityId.includes('simulation') && (entityId.includes('ideal') || entityId.includes('ideale')))) {
          return entity;
        }
        if (translationKey === 'real_ideal_devices' &&
          (entityId.includes('real') || entityId.includes('reale')) &&
          (entityId.includes('ideal') || entityId.includes('ideale')) &&
          !entityId.includes('simulation')) {
          return entity;
        }
        if (translationKey === 'simulation_power_budget' &&
          entityId.includes('simulation') &&
          (entityId.includes('budget') || entityId.includes('leistung'))) {
          return entity;
        }
        if (translationKey === 'power_budget' &&
          (entityId.includes('budget') || entityId.includes('leistung')) &&
          !entityId.includes('simulation')) {
          return entity;
        }
      }
    }
    return null;
  }

  _getIdealDevices(sensorName) {
    if (!this.hass) return [];
    const entity = this._findEntityByTranslationKey(sensorName);
    return entity?.attributes?.device_details || [];
  }

  _getPowerBudget(key) {
    if (!this.hass) return 0;
    const translationKey = key === 'real' ? 'power_budget' : 'simulation_power_budget';
    const entity = this._findEntityByTranslationKey(translationKey);
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

  _getDeviceColor(index) {
    const colors = [
      '#4CAF50', // Green
      '#2196F3', // Blue
      '#FFC107', // Amber
      '#9C27B0', // Purple
      '#F44336', // Red
      '#00BCD4', // Cyan
      '#FF9800', // Orange
      '#795548', // Brown
      '#607D8B', // Blue Grey
      '#E91E63'  // Pink
    ];
    return colors[index % colors.length];
  }

  _renderIdealDevicesCard(title, sensorKey, icon, colorVar) {
    const devices = this._getIdealDevices(sensorKey);
    const budget = this._getPowerBudget(sensorKey === 'real_ideal_devices' ? 'real' : 'simulation');
    const totalPower = devices.reduce((sum, d) => sum + (d.power || 0), 0);
    const usagePercent = budget > 0 ? Math.min((totalPower / budget) * 100, 100) : 0;

    return html`
      <ha-card class="ideal-devices-card" style="border-top: 4px solid var(${colorVar})">
        <h1 class="card-header">
          <ha-icon icon=${icon}></ha-icon>
          ${title}
        </h1>
        <div class="card-content">
          ${sensorKey === 'simulation_ideal_devices' ? html`
            <div class="simulation-offset-container" style="margin-bottom: 16px; padding: 0 8px;">
              <ha-textfield
                label="Additional Surplus (W)"
                type="number"
                .value=${this._config.optimizer_stats?.simulation_surplus_offset || 0}
                @change=${this._handleSimulationOffsetChange}
                icon="mdi:plus-minus"
                style="width: 100%;"
              >
                <ha-icon slot="leadingIcon" icon="mdi:plus-minus"></ha-icon>
              </ha-textfield>
              <div class="caption" style="font-size: 12px; color: var(--secondary-text-color); margin-top: 4px;">
                Add virtual surplus to test scenarios (e.g., +1000W)
              </div>
            </div>
          ` : ''}

          <div class="budget-bar">
            <div class="budget-info">
              <span>Power Budget</span>
              <span style="${budget < 0 ? 'color: var(--error-color); font-weight: 600;' : ''}">${budget.toFixed(0)} W</span>
            </div>
            <div class="progress-track" style="display: flex; overflow: hidden;">
              ${budget > 0 ? html`
                ${devices.map((device, index) => {
      const width = Math.min((device.power / budget) * 100, 100);
      const color = this._getDeviceColor(index);
      return html`<div class="progress-fill" style="width: ${width}%; background-color: ${color}; border-right: 1px solid rgba(255,255,255,0.2);" title="${device.name}: ${device.power}W"></div>`;
    })}
                ${(() => {
          const usedPower = devices.reduce((sum, d) => sum + (d.power || 0), 0);
          const remaining = Math.max(0, budget - usedPower);
          if (remaining > 0) {
            const width = Math.min((remaining / budget) * 100, 100);
            return html`<div class="progress-fill" style="width: ${width}%; background-color: var(${colorVar}); opacity: 0.2;" title="Unused: ${remaining.toFixed(0)}W"></div>`;
          }
          return '';
        })()}
              ` : ''}
            </div>
          </div>

          ${devices.length === 0
        ? html`<div class="empty-state">No active devices</div>`
        : html`
                <div class="device-list-compact">
                  ${devices.map((device, index) => html`
                    <div class="device-row">
                      <div class="device-main">
                        <div style="width: 8px; height: 8px; border-radius: 50%; background-color: ${this._getDeviceColor(index)}; margin-right: 8px; display: inline-block;"></div>
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
          <div class="stat-item">
            <span class="label">Current Surplus</span>
            <span class="value ${surplus < 0 ? 'negative' : ''}">${surplus.toFixed(0)} W</span>
          </div>
          <div class="stat-item">
            <span class="label">Avg Surplus (10m)</span>
            <span class="value ${avgSurplus < 0 ? 'negative' : ''}">${avgSurplus.toFixed(0)} W</span>
          </div>
          <div class="stat-item">
            <span class="label">Optimization Cycle</span>
            <span class="value">${global.optimization_cycle_time || 60}s</span>
          </div>
        </div >
      </div >
      `;
  }

  _renderManagedDevices() {
    if (!this._config) return html``;

    // Sort devices by priority (descending)
    const devices = [...(this._config.devices || [])].sort((a, b) => {
      return (b.config?.priority || 0) - (a.config?.priority || 0);
    });

    return html`
      < div class="devices-section" >
        <div class="section-header">Managed Devices</div>
        ${ devices.map(device => this._renderDeviceCard(device)) }
      </div >
      `;
  }

  _renderDeviceCard(device) {
    const state = device.state || {};
    const config = device.config || {};
    const isLocked = state.is_locked;
    const isLockedManual = state.is_locked_manual;
    const isLockedTiming = state.is_locked_timing;
    
    // Check availability (using the diagnostic sensor logic or state presence)
    const isUnavailable = state.is_on === undefined || state.is_on === null;

    return html`
      < div class="device-card ${isUnavailable ? 'unavailable' : ''}" >
        <div class="device-header">
          <span class="device-name">${config.name}</span>
          <div class="status-badges">
            <span
              class="badge ${state.is_on ? 'on' : 'off'}"
            >${state.is_on ? 'ON' : 'OFF'}</span>

            <span
              class="badge ${config.optimization_enabled ? 'auto' : 'manual'} clickable"
              @click="${() => this._toggleOptimization(device)}"
            title="Click to toggle Optimization"
            >${config.optimization_enabled ? 'Auto' : 'Manual'}</span>

          <span
            class="badge ${config.simulation_active ? 'sim' : 'sim-disabled'} clickable"
              @click="${() => this._toggleSimulation(device)}"
          title="Click to toggle Simulation"
            >Sim</span>
          </div >
        </div >

      <div class="device-details">
        <div class="detail-row">
          <span>Power: ${state.current_power || 0} W</span>
          <span>Priority: ${config.priority || 0}</span>
        </div>

        <div class="lock-icons">
          ${isLockedTiming ? html`<ha-icon class="lock-icon" icon="mdi:timer-lock" title="Timing Lock Active"></ha-icon>` : ''}
          ${isLockedManual ? html`
              <ha-icon class="lock-icon" icon="mdi:account-lock" title="Manual Lock Active"></ha-icon>
              <ha-icon 
                class="reset-icon" 
                icon="mdi:restore" 
                title="Reset Target State"
                @click="${() => this._handleResetDevice(device)}"
              ></ha-icon>
            ` : ''}
        </div>
      </div>
      </div >
      `;
  }
  
  async _toggleOptimization(device) {
    if (!device.config.optimization_enabled_entity_id) return;
    
    const service = device.config.optimization_enabled ? 'turn_off' : 'turn_on';
    await this.hass.callService('switch', service, {
      entity_id: device.config.optimization_enabled_entity_id
    });
    // Optimistic update or wait for refresh
    setTimeout(() => this._fetchConfig(), 500);
  }
  
  async _toggleSimulation(device) {
    if (!device.config.simulation_active_entity_id) return;
    
    const service = device.config.simulation_active ? 'turn_off' : 'turn_on';
    await this.hass.callService('switch', service, {
      entity_id: device.config.simulation_active_entity_id
    });
    setTimeout(() => this._fetchConfig(), 500);
  }

  _renderComparison() {
    if (!this._config || !this._showComparison) return html``;

    const real = this._config.real_optimization || {};
    const sim = this._config.simulation || {};
    
    // Sort lists by priority
    const sortDevices = (list) => {
      if (!list) return [];
      // We need to look up priority from the main devices list
      return list.sort((a, b) => {
        const devA = this._config.devices.find(d => d.config.name === a);
        const devB = this._config.devices.find(d => d.config.name === b);
        return ((devB?.config?.priority || 0) - (devA?.config?.priority || 0));
      });
    };

    const realOn = sortDevices(real.ideal_on_list || []);
    const simOn = sortDevices(sim.ideal_on_list || []);

    return html`
      < div class="comparison-view" >
        <div class="comparison-column">
          <div class="column-header">Real Optimization</div>
          <div class="device-list">
            ${realOn.length ? realOn.map(name => html`<div class="list-item">${name}</div>`) : html`<div class="empty-list">No devices</div>`}
          </div>
          <div class="column-footer">Budget: ${real.budget?.toFixed(0)} W</div>
        </div>
        
        <div class="comparison-column simulation">
          <div class="column-header">
            Simulation
            ${sim.surplus_offset ? html`<span class="sim-surplus-header">+${sim.surplus_offset}W</span>` : ''}
          </div>
          <div class="device-list">
            ${simOn.length ? simOn.map(name => html`<div class="list-item">${name}</div>`) : html`<div class="empty-list">No devices</div>`}
          </div>
          <div class="column-footer">
            Budget: ${sim.budget?.toFixed(0)} W
            <div class="offset-control">
              <label>Surplus Offset:</label>
              <input 
                type="number" 
                .value="${this._config.global.simulation_offset || 0}"
                @change="${this._handleSimulationOffsetChange}"
                step="100"
              >
            </div>
          </div>
        </div>
      </div >
      `;
  }

  render() {
    if (this._loading && !this._config) {
      return html`< div class="loading-screen" > <ha-circular-progress active></ha-circular-progress></div > `;
    }

    return html`
      ${ this._renderHeader() }

    <div class="content">
      ${this._error ? this._renderErrorCard() : ""}

      <div class="dashboard-grid">
        <div class="main-column">
          ${this._renderPowerBudget()}
          ${this._renderSystemOverview()}

          <div class="view-toggle">
            <ha-button @click=${this._toggleComparison}>
            <ha-icon slot="icon" icon=${this._showComparison ? "mdi:view-dashboard" : "mdi:table-large"}></ha-icon>
            ${this._showComparison ? "View Cards" : "View Comparison"}
          </ha-button>
        </div>

        ${this._renderComparison()}
      </div>

      <div class="devices-column">
        ${this._renderManagedDevices()}
      </div>
    </div>
      </div >
      `;
  }

  static get styles() {
    return css`
      :host {
      display: block;
      padding: 16px;
      background - color: var(--primary - background - color);
      color: var(--primary - text - color);
      font - family: var(--paper - font - body1_ - _font - family);
    }
      
      .power - budget - card, .overview - card, .devices - section, .comparison - view {
      background: var(--card - background - color);
      border - radius: 12px;
      padding: 16px;
      margin - bottom: 16px;
      box - shadow: var(--ha - card - box - shadow, 0 2px 2px 0 rgba(0, 0, 0, 0.14), 0 1px 5px 0 rgba(0, 0, 0, 0.12), 0 3px 1px - 2px rgba(0, 0, 0, 0.2));
    }

      .card - header {
      font - size: 1.2em;
      font - weight: 500;
      margin - bottom: 12px;
      display: flex;
      justify - content: space - between;
      align - items: center;
    }
      
      .section - header {
      font - size: 1.1em;
      font - weight: 500;
      margin - bottom: 12px;
      color: var(--secondary - text - color);
    }

      .progress - bar {
      background - color: var(--secondary - background - color);
      height: 24px;
      border - radius: 12px;
      overflow: hidden;
    }

      .progress - fill {
      background - color: var(--primary - color);
      height: 100 %;
      transition: width 0.5s ease -in -out;
    }
      
      .progress - fill.warning {
      background - color: var(--error - color);
    }

      .stats - grid {
      display: grid;
      grid - template - columns: repeat(3, 1fr);
      gap: 16px;
    }

      .stat - item {
      display: flex;
      .disabled - text { color: var(--disabled - text - color); }

      /* Device Cards */
      .device - card {
        padding: 16px;
        border - left: 1px solid var(--divider - color);
      }
      .device - card.active {
        border - left - color: var(--primary - color);
      }
      .device - header {
        display: flex;
        justify - content: space - between;
        align - items: flex - start;
        margin - bottom: 12px;
      }
      .lock - icons {
        display: flex;
        gap: 4px;
      }
      .lock - icon {
        color: var(--warning - color);
        --mdc - icon - size: 20px;
      }
      .reset - icon {
        color: var(--primary - color);
        --mdc - icon - size: 20px;
        margin - left: 8px;
        cursor: pointer;
        opacity: 0.8;
        transition: opacity 0.2s;
      }
      .reset - icon:hover {
        opacity: 1;
      }
      .device - title {
        font - weight: 500;
        display: flex;
        align - items: center;
        gap: 8px;
      }
      .device - body {
        margin - bottom: 12px;
      }
      .chip - container {
        display: flex;
        gap: 8px;
        margin - bottom: 8px;
      }
      .chip {
        font - size: 11px;
        padding: 2px 8px;
        border - radius: 10px;
        background: var(--secondary - background - color);
        color: var(--secondary - text - color);
      }
      .device - stats {
        display: flex;
        justify - content: space - between;
        font - size: 13px;
      }
      .status - badges {
        display: flex;
        gap: 8px;
      }
      .badge {
        font - size: 11px;
        padding: 2px 6px;
        border - radius: 4px;
        font - weight: 500;
      }
      .badge.success { background: rgba(76, 175, 80, 0.15); color: var(--success - color); }
      .badge.warning { background: rgba(255, 152, 0, 0.15); color: var(--warning - color); }
      .badge.info { background: rgba(33, 150, 243, 0.15); color: var(--info - color); }

      /* Progress Bar */
      .budget - bar {
        margin - bottom: 16px;
      }
      .budget - info {
        display: flex;
        justify - content: space - between;
        font - size: 12px;
        margin - bottom: 4px;
        color: var(--secondary - text - color);
      }
      .progress - track {
        height: 8px;
        background: var(--secondary - background - color);
        border - radius: 4px;
        overflow: hidden;
      }
      .progress - fill {
        height: 100 %;
        transition: width 0.5s ease;
      }

      /* Utilities */
      .view - toggle {
        margin: 16px 0;
        text - align: center;
      }
      .section - title {
        font - size: 20px;
        font - weight: 400;
        margin - bottom: 16px;
        color: var(--primary - text - color);
      }
      .loading - screen {
        display: flex;
        justify - content: center;
        padding: 40px;
      }

      /* Responsive */
      @media(max - width: 600px) {
        .dual - grid { grid - template - columns: 1fr; }
        .header - content { flex - direction: column; align - items: flex - start; }
        .actions { width: 100 %; justify - content: space - between; }
      }
      `;
  }
}

window.customElements.define("pv-optimizer-panel", PvOptimizerPanel);
