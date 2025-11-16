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
    };
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
            <p>
              Welcome to the PV Optimizer. Use this panel to monitor and control
              your PV optimization settings and devices.
            </p>

            <!-- Global Configuration Section -->
            <div class="section">
              <h3>Global Configuration</h3>
              <div class="config-grid">
                <div class="config-item">
                  <span class="config-label">Power Budget</span>
                  <span class="config-value">
                    ${this._getSensorState("sensor.pv_optimizer_power_budget", "W")}
                  </span>
                </div>
                <div class="config-item">
                  <span class="config-label">Averaged Surplus</span>
                  <span class="config-value">
                    ${this._getSensorState("sensor.pv_optimizer_averaged_surplus", "W")}
                  </span>
                </div>
                <div class="config-item">
                  <span class="config-label">Ideal On List</span>
                  <span class="config-value">
                    ${this._getSensorState("sensor.pv_optimizer_ideal_on_list", "devices")}
                  </span>
                </div>
              </div>
            </div>

            <!-- Device Management Section -->
            <div class="section">
              <h3>Device Management</h3>
              <div class="device-list">
                ${this._renderDeviceCards()}
              </div>
            </div>

            <!-- Actions Section -->
            <div class="section">
              <h3>Control</h3>
              <div class="actions">
                <mwc-button
                  raised
                  label="Refresh Data"
                  @click=${this._refreshData}
                ></mwc-button>
                <mwc-button
                  raised
                  label="Run Optimization Now"
                  @click=${this._runOptimization}
                ></mwc-button>
              </div>
            </div>
          </div>
        </ha-card>
      </hass-panel-router>
    `;
  }

  // --- Helper Functions ---
  _getSensorState(entityId, unit = "") {
    if (this.hass && this.hass.states && this.hass.states[entityId]) {
      const state = this.hass.states[entityId].state;
      return `${state} ${unit}`;
    }
    return "Unavailable";
  }

  _getSwitchState(entityId) {
    if (this.hass && this.hass.states && this.hass.states[entityId]) {
      return this.hass.states[entityId].state === "on";
    }
    return false;
  }

  _renderDeviceCards() {
    // Get all PV Optimizer related sensors and switches
    const entities = Object.keys(this.hass?.states || {})
      .filter(entityId => 
        entityId.startsWith("sensor.pv_optimizer_") || 
        entityId.startsWith("switch.pv_optimizer_") ||
        entityId.startsWith("number.pv_optimizer_")
      );

    if (entities.length === 0) {
      return html`
        <div class="no-devices">
          <p>No devices configured yet. Add devices through the integration setup.</p>
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
      if (nameParts.length >= 3 && nameParts[0] === "pvo") {
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
    
    return html`
      <div class="device-card">
        <h4>${displayName}</h4>
        <div class="device-entities">
          ${Object.entries(entities).map(([entityType, entityId]) => {
            if (entityType === "switch") {
              return html`
                <div class="entity-row">
                  <span>Control:</span>
                  <ha-switch
                    ?checked=${this._getSwitchState(entityId)}
                    @change=${(e) => this._toggleEntity(entityId, e.target.checked)}
                  ></ha-switch>
                </div>
              `;
            } else {
              const unit = this._getEntityUnit(entityId);
              return html`
                <div class="entity-row">
                  <span>${this._getEntityDisplayName(entityType)}:</span>
                  <span class="entity-value">
                    ${this._getSensorState(entityId, unit)}
                  </span>
                </div>
              `;
            }
          })}
        </div>
      </div>
    `;
  }

  _getEntityUnit(entityId) {
    if (entityId.includes("power") || entityId.includes("budget")) return "W";
    if (entityId.includes("time")) return "min";
    return "";
  }

  _getEntityDisplayName(entityType) {
    const typeMap = {
      "power": "Power",
      "power_avg": "Avg Power",
      "locked": "Locked",
      "priority": "Priority",
      "min_on_time": "Min On Time",
      "min_off_time": "Min Off Time",
      "contribution_to_budget": "Budget Contribution"
    };
    return typeMap[entityType] || entityType;
  }

  _toggleEntity(entityId, checked) {
    if (!this.hass) return;
    const domain = entityId.split(".")[0];
    const service = checked ? "turn_on" : "turn_off";
    this.hass.callService(domain, service, { entity_id: entityId });
  }

  _runOptimization() {
    if (!this.hass) return;
    this.hass.callService("pv_optimizer", "run_optimization", {});
    console.log("Called pv_optimizer.run_optimization service");
  }

  _refreshData() {
    if (!this.hass) return;
    // Trigger a refresh of the coordinator data
    this.hass.callService("pv_optimizer", "refresh_data", {});
    console.log("Refreshed PV Optimizer data");
  }

  // --- CSS Styles ---
  static get styles() {
    return css`
      :host {
        padding: 16px;
        display: block;
      }
      .card-content {
        padding: 16px;
      }
      .section {
        margin: 24px 0;
        padding: 16px;
        border: 1px solid var(--divider-color, #e0e0e0);
        border-radius: 8px;
      }
      .section h3 {
        margin: 0 0 16px 0;
        color: var(--primary-text-color);
      }
      .config-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 16px;
      }
      .config-item {
        background-color: var(--ha-card-background, #fafafa);
        border: 1px solid var(--divider-color, #e0e0e0);
        border-radius: 4px;
        padding: 16px;
        display: flex;
        flex-direction: column;
        align-items: center;
      }
      .config-label {
        font-weight: bold;
        color: var(--secondary-text-color);
        margin-bottom: 8px;
      }
      .config-value {
        font-size: 1.2em;
        color: var(--primary-text-color);
      }
      .device-list {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
        gap: 16px;
      }
      .device-card {
        background-color: var(--ha-card-background, #fafafa);
        border: 1px solid var(--divider-color, #e0e0e0);
        border-radius: 4px;
        padding: 16px;
      }
      .device-card h4 {
        margin: 0 0 12px 0;
        color: var(--primary-text-color);
        border-bottom: 1px solid var(--divider-color, #e0e0e0);
        padding-bottom: 8px;
      }
      .entity-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin: 8px 0;
      }
      .entity-value {
        font-weight: bold;
      }
      .actions {
        display: flex;
        gap: 16px;
        justify-content: center;
      }
      .no-devices {
        text-align: center;
        padding: 32px;
        color: var(--secondary-text-color);
      }
    `;
  }
}

customElements.define("pv-optimizer-panel", PvOptimizerPanel);