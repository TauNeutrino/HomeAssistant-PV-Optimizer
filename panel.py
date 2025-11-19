
"""
Panel Registration for PV Optimizer Integration

This module handles the registration of the custom sidebar panel that provides
a user interface for the PV Optimizer integration.

Purpose:
--------
The panel provides quick access to device status and a button to open the
configuration flow for managing devices and global settings.

Architecture:
------------
1. Static File Serving: Registers the JavaScript file that renders the panel
2. Panel Registration: Adds the panel to Home Assistant's sidebar

Panel Features:
--------------
- Device status overview (connected devices, their states)
- Quick navigation to configuration (options flow)
- Real-time status display via WebSocket connection
- Native Home Assistant styling and integration

Flow:
-----
1. User clicks "PV Optimizer" in sidebar
2. Home Assistant loads the JavaScript file from /pv_optimizer-panel.js
3. JavaScript connects to WebSocket API to fetch device states
4. Panel displays current status and configuration button
5. Button click navigates to integration's options flow for management
"""

from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration
from homeassistant.components import panel_custom
from homeassistant.components.http import StaticPathConfig

from .const import DOMAIN, FRONTEND_URL, PANEL_TITLE, PANEL_ICON, PANEL_URL


async def async_setup_panel(hass: HomeAssistant):
    """
    Set up the PV Optimizer sidebar panel.
    
    This function performs two key tasks:
    1. Registers a static file path to serve the panel's JavaScript
    2. Registers the panel with Home Assistant's frontend
    
    Functionality Achieved:
    ----------------------
    1. Static File Serving:
       - Makes the JavaScript panel file accessible via HTTP
       - Path: /pv_optimizer-panel.js
       - File: custom_components/pv_optimizer/www/pv-optimizer-panel.js
       - Caching disabled during development for easier testing
    
    2. Panel Registration:
       - Adds "PV Optimizer" to the sidebar
       - Icon: solar power symbol (mdi:solar-power)
       - URL: /pv-optimizer
       - Requires admin privileges
       - Loads as a JavaScript module (modern ES6 module)
    
    Panel Configuration Details:
    ---------------------------
    - component_name="custom": Indicates this is a custom panel
    - embed_iframe=False: Panel renders directly (not in iframe)
    - trust_external_script=False: Script is internal (part of integration)
    - module=True: JavaScript is loaded as ES6 module
    
    Technical Notes:
    ---------------
    - The panel JavaScript uses LitElement for rendering
    - WebSocket API provides real-time data updates
    - Panel integrates with Home Assistant's theme system
    - Navigation uses Home Assistant's event system
    
    Args:
        hass: Home Assistant instance
    
    Returns:
        None
    """
    # Register static file path for the panel JavaScript
    # This makes the JavaScript file accessible via HTTP at FRONTEND_URL
    # The file contains the panel's UI code written with LitElement
    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                FRONTEND_URL,  # URL path: "/pv_optimizer-panel.js"
                # Physical file path on disk
                hass.config.path("custom_components/pv_optimizer/www/pv-optimizer-panel.js"),
                False,  # Don't cache - useful during development to see changes immediately
            )
        ]
    )
    
    # Get version from manifest.json for cache busting
    integration = await async_get_integration(hass, DOMAIN)
    version = integration.version
    
    module_url_with_version = f"{FRONTEND_URL}?v={version}"

    # Register the custom panel with Home Assistant's frontend
    # This adds the "PV Optimizer" entry to the sidebar
    await panel_custom.async_register_panel(
        hass=hass,
        webcomponent_name="pv-optimizer-panel",
        frontend_url_path=PANEL_URL,
        sidebar_title=PANEL_TITLE,
        sidebar_icon=PANEL_ICON,
        module_url=module_url_with_version,
        embed_iframe=False,
        require_admin=False,
    )
