import "https://unpkg.com/wired-card@2.1.0/lib/wired-card.js?module";
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
      _config: { type: Object, state: true },
      _loading: { type: Boolean, state: true },
      _error: { type: String, state: true },
    };
  }

  constructor() {
    super();
    this._config = null;
    this._loading = true;
    this._error = null;
    this._refreshInterval = null;
  }

  connectedCallback() {
    super.connectedCallback();
    this._fetchConfig();
    
    // Auto-refresh every 30 seconds
    this._refreshInterval = setInterval(() => {
      this._fetchConfig();
    }, 30000);
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    if (this._refreshInterval) {
      clearInterval(this._refreshInterval);
      this._refreshInterval = null;
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

  _renderStatusCard() {
    const ready = !this._loading && !this._error && this._config;

    return html`
      <ha-card outlined>
        <h1 class="card-header">
          <div class="name">PV Optimizer</div>
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
        </h1>
        <div class="card-content">
          ${this._error
            ? html`
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
              `
            : html`
                <ha-alert alert-type="info">
                  Configure devices and settings through the integration's
                  options flow.
                </ha-alert>
              `}
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
              <div class="config-value">${stats.last_update_timestamp ? new Date(stats.last_update_timestamp).toLocaleString() : 'N/A'}</div>
            </div>
            <div class="config-group">
              <div class="config-label">Elapsed Time Since Last Update</div>
              <div class="config-value">${stats.elapsed_seconds_since_update ? stats.elapsed_seconds_since_update.toFixed(0) + ' s' : 'N/A'}</div>
            </div>
          ` : html`
            <div class="loading">⏳ Loading stats...</div>
          `}
        </div>
      </ha-card>
    `;
  }

  _renderDeviceCard(deviceData) {
    const device = deviceData.config;
    const state = deviceData.state || {};

    const statusIcon = device.optimization_enabled ? "🟢" : "🔴";
    const statusText = state.is_on ? "✅ ON" : "⭕ OFF";
    const lockIcon = state.is_locked ? "🔒" : "🔓";

    return html`
      <div class="device-card">
        <div class="device-name">${statusIcon} ${device.name}</div>
        <div class="device-details">
          <div><strong>Type:</strong> ${device.type}</div>
          <div><strong>Priority:</strong> ${device.priority}</div>
          <div><strong>Power:</strong> ${device.power}W</div>
          <div><strong>Status:</strong> ${statusText}</div>
          <div><strong>Locked:</strong> ${lockIcon} ${state.is_locked ? "Yes" : "No"}</div>
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
      <div class="card-container">
        ${this._renderStatusCard()} ${this._renderGlobalConfigCard()}
        ${this._renderDevicesCard()}
      </div>
    `;
  }

  static get styles() {
    return css`
      :host {
        display: block;
        padding: 16px;
        background-color: var(--primary-background-color);
        --app-header-background-color: var(--sidebar-background-color);
        --ha-card-border-radius: 8px;
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
        .card-container {
          gap: 8px;
        }
        ha-card {
          margin: 0;
        }

        .device-details {
          grid-template-columns: 1fr;
        }
      }
    `;
  }
}

// Register the custom element
window.customElements.define("pv-optimizer-panel", PvOptimizerPanel);
