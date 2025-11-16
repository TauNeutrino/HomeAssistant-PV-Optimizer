# PV Optimizer Frontend Panel Fix

## Changes Made

This document describes the changes made to fix the PV Optimizer frontend panel that was not appearing in the Home Assistant sidebar.

### Issues Fixed

1. **Modern Manifest Registration**: Updated `manifest.json` to use the modern Home Assistant panel registration approach
2. **Proper File Structure**: Moved panel files to the correct `www/` directory structure
3. **Modern Panel JavaScript**: Updated the panel to use current Home Assistant web component patterns
4. **Sidebar Configuration**: Added proper sidebar configuration with title and icon

### Files Modified

#### 1. manifest.json
```json
{
  "domain": "pv_optimizer",
  "name": "PV Optimizer",
  "codeowners": ["@your_username"],
  "config_flow": true,
  "documentation": "https://github.com/your_repo/pv_optimizer",
  "integration_type": "device",
  "iot_class": "local_polling",
  "issue_tracker": "https://github.com/your_repo/pv_optimizer/issues",
  "requirements": [],
  "version": "0.1.0",
  "frontend": {
    "entrypoint": "/local/pv_optimizer/panel.js",
    "sidebar": {
      "title": "PV Optimizer",
      "icon": "mdi:solar-panel"
    }
  }
}
```

**Key changes:**
- Changed from `"frontend": {"panel": "pv_optimizer"}` to `"frontend": {"entrypoint": "/local/pv_optimizer/panel.js", "sidebar": {...}}`
- Added proper sidebar configuration with title and Material Design icon

#### 2. Panel File Structure
- **Old**: `frontend/panel_pv_optimizer.js`
- **New**: `www/pv_optimizer/panel.js`

The panel is now accessible via `/local/pv_optimizer/panel.js` URL, which maps to the `custom_components/pv_optimizer/www/pv_optimizer/panel.js` file.

#### 3. Panel JavaScript Updates
The panel now uses modern Home Assistant patterns:
- Updated LitElement imports to version 2.4.0
- Added `hass-panel-router` wrapper component
- Improved entity discovery and rendering
- Added proper error handling for missing entities
- Enhanced UI with device management sections

## Testing Instructions

### 1. Verify File Structure
Ensure these files exist:
```
custom_components/pv_optimizer/
├── manifest.json (updated)
├── www/
│   └── pv_optimizer/
│       └── panel.js (new)
└── frontend/
    └── panel_pv_optimizer.js (renamed - contains only a comment)
```

### 2. Restart Home Assistant
After copying the files:
1. **Restart Home Assistant** completely
2. Wait for the integration to load
3. Check the sidebar for "PV Optimizer" entry with solar panel icon

### 3. Check Browser Console
Open the browser developer tools (F12) and check for any JavaScript errors related to the panel loading.

### 4. Verify Panel Accessibility
The panel should be accessible directly via:
- Sidebar click: "PV Optimizer"
- Direct URL: `http://your-ha-instance:8123/panel/pv_optimizer`

## Debugging Steps

If the panel still doesn't appear:

### Step 1: Check Manifest Loading
1. Go to Home Assistant Developer Tools → Info
2. Look for "Custom Components" section
3. Verify "PV Optimizer" is listed without errors
4. Check Home Assistant logs for any manifest-related errors

### Step 2: Verify File Accessibility
1. Check if the panel file is accessible via direct URL:
   `http://your-ha-instance:8123/local/pv_optimizer/panel.js`
2. You should see the JavaScript code (not a 404 error)

### Step 3: Check Browser Network Tab
1. Open developer tools (F12)
2. Go to Network tab
3. Reload the Home Assistant page
4. Look for requests to `/local/pv_optimizer/panel.js`
5. Check response status (should be 200, not 404)

### Step 4: Check JavaScript Console
1. Look for any JavaScript errors in the console
2. Common issues:
   - CORS errors (should not happen with local files)
   - Module import errors
   - Missing dependencies

### Step 5: Verify Integration Status
1. Go to Settings → Integrations
2. Find "PV Optimizer" integration
3. Verify it's loaded without errors
4. Check if entities are being created

### Step 6: Check Home Assistant Logs
Look for these types of errors in Home Assistant logs:
- Frontend loading errors
- Manifest validation errors
- JavaScript module errors
- Integration setup errors

## Common Issues and Solutions

### Issue 1: Panel doesn't appear in sidebar
**Possible causes:**
- File not in correct location
- Permissions issues
- Browser cache

**Solutions:**
1. Clear browser cache
2. Verify file structure matches exactly
3. Check Home Assistant has read permissions to the files

### Issue 2: Panel appears but shows errors
**Possible causes:**
- Missing entities
- JavaScript errors
- API compatibility issues

**Solutions:**
1. Check browser console for specific errors
2. Verify the integration is properly set up with entities
3. Check that sensors are being created

### Issue 3: 404 error when accessing panel URL
**Possible causes:**
- File path mismatch
- File not created correctly
- URL rewriting issues

**Solutions:**
1. Verify the file exists at `custom_components/pv_optimizer/www/pv_optimizer/panel.js`
2. Check that the path in manifest matches the file location
3. Restart Home Assistant to reload static files

## Verification Checklist

- [ ] Files are in correct locations
- [ ] Home Assistant has been restarted
- [ ] "PV Optimizer" appears in sidebar
- [ ] Panel loads without JavaScript errors
- [ ] Entities are properly displayed
- [ ] Panel is responsive and functional

## Next Steps

After the panel is working:
1. Test all functionality in the panel
2. Add more advanced features as needed
3. Customize the UI according to your requirements
4. Test on different devices and browsers

## File Locations

- **Manifest**: `custom_components/pv_optimizer/manifest.json`
- **Panel JS**: `custom_components/pv_optimizer/www/pv_optimizer/panel.js`
- **Integration**: All files in `custom_components/pv_optimizer/`

For additional help, check the Home Assistant developer documentation for custom panel development.