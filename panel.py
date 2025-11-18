
from homeassistant.core import HomeAssistant
from homeassistant.components.frontend import async_register_built_in_panel
from homeassistant.components.http import StaticPathConfig

from .const import FRONTEND_URL, PANEL_TITLE, PANEL_ICON, PANEL_URL


async def async_setup_panel(hass: HomeAssistant):
    # Serve the PV Optimizer panel and register it
    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                FRONTEND_URL,
                hass.config.path("custom_components/pv_optimizer/www/pv-optimizer-panel.js"),
                True,
            )
        ]
    )
    async_register_built_in_panel(
        hass=hass,
        component_name="custom",
        sidebar_title=PANEL_TITLE,
        sidebar_icon=PANEL_ICON,
        frontend_url_path=PANEL_URL,
        require_admin=True,
        config={
            "_panel_custom": {
                "name": "pv-optimizer-panel",
                "js_url": FRONTEND_URL,
            }
        },
    )
