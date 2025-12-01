[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![version](https://img.shields.io/github/v/release/TauNeutrino/HomeAssistant-PV-Optimizer?style=flat-square)](https://github.com/TauNeutrino/HomeAssistant-PV-Optimizer/releases)
[![beta](https://img.shields.io/badge/status-beta-blue)](https://github.com/TauNeutrino/HomeAssistant-PV-Optimizer)


# ☀️ PV Optimizer

**Maximize your solar self-consumption with intelligent device scheduling.**

PV Optimizer is a custom integration for Home Assistant that automatically manages your appliances based on available solar surplus. Unlike simple "threshold" automations, it uses the **Knapsack Algorithm** to find the optimal combination of devices to run, respecting priorities, power limits, and minimum runtime constraints.

## ✨ Features

*   **🧠 Intelligent Optimization**: Uses the Knapsack algorithm to fit the most important devices into your available solar budget.
*   **🧪 Simulation Mode**: Test your priorities and settings safely! Run a parallel "what-if" simulation to see how the optimizer *would* behave without actually switching any devices.
*   **📊 Custom Dashboard**: Includes a beautiful, built-in dashboard to visualize power usage, surplus, and device states over time.
*   **⚡ Dynamic Power Budget**: Automatically adjusts the power budget based on current surplus + power of currently running devices.
*   **⏱️ Smart Constraints**: Respects "Minimum On Time" and "Minimum Off Time" to protect your appliances (e.g., heat pumps, washing machines).
*   **🔌 Universal Compatibility**: Works with any `switch` entity or `input_number` in Home Assistant.

## 📥 Installation

### Option 1: HACS (Recommended)

1.  Open HACS in Home Assistant.
2.  Go to **Integrations** > **Explore & Download Repositories**.
3.  Search for **"PV Optimizer"**.
4.  Click **Download**.
5.  Restart Home Assistant.

### Option 2: Manual Installation

1.  Download the `pv_optimizer` folder from the latest release.
2.  Copy the folder to your `custom_components/` directory in Home Assistant.
3.  Restart Home Assistant.

## ⚙️ Configuration

PV Optimizer is fully configurable via the UI.

1.  Go to **Settings** > **Devices & Services**.
2.  Click **Add Integration** and search for **PV Optimizer**.
3.  Follow the configuration wizard.

### 1. Main Service Configuration
*   **Grid Import/Export Sensor**: The sensor measuring grid import (positive value = import, negative value = export).
*   **Update Interval**: How often to recalculate (default: 60s).
*   **Average Window**: How many minutes to average all power sensors (default: 5).

### 2. Adding Devices
Once the integration is added, click **Configure** on the integration entry to manage devices.

Select the type of device you want to add:

*   **Switch**: A switch entity to control (e.g., `switch.heater`).
*   **Input Number**: An input number entity to control (e.g., `input_number.heater`).

Fill in the following fields:
*   **Device Name**: Friendly name for the device.
*   **Power Consumption**: Rated power of the device in Watts.
*   **Priority**: Higher number = higher priority (1-100).
*   **Min On/Off Time**: Prevent rapid switching.
*   **Simulation Active**: Check this to run in Simulation Mode only (no physical switching).

## 🖥️ Dashboard

The integration comes with a custom panel accessible from the sidebar.

*   **System Overview**: Live view of surplus, budget, and active devices.
*   **Diagrams**: Historical charts showing surplus trends and device activation.
*   **Statistics**: Efficiency metrics and event counters.

## 🧪 Simulation Mode Explained

Simulation mode allows you to "shadow test" devices.
*   **Real Optimization**: Controls devices with `Optimization Enabled`.
*   **Simulation**: Runs a parallel calculation for devices with `Simulation Active`.

Use this to:
*   Test if a new device *would* fit into your solar curve.
*   Fine-tune priorities without disrupting your actual home automation.
*   Compare "Real" vs "Simulation" in the Dashboard to verify your settings.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
