
import { LitElement, html, css } from 'lit';

class PvOptimizerPanel extends LitElement {
  static properties = {
    hass: {},
    narrow: {},
    route: {},
    panel: {},
    surplusSensor: { type: String },
    slidingWindow: { type: Number },
    cycleTime: { type: Number },
  };

  static styles = css`
    :host {
      display: block;
      padding: 16px;
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
    }

    .form-group {
      margin-bottom: 16px;
    }

    label {
      display: block;
      margin-bottom: 8px;
    }

    input {
      width: 100%;
      padding: 8px;
      box-sizing: border-box;
    }
  `;

  firstUpdated() {
    this.getConfig();
  }

  async getConfig() {
    const config = await this.hass.callWS({
      type: 'pv_optimizer/get_config',
    });
    this.surplusSensor = config.surplus_sensor_entity_id;
    this.slidingWindow = config.sliding_window_size;
    this.cycleTime = config.optimization_cycle_time;
  }

  async setConfig() {
    await this.hass.callWS({
      type: 'pv_optimizer/set_config',
      data: {
        surplus_sensor_entity_id: this.surplusSensor,
        sliding_window_size: this.slidingWindow,
        optimization_cycle_time: this.cycleTime,
      },
    });
  }

  render() {
    return html`
      <div class="card">
        <div class="card-header">General Settings</div>
        <div class="form-group">
          <label for="surplus-sensor">PV Surplus Sensor</label>
          <input
            type="text"
            id="surplus-sensor"
            .value=${this.surplusSensor}
            @change=${(e) => {
              this.surplusSensor = e.target.value;
              this.setConfig();
            }}
          />
        </div>
        <div class="form-group">
          <label for="sliding-window">Sliding Window Size (minutes)</label>
          <input
            type="number"
            id="sliding-window"
            .value=${this.slidingWindow}
            @change=${(e) => {
              this.slidingWindow = e.target.value;
              this.setConfig();
            }}
          />
        </div>
        <div class="form-group">
          <label for="cycle-time">Optimization Cycle Time (seconds)</label>
          <input
            type="number"
            id="cycle-time"
            .value=${this.cycleTime}
            @change=${(e) => {
              this.cycleTime = e.target.value;
              this.setConfig();
            }}
          />
        </div>
      </div>
    `;
  }
}

customElements.define('pv-optimizer-panel', PvOptimizerPanel);
