import {
  LitElement,
  html,
  css,
} from "https://unpkg.com/lit@2.7.0/index.js?module";

class PvOptimizerPanel extends LitElement {
  static get properties() {
    return {
      hass: { type: Object },
      narrow: { type: Boolean },
      panel: { type: Object },
      _config: { type: Object },
      _error: { type: String },
      _loading: { type: Boolean },
      _editingGlobal: { type: Boolean },
      _editingDevice: { type: Object },
      _showAddDevice: { type: Boolean },
      _deviceFormData: { type: Object },
    };
  }

  constructor() {
    super();
    this._config = null;
    this._error = null;
    this._loading = true;
    this._editingGlobal = false;
    this._editingDevice = null;
    this._showAddDevice = false;
    this._deviceFormData = this._getEmptyDeviceForm();
  }

  firstUpdated() {
    this._getConfigWithRetry();
  }

  _getEmptyDeviceForm() {
    return {
      name: '',
      type: 'switch',
      priority: 5,
      power: 0,
      optimization_enabled: true,
      switch_entity_id: '',
      invert_switch: false,
      measured_power_entity_id: '',
      power_threshold: 100,
      min_on_time: 0,
      min_off_time: 0,
      numeric_targets: [],
    };
  }

  async _getConfigWithRetry(retryCount = 0) {
    if (!this.hass?.connection) {
      this._error = 'WebSocket connection not available';
      this._loading = false;
      return;
    }

    try {
      this._loading = true;
      this._error = null;

      await new Promise(resolve => setTimeout(resolve, 500));

      const response = await this.hass.callWS({
        type: 'pv_optimizer/config',
      });
      
      this._config = response;
      this._loading = false;
      this._error = null;
      
    } catch (error) {
      console.error('Failed to get config:', error);
      
      if (retryCount < 3) {
        const delay = Math.pow(2, retryCount) * 1000;
        setTimeout(() => this._getConfigWithRetry(retryCount + 1), delay);
      } else {
        this._error = `Failed to load configuration: ${error.message}`;
        this._loading = false;
      }
    }
  }

  async _saveGlobalConfig(config) {
    try {
      await this.hass.callWS({
        type: 'pv_optimizer/set_config',
        data: config,
      });
      
      this._editingGlobal = false;
      await this._getConfigWithRetry();
      this._showToast('Global configuration saved successfully', 'success');
    } catch (error) {
      console.error('Failed to save global config:', error);
      this._showToast(`Failed to save: ${error.message}`, 'error');
    }
  }

  async _addDevice(deviceConfig) {
    try {
      await this.hass.callWS({
        type: 'pv_optimizer/add_device',
        device: deviceConfig,
      });
      
      this._showAddDevice = false;
      this._deviceFormData = this._getEmptyDeviceForm();
      await this._getConfigWithRetry();
      this._showToast('Device added successfully', 'success');
    } catch (error) {
      console.error('Failed to add device:', error);
      this._showToast(`Failed to add device: ${error.message}`, 'error');
    }
  }

  async _updateDevice(deviceName, deviceConfig) {
    try {
      await this.hass.callWS({
        type: 'pv_optimizer/update_device',
        device_name: deviceName,
        device: deviceConfig,
      });
      
      this._editingDevice = null;
      await this._getConfigWithRetry();
      this._showToast('Device updated successfully', 'success');
    } catch (error) {
      console.error('Failed to update device:', error);
      this._showToast(`Failed to update device: ${error.message}`, 'error');
    }
  }

  async _deleteDevice(deviceName) {
    if (!confirm(`Are you sure you want to delete device "${deviceName}"?`)) {
      return;
    }
    
    try {
      await this.hass.callWS({
        type: 'pv_optimizer/delete_device',
        device_name: deviceName,
      });
      
      await this._getConfigWithRetry();
      this._showToast('Device deleted successfully', 'success');
    } catch (error) {
      console.error('Failed to delete device:', error);
      this._showToast(`Failed to delete device: ${error.message}`, 'error');
    }
  }

  _showToast(message, type = 'info') {
    const event = new CustomEvent('hass-notification', {
      detail: { message },
      bubbles: true,
      composed: true,
    });
    this.dispatchEvent(event);
  }

  _handleGlobalConfigSubmit(e) {
    e.preventDefault();
    const formData = new FormData(e.target);
    const config = {
      surplus_sensor_entity_id: formData.get('surplus_sensor_entity_id'),
      sliding_window_size: parseInt(formData.get('sliding_window_size')),
      optimization_cycle_time: parseInt(formData.get('optimization_cycle_time')),
    };
    this._saveGlobalConfig(config);
  }

  _handleDeviceSubmit(e) {
    e.preventDefault();
    const formData = this._deviceFormData;
    
    const deviceConfig = {
      name: formData.name,
      type: formData.type,
      priority: parseInt(formData.priority),
      power: parseFloat(formData.power),
      optimization_enabled: formData.optimization_enabled,
      measured_power_entity_id: formData.measured_power_entity_id || null,
      power_threshold: parseFloat(formData.power_threshold) || 100,
      min_on_time: parseInt(formData.min_on_time) || 0,
      min_off_time: parseInt(formData.min_off_time) || 0,
    };
    
    if (deviceConfig.type === 'switch') {
      deviceConfig.switch_entity_id = formData.switch_entity_id;
      deviceConfig.invert_switch = formData.invert_switch;
    } else if (deviceConfig.type === 'numeric') {
      deviceConfig.numeric_targets = formData.numeric_targets || [];
    }
    
    if (this._editingDevice) {
      this._updateDevice(this._editingDevice.config.name, deviceConfig);
    } else {
      this._addDevice(deviceConfig);
    }
  }

  _updateFormData(field, value) {
    this._deviceFormData = {
      ...this._deviceFormData,
      [field]: value,
    };
  }

  _addNumericTarget() {
    const targets = [...(this._deviceFormData.numeric_targets || [])];
    targets.push({
      numeric_entity_id: '',
      activated_value: '',
      deactivated_value: ''
    });
    this._updateFormData('numeric_targets', targets);
  }

  _removeNumericTarget(index) {
    const targets = [...(this._deviceFormData.numeric_targets || [])];
    targets.splice(index, 1);
    this._updateFormData('numeric_targets', targets);
  }

  _updateNumericTarget(index, field, value) {
    const targets = [...(this._deviceFormData.numeric_targets || [])];
    targets[index] = {
      ...targets[index],
      [field]: value
    };
    this._updateFormData('numeric_targets', targets);
  }

  static get styles() {
    return css`
      :host {
        display: block;
        padding: 16px;
      }

      .header {
        font-size: 24px;
        font-weight: 500;
        margin-bottom: 24px;
        display: flex;
        align-items: center;
        gap: 12px;
      }

      ha-card {
        margin-bottom: 16px;
      }

      .card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 16px;
        border-bottom: 1px solid var(--divider-color);
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
        color: var(--primary-text-color);
      }

      .config-value {
        padding: 8px 12px;
        background-color: var(--secondary-background-color);
        border-radius: 4px;
        font-family: monospace;
        font-size: 14px;
      }

      .device-list {
        display: grid;
        gap: 12px;
      }

      .device-card {
        background-color: var(--card-background-color);
        border: 1px solid var(--divider-color);
        border-left: 4px solid var(--primary-color);
        border-radius: 8px;
        padding: 16px;
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
      }

      .device-info {
        flex: 1;
      }

      .device-name {
        font-size: 16px;
        font-weight: 500;
        margin-bottom: 8px;
        display: flex;
        align-items: center;
        gap: 8px;
      }

      .device-details {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
        gap: 8px;
        font-size: 13px;
        color: var(--secondary-text-color);
      }

      .device-detail {
        display: flex;
        gap: 4px;
      }

      .device-actions {
        display: flex;
        gap: 8px;
        margin-left: 16px;
      }

      .empty-state {
        text-align: center;
        padding: 40px 20px;
        color: var(--secondary-text-color);
      }

      .empty-icon {
        font-size: 48px;
        opacity: 0.5;
        margin-bottom: 16px;
      }

      .form-group {
        margin-bottom: 16px;
      }

      .help-text {
        font-size: 12px;
        color: var(--secondary-text-color);
        margin-top: 4px;
      }

      .numeric-targets {
        border: 1px solid var(--divider-color);
        border-radius: 4px;
        padding: 12px;
        margin-bottom: 12px;
      }

      .numeric-target {
        padding: 12px;
        border: 1px solid var(--divider-color);
        border-radius: 4px;
        margin-bottom: 12px;
        background-color: var(--secondary-background-color);
      }

      .target-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 12px;
        font-weight: 500;
      }

      mwc-button {
        --mdc-theme-primary: var(--primary-color);
      }

      ha-formfield {
        display: block;
        margin-bottom: 8px;
      }

      ha-textfield,
      ha-entity-picker {
        display: block;
        margin-bottom: 8px;
      }

      ha-switch {
        padding: 16px 0;
      }
    `;
  }

  render() {
    if (this._error) {
      return html`
        <div class="header">
          <ha-icon icon="mdi:alert-circle"></ha-icon>
          PV Optimizer
        </div>
        <ha-card>
          <div class="card-content">
            <ha-alert alert-type="error">
              ${this._error}
              <mwc-button slot="action" @click=${() => location.reload()}>
                Refresh
              </mwc-button>
            </ha-alert>
          </div>
        </ha-card>
      `;
    }

    if (this._loading) {
      return html`
        <div class="header">
          <ha-circular-progress active></ha-circular-progress>
          PV Optimizer
        </div>
        <ha-card>
          <div class="card-content">
            Loading configuration...
          </div>
        </ha-card>
      `;
    }

    const globalConfig = this._config?.global_config || {};
    const devices = this._config?.devices || [];

    return html`
      <div class="header">
        <ha-icon icon="mdi:solar-power"></ha-icon>
        PV Optimizer
      </div>

      ${this._renderGlobalConfig(globalConfig)}
      ${this._renderDeviceList(devices)}
      ${this._editingGlobal ? this._renderGlobalConfigDialog(globalConfig) : ''}
      ${this._showAddDevice || this._editingDevice ? this._renderDeviceDialog() : ''}
    `;
  }

  _renderGlobalConfig(globalConfig) {
    return html`
      <ha-card>
        <div class="card-header">
          <span>Global Configuration</span>
          <mwc-button @click=${() => this._editingGlobal = true}>
            <ha-icon icon="mdi:pencil"></ha-icon>
            Edit
          </mwc-button>
        </div>
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
    `;
  }

  _renderDeviceList(devices) {
    return html`
      <ha-card>
        <div class="card-header">
          <span>Devices (${devices.length})</span>
          <mwc-button raised @click=${() => {
            this._deviceFormData = this._getEmptyDeviceForm();
            this._showAddDevice = true;
          }}>
            <ha-icon icon="mdi:plus"></ha-icon>
            Add Device
          </mwc-button>
        </div>
        <div class="card-content">
          ${devices.length === 0 ? html`
            <div class="empty-state">
              <div class="empty-icon">📱</div>
              <div>No devices configured yet</div>
              <div style="margin-top: 8px; font-size: 14px;">
                Click "Add Device" to configure your first controllable device
              </div>
            </div>
          ` : html`
            <div class="device-list">
              ${devices.map(device => this._renderDeviceCard(device))}
            </div>
          `}
        </div>
      </ha-card>
    `;
  }

  _renderDeviceCard(deviceData) {
    const device = deviceData.config;
    const state = deviceData.state || {};
    
    return html`
      <div class="device-card">
        <div class="device-info">
          <div class="device-name">
            ${device.optimization_enabled ? html`<ha-icon icon="mdi:check-circle" style="color: var(--success-color);"></ha-icon>` : html`<ha-icon icon="mdi:close-circle" style="color: var(--error-color);"></ha-icon>`}
            ${device.name}
          </div>
          <div class="device-details">
            <div class="device-detail">
              <strong>Type:</strong> ${device.type}
            </div>
            <div class="device-detail">
              <strong>Priority:</strong> ${device.priority}
            </div>
            <div class="device-detail">
              <strong>Power:</strong> ${device.power}W
            </div>
            <div class="device-detail">
              <strong>Status:</strong> ${state.is_on ? 'ON' : 'OFF'}
            </div>
            <div class="device-detail">
              <strong>Locked:</strong> ${state.is_locked ? 'Yes' : 'No'}
            </div>
            ${state.measured_power_avg ? html`
              <div class="device-detail">
                <strong>Measured:</strong> ${state.measured_power_avg.toFixed(1)}W
              </div>
            ` : ''}
          </div>
        </div>
        <div class="device-actions">
          <mwc-icon-button @click=${() => {
            this._deviceFormData = { ...device };
            this._editingDevice = deviceData;
          }}>
            <ha-icon icon="mdi:pencil"></ha-icon>
          </mwc-icon-button>
          <mwc-icon-button @click=${() => this._deleteDevice(device.name)}>
            <ha-icon icon="mdi:delete"></ha-icon>
          </mwc-icon-button>
        </div>
      </div>
    `;
  }

  _renderGlobalConfigDialog(globalConfig) {
    return html`
      <ha-dialog
        open
        @closed=${() => this._editingGlobal = false}
        .heading=${'Edit Global Configuration'}
      >
        <div>
          <div class="form-group">
            <ha-entity-picker
              .hass=${this.hass}
              .value=${globalConfig.surplus_sensor_entity_id}
              .label=${'PV Surplus Sensor'}
              .required=${true}
              .includeDomains=${['sensor']}
              @value-changed=${(e) => {
                globalConfig.surplus_sensor_entity_id = e.detail.value;
              }}
            ></ha-entity-picker>
            <div class="help-text">The sensor that provides the PV surplus/deficit value</div>
          </div>

          <div class="form-group">
            <ha-textfield
              .label=${'Sliding Window Size (minutes)'}
              .value=${globalConfig.sliding_window_size || 5}
              type="number"
              min="1"
              max="60"
              required
              @input=${(e) => {
                globalConfig.sliding_window_size = parseInt(e.target.value);
              }}
            ></ha-textfield>
            <div class="help-text">Time window for averaging power measurements</div>
          </div>

          <div class="form-group">
            <ha-textfield
              .label=${'Optimization Cycle Time (seconds)'}
              .value=${globalConfig.optimization_cycle_time || 60}
              type="number"
              min="10"
              max="300"
              required
              @input=${(e) => {
                globalConfig.optimization_cycle_time = parseInt(e.target.value);
              }}
            ></ha-textfield>
            <div class="help-text">How often the optimizer runs</div>
          </div>
        </div>

        <mwc-button slot="secondaryAction" @click=${() => this._editingGlobal = false}>
          Cancel
        </mwc-button>
        <mwc-button slot="primaryAction" @click=${() => this._saveGlobalConfig(globalConfig)}>
          Save
        </mwc-button>
      </ha-dialog>
    `;
  }

  _renderDeviceDialog() {
    const isEdit = !!this._editingDevice;
    const formData = this._deviceFormData;

    return html`
      <ha-dialog
        open
        @closed=${() => {
          this._showAddDevice = false;
          this._editingDevice = null;
        }}
        .heading=${isEdit ? `Edit Device: ${formData.name}` : 'Add New Device'}
      >
        <div>
          <div class="form-group">
            <ha-textfield
              .label=${'Device Name'}
              .value=${formData.name}
              required
              .disabled=${isEdit}
              @input=${(e) => this._updateFormData('name', e.target.value)}
            ></ha-textfield>
            <div class="help-text">A unique name for this device</div>
          </div>

          <div class="form-group">
            <ha-formfield .label=${'Device Type'}>
              <mwc-select
                .value=${formData.type}
                @selected=${(e) => {
                  const newType = e.target.value === 0 ? 'switch' : 'numeric';
                  this._updateFormData('type', newType);
                }}
              >
                <mwc-list-item value="switch" ?selected=${formData.type === 'switch'}>
                  Switch
                </mwc-list-item>
                <mwc-list-item value="numeric" ?selected=${formData.type === 'numeric'}>
                  Numeric
                </mwc-list-item>
              </mwc-select>
            </ha-formfield>
            <div class="help-text">Switch: On/Off control | Numeric: Value adjustment</div>
          </div>

          <div class="form-group">
            <ha-textfield
              .label=${'Priority'}
              .value=${formData.priority}
              type="number"
              min="1"
              max="10"
              required
              @input=${(e) => this._updateFormData('priority', parseInt(e.target.value))}
            ></ha-textfield>
            <div class="help-text">1 = highest priority, 10 = lowest</div>
          </div>

          <div class="form-group">
            <ha-textfield
              .label=${'Nominal Power (W)'}
              .value=${formData.power}
              type="number"
              min="0"
              step="0.1"
              required
              @input=${(e) => this._updateFormData('power', parseFloat(e.target.value))}
            ></ha-textfield>
            <div class="help-text">The device's power consumption in Watts</div>
          </div>

          <div class="form-group">
            <ha-formfield .label=${'Optimization Enabled'}>
              <ha-switch
                .checked=${formData.optimization_enabled}
                @change=${(e) => this._updateFormData('optimization_enabled', e.target.checked)}
              ></ha-switch>
            </ha-formfield>
          </div>

          ${formData.type === 'switch' ? html`
            <div class="form-group">
              <ha-entity-picker
                .hass=${this.hass}
                .value=${formData.switch_entity_id}
                .label=${'Switch Entity'}
                .required=${true}
                .includeDomains=${['switch']}
                @value-changed=${(e) => this._updateFormData('switch_entity_id', e.detail.value)}
              ></ha-entity-picker>
              <div class="help-text">The switch entity to control</div>
            </div>

            <div class="form-group">
              <ha-formfield .label=${'Invert Switch Logic'}>
                <ha-switch
                  .checked=${formData.invert_switch}
                  @change=${(e) => this._updateFormData('invert_switch', e.target.checked)}
                ></ha-switch>
              </ha-formfield>
              <div class="help-text">Turn OFF to activate, ON to deactivate</div>
            </div>
          ` : ''}

          ${formData.type === 'numeric' ? html`
            <div class="form-group">
              <div class="config-label">Numeric Targets</div>
              <div class="numeric-targets">
                ${(formData.numeric_targets || []).length === 0 ? html`
                  <div class="help-text" style="padding: 12px;">
                    No targets configured. Click "Add Target" to add one.
                  </div>
                ` : html`
                  ${(formData.numeric_targets || []).map((target, index) => html`
                    <div class="numeric-target">
                      <div class="target-header">
                        <span>Target ${index + 1}</span>
                        <mwc-icon-button @click=${() => this._removeNumericTarget(index)}>
                          <ha-icon icon="mdi:delete"></ha-icon>
                        </mwc-icon-button>
                      </div>
                      <ha-entity-picker
                        .hass=${this.hass}
                        .value=${target.numeric_entity_id}
                        .label=${'Entity ID'}
                        .required=${true}
                        .includeDomains=${['number', 'input_number']}
                        @value-changed=${(e) => this._updateNumericTarget(index, 'numeric_entity_id', e.detail.value)}
                      ></ha-entity-picker>
                      <ha-textfield
                        .label=${'Activated Value'}
                        .value=${target.activated_value}
                        type="number"
                        step="any"
                        required
                        @input=${(e) => this._updateNumericTarget(index, 'activated_value', parseFloat(e.target.value))}
                      ></ha-textfield>
                      <ha-textfield
                        .label=${'Deactivated Value'}
                        .value=${target.deactivated_value}
                        type="number"
                        step="any"
                        required
                        @input=${(e) => this._updateNumericTarget(index, 'deactivated_value', parseFloat(e.target.value))}
                      ></ha-textfield>
                    </div>
                  `)}
                `}
              </div>
              <mwc-button @click=${() => this._addNumericTarget()}>
                <ha-icon icon="mdi:plus"></ha-icon>
                Add Target
              </mwc-button>
            </div>
          ` : ''}

          <div class="form-group">
            <ha-entity-picker
              .hass=${this.hass}
              .value=${formData.measured_power_entity_id}
              .label=${'Measured Power Sensor (optional)'}
              .includeDomains=${['sensor']}
              @value-changed=${(e) => this._updateFormData('measured_power_entity_id', e.detail.value)}
            ></ha-entity-picker>
            <div class="help-text">Sensor providing actual power consumption</div>
          </div>

          <div class="form-group">
            <ha-textfield
              .label=${'Power Threshold (W)'}
              .value=${formData.power_threshold}
              type="number"
              min="0"
              step="0.1"
              @input=${(e) => this._updateFormData('power_threshold', parseFloat(e.target.value))}
            ></ha-textfield>
            <div class="help-text">Threshold to determine if device is ON</div>
          </div>

          <div class="form-group">
            <ha-textfield
              .label=${'Minimum On Time (minutes)'}
              .value=${formData.min_on_time}
              type="number"
              min="0"
              @input=${(e) => this._updateFormData('min_on_time', parseInt(e.target.value))}
            ></ha-textfield>
            <div class="help-text">Device must stay on for at least this long</div>
          </div>

          <div class="form-group">
            <ha-textfield
              .label=${'Minimum Off Time (minutes)'}
              .value=${formData.min_off_time}
              type="number"
              min="0"
              @input=${(e) => this._updateFormData('min_off_time', parseInt(e.target.value))}
            ></ha-textfield>
            <div class="help-text">Device must stay off for at least this long</div>
          </div>
        </div>

        <mwc-button slot="secondaryAction" @click=${() => {
          this._showAddDevice = false;
          this._editingDevice = null;
        }}>
          Cancel
        </mwc-button>
        <mwc-button slot="primaryAction" @click=${(e) => this._handleDeviceSubmit(e)}>
          ${isEdit ? 'Update' : 'Add'} Device
        </mwc-button>
      </ha-dialog>
    `;
  }
}

customElements.define('pv-optimizer-panel', PvOptimizerPanel);
