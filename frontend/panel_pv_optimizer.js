import {
  LitElement,
  html,
  css,
} from "https://unpkg.com/lit-element@2.0.1/lit-element.js?module";

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
      <ha-card header="PV Optimizer Control Panel">
        <div class="card-content">
          <p>
            Welcome to the PV Optimizer. Use this panel to monitor and control
            your PV optimization settings.
          </p>

          <div class="stat-grid">
            <div class="stat-item">
              <span class="stat-title">Power Budget</span>
              <span class="stat-value">
                ${this._getSensorState("sensor.pv_optimizer_power_budget", "W")}
              </span>
            </div>
            <div class="stat-item">
              <span class="stat-title">Averaged Surplus</span>
              <span class="stat-value">
                ${this._getSensorState("sensor.pv_optimizer_averaged_surplus", "W")}
              </span>
            </div>
          </div>

          <div class="actions">
            <mwc-button
              raised
              label="Run Optimization Now"
              @click=${this._runOptimization}
            ></mwc-button>
          </div>
        </div>
      </ha-card>
    `;
  }

  // --- Helper Functions ---
  _getSensorState(entityId, unit = "") {
    if (this.hass && this.hass.states[entityId]) {
      const state = this.hass.states[entityId].state;
      return `${state} ${unit}`;
    }
    return "Unavailable";
  }

  _runOptimization() {
    if (!this.hass) return;
    this.hass.callService("pv_optimizer", "run", {});
    console.log("Called pv_optimizer.run service");
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
      .stat-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
        gap: 16px;
        margin-top: 20px;
        margin-bottom: 20px;
      }
      .stat-item {
        background-color: var(--ha-card-background, #fafafa);
        border: 1px solid var(--divider-color, #e0e0e0);
        border-radius: 4px;
        padding: 16px;
        display: flex;
        flex-direction: column;
        align-items: center;
      }
      .stat-title {
        font-weight: bold;
        color: var(--secondary-text-color);
      }
      .stat-value {
        font-size: 1.5em;
        color: var(--primary-text-color);
        margin-top: 8px;
      }
      .actions {
        margin-top: 24px;
        text-align: center;
      }
    `;
  }
}

customElements.define("pv-optimizer-panel", PvOptimizerPanel);

