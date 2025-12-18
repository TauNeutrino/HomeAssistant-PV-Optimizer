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
      _currentTab: { type: String, state: true },
      _historyData: { type: Object, state: true },
      _statisticsData: { type: Object, state: true },
      _apexChartsLoaded: { type: Boolean, state: true },
      _chartTimeRange: { type: String, state: true },
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
    this._currentTab = 'overview';  // overview | charts | stats
    this._apexChartsLoaded = false;
    this._chartTimeRange = 'today'; // today | 7days
    this._historyData = null;
    this._statisticsData = null;
  }

  async connectedCallback() {
    super.connectedCallback();
    await this._loadTranslations();
    this._loadApexCharts();
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

  async _loadTranslations() {
    try {
      const language = this.hass.language || 'en';
      const response = await fetch(`/pv_optimizer_translations/${language}.json`);
      if (!response.ok) {
        // Fallback to English
        const fallback = await fetch(`/pv_optimizer_translations/en.json`);
        this._translations = (await fallback.json()).panel || {};
      } else {
        this._translations = (await response.json()).panel || {};
      }
    } catch (err) {
      console.warn('Failed to load translations, using English fallback');
      // Hardcoded English fallback
      this._translations = {};
    }
  }

  async _loadApexCharts() {
    if (window.ApexCharts) {
      this._apexChartsLoaded = true;
      return;
    }

    if (document.getElementById('apexcharts-script')) {
      return;
    }

    const script = document.createElement('script');
    script.id = 'apexcharts-script';
    script.src = 'https://cdn.jsdelivr.net/npm/apexcharts';
    script.onload = () => {
      this._apexChartsLoaded = true;
      this._updateCharts();
    };
    document.head.appendChild(script);
  }

  // Utility method to get translated string
  t(path, fallback = '') {
    if (!this._translations) return fallback || path;
    const keys = path.split('.');
    let value = this._translations;
    for (const key of keys) {
      value = value?.[key];
      if (value === undefined) return fallback || path;
    }
    return value;
  }

  /**
   * Error boundary wrapper for render methods
   * @param {Function} renderFn - Function to execute with error handling
   * @param {string} componentName - Name of component for error logging
   * @param {*} fallback - Fallback content to render on error
   * @returns {TemplateResult} Rendered content or fallback
   */
  _renderWithErrorBoundary(renderFn, componentName = 'Component', fallback = null) {
    try {
      return renderFn();
    } catch (error) {
      console.error(`[PV Optimizer] Error rendering ${componentName}:`, error);

      // Store error for potential reporting
      if (!this._renderErrors) this._renderErrors = [];
      this._renderErrors.push({
        component: componentName,
        error: error.message,
        timestamp: new Date()
      });

      // Return fallback or default error UI
      return fallback || html`
        <div class="error-boundary">
          <ha-icon icon="mdi:alert-circle" class="error-icon"></ha-icon>
          <div class="error-content">
            <h3>Error Loading ${componentName}</h3>
            <p>${error.message || 'An unexpected error occurred'}</p>
            <mwc-button @click=${() => this._fetchConfig()}>
              <ha-icon icon="mdi:refresh"></ha-icon>
              Retry
            </mwc-button>
          </div>
        </div>
      `;
    }
  }

  /**
   * Safe data accessor with fallback
   * @param {Object} obj - Object to access
   * @param {string} path - Dot-notation path
   * @param {*} defaultValue - Default value if path not found
   * @returns {*} Value or default
   */
  _safeGet(obj, path, defaultValue = null) {
    if (!obj) return defaultValue;
    const value = path.split('.').reduce((acc, part) => acc?.[part], obj);
    return value !== undefined && value !== null ? value : defaultValue;
  }

  async _handleResetDevice(e, deviceName) {
    e.stopPropagation();
    if (!confirm(`Reset target state for ${deviceName}? This will clear the manual lock.`)) return;

    try {
      await this.hass.callWS({
        type: "pv_optimizer/reset_device",
        device_name: deviceName
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
    this._destroyCharts();
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
      // Sort devices by priority (ascending)
      const sortedDevices = response.devices
        ? Object.values(response.devices).sort((a, b) => (a.config?.priority || 99) - (b.config?.priority || 99))
        : [];

      this._config = {
        ...response,
        devices: sortedDevices,
      };

      if (response?.optimizer_stats?.last_update_timestamp) {
        this._lastUpdateTimestamp = new Date(response.optimizer_stats.last_update_timestamp);
        this._updateElapsedTime();
      } else {
        this._lastUpdateTimestamp = null;
      }
      this._lastUpdateTimestamp = new Date();

      // Also refresh active tab data
      if (this._currentTab === 'charts') {
        this._fetchHistory();
      } else if (this._currentTab === 'stats') {
        this._fetchStatistics();
      }
    } catch (err) {
      console.error("Error fetching config:", err);
      this._error = err.message;
    } finally {
      this._loading = false;
    }
  }

  async _fetchHistory() {
    try {
      // Calculate hours based on time range selection
      let hours;
      if (this._chartTimeRange === 'today') {
        // Calculate hours since midnight
        const now = new Date();
        const midnight = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        hours = Math.ceil((now - midnight) / (1000 * 60 * 60)); // Convert ms to hours
      } else if (this._chartTimeRange === '7days') {
        hours = 7 * 24; // 168 hours
      } else {
        hours = 24; // Default fallback
      }

      const response = await this.hass.callWS({
        type: "pv_optimizer/history",
        hours: hours
      });
      this._historyData = response;
    } catch (err) {
      console.error("Error fetching history:", err);
    }
  }

  async _fetchStatistics() {
    try {
      const response = await this.hass.callWS({
        type: "pv_optimizer/statistics"
      });
      this._statisticsData = response;
    } catch (err) {
      console.error("Error fetching statistics:", err);
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
    const devices = (entity?.attributes?.device_details || [])
      .sort((a, b) => (a.priority || 99) - (b.priority || 99));

    // Enrich devices with measured power from device state
    return devices.map(device => {
      // Find matching device in config to get state
      const deviceData = this._config?.devices?.find(d => d.config.name === device.name);
      const state = deviceData?.state || {};

      return {
        ...device,
        measured_power: state.power_measured_average || state.power_measured || device.power || 0,
        is_available: state.is_available !== undefined ? state.is_available : true
      };
    });
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
      <div class="pvo-header">
        ${this.narrow ? html`
          <ha-menu-button
            .hass=${this.hass}
            .narrow=${this.narrow}
          ></ha-menu-button>
        ` : ""}
        
        <div class="pvo-title">
          <ha-icon icon="mdi:solar-power"></ha-icon>
          <span>PV Optimizer</span>
          ${this._config?.version ? html`<span class="pvo-version">v${this._config.version}</span>` : ""}
        </div>
        
        <div class="pvo-spacer"></div>
        
        <ha-button @click=${this._openConfiguration}>
          <ha-icon slot="icon" icon="mdi:cog"></ha-icon>
          ${this.t('header.configuration', 'Configuration')}
        </ha-button>
        
        <div class="pvo-status ${ready ? 'ready' : 'error'}">
          <ha-icon icon=${ready ? "mdi:check-circle" : "mdi:alert-circle"}></ha-icon>
          <span>${ready ? this.t('header.system_ready', 'System Ready') : this.t('header.system_issue', 'System Issue')}</span>
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

    return html`
      <ha-card class="system-overview-card">
        <div class="card-header">
          <div class="name">${this.t('system_overview.title', 'System Overview')}</div>
          <div class="tab-selector">
            <button 
              class="${this._currentTab === 'overview' ? 'active' : ''}" 
              @click=${() => this._currentTab = 'overview'}
            >
              ${this.t('system_overview.tab_overview', 'Overview')}
            </button>
            <button 
              class="${this._currentTab === 'charts' ? 'active' : ''}" 
              @click=${() => { this._currentTab = 'charts'; this._fetchHistory(); }}
            >
              ${this.t('system_overview.tab_charts', 'Charts')}
            </button>
            <button 
              class="${this._currentTab === 'stats' ? 'active' : ''}" 
              @click=${() => { this._currentTab = 'stats'; this._fetchStatistics(); }}
            >
              ${this.t('system_overview.tab_statistics', 'Statistics')}
            </button>
          </div>
        </div>
        <div class="card-content">
          ${this._currentTab === 'overview' ? this._renderOverview() : ''}
          ${this._currentTab === 'charts' ? this._renderCharts() : ''}
          ${this._currentTab === 'stats' ? this._renderStatistics() : ''}
        </div>
      </ha-card>
    `;
  }

  _renderOverview() {
    return this._renderWithErrorBoundary(
      () => {
        const stats = this._config.optimizer_stats;
        if (!stats) {
          return html`
            <div class="loading-state">
              <ha-icon icon="mdi:loading" class="spinning"></ha-icon>
              <p>Loading statistics...</p>
            </div>
          `;
        }

        const items = [
          {
            label: this.t('system_overview.current_surplus', 'Current Surplus'),
            value: `${this._safeGet(stats, 'surplus_current', 0).toFixed(0)} W`,
            rawValue: stats.surplus_current,
            icon: "mdi:flash"
          },
          {
            label: this.t('system_overview.avg_surplus', 'Avg Surplus'),
            value: `${this._safeGet(stats, 'surplus_average', 0).toFixed(0)} W`,
            rawValue: stats.surplus_average,
            icon: "mdi:chart-bell-curve-cumulative"
          },
          {
            label: this.t('system_overview.potential_load', 'Rated Power'),
            value: `${this._safeGet(stats, 'power_rated_total', 0).toFixed(0)} W`,
            icon: "mdi:lightning-bolt-outline"
          },
          {
            label: this.t('system_overview.active_load', 'Active Load'),
            value: `${this._safeGet(stats, 'power_measured_total', 0).toFixed(0)} W`,
            icon: "mdi:lightning-bolt"
          },
          {
            label: this.t('system_overview.last_update', 'Last Update'),
            value: this._lastUpdateTimestamp ? this._lastUpdateTimestamp.toLocaleTimeString() : 'N/A',
            icon: "mdi:clock-outline"
          },
          {
            label: this.t('system_overview.age', 'Age'),
            value: this._elapsedSeconds !== null ? `${this._elapsedSeconds}s` : 'N/A',
            icon: "mdi:timer-outline"
          },
        ];

        return html`
          <div class="stats-grid">
            ${items.map(item => html`
              <div class="stat-item">
                <div class="stat-icon">
                  <ha-icon icon="${item.icon}"></ha-icon>
                </div>
                <div class="stat-content">
                  <span class="stat-label">${item.label}</span>
                  <span class="stat-value ${item.rawValue < 0 ? 'negative' : ''}">${item.value}</span>
                </div>
              </div>
            `)}
          </div>
        `;
      },
      'System Overview'
    );
  }

  _renderCharts() {
    return this._renderWithErrorBoundary(
      () => {
        if (!this._historyData) {
          return html`<div class="loading-state">
            <ha-icon icon="mdi:loading" class="spinning"></ha-icon>
            <p>Loading charts...</p>
          </div>`;
        }

        const snapshots = this._historyData.snapshots || [];

        if (snapshots.length === 0) {
          return html`<div class="loading-state">
            <ha-icon icon="mdi:information-outline"></ha-icon>
            <p>No historical data available yet.</p>
            <p style="font-size: 0.9em; color: var(--secondary-text-color);">Data will appear after the optimizer runs for a few minutes.</p>
          </div>`;
        }

        return html`
          <div class="chart-controls">
            <label style="display: flex; align-items: center; gap: 8px; font-size: 0.9em;">
              <span>Time Range:</span>
              <select 
                .value=${this._chartTimeRange}
                @change=${(e) => {
            this._chartTimeRange = e.target.value;
            this._fetchHistory();
          }}
                style="padding: 4px 8px; border: 1px solid var(--divider-color); border-radius: 4px; background: var(--card-background-color); color: var(--primary-text-color); cursor: pointer;"
              >
                <option value="today">Today</option>
                <option value="7days">Last 7 Days</option>
              </select>
            </label>
          </div>
          <div class="charts-container">
            <div class="chart-wrapper">
              <h3 class="chart-title">${this.t('charts.surplus_trend', 'Surplus Trend')}</h3>
              <div id="surplus-chart" class="chart-div"></div>
            </div>

            <div class="chart-wrapper">
              <h3 class="chart-title">${this.t('charts.active_devices_power', 'Active Devices Power')}</h3>
              <div id="device-chart" class="chart-div"></div>
            </div>
          </div>
        `;
      },
      'Charts'
    );
  }

  updated(changedProps) {
    super.updated(changedProps);

    if (changedProps.has('_currentTab')) {
      const oldTab = changedProps.get('_currentTab');
      if (oldTab === 'charts' && this._currentTab !== 'charts') {
        this._destroyCharts();
      }
    }

    if (this._currentTab === 'charts') {
      // Only update charts if history data changed or we just switched to charts tab
      if (changedProps.has('_historyData') || changedProps.has('_currentTab')) {
        // Small delay to ensure DOM is ready
        setTimeout(() => this._updateCharts(), 0);
      }
    }
  }

  async _updateCharts() {
    if (!this._historyData?.snapshots?.length || !this._apexChartsLoaded) return;

    // Ensure elements exist
    const surplusEl = this.shadowRoot.getElementById('surplus-chart');
    const deviceEl = this.shadowRoot.getElementById('device-chart');

    if (!surplusEl || !deviceEl) return;

    const snapshots = this._historyData.snapshots;

    // Prepare Data
    const surplusSeries = [{
      name: 'Avg Surplus',
      data: snapshots.map(s => [new Date(s.timestamp).getTime(), s.surplus_average || s.averaged_surplus || 0])
    }, {
      name: 'Power Budget',
      data: snapshots.map(s => [new Date(s.timestamp).getTime(), s.budget_real || s.power_budget || 0])
    }];

    // Get unique devices
    const deviceNames = new Set();
    snapshots.forEach(s => {
      if (s.active_devices && Array.isArray(s.active_devices)) {
        s.active_devices.forEach(d => deviceNames.add(d.name));
      }
    });

    // Build device color map
    const deviceColorMap = {};
    if (this._config?.devices) {
      this._config.devices.forEach(d => {
        deviceColorMap[d.config.name] = d.config.device_color || '#4CAF50';
      });
    }

    // Build series and colors in parallel to ensure correct mapping
    const deviceSeriesData = [];
    const deviceColorsData = [];

    Array.from(deviceNames).forEach(name => {
      const color = deviceColorMap[name] || this._getDeviceColor(deviceSeriesData.length);
      deviceColorsData.push(color);

      const seriesData = snapshots.map(s => {
        const device = s.active_devices?.find(d => d.name === name);
        return [new Date(s.timestamp).getTime(), device ? (device.power_measured || device.power || 0) : 0];
      });

      deviceSeriesData.push({
        name: name,
        data: seriesData
      });
    });

    // Check if we have any data
    const hasData = deviceSeriesData.some(series => series.data.some(point => point[1] > 0));

    // If no device data, add a dummy series to preserve x-axis
    if (deviceSeriesData.length === 0) {
      deviceSeriesData.push({
        name: 'No Activity',
        data: snapshots.map(s => [new Date(s.timestamp).getTime(), 0])
      });
      deviceColorsData.push('transparent');
    }

    // Common options
    const commonOptions = {
      chart: {
        height: 300,
        toolbar: {
          show: true,
          tools: {
            download: false,
            selection: true,
            zoom: true,
            zoomin: true,
            zoomout: true,
            pan: true,
            reset: true
          }
        },
        animations: { enabled: false },
        background: 'transparent',
        foreColor: 'var(--primary-text-color)',
        group: 'pv-optimizer-charts' // Sync zoom/pan across charts
      },
      theme: { mode: 'dark' }, // Assume dark mode for now, could be dynamic
      stroke: { curve: 'stepline', width: 2 },
      xaxis: {
        type: 'datetime',
        tooltip: { enabled: false },
        axisBorder: { show: false },
        axisTicks: { show: false }
      },
      grid: {
        borderColor: 'rgba(255,255,255,0.1)',
        strokeDashArray: 3
      },
      tooltip: {
        theme: 'dark',
        x: {
          format: 'dd.MM.yyyy HH:mm'
        }
      },
      legend: { position: 'top' }
    };

    // Render Surplus Chart
    this._renderApexChart('surplus-chart', {
      ...commonOptions,
      chart: { ...commonOptions.chart, type: 'line', id: 'surplus-chart' },
      colors: ['#2196f3', '#ff9800'],
      yaxis: {
        min: 0,
        labels: {
          formatter: (value) => Math.round(value) + 'W'
        }
      },
      series: surplusSeries
    });

    // Render Device Chart
    this._renderApexChart('device-chart', {
      ...commonOptions,
      chart: { ...commonOptions.chart, type: 'area', stacked: true, id: 'device-chart' },
      colors: deviceColorsData,
      stroke: { curve: 'stepline', width: 0 },
      fill: { type: 'solid', opacity: 0.95 },
      dataLabels: { enabled: false },
      yaxis: {
        min: 0,
        max: hasData ? undefined : 100, // Default max to prevent weird scaling when empty
        labels: {
          formatter: (value) => Math.round(value) + 'W'
        }
      },
      series: deviceSeriesData
    });
  }

  _renderApexChart(elementId, options) {
    const element = this.shadowRoot.getElementById(elementId);
    if (!element) return;

    if (!this._charts) this._charts = {};

    // Check if chart instance exists
    if (this._charts[elementId]) {
      try {
        // Destroy and recreate to ensure colors and all options are applied correctly
        this._charts[elementId].destroy();
        this._createChart(elementId, element, options);
      } catch (e) {
        console.warn('Failed to update chart, recreating...', e);
        this._createChart(elementId, element, options);
      }
    } else {
      this._createChart(elementId, element, options);
    }
  }

  _createChart(id, element, options) {
    if (window.ApexCharts) {
      this._charts[id] = new window.ApexCharts(element, options);
      this._charts[id].render();
    }
  }

  _destroyCharts() {
    if (this._charts) {
      Object.values(this._charts).forEach(chart => {
        try {
          chart.destroy();
        } catch (e) {
          console.warn('Error destroying chart:', e);
        }
      });
      this._charts = {};
    }
  }

  async _handleColorChange(e, deviceName) {
    const newColor = e.target.value;
    try {
      await this.hass.callWS({
        type: "pv_optimizer/update_device_color",
        device_name: deviceName,
        color: newColor
      });
      // Refresh config to update UI
      await this._fetchConfig();
    } catch (err) {
      console.error('Failed to update device color:', err);
    }
  }


  _renderStatistics() {
    if (!this._statisticsData) return html`<div class="loading">Loading statistics...</div>`;

    const stats = this._statisticsData;

    const items = [
      { label: this.t('statistics.total_events', 'Total Optimization Events'), value: stats.total_events ?? '-', icon: "mdi:counter" },
      { label: this.t('statistics.utilization_rate', 'Surplus Utilization'), value: stats.utilization_rate !== undefined ? `${stats.utilization_rate}%` : '-', icon: "mdi:percent" },
      { label: this.t('statistics.most_active', 'Most Active Device'), value: stats.most_active_device || '-', icon: "mdi:trophy" },
      { label: this.t('statistics.peak_time', 'Peak Optimization Time'), value: stats.peak_hour !== undefined ? `${stats.peak_hour}:00` : '-', icon: "mdi:clock-time-eight" },
      { label: this.t('statistics.snapshots', 'Data Points'), value: stats.snapshots_count ?? '-', icon: "mdi:database" },
    ];

    return html`
      <div class="stats-grid">
        ${items.map(item => html`
          <div class="stat-item">
            <div class="stat-icon">
              <ha-icon icon="${item.icon}"></ha-icon>
            </div>
            <div class="stat-content">
              <span class="stat-label">${item.label}</span>
              <span class="stat-value">${item.value}</span>
            </div>
          </div>
        `)}
      </div>
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
    let devices = [...this._getIdealDevices(sensorKey)];
    let budget = this._getPowerBudget(sensorKey === 'real_ideal_devices' ? 'real' : 'simulation');

    // Frontend-only fix: Include timing-locked ON devices in the budget view
    if (this._config?.devices) {
      const lockedOnDevices = this._config.devices.filter(d => {
        const state = d.state || {};
        const config = d.config || {};
        const isTimingLocked = state.is_locked_timing;
        const isOn = state.is_on;
        const alreadyInList = devices.some(existing => existing.name === config.name);
        return isOn && isTimingLocked && !alreadyInList;
      });

      lockedOnDevices.forEach(d => {
        const config = d.config || {};
        const state = d.state || {};

        // Determine power to use based on card type
        // Simulation: Always use nominal power
        // Real: Use measured power if available, else nominal
        let powerToUse;
        if (sensorKey === 'simulation_ideal_devices') {
          powerToUse = config.power || 0;
        } else {
          powerToUse = state.power_measured_average !== undefined ? state.power_measured_average : (config.power || 0);
        }

        budget += powerToUse;
        devices.push({
          name: config.name,
          power: config.power || 0,
          measured_power: state.power_measured_average,
          priority: config.priority || 5
        });
      });

      // Re-sort to ensure correct order
      devices.sort((a, b) => (a.priority || 99) - (b.priority || 99));
    }

    // Calculate total power for the bar
    const totalPower = devices.reduce((sum, d) => {
      // Unavailable devices don't contribute to power usage
      if (!d.is_available) return sum;

      let powerToUse;
      if (sensorKey === 'simulation_ideal_devices') {
        powerToUse = d.power || 0;
      } else {
        powerToUse = d.measured_power !== undefined ? d.measured_power : (d.power || 0);
      }
      return sum + powerToUse;
    }, 0);
    const usagePercent = budget > 0 ? Math.min((totalPower / budget) * 100, 100) : 0;

    return html`
      <ha-card class="ideal-devices-card" style="border-top: 4px solid var(${colorVar})">
        <h1 class="card-header">
          <ha-icon icon=${icon}></ha-icon>
          <span style="flex: 1; margin-left: 10px;">${title}</span>
          ${sensorKey === 'simulation_ideal_devices' ? html`
            <div style="margin-left: auto; display: flex; align-items: center;">
              <ha-textfield
                label="Additional Surplus (W)"
                type="number"
                .value=${this._config.optimizer_stats?.surplus_offset || 0}
                @change=${this._handleSimulationOffsetChange}
                icon="mdi:plus-minus"
                style="width: 100%;"
              >
                <ha-icon slot="leadingIcon" icon="mdi:plus-minus"></ha-icon>
              </ha-textfield>
            </div>
          ` : ''}
        </h1>
        <div class="card-content">

          <div class="budget-bar">
            <div class="budget-info">
              <span>${this.t('real_optimization.power_budget', 'Power Budget')}</span>
              <span style="${budget < 0 ? 'color: var(--error-color); font-weight: 600;' : ''}">${budget.toFixed(0)} W</span>
            </div>
            <div class="progress-track" style="display: flex; overflow: hidden;">
              ${budget > 0 ? html`
                ${devices.map((device, index) => {
      // Unavailable devices show no bar segment
      if (!device.is_available) return '';

      let power;
      if (sensorKey === 'simulation_ideal_devices') {
        power = device.power || 0;
      } else {
        power = device.measured_power !== undefined ? device.measured_power : (device.power || 0);
      }
      const width = Math.min((power / budget) * 100, 100);
      // Get device color from config
      const deviceData = this._config?.devices?.find(d => d.config.name === device.name);
      const color = deviceData?.config?.device_color || this._getDeviceColor(index);
      return html`<div class="progress-fill" style="width: ${width}%; background-color: ${color}; border-right: 1px solid rgba(255,255,255,0.2);" title="${device.name}: ${power}W"></div>`;
    })}
                ${(() => {
          const usedPower = devices.reduce((sum, d) => {
            // Unavailable devices don't use power
            if (!d.is_available) return sum;

            let power;
            if (sensorKey === 'simulation_ideal_devices') {
              power = d.power || 0;
            } else {
              power = d.measured_power !== undefined ? d.measured_power : (d.power || 0);
            }
            return sum + power;
          }, 0);
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
        ? html`<div class="empty-state">${this.t('common.no_active_devices', 'No active devices')}</div>`
        : html`
            <div class="device-list-compact">
              ${devices.map((device, index) => {
          // Use measured power for Real, nominal for Simulation
          // But use 0W for unavailable devices
          let power;
          if (!device.is_available) {
            power = 0;
          } else if (sensorKey === 'simulation_ideal_devices') {
            power = device.power || 0;
          } else {
            power = device.measured_power !== undefined ? device.measured_power : (device.power || 0);
          }

          const isUnavailable = !device.is_available;
          // Get device color from config
          const deviceData = this._config?.devices?.find(d => d.config.name === device.name);
          const color = deviceData?.config?.device_color || this._getDeviceColor(index);

          return html`
                  <div class="device-row ${isUnavailable ? 'unavailable' : ''}">
                    <div class="device-main">
                      <div style="width: 8px; height: 8px; border-radius: 50%; background-color: ${isUnavailable ? 'var(--disabled-text-color)' : color}; margin-right: 8px; display: inline-block;"></div>
                      <span class="device-name" style="${isUnavailable ? 'text-decoration: line-through; opacity: 0.6;' : ''}">${device.name}</span>
                      <span class="device-meta">${this.t('common.prio', 'Prio')} ${device.priority}</span>
                    </div>
                    <div class="device-power" style="${isUnavailable ? 'opacity: 0.6;' : ''}">${power.toFixed(0)} W</div>
                  </div>
                `;
        })}
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
          ${this.t('comparison.title', 'Comparison')}
        </h1>
        <div class="table-container">
          <table>
            <thead>
              <tr>
                <th>${this.t('comparison.device', 'Device')}</th>
                <th>${this.t('comparison.priority', 'Priority')}</th>
                <th class="text-right">${this.t('comparison.power', 'Power')}</th>
                <th class="text-center">${this.t('comparison.real', 'Real')}</th>
                <th class="text-center">${this.t('comparison.simulation', 'Sim')}</th>
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

    // Check availability flag from backend (default to true if undefined for backward compatibility)
    const isAvailable = state.is_available !== undefined ? state.is_available : true;
    const isUnavailable = !isAvailable;

    return html`
      <ha-card class="device-card ${isOn ? 'active' : ''}">
        <div class="device-header">
      <div class="device-title" style="${isUnavailable ? 'text-decoration: line-through; opacity: 0.6;' : ''}">
        <div style="display: flex; align-items: center; gap: 8px;">
          <ha-icon icon=${isOn ? "mdi:power-plug" : "mdi:power-plug-off"} class="device-icon"></ha-icon>
          ${state.device_id
        ? html`<a href="/config/devices/device/${state.device_id}" style="color: inherit; text-decoration: none;">${device.name}</a>`
        : device.name
      }
        </div>
      </div>
          <div class="lock-icons">
            ${state.is_locked_timing ? html`<ha-icon icon="mdi:timer-lock" title="Timing Lock: Device cannot be controlled due to Min On/Off time constraints" class="lock-icon"></ha-icon>` : ''}
            ${state.is_locked_manual ? html`<span title="${state.lock_reason || 'Manual Lock: Device state was manually changed by user'}" class="lock-icon"><ha-icon icon="mdi:account-lock"></ha-icon></span>` : ''}
            ${(state.is_locked_timing || state.is_locked_manual || state.is_fault_locked) ? html`
              <ha-icon-button
                icon="mdi:lock-open-variant"
                label="Reset Lock"
                title="Clear manual lock and allow optimizer to control this device"
                class="reset-icon"
                @click=${(e) => this._handleResetDevice(e, device.name)}
              ></ha-icon-button>
            ` : ''}
          </div>
        </div>
        
        <div class="device-body">
        <div class="chip-container">
          <input 
            type="color" 
            value="${device.device_color || '#4CAF50'}" 
            @input=${(e) => this._handleColorChange(e, device.name)}
            style="width: 20px; height: 20px; border: none; background: none; cursor: pointer; padding: 0;"
            title="Click to change device color"
          />
          <span class="chip type">${device.type}</span>
          <span class="chip priority">${this.t('common.prio', 'Prio')} ${device.priority}</span>
        </div>
          
          <div class="device-stats">
            <div class="stat">
              <span class="label">${this.t('managed_devices.rated', 'Rated')}</span>
              <span class="value">${device.power} W</span>
            </div>
            ${state.power_measured_average ? html`
              <div class="stat">
                <span class="label">${this.t('managed_devices.measured', 'Measured')}</span>
                <span class="value">${state.power_measured_average.toFixed(0)} W</span>
              </div>
            ` : ''}
          </div>
        </div>

        <div class="device-footer">
          <div class="status-badges">
            <span 
              class="badge ${device.optimization_enabled !== false ? 'auto' : 'manual'}"
              @click=${(e) => this._handleToggleOptimization(e, device)}
              style="cursor: pointer;"
              title="${device.optimization_enabled !== false ? 'Optimization Active: Click to disable and control manually' : 'Manual Control: Click to enable automatic optimization'}"
            >
              ${device.optimization_enabled !== false ? this.t('managed_devices.auto', 'Auto') : this.t('managed_devices.manual', 'Manual')}
            </span>
            <span 
              class="badge ${device.simulation_active ? 'sim' : 'sim-disabled'}"
              @click=${(e) => this._handleToggleSimulation(e, device)}
              style="cursor: pointer; ${!device.simulation_active ? 'background-color: var(--warning-color, #ff9800); color: black;' : ''}"
              title="${device.simulation_active ? 'Simulation Enabled: Device participates in what-if scenarios' : 'Simulation Disabled: Device excluded from simulation calculations'}"
            >
              ${this.t('managed_devices.sim', 'Sim')}
            </span>
          </div>
        </div>
      </ha-card>
    `;
  }

  async _handleToggleOptimization(e, device) {
    e.stopPropagation();
    const badge = e.currentTarget;

    // Disable badge during operation
    badge.style.opacity = '0.5';
    badge.style.pointerEvents = 'none';

    try {
      const newValue = device.optimization_enabled === false; // Toggle
      await this._updateDeviceConfig(device.name, { optimization_enabled: newValue });

      // Show success toast
      this._showToast(`${device.name}: Optimization ${newValue ? 'enabled' : 'disabled'}`, 'success');
    } catch (err) {
      // Restore on error
      badge.style.opacity = '';
      badge.style.pointerEvents = '';
    } finally {
      // Always restore after operation
      badge.style.opacity = '';
      badge.style.pointerEvents = '';
    }
  }

  async _handleToggleSimulation(e, device) {
    e.stopPropagation();
    const badge = e.currentTarget;

    // Disable badge during operation
    badge.style.opacity = '0.5';
    badge.style.pointerEvents = 'none';

    try {
      const newValue = !device.simulation_active; // Toggle
      await this._updateDeviceConfig(device.name, { simulation_active: newValue });

      // Show success toast
      this._showToast(`${device.name}: Simulation ${newValue ? 'enabled' : 'disabled'}`, 'success');
    } catch (err) {
      // Restore on error
      badge.style.opacity = '';
      badge.style.pointerEvents = '';
    } finally {
      // Always restore after operation
      badge.style.opacity = '';
      badge.style.pointerEvents = '';
    }
  }

  async _updateDeviceConfig(deviceName, updates) {
    try {
      await this.hass.callWS({
        type: "pv_optimizer/update_device_config",
        device_name: deviceName,
        updates: updates
      });
      // Refresh config to reflect changes
      await new Promise(resolve => setTimeout(resolve, 100));
      await this._fetchConfig();
      // Force re-render to restore badge content
      this.requestUpdate();
    } catch (err) {
      console.error("Failed to update device config:", err);
      this._showToast(`Failed to update ${deviceName}: ${err.message}`, 'error');
      throw err; // Re-throw so callers can handle
    }
  }

  _showToast(message, type = 'info') {
    const event = new CustomEvent('hass-notification', {
      detail: {
        message: message,
        duration: type === 'error' ? 5000 : 3000,
      },
      bubbles: true,
      composed: true,
    });
    this.dispatchEvent(event);
  }

  render() {
    if (this._loading && !this._config) {
      return html`<div class="loading-screen"><ha-circular-progress active></ha-circular-progress></div>`;
    }

    return html`
      ${this._renderHeader()}
      
      <div class="content">
        ${this._error ? this._renderErrorCard() : ""}

        <div class="dashboard-grid">
          <div class="main-column">
            ${this._renderGlobalConfigCard()}
            
            <div class="view-toggle">
              <ha-button @click=${this._toggleComparison}>
                <ha-icon slot="icon" icon=${this._showComparison ? "mdi:view-dashboard" : "mdi:table-large"}></ha-icon>
                ${this._showComparison ? this.t('comparison.view_cards', 'View Cards') : this.t('comparison.view_comparison', 'View Comparison')}
              </ha-button>
            </div>

            ${this._showComparison
        ? this._renderComparisonTable()
        : html`
                  <div class="dual-grid">
                    ${this._renderIdealDevicesCard(this.t('real_optimization.title', 'Real Optimization'), "real_ideal_devices", "mdi:lightning-bolt", "--success-color")}
                    ${this._renderIdealDevicesCard(this.t('simulation.title', 'Simulation'), "simulation_ideal_devices", "mdi:flask", "--info-color")}
                  </div>
                `}
          </div>

          <div class="devices-column">
            <h2 class="section-title">${this.t('managed_devices.title', 'Managed Devices')}</h2>
            <div class="devices-grid">
              ${this._config?.devices
        ?.map(d => this._renderDeviceCard(d))}
            </div>
          </div>
        </div>
      </div>
    `;
  }

  static get styles() {
    return css`
      :host {
        display: block;
        --ha-card-border-radius: 12px;
        --success-color: var(--success-color, #4caf50);
        --info-color: var(--info-color, #2196f3);
        --warning-color: var(--warning-color, #ff9800);
        --error-color: var(--error-color, #f44336);
      }

      /* Layout */
      .content {
        padding: 16px;
      }

      .dashboard-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
        gap: 24px;
        margin-top: 24px;
        align-items: start;
      }

      .main-column {
        display: flex;
        flex-direction: column;
        gap: 24px;
        min-width: 400px;
      }

      .dual-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
        gap: 16px;
      }

      .devices-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
        gap: 16px;
        align-items: start;
      }

      /* PV Optimizer Header */
      .pvo-header {
        display: flex;
        align-items: center;
        gap: 16px;
        height: 64px;
        padding: 0 16px;
        background-color: var(--app-header-background-color, var(--primary-color));
        color: var(--app-header-text-color, var(--text-primary-color));
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
      }
      
      .pvo-title {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 20px;
        font-weight: 400;
      }
      
      .pvo-spacer {
        flex: 1;
      }
      
      .pvo-version {
        font-size: 12px;
        opacity: 0.8;
        margin-left: 8px;
        font-weight: normal;
        background: rgba(255, 255, 255, 0.2);
        padding: 2px 6px;
        border-radius: 4px;
      }
      
      .pvo-status {
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 14px;
        font-weight: 500;
        padding: 6px 12px;
        border-radius: 16px;
        background: rgba(255, 255, 255, 0.1);
      }
      .pvo-status.ready { color: var(--success-color); }
      .pvo-status.error { color: var(--error-color); }

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
        grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
        gap: 16px;
        padding: 16px;
      }
      .stat-item {
        display: flex;
        align-items: center;
        gap: 12px;
      }
      .stat-content {
        display: flex;
        flex-direction: column;
        justify-content: center;
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
      .lock-icons {
        display: flex;
        gap: 4px;
      }
      .lock-icon {
        color: var(--warning-color);
        --mdc-icon-size: 20px;
      }
      .reset-icon {
        color: var(--primary-color);
        --mdc-icon-size: 20px;
        margin-left: 8px;
        cursor: pointer;
        opacity: 0.8;
        transition: opacity 0.2s;
      }
      .reset-icon:hover {
        opacity: 1;
      }
      .device-title {
        font-weight: 500;
        display: flex;
        align-items: center;
        gap: 8px;
      }
      .device-title a {
        color: inherit;
        text-decoration: none;
        border-bottom: none;
      }
      .device-title a:hover {
        text-decoration: underline;
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
        justify-content: space-between;
        font-size: 13px;
        gap: 8px;
      }
      .device-stats .stat {
        white-space: nowrap;
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
      .badge.success, .badge.auto { background: rgba(76, 175, 80, 0.15); color: var(--success-color); }
      .badge.warning, .badge.manual { background: rgba(255, 152, 0, 0.15); color: var(--warning-color); }
      .badge.info, .badge.sim { background: rgba(33, 150, 243, 0.15); color: var(--info-color); }

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

      /* Device List */
      .device-list-compact {
        display: flex;
        flex-direction: column;
        gap: 8px;
        padding: 0 16px 16px;
      }
      .device-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-size: 13px;
      }
      .device-main {
        display: flex;
        align-items: center;
        gap: 8px;
        flex: 1;
      }
      .device-meta {
        color: var(--secondary-text-color);
        font-size: 11px;
      }
      .device-power {
        margin-left: auto;
        white-space: nowrap;
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
      /* Charts */
      .charts-container {
        display: flex;
        flex-direction: column;
        gap: 24px;
        padding-bottom: 24px;
      }
      
      .loading-screen {
        display: flex;
        justify-content: center;
        padding: 40px;
      }
      
      /* Charts */
      .charts-container {
        display: flex;
        flex-direction: column;
        gap: 24px;
        padding-bottom: 24px;
      }
      
      /* Responsive */
      @media (max-width: 1200px) {
        .dashboard-grid {
          grid-template-columns: 1fr;
        }
      }
      
      @media (max-width: 768px) {
        .dual-grid { 
          grid-template-columns: 1fr; 
        }
        .devices-grid {
          grid-template-columns: 1fr;
        }
        .device-stats {
          flex-direction: column;
          gap: 4px;
        }
      }
      
      .dual-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
        gap: 16px;
        margin-bottom: 24px;
      }

      /* Tab Selector Styles */
      .card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 16px;
      }
      
      .tab-selector {
        display: flex;
        background: rgba(0,0,0,0.1);
        border-radius: 8px;
        padding: 4px;
        gap: 4px;
      }
      
      .tab-selector button {
        background: transparent;
        border: none;
        color: var(--secondary-text-color);
        padding: 6px 12px;
        border-radius: 6px;
        cursor: pointer;
        font-weight: 500;
        transition: all 0.2s ease;
      }
      
      .tab-selector button:hover {
        background: rgba(255,255,255,0.05);
        color: var(--primary-text-color);
      }
      
      .tab-selector button.active {
        background: var(--primary-color);
        color: white;
      }
      
      /* Charts Container */
      .charts-container {
        display: flex;
        flex-direction: column;
        gap: 24px;
      }
      
      .chart-wrapper {
        background: rgba(0,0,0,0.1);
        border-radius: 8px;
        padding: 16px;
        border: 1px solid var(--divider-color);
      }
      
      .chart-title {
        margin: 0 0 16px 0;
        font-size: 16px;
        font-weight: 500;
        color: var(--primary-text-color);
      }
      
      .chart-controls {
        display: flex;
        justify-content: flex-end;
        margin-bottom: 16px;
        padding: 8px 12px;
        background: rgba(var(--rgb-primary-color), 0.05);
        border-radius: 8px;
        border: 1px solid var(--divider-color);
      }
      
      .chart-div {
        min-height: 300px;
      }

      @media (max-width: 600px) {
        .header-content { 
          flex-direction: column; 
          align-items: flex-start; 
          gap: 12px;
        }
        .actions { 
          width: 100%; 
          justify-content: space-between; 
        }
        .card-header {
          flex-direction: column;
          align-items: flex-start;
          gap: 12px;
        }
        .tab-selector {
          width: 100%;
          justify-content: space-between;
        }
        .tab-selector button {
          flex: 1;
          text-align: center;
          padding: 8px 4px;
          font-size: 0.9em;
        }
        .device-card {
          padding: 12px;
        }
      }

      /* Error Boundaries & Loading States */
      .error-boundary {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 48px 24px;
        text-align: center;
        background: var(--card-background-color, #fff);
        border-radius: var(--ha-card-border-radius, 12px);
        border: 2px dashed var(--error-color);
      }

      .error-icon {
        --mdc-icon-size: 48px;
        color: var(--error-color);
        margin-bottom: 16px;
      }

      .error-content h3 {
        margin: 0 0 8px 0;
        color: var(--primary-text-color);
        font-size: 18px;
        font-weight: 500;
      }

      .error-content p {
        margin: 0 0 24px 0;
        color: var(--secondary-text-color);
        font-size: 14px;
        max-width: 400px;
      }

      .error-content mwc-button {
        --mdc-theme-primary: var(--primary-color);
      }

      .loading-state {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 48px 24px;
        text-align: center;
      }

      .loading-state ha-icon {
        --mdc-icon-size: 48px;
        color: var(--primary-color);
        margin-bottom: 16px;
      }

      .loading-state p {
        margin: 0;
        color: var(--secondary-text-color);
        font-size: 14px;
      }

      .spinning {
        animation: spin 2s linear infinite;
      }

      @keyframes spin {
        from {
          transform: rotate(0deg);
        }
        to {
          transform: rotate(360deg);
        }
      }
    `;
  }
}

if (!customElements.get("pv-optimizer-panel")) {
  window.customElements.define("pv-optimizer-panel", PvOptimizerPanel);
}
