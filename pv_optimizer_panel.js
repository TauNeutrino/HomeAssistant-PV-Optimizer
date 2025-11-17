import {
  LitElement,
  html,
  css,
} from "https://unpkg.com/lit-element@2.4.0/lit-element.js?module";

class PvOptimizerPanel extends LitElement {
  static get properties() {
    return {
      hass: { type: Object },
      narrow: { type: Boolean },
      route: { type: Object },
      panel: { type: Object },
      _activeTab: { type: String },
      _isBusy: { type: Boolean },
    };
  }

  constructor() {
    super();
    this._activeTab = 'global';
    this._isBusy = false;
  }

  // --- HTML Template ---
  render() {
    return html`
      <hass-panel-router
        .hass=${this.hass}
        .narrow=${this.narrow}
        .route=${this.route}
        .panel=${this.panel}
      >
        <ha-card header="PV Optimizer Control Panel">
          <div class="card-content">
            <div class="tab-container">
              <div class="tab-header">
                <button 
                  class="tab-button ${this._activeTab === 'global' ? 'active' : ''}"
                  @click=${() => this._setActiveTab('global')}
                >
                  <ha-icon class="tab-icon" .icon="mdi:home-analytics"></ha-icon>
                  Global
                </button>
                <button 
                  class="tab-button ${this._activeTab === 'devices' ? 'active' : ''}"
                  @click=${() => this._setActiveTab('devices')}
                >
                  <ha-icon class="tab-icon" .icon="mdi:devices"></ha-icon>
                  Devices
                </button>
                <button 
                  class="tab-button ${this._activeTab === 'control' ? 'active' : ''}"
                  @click=${() => this._setActiveTab('control')}
                >
                  <ha-icon class="tab-icon" .icon="mdi:cog"></ha-icon>
                  Control
                </button>
              </div>

              <div class="tab-content">
                ${this._activeTab === 'global' ? html`
                  <div class="section">
                    <div class="info-text">
                      <p>Monitor your PV optimization system performance and global settings.</p>
                    </div>

                    <div class="stats-grid">
                      <div class="stat-card">
                        <div class="stat-header">
                          <span class="stat-label">Power Budget</span>
                          <ha-icon .icon="mdi:lightning-bolt" class="stat-icon"></ha-icon>
                        </div>
                        <div class="stat-value">
                          ${this._getSensorState("sensor.pv_optimizer_power_budget", "W")}
                        </div>
                        <div class="stat-description">Current power allocation budget for optimization</div>
                      </div>

                      <div class="stat-card">
                        <div class="stat-header">
                          <span class="stat-label">Averaged Surplus</span>
                          <ha-icon .icon="mdi:chart-line" class="stat-icon"></ha-icon>
                        </div>
                        <div class="stat-value">
                          ${this._getSensorState("sensor.pv_optimizer_averaged_surplus", "W")}
                        </div>
                        <div class="stat-description">Average surplus power available for optimization</div>
                      </div>

                      <div class="stat-card">
                        <div class="stat-header">
                          <span class="stat-label">Ideal On List</span>
                          <ha-icon .icon="mdi:view-list" class="stat-icon"></ha-icon>
                        </div>
                        <div class="stat-value">
                          ${this._getSensorState("sensor.pv_optimizer_ideal_on_list", "devices")}
                        </div>
                        <div class="stat-description">Number of devices currently in ideal activation list</div>
                      </div>

                      <div class="stat-card">
                        <div class="stat-header">
                          <span class="stat-label">Total Active Devices</span>
                          <ha-icon .icon="mdi:power-plug" class="stat-icon"></ha-icon>
                        </div>
                        <div class="stat-value">
                          ${this._getActiveDeviceCount()}
                        </div>
                        <div class="stat-description">Currently optimized and active devices</div>
                      </div>

                      <div class="stat-card">
                        <div class="stat-header">
                          <span class="stat-label">System Status</span>
                          <ha-icon 
                            .icon=${this._getSystemStatus() ? "mdi:check-circle" : "mdi:alert-circle"} 
                            class="stat-icon"
                            style=${`color: ${this._getSystemStatus() ? 'var(--success-color, #4CAF50)' : 'var(--warning-color, #FF9800)'};`}
                          ></ha-icon>
                        </div>
                        <div class="stat-value">
                          ${this._getSystemStatus() ? 'Healthy' : 'Warning'}
                        </div>
                        <div class="stat-description">Overall PV optimization system health</div>
                      </div>
                    </div>
                  </div>
                ` : ""}

                ${this._activeTab === 'devices' ? html`
                  <div class="section">
                    <div class="info-text">
                      <p>Configure and monitor individual devices for PV optimization.</p>
                    </div>

                    <div class="device-list">
                      ${this._renderDeviceCards()}
                    </div>
                  </div>
                ` : ""}

                ${this._activeTab === 'control' ? html`
                  <div class="section">
                    <div class="info-text">
                      <p>Manual control actions for PV optimization system.</p>
                    </div>

                    <div class="control-actions">
                      <div class="action-card">
                        <div class="action-header">
                          <span class="action-label">Manual Refresh</span>
                          <ha-icon .icon="mdi:refresh" class="action-icon"></ha-icon>
                        </div>
                        <div class="action-description">Refresh all sensor data and recalculate optimization</div>
                        <ha-button
                          @click=${this._refreshData}
                          .disabled=${this._isBusy}
                        >
                          <ha-icon slot="start" .icon="mdi:refresh"></ha-icon>
                          Refresh Data
                        </ha-button>
                      </div>

                      <div class="action-card">
                        <div class="action-header">
                          <span class="action-label">Run Optimization</span>
                          <ha-icon .icon="mdi:play" class="action-icon"></ha-icon>
                        </div>
                        <div class="action-description">Trigger optimization calculation immediately</div>
                        <ha-button
                          @click=${this._runOptimization}
                          .disabled=${this._isBusy}
                        >
                          <ha-icon slot="start" .icon="mdi:play"></ha-icon>
                          Run Now
                        </ha-button>
                      </div>

                      <div class="action-card">
                        <div class="action-header">
                          <span class="action-label">System Reset</span>
                          <ha-icon .icon="mdi:restart" class="action-icon"></ha-icon>
                        </div>
                        <div class="action-description">Reset all devices to default states</div>
                        <ha-button
                          @click=${this._resetSystem}
                          .disabled=${this._isBusy}
                        >
                          <ha-icon slot="start" .icon="mdi:restart"></ha-icon>
                          Reset System
                        </ha-button>
                      </div>
                    </div>
                  </div>

                  <div class="section">
                    <h3 class="section-title">Statistics</h3>
                    <div class="stats-grid">
                      <div class="stat-card">
                        <div class="stat-header">
                          <span class="stat-label">Devices Optimized Today</span>
                          <ha-icon .icon="mdi:calendar-today" class="stat-icon"></ha-icon>
                        </div>
                        <div class="stat-value">
                          ${this._getTodaysOptimizations()}
                        </div>
                      </div>

                      <div class="stat-card">
                        <div class="stat-header">
                          <span class="stat-label">Energy Saved Today</span>
                          <ha-icon .icon="mdi:battery" class="stat-icon"></ha-icon>
                        </div>
                        <div class="stat-value">
                          ${this._getEnergySavedToday()}
                        </div>
                      </div>

                      <div class="stat-card">
                        <div class="stat-header">
                          <span class="stat-label">Optimization Efficiency</span>
                          <ha-icon .icon="mdi:trending-up" class="stat-icon"></ha-icon>
                        </div>
                        <div class="stat-value">
                          ${this._getOptimizationEfficiency()}
                        </div>
                      </div>
                    </div>
                  </div>
                ` : ""}
              </div>
            </div>
          </div>
        </ha-card>
      </hass-panel-router>
    `;
  }

  // --- Helper Functions ---
  _setActiveTab(tab) {
    if (tab !== this._activeTab) {
      this._activeTab = tab;
      this.requestUpdate();
    }
  }

  _getSensorState(entityId, unit = "") {
    if (this.hass && this.hass.states && this.hass.states[entityId]) {
      const state = this.hass.states[entityId].state;
      return `${state} ${unit}`;
    }
    return "N/A";
  }

  _getSwitchState(entityId) {
    if (this.hass && this.hass.states && this.hass.states[entityId]) {
      return this.hass.states[entityId].state === "on";
    }
    return false;
  }

  _getActiveDeviceCount() {
    if (!this.hass) return "0";
    const deviceSwitches = Object.keys(this.hass.states || {})
      .filter(entityId => entityId.startsWith("switch.pv_optimizer_pvo_") && entityId.endsWith("_switch"));
    
    let activeCount = 0;
    deviceSwitches.forEach(entityId => {
      if (this._getSwitchState(entityId)) {
        activeCount++;
      }
    });
    
    return `${activeCount}/${deviceSwitches.length}`;
  }

  _getSystemStatus() {
    // Check if all critical sensors are available
    const criticalSensors = [
      "sensor.pv_optimizer_power_budget",
      "sensor.pv_optimizer_averaged_surplus"
    ];
    
    return criticalSensors.every(sensorId => 
      this.hass?.states?.[sensorId] && this.hass.states[sensorId].state !== "unavailable"
    );
  }

  _renderDeviceCards() {
    // Get all PV Optimizer related sensors and switches
    const entities = Object.keys(this.hass?.states || {})
      .filter(entityId => 
        entityId.startsWith("sensor.pv_optimizer_pvo_") || 
        entityId.startsWith("switch.pv_optimizer_pvo_") ||
        entityId.startsWith("number.pv_optimizer_pvo_")
      );

    if (entities.length === 0) {
      return html`
        <div class="no-devices">
          <ha-icon .icon="mdi:lightbulb-outline" style="font-size: 48px; color: var(--secondary-text-color, #666);"></ha-icon>
          <p>No devices configured yet.</p>
          <p>Add devices through the integration setup to see them here.</p>
        </div>
      `;
    }

    // Group entities by device name
    const deviceGroups = {};
    entities.forEach(entityId => {
      const parts = entityId.split(".");
      const domain = parts[0];
      const nameParts = parts[1].split("_");
      
      // Extract device name (assuming format: pvo_{device_name}_{entity_type})
      if (nameParts.length >= 4 && nameParts[0] === "pvo") {
        const deviceName = nameParts.slice(1, -1).join("_");
        if (!deviceGroups[deviceName]) {
          deviceGroups[deviceName] = {};
        }
        deviceGroups[deviceName][nameParts[nameParts.length - 1]] = entityId;
      }
    });

    // Render device cards
    return html`
      ${Object.entries(deviceGroups).map(([deviceName, entities]) => 
        this._renderDeviceCard(deviceName, entities)
      )}
    `;
  }

  _renderDeviceCard(deviceName, entities) {
    const displayName = deviceName.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase());
    const switchEntity = entities.switch;
    const powerEntity = entities.power;
    const isActive = this._getSwitchState(switchEntity);
    
    return html`
      <div class="device-card">
        <div class="device-header">
          <h4 class="device-name">${displayName}</h4>
          <ha-icon
            .icon=${isActive ? "mdi:power-plug" : "mdi:power-plug-off"}
            style=${`color: ${isActive ? 'var(--success-color, #4CAF50)' : 'var(--secondary-text-color, #666)'};`}
          ></ha-icon>
        </div>
        
        <div class="device-controls">
          ${switchEntity ? html`
            <div class="device-control">
              <span class="control-label">Control</span>
              <ha-switch
                .checked=${isActive}
                @change=${(e) => this._toggleEntity(switchEntity, e.target.checked)}
              ></ha-switch>
            </div>
          ` : ""}

          ${powerEntity ? html`
            <div class="device-control">
              <span class="control-label">Current Power</span>
              <span class="control-value">${this._getSensorState(powerEntity, "W")}</span>
            </div>
          ` : ""}

          ${this._renderAdditionalDeviceInfo(entities)}
        </div>
      </div>
    `;
  }

  _renderAdditionalDeviceInfo(entities) {
    const infoItems = [];
    
    if (entities.power_avg) {
      infoItems.push({
        name: "Average Power",
        value: this._getSensorState(entities.power_avg, "W")
      });
    }
    
    if (entities.priority) {
      infoItems.push({
        name: "Priority",
        value: this._getSensorState(entities.priority, "")
      });
    }
    
    if (entities.min_on_time) {
      infoItems.push({
        name: "Min On Time",
        value: this._getSensorState(entities.min_on_time, "min")
      });
    }

    if (infoItems.length === 0) return "";

    return html`
      ${infoItems.map(item => html`
        <div class="device-control">
          <span class="control-label">${item.name}</span>
          <span class="control-value">${item.value}</span>
        </div>
      `)}
    `;
  }

  _toggleEntity(entityId, checked) {
    if (!this.hass) return;
    const domain = entityId.split(".")[0];
    const service = checked ? "turn_on" : "turn_off";
    this.hass.callService(domain, service, { entity_id: entityId });
    console.log(`Called ${domain}.${service} for ${entityId}`);
  }

  _runOptimization() {
    if (!this.hass) return;
    this._isBusy = true;
    this.requestUpdate();
    
    this.hass.callService("pv_optimizer", "run_optimization", {})
      .then(() => {
        console.log("Optimization run successfully");
        this._isBusy = false;
        this.requestUpdate();
      })
      .catch((error) => {
        console.error("Error running optimization:", error);
        this._isBusy = false;
        this.requestUpdate();
      });
  }

  _refreshData() {
    if (!this.hass) return;
    this._isBusy = true;
    this.requestUpdate();
    
    this.hass.callService("pv_optimizer", "refresh_data", {})
      .then(() => {
        console.log("Data refreshed successfully");
        this._isBusy = false;
        this.requestUpdate();
      })
      .catch((error) => {
        console.error("Error refreshing data:", error);
        this._isBusy = false;
        this.requestUpdate();
      });
  }

  _resetSystem() {
    if (!this.hass) return;
    this._isBusy = true;
    this.requestUpdate();
    
    this.hass.callService("pv_optimizer", "reset_system", {})
      .then(() => {
        console.log("System reset successfully");
        this._isBusy = false;
        this.requestUpdate();
      })
      .catch((error) => {
        console.error("Error resetting system:", error);
        this._isBusy = false;
        this.requestUpdate();
      });
  }

  _getTodaysOptimizations() {
    // Mock data - replace with actual sensor call
    return "12 devices";
  }

  _getEnergySavedToday() {
    // Mock data - replace with actual sensor call
    return "2.4 kWh";
  }

  _getOptimizationEfficiency() {
    // Mock data - replace with actual sensor call
    return "85%";
  }

  // --- CSS Styles ---
  static get styles() {
    return css`
      :host {
        display: block;
      }

      .card-content {
        padding: 16px;
      }

      .tab-container {
        display: flex;
        flex-direction: column;
        min-height: 400px;
      }

      .tab-header {
        display: flex;
        background-color: var(--card-background-color, #fff);
        border-radius: 8px 8px 0 0;
        overflow: hidden;
        margin-bottom: 0;
      }

      .tab-button {
        flex: 1;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 8px;
        padding: 12px 16px;
        background: none;
        border: none;
        color: var(--secondary-text-color, #666);
        font-size: 14px;
        font-weight: 500;
        cursor: pointer;
        transition: all 0.2s ease;
        border-bottom: 3px solid transparent;
      }

      .tab-button:hover {
        background-color: var(--card-background-color, #f8f9fa);
      }

      .tab-button.active {
        color: var(--primary-color, #2196F3);
        border-bottom-color: var(--primary-color, #2196F3);
        background-color: var(--card-background-color, #f8f9fa);
      }

      .tab-icon {
        width: 16px;
        height: 16px;
      }

      .tab-content {
        background-color: var(--card-background-color, #fff);
        border-radius: 0 0 8px 8px;
        padding: 16px;
        min-height: 300px;
        border-top: 1px solid var(--divider-color, #e0e0e0);
      }

      .section {
        margin-bottom: 24px;
      }

      .section:last-child {
        margin-bottom: 0;
      }

      .section-title {
        margin: 0 0 16px 0;
        color: var(--primary-text-color, #212121);
        font-size: 18px;
        font-weight: 600;
      }

      .info-text {
        margin-bottom: 16px;
        padding: 12px;
        background-color: var(--primary-background-color, #f5f5f5);
        border-radius: 4px;
        border-left: 4px solid var(--primary-color, #2196F3);
      }

      .info-text p {
        margin: 0;
        color: var(--secondary-text-color, #666);
        font-size: 14px;
      }

      .stats-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
        gap: 16px;
      }

      .stat-card {
        background-color: var(--card-background-color, #fff);
        border: 1px solid var(--divider-color, #e0e0e0);
        border-radius: 8px;
        padding: 16px;
        transition: box-shadow 0.2s ease;
      }

      .stat-card:hover {
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
      }

      .stat-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 8px;
      }

      .stat-label {
        font-size: 14px;
        font-weight: 600;
        color: var(--primary-text-color, #212121);
      }

      .stat-icon {
        width: 20px;
        height: 20px;
        color: var(--primary-color, #2196F3);
      }

      .stat-value {
        font-size: 24px;
        font-weight: 700;
        color: var(--primary-text-color, #212121);
        margin-bottom: 4px;
      }

      .stat-description {
        font-size: 12px;
        color: var(--secondary-text-color, #666);
        line-height: 1.4;
      }

      .device-list {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
        gap: 16px;
      }

      .device-card {
        background-color: var(--card-background-color, #fff);
        border: 1px solid var(--divider-color, #e0e0e0);
        border-radius: 8px;
        padding: 16px;
        transition: box-shadow 0.2s ease;
      }

      .device-card:hover {
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
      }

      .device-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 12px;
        padding-bottom: 8px;
        border-bottom: 1px solid var(--divider-color, #e0e0e0);
      }

      .device-name {
        margin: 0;
        font-size: 16px;
        font-weight: 600;
        color: var(--primary-text-color, #212121);
      }

      .device-controls {
        display: flex;
        flex-direction: column;
        gap: 8px;
      }

      .device-control {
        display: flex;
        justify-content: space-between;
        align-items: center;
      }

      .control-label {
        font-size: 14px;
        color: var(--secondary-text-color, #666);
      }

      .control-value {
        font-size: 14px;
        font-weight: 600;
        color: var(--primary-text-color, #212121);
      }

      .control-actions {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
        gap: 16px;
      }

      .action-card {
        background-color: var(--card-background-color, #fff);
        border: 1px solid var(--divider-color, #e0e0e0);
        border-radius: 8px;
        padding: 16px;
        transition: box-shadow 0.2s ease;
      }

      .action-card:hover {
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
      }

      .action-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 8px;
      }

      .action-label {
        font-size: 16px;
        font-weight: 600;
        color: var(--primary-text-color, #212121);
      }

      .action-icon {
        width: 20px;
        height: 20px;
        color: var(--primary-color, #2196F3);
      }

      .action-description {
        font-size: 14px;
        color: var(--secondary-text-color, #666);
        margin-bottom: 12px;
        line-height: 1.4;
      }

      .no-devices {
        text-align: center;
        padding: 48px 16px;
        color: var(--secondary-text-color, #666);
      }

      .no-devices p {
        margin: 8px 0;
      }

      ha-button {
        width: 100%;
      }

      ha-switch {
        margin-left: 12px;
      }

      /* Responsive design */
      @media (max-width: 768px) {
        .tab-header {
          flex-direction: column;
        }

        .tab-button {
          flex: none;
          padding: 16px;
        }

        .stats-grid {
          grid-template-columns: 1fr;
        }

        .device-list {
          grid-template-columns: 1fr;
        }

        .control-actions {
          grid-template-columns: 1fr;
        }
      }

      @media (min-width: 1024px) {
        .stats-grid {
          grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        }

        .device-list {
          grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
        }

        .control-actions {
          grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
        }
      }
    `;
  }
}

customElements.define("pv-optimizer-panel", PvOptimizerPanel);
