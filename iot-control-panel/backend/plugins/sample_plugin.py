"""Sample Plugin for Karyx IoT Panel

This demonstrates how to create plugins for the IoT panel.
Plugins can extend functionality by adding custom routes, diagnostics, or device handlers.
"""

import logging
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Plugin metadata
PLUGIN_NAME = "sample_plugin"
PLUGIN_VERSION = "1.0.0"
PLUGIN_DESCRIPTION = "Sample plugin demonstrating IoT panel extensibility"

# Create plugin router
plugin_router = APIRouter(prefix="/api/plugins/sample", tags=["sample_plugin"])

class PluginConfig(BaseModel):
    enabled: bool = True
    setting1: str = "default_value"
    setting2: int = 42

# Plugin configuration
config = PluginConfig()

@plugin_router.get("/info")
async def plugin_info():
    """Get plugin information"""
    return {
        "name": PLUGIN_NAME,
        "version": PLUGIN_VERSION,
        "description": PLUGIN_DESCRIPTION,
        "enabled": config.enabled
    }

@plugin_router.get("/status")
async def plugin_status():
    """Get plugin status"""
    return {
        "status": "active" if config.enabled else "disabled",
        "config": config.model_dump()
    }

@plugin_router.post("/action")
async def custom_action(data: Dict[str, Any]):
    """Perform custom plugin action"""
    logger.info(f"Plugin action called with data: {data}")
    
    # Implement your custom logic here
    result = {
        "action": "processed",
        "received_data": data,
        "plugin": PLUGIN_NAME
    }
    
    return result

@plugin_router.get("/devices/custom-check/{device_id}")
async def custom_device_check(device_id: str):
    """Perform custom device check"""
    # Implement custom device diagnostics or checks
    return {
        "device_id": device_id,
        "check_type": "custom_plugin_check",
        "status": "passed",
        "details": {
            "custom_metric_1": 123.45,
            "custom_metric_2": "optimal"
        }
    }

def register(app):
    """Register plugin with the main application
    
    This function is called by the plugin loader when the application starts.
    It should register all routes and initialize the plugin.
    
    Args:
        app: FastAPI application instance
    
    Returns:
        str: Plugin name
    """
    # Include plugin router in main app
    app.include_router(plugin_router)
    
    logger.info(f"Plugin '{PLUGIN_NAME}' v{PLUGIN_VERSION} registered successfully")
    
    return PLUGIN_NAME

# Plugin hooks (optional)
async def on_device_connected(device: Dict[str, Any]):
    """Called when a device connects"""
    logger.info(f"Plugin hook: Device connected - {device.get('name')}")

async def on_device_disconnected(device: Dict[str, Any]):
    """Called when a device disconnects"""
    logger.info(f"Plugin hook: Device disconnected - {device.get('name')}")

async def on_firmware_update(device_id: str, firmware_version: str):
    """Called when firmware is updated"""
    logger.info(f"Plugin hook: Firmware updated on {device_id} to {firmware_version}")
