class PvOptimizerPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._config = null;
    this._error = null;
    this._loading = true;
    this._editingGlobal = false;
    this._editingDevice = null;
    this._showAddDevice = false;
    this._deviceFormData = this._getEmptyDeviceForm();
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._config) {
      this._getConfigWithRetry();
    }
    this.render();
  }

  get hass() {
    return this._hass;
  }

  set panel(panel) {
    this._panel = panel;
  }

  connectedCallback() {
    this.render();
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
    if (!this._hass?.connection) {
      this._error = 'WebSocket connection not available';
      this._loading = false;
      this.render();
      return;
    }

    try {
      this._loading = true;
      this._error = null;
      this.render();

      await new Promise(resolve => setTimeout(resolve, 500));

      const response = await this._hass.callWS({
        type: 'pv_optimizer/config',
      });
      
      this._config = response;
      this._loading = false;
      this._error = null;
      this.render();
      
    } catch (error) {
      console.error('Failed to get config:', error);
      
      if (retryCount < 3) {
        const delay = Math.pow(2, retryCount) * 1000;
        setTimeout(() => this._getConfigWithRetry(retryCount + 1), delay);
      } else {
        this._error = `Failed to load configuration: ${error.message}`;
        this._loading = false;
        this.render();
      }
    }
  }

  async _saveGlobalConfig(config) {
    try {
      await this._hass.callWS({
        type: 'pv_optimizer/set_config',
        data: config,
      });
      
      this._editingGlobal = false;
      await this._getConfigWithRetry();
      this._showToast('Global configuration saved successfully');
    } catch (error) {
      console.error('Failed to save global config:', error);
      this._showToast(`Failed to save: ${error.message}`);
    }
  }

  async _addDevice(deviceConfig) {
    try {
      await this._hass.callWS({
        type: 'pv_optimizer/add_device',
        device: deviceConfig,
      });
      
      this._showAddDevice = false;
      this._deviceFormData = this._getEmptyDeviceForm();
      await this._getConfigWithRetry();
      this._showToast('Device added successfully');
    } catch (error) {
      console.error('Failed to add device:', error);
      this._showToast(`Failed to add device: ${error.message}`);
    }
  }

  async _updateDevice(deviceName, deviceConfig) {
    try {
      await this._hass.callWS({
        type: 'pv_optimizer/update_device',
        device_name: deviceName,
        device: deviceConfig,
      });
      
      this._editingDevice = null;
      await this._getConfigWithRetry();
      this._showToast('Device updated successfully');
    } catch (error) {
      console.error('Failed to update device:', error);
      this._showToast(`Failed to update device: ${error.message}`);
    }
  }

  async _deleteDevice(deviceName) {
    if (!confirm(`Are you sure you want to delete device "${deviceName}"?`)) {
      return;
    }
    
    try {
      await this._hass.callWS({
        type: 'pv_optimizer/delete_device',
        device_name: deviceName,
      });
      
      await this._getConfigWithRetry();
      this._showToast('Device deleted successfully');
    } catch (error) {
      console.error('Failed to delete device:', error);
      this._showToast(`Failed to delete device: ${error.message}`);
    }
  }

  _showToast(message) {
    const event = new CustomEvent('hass-notification', {
      detail: { message },
      bubbles: true,
      composed: true,
    });
    this.dispatchEvent(event);
  }

  _updateFormData(field, value) {
    this._deviceFormData = {
      ...this._deviceFormData,
      [field]: value,
    };
    this.render();
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

  _handleDeviceSubmit() {
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

  render() {
    if (!this.shadowRoot) return;

    const styles = `
      <style>
        :host {
          display: block;
          padding: 16px;
          background-color: var(--primary-background-color);
        }

        .header {
          font-size: 24px;
          font-weight: 500;
          margin-bottom: 24px;
          color: var(--primary-text-color);
        }

        .card {
          background-color: var(--ha-card-background, var(--card-background-color, white));
          border-radius: var(--ha-card-border-radius, 12px);
          box-shadow: var(--ha-card-box-shadow, 0 2px 4px rgba(0,0,0,0.1));
          padding: 20px;
          margin-bottom: 20px;
        }

        .card-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 16px;
          font-size: 18px;
          font-weight: 600;
          color: var(--primary-text-color);
        }

        .card-content {
          color: var(--primary-text-color);
        }

        .config-group {
          margin-bottom: 16px;
        }

        .config-label {
          font-weight: 500;
          margin-bottom: 4px;
          font-size: 14px;
        }

        .config-value {
          padding: 8px 12px;
          background-color: var(--secondary-background-color);
          border-radius: 4px;
          font-family: monospace;
          font-size: 13px;
        }

        button {
          background-color: var(--primary-color);
          color: white;
          border: none;
          padding: 8px 16px;
          border-radius: 4px;
          cursor: pointer;
          font-size: 14px;
          font-weight: 500;
          transition: all 0.2s;
        }

        button:hover {
          background-color: var(--primary-color-dark, #0288d1);
        }

        button.secondary {
          background-color: var(--secondary-text-color);
        }

        button.danger {
          background-color: var(--error-color, #f44336);
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
        }

        .device-details {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
          gap: 8px;
          font-size: 13px;
          color: var(--secondary-text-color);
        }

        .device-actions {
          display: flex;
          gap: 8px;
        }

        .empty-state {
          text-align: center;
          padding: 40px 20px;
          color: var(--secondary-text-color);
        }

        .modal-overlay {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background-color: rgba(0, 0, 0, 0.5);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 999;
        }

        .modal {
          background-color: var(--ha-card-background, var(--card-background-color, white));
          border-radius: 8px;
          padding: 24px;
          max-width: 600px;
          width: 100%;
          max-height: 90vh;
          overflow-y: auto;
        }

        .modal-header {
          font-size: 20px;
          font-weight: 600;
          margin-bottom: 20px;
          color: var(--primary-text-color);
        }

        .modal-actions {
          display: flex;
          justify-content: flex-end;
          gap: 12px;
          margin-top: 20px;
          padding-top: 20px;
          border-top: 1px solid var(--divider-color);
        }

        .form-group {
          margin-bottom: 16px;
        }

        label {
          display: block;
          margin-bottom: 6px;
          color: var(--primary-text-color);
          font-weight: 500;
          font-size: 14px;
        }

        input[type="text"],
        input[type="number"],
        select {
          width: 100%;
          padding: 10px;
          border: 1px solid var(--divider-color);
          border-radius: 4px;
          background-color: var(--primary-background-color);
          color: var(--primary-text-color);
          font-size: 14px;
          box-sizing: border-box;
        }

        input[type="text"]:focus,
        input[type="number"]:focus,
        select:focus {
          outline: none;
          border-color: var(--primary-color);
        }

        input[type="checkbox"] {
          width: 18px;
          height: 18px;
          margin-right: 8px;
        }

        .checkbox-group {
          display: flex;
          align-items: center;
          margin-bottom: 16px;
        }

        .checkbox-group label {
          margin-bottom: 0;
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

        .error {
          color: var(--error-color);
          background-color: rgba(244, 67, 54, 0.1);
          padding: 12px;
          border-radius: 4px;
          margin: 8px 0;
        }

        .loading {
          text-align: center;
          padding: 20px;
          color: var(--secondary-text-color);
        }
      </style>
    `;

    if (this._error) {
      this.shadowRoot.innerHTML = `
        ${styles}
        <div class="header">PV Optimizer</div>
        <div class="card">
          <div class="error">
            <strong>Error:</strong> ${this._error}
            <div><button onclick="location.reload()" style="margin-top: 12px;">Refresh</button></div>
          </div>
        </div>
      `;
      return;
    }

    if (this._loading) {
      this.shadowRoot.innerHTML = `
        ${styles}
        <div class="header">PV Optimizer</div>
        <div class="card">
          <div class="loading">Loading configuration...</div>
        </div>
      `;
      return;
    }

    const globalConfig = this._config?.global_config || {};
    const devices = this._config?.devices || [];

    this.shadowRoot.innerHTML = `
      ${styles}
      <div class="header">⚡ PV Optimizer</div>
      
      ${this._renderGlobalConfig(globalConfig)}
      ${this._renderDeviceList(devices)}
      ${this._editingGlobal ? this._renderGlobalConfigModal(globalConfig) : ''}
      ${this._showAddDevice || this._editingDevice ? this._renderDeviceModal() : ''}
    `;

    this._attachEventListeners();
  }

  _renderGlobalConfig(globalConfig) {
    return `
      <div class="card">
        <div class="card-header">
          <span>Global Configuration</span>
          <button onclick="this.getRootNode().host._editGlobalConfig()">✏️ Edit</button>
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
      </div>
    `;
  }

  _renderDeviceList(devices) {
    return `
      <div class="card">
        <div class="card-header">
          <span>Devices (${devices.length})</span>
          <button onclick="this.getRootNode().host._showAddDeviceModal()">➕ Add Device</button>
        </div>
        <div class="card-content">
          ${devices.length === 0 ? `
            <div class="empty-state">
              <div style="font-size: 48px; margin-bottom: 16px;">📱</div>
              <div>No devices configured yet</div>
              <div style="margin-top: 8px; font-size: 14px;">
                Click "Add Device" to configure your first controllable device
              </div>
            </div>
          ` : `
            <div class="device-list">
              ${devices.map(device => this._renderDeviceCard(device)).join('')}
            </div>
          `}
        </div>
      </div>
    `;
  }

  _renderDeviceCard(deviceData) {
    const device = deviceData.config;
    const state = deviceData.state || {};
    
    return `
      <div class="device-card">
        <div class="device-info">
          <div class="device-name">
            ${device.optimization_enabled ? '🟢' : '🔴'} ${device.name}
          </div>
          <div class="device-details">
            <div><strong>Type:</strong> ${device.type}</div>
            <div><strong>Priority:</strong> ${device.priority}</div>
            <div><strong>Power:</strong> ${device.power}W</div>
            <div><strong>Status:</strong> ${state.is_on ? 'ON' : 'OFF'}</div>
            <div><strong>Locked:</strong> ${state.is_locked ? 'Yes' : 'No'}</div>
            ${state.measured_power_avg ? `
              <div><strong>Measured:</strong> ${state.measured_power_avg.toFixed(1)}W</div>
            ` : ''}
          </div>
        </div>
        <div class="device-actions">
          <button onclick="this.getRootNode().host._editDevice('${device.name}')">✏️</button>
          <button class="danger" onclick="this.getRootNode().host._deleteDevice('${device.name}')">🗑️</button>
        </div>
      </div>
    `;
  }

  _renderGlobalConfigModal(globalConfig) {
    return `
      <div class="modal-overlay" onclick="if(event.target === this) this.getRootNode().host._cancelEdit()">
        <div class="modal" onclick="event.stopPropagation()">
          <div class="modal-header">Edit Global Configuration</div>
          <form id="global-config-form">
            <div class="form-group">
              <label>PV Surplus Sensor *</label>
              <input type="text" id="surplus_sensor" value="${globalConfig.surplus_sensor_entity_id || ''}" required>
              <div class="help-text">The sensor that provides the PV surplus/deficit value</div>
            </div>
            
            <div class="form-group">
              <label>Sliding Window Size (minutes) *</label>
              <input type="number" id="sliding_window" value="${globalConfig.sliding_window_size || 5}" 
                     min="1" max="60" required>
              <div class="help-text">Time window for averaging power measurements</div>
            </div>
            
            <div class="form-group">
              <label>Optimization Cycle Time (seconds) *</label>
              <input type="number" id="cycle_time" value="${globalConfig.optimization_cycle_time || 60}" 
                     min="10" max="300" required>
              <div class="help-text">How often the optimizer runs</div>
            </div>
            
            <div class="modal-actions">
              <button type="button" class="secondary" onclick="this.getRootNode().host._cancelEdit()">
                Cancel
              </button>
              <button type="submit">Save</button>
            </div>
          </form>
        </div>
      </div>
    `;
  }

  _renderDeviceModal() {
    const isEdit = !!this._editingDevice;
    const formData = this._deviceFormData;

    return `
      <div class="modal-overlay" onclick="if(event.target === this) this.getRootNode().host._cancelEdit()">
        <div class="modal" onclick="event.stopPropagation()">
          <div class="modal-header">${isEdit ? `Edit: ${formData.name}` : 'Add New Device'}</div>
          <form id="device-form">
            <div class="form-group">
              <label>Device Name *</label>
              <input type="text" id="device_name" value="${formData.name}" 
                     ${isEdit ? 'readonly' : ''} required>
              <div class="help-text">A unique name for this device</div>
            </div>

            <div class="form-group">
              <label>Device Type *</label>
              <select id="device_type" onchange="this.getRootNode().host._handleTypeChange(this.value)">
                <option value="switch" ${formData.type === 'switch' ? 'selected' : ''}>Switch</option>
                <option value="numeric" ${formData.type === 'numeric' ? 'selected' : ''}>Numeric</option>
              </select>
              <div class="help-text">Switch: On/Off control | Numeric: Value adjustment</div>
            </div>

            <div class="form-group">
              <label>Priority * (1=highest, 10=lowest)</label>
              <input type="number" id="priority" value="${formData.priority}" min="1" max="10" required>
            </div>

            <div class="form-group">
              <label>Nominal Power (W) *</label>
              <input type="number" id="power" value="${formData.power}" min="0" step="0.1" required>
            </div>

            <div class="checkbox-group">
              <input type="checkbox" id="optimization_enabled" 
                     ${formData.optimization_enabled ? 'checked' : ''}>
              <label>Optimization Enabled</label>
            </div>

            <div id="switch-fields" style="display: ${formData.type === 'switch' ? 'block' : 'none'};">
              <div class="form-group">
                <label>Switch Entity *</label>
                <input type="text" id="switch_entity" value="${formData.switch_entity_id || ''}">
                <div class="help-text">e.g., switch.my_device</div>
              </div>
              
              <div class="checkbox-group">
                <input type="checkbox" id="invert_switch" ${formData.invert_switch ? 'checked' : ''}>
                <label>Invert Switch Logic</label>
              </div>
            </div>

            <div id="numeric-fields" style="display: ${formData.type === 'numeric' ? 'block' : 'none'};">
              <div class="form-group">
                <label>Numeric Targets</label>
                <div class="numeric-targets" id="numeric-targets">
                  ${this._renderNumericTargets(formData.numeric_targets || [])}
                </div>
                <button type="button" onclick="this.getRootNode().host._addNumericTarget()">
                  ➕ Add Target
                </button>
              </div>
            </div>

            <div class="form-group">
              <label>Measured Power Sensor (optional)</label>
              <input type="text" id="measured_power" value="${formData.measured_power_entity_id || ''}">
              <div class="help-text">Sensor providing actual power consumption</div>
            </div>

            <div class="form-group">
              <label>Power Threshold (W)</label>
              <input type="number" id="power_threshold" value="${formData.power_threshold || 100}" 
                     min="0" step="0.1">
            </div>

            <div class="form-group">
              <label>Minimum On Time (minutes)</label>
              <input type="number" id="min_on_time" value="${formData.min_on_time || 0}" min="0">
            </div>

            <div class="form-group">
              <label>Minimum Off Time (minutes)</label>
              <input type="number" id="min_off_time" value="${formData.min_off_time || 0}" min="0">
            </div>

            <div class="modal-actions">
              <button type="button" class="secondary" onclick="this.getRootNode().host._cancelEdit()">
                Cancel
              </button>
              <button type="submit">${isEdit ? 'Update' : 'Add'} Device</button>
            </div>
          </form>
        </div>
      </div>
    `;
  }

  _renderNumericTargets(targets) {
    if (targets.length === 0) {
      return '<div class="help-text">No targets configured. Click "Add Target" to add one.</div>';
    }
    
    return targets.map((target, index) => `
      <div class="numeric-target">
        <div class="target-header">
          <span>Target ${index + 1}</span>
          <button type="button" class="danger" onclick="this.getRootNode().host._removeNumericTarget(${index})">
            🗑️ Remove
          </button>
        </div>
        <div class="form-group">
          <label>Entity ID *</label>
          <input type="text" value="${target.numeric_entity_id || ''}" 
                 onchange="this.getRootNode().host._updateNumericTarget(${index}, 'numeric_entity_id', this.value)" required>
        </div>
        <div class="form-group">
          <label>Activated Value *</label>
          <input type="number" value="${target.activated_value || ''}" step="any"
                 onchange="this.getRootNode().host._updateNumericTarget(${index}, 'activated_value', parseFloat(this.value))" required>
        </div>
        <div class="form-group">
          <label>Deactivated Value *</label>
          <input type="number" value="${target.deactivated_value || ''}" step="any"
                 onchange="this.getRootNode().host._updateNumericTarget(${index}, 'deactivated_value', parseFloat(this.value))" required>
        </div>
      </div>
    `).join('');
  }

  _attachEventListeners() {
    const globalForm = this.shadowRoot.querySelector('#global-config-form');
    if (globalForm) {
      globalForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const config = {
          surplus_sensor_entity_id: this.shadowRoot.querySelector('#surplus_sensor').value,
          sliding_window_size: parseInt(this.shadowRoot.querySelector('#sliding_window').value),
          optimization_cycle_time: parseInt(this.shadowRoot.querySelector('#cycle_time').value),
        };
        this._saveGlobalConfig(config);
      });
    }

    const deviceForm = this.shadowRoot.querySelector('#device-form');
    if (deviceForm) {
      deviceForm.addEventListener('submit', (e) => {
        e.preventDefault();
        
        this._deviceFormData.name = this.shadowRoot.querySelector('#device_name').value;
        this._deviceFormData.type = this.shadowRoot.querySelector('#device_type').value;
        this._deviceFormData.priority = parseInt(this.shadowRoot.querySelector('#priority').value);
        this._deviceFormData.power = parseFloat(this.shadowRoot.querySelector('#power').value);
        this._deviceFormData.optimization_enabled = this.shadowRoot.querySelector('#optimization_enabled').checked;
        this._deviceFormData.measured_power_entity_id = this.shadowRoot.querySelector('#measured_power').value;
        this._deviceFormData.power_threshold = parseFloat(this.shadowRoot.querySelector('#power_threshold').value);
        this._deviceFormData.min_on_time = parseInt(this.shadowRoot.querySelector('#min_on_time').value);
        this._deviceFormData.min_off_time = parseInt(this.shadowRoot.querySelector('#min_off_time').value);
        
        if (this._deviceFormData.type === 'switch') {
          this._deviceFormData.switch_entity_id = this.shadowRoot.querySelector('#switch_entity').value;
          this._deviceFormData.invert_switch = this.shadowRoot.querySelector('#invert_switch').checked;
        }
        
        this._handleDeviceSubmit();
      });
    }
  }

  _editGlobalConfig() {
    this._editingGlobal = true;
    this.render();
  }

  _showAddDeviceModal() {
    this._showAddDevice = true;
    this._deviceFormData = this._getEmptyDeviceForm();
    this.render();
  }

  _editDevice(deviceName) {
    const deviceData = this._config.devices.find(d => d.config.name === deviceName);
    if (deviceData) {
      this._deviceFormData = { ...deviceData.config };
      this._editingDevice = deviceData;
      this.render();
    }
  }

  _cancelEdit() {
    this._editingGlobal = false;
    this._editingDevice = null;
    this._showAddDevice = false;
    this.render();
  }

  _handleTypeChange(newType) {
    this._deviceFormData.type = newType;
    this.render();
  }
}

customElements.define('pv-optimizer-panel', PvOptimizerPanel);
