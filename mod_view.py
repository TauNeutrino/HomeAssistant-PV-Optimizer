"""Frontend panel setup for PV Optimizer integration."""
import logging
from pathlib import Path

from homeassistant.core import HomeAssistant
from homeassistant.components.frontend import add_extra_js_url, async_register_built_in_panel
from homeassistant.components.http import StaticPathConfig

from .const import PANEL_URL, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_panel(hass: HomeAssistant) -> None:
    """Set up the PV Optimizer panel."""
    
    # Get the path to the panel JavaScript file
    panel_path = Path(hass.config.path("custom_components/pv_optimizer/pv_optimizer_panel.js"))
    
    # Verify the file exists
    if not panel_path.exists():
        _LOGGER.error(f"PV Optimizer panel JS file not found at: {panel_path}")
        return
    
    # Register static path for panel JavaScript
    await hass.http.async_register_static_paths([
        StaticPathConfig(
            PANEL_URL,
            str(panel_path),
            True,
        )
    ])
    
    # Add as module URL to enable ES6 module loading
    add_extra_js_url(hass, PANEL_URL)
    
    # Register the panel in sidebar
    async_register_built_in_panel(
        hass=hass,
        component_name="custom",
        sidebar_title="PV Optimizer",
        sidebar_icon="mdi:solar-panel",
        frontend_url_path="pv_optimizer",
        require_admin=False,
        config={
            "_panel_custom": {
                "name": "pv-optimizer-panel",
                "js_url": PANEL_URL,
            }
        },
    )
    
    _LOGGER.info(f"PV Optimizer panel registered successfully. Panel available at: {PANEL_URL}")
    _LOGGER.info(f"Panel file path: {panel_path}")