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
    this._availableEntities = {};
    this._deviceTypes = ['switch', 'numeric'];
  }

  set hass(hass) {
    this._hass = hass;
    this._checkWebSocket();
    this.render();
  }

  get hass() {
    return this._hass;
  }

  set panel(panel) {
    this._panel = panel;
    this.render();
  }

  async connectedCallback() {
    this.render();
    await this._getConfigWithRetry();
  }

  _checkWebSocket() {
    if (this._hass && !this._hass.connection) {
      this._error = 'WebSocket connection not available. Please ensure Home Assistant is properly connected.';
      this._loading = false;
      this.render();
      return false;
    }
    return true;
  }

  async _getConfigWithRetry(retryCount = 0) {
    if (!this._hass || !this._checkWebSocket()) {
      return;
    }

    try {
      this._loading = true;
      this._error = null;
      this.render();

      await new Promise(resolve => setTimeout(resolve, 1000));

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
        this._error = `Failed to load configuration: ${error.message || 'Connection error'}`;
        this._loading = false;
        this.render();
      }
    }
  }

  async _loadAvailableEntities(domain = null) {
    if (!this._hass) return;
    
    try {
      const response = await this._hass.callWS({
        type: 'pv_optimizer/get_available_entities',
        domain: domain,
      });
      
      if (domain) {
        this._availableEntities[domain] = response.entities || [];
      } else {
        this._availableEntities['all'] = response.entities || [];
      }
      
      this.render();
    } catch (error) {
      console.error('Failed to load entities:', error);
    }
  }

  async _saveGlobalConfig(config) {
    if (!this._hass) return;
    
    try {
      await this._hass.callWS({
        type: 'pv_optimizer/set_config',
        data: config,
      });
      
      this._editingGlobal = false;
      await this._getConfigWithRetry();
      this._showMessage('Global configuration saved successfully', 'success');
    } catch (error) {
      console.error('Failed to save global config:', error);
      this._showMessage(`Failed to save: ${error.message}`, 'error');
    }
  }

  async _addDevice(deviceConfig) {
    if (!this._hass) return;
    
    try {
      await this._hass.callWS({
        type: 'pv_optimizer/add_device',
        device: deviceConfig,
      });
      
      this._showAddDevice = false;
      await this._getConfigWithRetry();
      this._showMessage('Device added successfully', 'success');
    } catch (error) {
      console.error('Failed to add device:', error);
      this._showMessage(`Failed to add device: ${error.message}`, 'error');
    }
  }

  async _updateDevice(deviceName, deviceConfig) {
    if (!this._hass) return;
    
    try {
      await this._hass.callWS({
        type: 'pv_optimizer/update_device',
        device_name: deviceName,
        device: deviceConfig,
      });
      
      this._editingDevice = null;
      await this._getConfigWithRetry();
      this._showMessage('Device updated successfully', 'success');
    } catch (error) {
      console.error('Failed to update device:', error);
      this._showMessage(`Failed to update device: ${error.message}`, 'error');
    }
  }

  async _deleteDevice(deviceName) {
    if (!this._hass) return;
    
    if (!confirm(`Are you sure you want to delete device "${deviceName}"?`)) {
      return;
    }
    
    try {
      await this._hass.callWS({
        type: 'pv_optimizer/delete_device',
        device_name: deviceName,
      });
      
      await this._getConfigWithRetry();
      this._showMessage('Device deleted successfully', 'success');
    } catch (error) {
      console.error('Failed to delete device:', error);
      this._showMessage(`Failed to delete device: ${error.message}`, 'error');
    }
  }

  _showMessage(message, type = 'info') {
    // Simple message display - could be enhanced with toast notifications
    const messageEl = this.shadowRoot.querySelector('.message-container');
    if (messageEl) {
      messageEl.innerHTML = `<div class="message message-${type}">${message}</div>`;
      setTimeout(() => {
        messageEl.innerHTML = '';
      }, 5000);
    }
  }

  _formatConfigValue(value) {
    if (value === null || value === undefined) {
      return 'Not configured';
    }
    return String(value);
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

  _handleDeviceSubmit(e, isEdit = false, originalName = null) {
    e.preventDefault();
    const formData = new FormData(e.target);
    
    const deviceConfig = {
      name: formData.get('name'),
      type: formData.get('type'),
      priority: parseInt(formData.get('priority')),
      power: parseFloat(formData.get('power')),
      optimization_enabled: formData.get('optimization_enabled') === 'on',
      measured_power_entity_id: formData.get('measured_power_entity_id') || null,
      power_threshold: parseFloat(formData.get('power_threshold')) || 100,
      min_on_time: parseInt(formData.get('min_on_time')) || 0,
      min_off_time: parseInt(formData.get('min_off_time')) || 0,
    };
    
    if (deviceConfig.type === 'switch') {
      deviceConfig.switch_entity_id = formData.get('switch_entity_id');
      deviceConfig.invert_switch = formData.get('invert_switch') === 'on';
    } else if (deviceConfig.type === 'numeric') {
      // Parse numeric targets from form
      const targets = [];
      const targetCount = parseInt(formData.get('target_count') || '0');
      
      for (let i = 0; i < targetCount; i++) {
        const entityId = formData.get(`target_${i}_entity_id`);
        const activatedValue = formData.get(`target_${i}_activated_value`);
        const deactivatedValue = formData.get(`target_${i}_deactivated_value`);
        
        if (entityId && activatedValue && deactivatedValue) {
          targets.push({
            numeric_entity_id: entityId,
            activated_value: parseFloat(activatedValue),
            deactivated_value: parseFloat(deactivatedValue),
          });
        }
      }
      
      deviceConfig.numeric_targets = targets;
    }
    
    if (isEdit) {
      this._updateDevice(originalName, deviceConfig);
    } else {
      this._addDevice(deviceConfig);
    }
  }

  render() {
    if (!this.shadowRoot) return;

    const hasConnection = this._checkWebSocket();
    const loading = this._loading && hasConnection;
    const error = this._error;
    const config = this._config || {};
    const globalConfig = config.global_config || {};
    const devices = config.devices || [];

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          padding: 16px;
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
          background-color: var(--primary-background-color);
          min-height: 100vh;
        }

        .message-container {
          position: fixed;
          top: 70px;
          right: 20px;
          z-index: 1000;
        }

        .message {
          padding: 12px 20px;
          border-radius: 4px;
          box-shadow: 0 2px 8px rgba(0,0,0,0.2);
          animation: slideIn 0.3s ease-out;
        }

        .message-success {
          background-color: var(--success-color, #4caf50);
          color: white;
        }

        .message-error {
          background-color: var(--error-color, #f44336);
          color: white;
        }

        @keyframes slideIn {
          from {
            transform: translateX(400px);
            opacity: 0;
          }
          to {
            transform: translateX(0);
            opacity: 1;
          }
        }

        .header {
          font-size: 24px;
          font-weight: bold;
          margin-bottom: 24px;
          color: var(--primary-text-color);
        }

        .card {
          background-color: var(--ha-card-background, var(--card-background-color, white));
          border-radius: var(--ha-card-border-radius, 12px);
          box-shadow: var(--ha-card-box-shadow, 0px 2px 4px rgba(0, 0, 0, 0.1));
          padding: 20px;
          margin-bottom: 20px;
        }

        .card-header {
          font-size: 18px;
          font-weight: 600;
          margin-bottom: 16px;
          color: var(--primary-text-color);
          display: flex;
          justify-content: space-between;
          align-items: center;
        }

        .card-actions {
          display: flex;
          gap: 8px;
        }

        button {
          background-color: var(--primary-color, #03a9f4);
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
          transform: translateY(-1px);
          box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        }

        button.secondary {
          background-color: var(--secondary-text-color, #757575);
        }

        button.secondary:hover {
          background-color: var(--disabled-text-color, #9e9e9e);
        }

        button.danger {
          background-color: var(--error-color, #f44336);
        }

        button.danger:hover {
          background-color: #d32f2f;
        }

        button:disabled {
          opacity: 0.5;
          cursor: not-allowed;
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
          border: 1px solid var(--divider-color, #e0e0e0);
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
          border-color: var(--primary-color, #03a9f4);
          box-shadow: 0 0 0 2px rgba(3, 169, 244, 0.1);
        }

        input[type="checkbox"] {
          width: 18px;
          height: 18px;
          margin-right: 8px;
          cursor: pointer;
        }

        .checkbox-group {
          display: flex;
          align-items: center;
          margin-bottom: 16px;
        }

        .checkbox-group label {
          margin-bottom: 0;
          cursor: pointer;
        }

        .value {
          padding: 10px 12px;
          background-color: var(--secondary-background-color, #f5f5f5);
          border-radius: 4px;
          color: var(--primary-text-color);
          font-family: 'Courier New', monospace;
          font-size: 13px;
        }

        .error {
          color: var(--error-color, #f44336);
          background-color: rgba(244, 67, 54, 0.1);
          padding: 12px;
          border-radius: 4px;
          margin: 8px 0;
          border-left: 4px solid var(--error-color, #f44336);
        }

        .loading {
          color: var(--secondary-text-color, #666);
          font-style: italic;
          text-align: center;
          padding: 20px;
        }

        .success {
          color: var(--success-color, #4caf50);
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .status-indicator {
          width: 12px;
          height: 12px;
          border-radius: 50%;
          display: inline-block;
        }

        .status-connected {
          background-color: var(--success-color, #4caf50);
        }

        .status-disconnected {
          background-color: var(--error-color, #f44336);
        }

        .status-loading {
          background-color: var(--warning-color, #ff9800);
          animation: pulse 1.5s infinite;
        }

        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }

        .device-list {
          display: grid;
          gap: 12px;
        }

        .device-card {
          background-color: var(--secondary-background-color, #f0f0f0);
          border-left: 4px solid var(--primary-color, #03a9f4);
          padding: 16px;
          border-radius: 6px;
          display: flex;
          justify-content: space-between;
          align-items: start;
          transition: all 0.2s;
        }

        .device-card:hover {
          box-shadow: 0 2px 8px rgba(0,0,0,0.1);
          transform: translateY(-2px);
        }

        .device-info {
          flex: 1;
        }

        .device-name {
          font-size: 16px;
          font-weight: 600;
          color: var(--primary-text-color);
          margin-bottom: 8px;
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

        .device-detail-label {
          font-weight: 500;
        }

        .device-actions {
          display: flex;
          gap: 8px;
          flex-shrink: 0;
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
          padding: 20px;
        }

        .modal {
          background-color: var(--ha-card-background, white);
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
          border-top: 1px solid var(--divider-color, #e0e0e0);
        }

        .numeric-targets {
          border: 1px solid var(--divider-color, #e0e0e0);
          border-radius: 4px;
          padding: 12px;
          margin-bottom: 16px;
          background-color: var(--primary-background-color);
        }

        .numeric-target {
          padding: 12px;
          border: 1px solid var(--divider-color, #e0e0e0);
          border-radius: 4px;
          margin-bottom: 12px;
          background-color: var(--secondary-background-color, #fafafa);
        }

        .numeric-target-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 12px;
          font-weight: 500;
        }

        .help-text {
          font-size: 12px;
          color: var(--secondary-text-color);
          margin-top: 4px;
          font-style: italic;
        }

        .empty-state {
          text-align: center;
          padding: 40px 20px;
          color: var(--secondary-text-color);
        }

        .empty-state-icon {
          font-size: 48px;
          margin-bottom: 16px;
          opacity: 0.5;
        }
      </style>
      
      <div class="message-container"></div>

      <div class="header">
        <span class="status-indicator ${error ? 'status-disconnected' : (loading ? 'status-loading' : 'status-connected')}"></span>
        PV Optimizer
      </div>
      
      ${error ? `
        <div class="card">
          <div class="error">
            <strong>Connection Error:</strong><br>
            ${error}<br>
            <button onclick="location.reload()" style="margin-top: 12px;">Refresh Page</button>
          </div>
        </div>
      ` : loading ? `
        <div class="card">
          <div class="loading">🔄 Loading configuration...</div>
        </div>
      ` : `
        ${this._renderGlobalConfig(globalConfig)}
        ${this._renderDeviceList(devices)}
      `}
      
      ${this._editingGlobal ? this._renderGlobalConfigModal(globalConfig) : ''}
      ${this._showAddDevice ? this._renderDeviceModal() : ''}
      ${this._editingDevice ? this._renderDeviceModal(this._editingDevice) : ''}
    `;

    this._attachEventListeners();
  }

  _renderGlobalConfig(globalConfig) {
    return `
      <div class="card">
        <div class="card-header">
          <span>Global Configuration</span>
          <button onclick="this.getRootNode().host._editGlobalConfig()">
            ✏️ Edit
          </button>
        </div>
        
        <div class="form-group">
          <label>PV Surplus Sensor</label>
          <div class="value">${this._formatConfigValue(globalConfig.surplus_sensor_entity_id)}</div>
        </div>
        
        <div class="form-group">
          <label>Sliding Window Size</label>
          <div class="value">${this._formatConfigValue(globalConfig.sliding_window_size)} minutes</div>
        </div>
        
        <div class="form-group">
          <label>Optimization Cycle Time</label>
          <div class="value">${this._formatConfigValue(globalConfig.optimization_cycle_time)} seconds</div>
        </div>
      </div>
    `;
  }

  _renderDeviceList(devices) {
    return `
      <div class="card">
        <div class="card-header">
          <span>Devices (${devices.length})</span>
          <button onclick="this.getRootNode().host._showAddDeviceModal()">
            ➕ Add Device
          </button>
        </div>
        
        ${devices.length === 0 ? `
          <div class="empty-state">
            <div class="empty-state-icon">📱</div>
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
            <div class="device-detail">
              <span class="device-detail-label">Type:</span>
              <span>${device.type}</span>
            </div>
            <div class="device-detail">
              <span class="device-detail-label">Priority:</span>
              <span>${device.priority}</span>
            </div>
            <div class="device-detail">
              <span class="device-detail-label">Power:</span>
              <span>${device.power}W</span>
            </div>
            <div class="device-detail">
              <span class="device-detail-label">Status:</span>
              <span>${state.is_on ? 'ON' : 'OFF'}</span>
            </div>
            <div class="device-detail">
              <span class="device-detail-label">Locked:</span>
              <span>${state.is_locked ? 'Yes' : 'No'}</span>
            </div>
            ${state.measured_power_avg ? `
              <div class="device-detail">
                <span class="device-detail-label">Measured:</span>
                <span>${state.measured_power_avg.toFixed(1)}W</span>
              </div>
            ` : ''}
          </div>
        </div>
        <div class="device-actions">
          <button onclick="this.getRootNode().host._editDevice('${device.name}')">
            ✏️ Edit
          </button>
          <button class="danger" onclick="this.getRootNode().host._deleteDevice('${device.name}')">
            🗑️ Delete
          </button>
        </div>
      </div>
    `;
  }

  _renderGlobalConfigModal(globalConfig) {
    return `
      <div class="modal-overlay" onclick="if(event.target === this) this.getRootNode().host._cancelEdit()">
        <div class="modal">
          <div class="modal-header">Edit Global Configuration</div>
          <form id="global-config-form">
            <div class="form-group">
              <label for="surplus_sensor_entity_id">PV Surplus Sensor *</label>
              <input type="text" id="surplus_sensor_entity_id" name="surplus_sensor_entity_id" 
                     value="${globalConfig.surplus_sensor_entity_id || ''}" required>
              <div class="help-text">The sensor that provides the PV surplus/deficit value</div>
            </div>
            
            <div class="form-group">
              <label for="sliding_window_size">Sliding Window Size (minutes) *</label>
              <input type="number" id="sliding_window_size" name="sliding_window_size" 
                     value="${globalConfig.sliding_window_size || 5}" min="1" max="60" required>
              <div class="help-text">Time window for averaging power measurements</div>
            </div>
            
            <div class="form-group">
              <label for="optimization_cycle_time">Optimization Cycle Time (seconds) *</label>
              <input type="number" id="optimization_cycle_time" name="optimization_cycle_time" 
                     value="${globalConfig.optimization_cycle_time || 60}" min="10" max="300" required>
              <div class="help-text">How often the optimizer runs</div>
            </div>
            
            <div class="modal-actions">
              <button type="button" class="secondary" onclick="this.getRootNode().host._cancelEdit()">
                Cancel
              </button>
              <button type="submit">
                Save
              </button>
            </div>
          </form>
        </div>
      </div>
    `;
  }

  _renderDeviceModal(deviceData = null) {
    const isEdit = !!deviceData;
    const device = isEdit ? deviceData.config : {
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
      numeric_targets: []
    };
    
    return `
      <div class="modal-overlay" onclick="if(event.target === this) this.getRootNode().host._cancelEdit()">
        <div class="modal">
          <div class="modal-header">${isEdit ? `Edit Device: ${device.name}` : 'Add New Device'}</div>
          <form id="device-form">
            <div class="form-group">
              <label for="name">Device Name *</label>
              <input type="text" id="name" name="name" value="${device.name}" required 
                     ${isEdit ? 'readonly' : ''}>
              <div class="help-text">A unique name for this device</div>
            </div>
            
            <div class="form-group">
              <label for="type">Device Type *</label>
              <select id="type" name="type" onchange="this.getRootNode().host._handleTypeChange(this.value)" required>
                <option value="switch" ${device.type === 'switch' ? 'selected' : ''}>Switch</option>
                <option value="numeric" ${device.type === 'numeric' ? 'selected' : ''}>Numeric</option>
              </select>
              <div class="help-text">Switch: On/Off control | Numeric: Value adjustment</div>
            </div>
            
            <div class="form-group">
              <label for="priority">Priority *</label>
              <input type="number" id="priority" name="priority" value="${device.priority}" 
                     min="1" max="10" required>
              <div class="help-text">1 = highest priority, 10 = lowest</div>
            </div>
            
            <div class="form-group">
              <label for="power">Nominal Power (W) *</label>
              <input type="number" id="power" name="power" value="${device.power}" 
                     min="0" step="0.1" required>
              <div class="help-text">The device's power consumption in Watts</div>
            </div>
            
            <div class="checkbox-group">
              <input type="checkbox" id="optimization_enabled" name="optimization_enabled" 
                     ${device.optimization_enabled ? 'checked' : ''}>
              <label for="optimization_enabled">Optimization Enabled</label>
            </div>
            
            <div id="switch-fields" style="display: ${device.type === 'switch' ? 'block' : 'none'};">
              <div class="form-group">
                <label for="switch_entity_id">Switch Entity *</label>
                <input type="text" id="switch_entity_id" name="switch_entity_id" 
                       value="${device.switch_entity_id || ''}">
                <div class="help-text">e.g., switch.my_device</div>
              </div>
              
              <div class="checkbox-group">
                <input type="checkbox" id="invert_switch" name="invert_switch" 
                       ${device.invert_switch ? 'checked' : ''}>
                <label for="invert_switch">Invert Switch Logic</label>
              </div>
            </div>
            
            <div id="numeric-fields" style="display: ${device.type === 'numeric' ? 'block' : 'none'};">
              <div class="form-group">
                <label>Numeric Targets *</label>
                <div class="numeric-targets" id="numeric-targets-container">
                  ${this._renderNumericTargets(device.numeric_targets || [])}
                </div>
                <button type="button" onclick="this.getRootNode().host._addNumericTarget()">
                  ➕ Add Target
                </button>
              </div>
            </div>
            
            <div class="form-group">
              <label for="measured_power_entity_id">Measured Power Sensor (optional)</label>
              <input type="text" id="measured_power_entity_id" name="measured_power_entity_id" 
                     value="${device.measured_power_entity_id || ''}">
              <div class="help-text">Sensor providing actual power consumption</div>
            </div>
            
            <div class="form-group">
              <label for="power_threshold">Power Threshold (W)</label>
              <input type="number" id="power_threshold" name="power_threshold" 
                     value="${device.power_threshold || 100}" min="0" step="0.1">
              <div class="help-text">Threshold to determine if device is ON</div>
            </div>
            
            <div class="form-group">
              <label for="min_on_time">Minimum On Time (minutes)</label>
              <input type="number" id="min_on_time" name="min_on_time" 
                     value="${device.min_on_time || 0}" min="0">
              <div class="help-text">Device must stay on for at least this long</div>
            </div>
            
            <div class="form-group">
              <label for="min_off_time">Minimum Off Time (minutes)</label>
              <input type="number" id="min_off_time" name="min_off_time" 
                     value="${device.min_off_time || 0}" min="0">
              <div class="help-text">Device must stay off for at least this long</div>
            </div>
            
            <input type="hidden" name="target_count" id="target_count" value="${(device.numeric_targets || []).length}">
            
            <div class="modal-actions">
              <button type="button" class="secondary" onclick="this.getRootNode().host._cancelEdit()">
                Cancel
              </button>
              <button type="submit">
                ${isEdit ? 'Update' : 'Add'} Device
              </button>
            </div>
          </form>
        </div>
      </div>
    `;
  }

  _renderNumericTargets(targets) {
    if (targets.length === 0) {
      return '<div class="help-text" style="padding: 12px;">No targets configured. Click "Add Target" to add one.</div>';
    }
    
    return targets.map((target, index) => `
      <div class="numeric-target">
        <div class="numeric-target-header">
          <span>Target ${index + 1}</span>
          <button type="button" class="danger" onclick="this.getRootNode().host._removeNumericTarget(${index})">
            🗑️ Remove
          </button>
        </div>
        <div class="form-group">
          <label for="target_${index}_entity_id">Entity ID *</label>
          <input type="text" id="target_${index}_entity_id" name="target_${index}_entity_id" 
                 value="${target.numeric_entity_id || ''}" required>
        </div>
        <div class="form-group">
          <label for="target_${index}_activated_value">Activated Value *</label>
          <input type="number" id="target_${index}_activated_value" name="target_${index}_activated_value" 
                 value="${target.activated_value || ''}" step="any" required>
        </div>
        <div class="form-group">
          <label for="target_${index}_deactivated_value">Deactivated Value *</label>
          <input type="number" id="target_${index}_deactivated_value" name="target_${index}_deactivated_value" 
                 value="${target.deactivated_value || ''}" step="any" required>
        </div>
      </div>
    `).join('');
  }

  _attachEventListeners() {
    const globalForm = this.shadowRoot.querySelector('#global-config-form');
    if (globalForm) {
      globalForm.addEventListener('submit', (e) => this._handleGlobalConfigSubmit(e));
    }
    
    const deviceForm = this.shadowRoot.querySelector('#device-form');
    if (deviceForm) {
      deviceForm.addEventListener('submit', (e) => {
        const isEdit = !!this._editingDevice;
        const originalName = isEdit ? this._editingDevice.config.name : null;
        this._handleDeviceSubmit(e, isEdit, originalName);
      });
    }
  }

  _editGlobalConfig() {
    this._editingGlobal = true;
    this.render();
  }

  _showAddDeviceModal() {
    this._showAddDevice = true;
    this.render();
  }

  _editDevice(deviceName) {
    const deviceData = this._config.devices.find(d => d.config.name === deviceName);
    if (deviceData) {
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
    const switchFields = this.shadowRoot.querySelector('#switch-fields');
    const numericFields = this.shadowRoot.querySelector('#numeric-fields');
    
    if (switchFields && numericFields) {
      switchFields.style.display = newType === 'switch' ? 'block' : 'none';
      numericFields.style.display = newType === 'numeric' ? 'block' : 'none';
    }
  }

  _addNumericTarget() {
    const container = this.shadowRoot.querySelector('#numeric-targets-container');
    const countInput = this.shadowRoot.querySelector('#target_count');
    
    if (container && countInput) {
      const currentCount = parseInt(countInput.value) || 0;
      const newTarget = {
        numeric_entity_id: '',
        activated_value: '',
        deactivated_value: ''
      };
      
      // Get current targets
      const currentTargets = [];
      for (let i = 0; i < currentCount; i++) {
        const entityId = this.shadowRoot.querySelector(`#target_${i}_entity_id`)?.value || '';
        const activatedValue = this.shadowRoot.querySelector(`#target_${i}_activated_value`)?.value || '';
        const deactivatedValue = this.shadowRoot.querySelector(`#target_${i}_deactivated_value`)?.value || '';
        
        if (entityId) {
          currentTargets.push({
            numeric_entity_id: entityId,
            activated_value: parseFloat(activatedValue),
            deactivated_value: parseFloat(deactivatedValue)
          });
        }
      }
      
      currentTargets.push(newTarget);
      container.innerHTML = this._renderNumericTargets(currentTargets);
      countInput.value = currentTargets.length;
    }
  }

  _removeNumericTarget(index) {
    const container = this.shadowRoot.querySelector('#numeric-targets-container');
    const countInput = this.shadowRoot.querySelector('#target_count');
    
    if (container && countInput) {
      const currentCount = parseInt(countInput.value) || 0;
      const targets = [];
      
      for (let i = 0; i < currentCount; i++) {
        if (i !== index) {
          const entityId = this.shadowRoot.querySelector(`#target_${i}_entity_id`)?.value || '';
          const activatedValue = this.shadowRoot.querySelector(`#target_${i}_activated_value`)?.value || '';
          const deactivatedValue = this.shadowRoot.querySelector(`#target_${i}_deactivated_value`)?.value || '';
          
          if (entityId) {
            targets.push({
              numeric_entity_id: entityId,
              activated_value: parseFloat(activatedValue),
              deactivated_value: parseFloat(deactivatedValue)
            });
          }
        }
      }
      
      container.innerHTML = this._renderNumericTargets(targets);
      countInput.value = targets.length;
    }
  }
}

customElements.define('pv-optimizer-panel', PvOptimizerPanel);
