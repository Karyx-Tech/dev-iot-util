from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime, timezone
import logging
import json
import uuid
import os
import importlib.util
import sys
from pathlib import Path

# Import diagnostics module
from diagnostics import DiagnosticsEngine

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Karyx IoT Utils Panel",
    description="IoT Device Management and Monitoring Platform",
    version="1.0.0"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize diagnostics engine
diagnostics = DiagnosticsEngine()

# In-memory storage (replace with database in production)
devices_db: Dict[str, Dict] = {}
firmware_db: Dict[str, Dict] = {}
plugins_loaded: Dict[str, Any] = {}

# WebSocket connections for real-time updates
active_connections: List[WebSocket] = []

# Models
class Device(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    device_type: str
    status: str = "offline"
    ip_address: Optional[str] = None
    firmware_version: Optional[str] = None
    last_seen: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metrics: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class DeviceCreate(BaseModel):
    name: str
    device_type: str
    ip_address: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class DeviceUpdate(BaseModel):
    status: Optional[str] = None
    firmware_version: Optional[str] = None
    metrics: Optional[Dict[str, Any]] = None

class Firmware(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    version: str
    device_type: str
    filename: str
    checksum: str
    size: int
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    description: Optional[str] = None

class FirmwareCreate(BaseModel):
    version: str
    device_type: str
    filename: str
    checksum: str
    size: int
    description: Optional[str] = None

class CommandRequest(BaseModel):
    device_id: str
    command: str
    parameters: Dict[str, Any] = Field(default_factory=dict)

# WebSocket manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting to WebSocket: {e}")

manager = ConnectionManager()

# Routes
@app.get("/")
async def root():
    return {
        "message": "Karyx IoT Utils Panel API",
        "version": "1.0.0",
        "status": "operational"
    }

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "devices_count": len(devices_db),
        "plugins_loaded": len(plugins_loaded)
    }

# Device Management
@app.get("/api/devices", response_model=List[Device])
async def get_devices():
    """Get all registered devices"""
    return list(devices_db.values())

@app.get("/api/devices/{device_id}", response_model=Device)
async def get_device(device_id: str):
    """Get specific device by ID"""
    if device_id not in devices_db:
        raise HTTPException(status_code=404, detail="Device not found")
    return devices_db[device_id]

@app.post("/api/devices", response_model=Device)
async def create_device(device: DeviceCreate):
    """Register a new device"""
    new_device = Device(**device.model_dump())
    devices_db[new_device.id] = new_device.model_dump()
    
    # Broadcast update
    await manager.broadcast({
        "type": "device_added",
        "device": devices_db[new_device.id]
    })
    
    logger.info(f"Device registered: {new_device.name} ({new_device.id})")
    return new_device

@app.put("/api/devices/{device_id}", response_model=Device)
async def update_device(device_id: str, update: DeviceUpdate):
    """Update device information"""
    if device_id not in devices_db:
        raise HTTPException(status_code=404, detail="Device not found")
    
    device = devices_db[device_id]
    update_data = update.model_dump(exclude_unset=True)
    
    for key, value in update_data.items():
        device[key] = value
    
    device['last_seen'] = datetime.now(timezone.utc).isoformat()
    
    # Broadcast update
    await manager.broadcast({
        "type": "device_updated",
        "device": device
    })
    
    return Device(**device)

@app.delete("/api/devices/{device_id}")
async def delete_device(device_id: str):
    """Remove a device"""
    if device_id not in devices_db:
        raise HTTPException(status_code=404, detail="Device not found")
    
    del devices_db[device_id]
    
    # Broadcast update
    await manager.broadcast({
        "type": "device_removed",
        "device_id": device_id
    })
    
    logger.info(f"Device removed: {device_id}")
    return {"message": "Device removed successfully"}

# Diagnostics
@app.get("/api/diagnostics/{device_id}")
async def run_diagnostics(device_id: str):
    """Run diagnostics on a device"""
    if device_id not in devices_db:
        raise HTTPException(status_code=404, detail="Device not found")
    
    device = devices_db[device_id]
    results = await diagnostics.run_full_diagnostics(device)
    
    return {
        "device_id": device_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "results": results
    }

@app.post("/api/diagnostics/{device_id}/test")
async def run_diagnostic_test(device_id: str, test_name: str):
    """Run specific diagnostic test"""
    if device_id not in devices_db:
        raise HTTPException(status_code=404, detail="Device not found")
    
    device = devices_db[device_id]
    result = await diagnostics.run_test(test_name, device)
    
    return {
        "device_id": device_id,
        "test": test_name,
        "result": result
    }

# Firmware Management
@app.get("/api/firmware", response_model=List[Firmware])
async def get_firmware():
    """Get all firmware versions"""
    return list(firmware_db.values())

@app.post("/api/firmware", response_model=Firmware)
async def register_firmware(firmware: FirmwareCreate):
    """Register new firmware version"""
    new_firmware = Firmware(**firmware.model_dump())
    firmware_db[new_firmware.id] = new_firmware.model_dump()
    
    logger.info(f"Firmware registered: {new_firmware.version} for {new_firmware.device_type}")
    return new_firmware

@app.post("/api/firmware/{firmware_id}/deploy/{device_id}")
async def deploy_firmware(firmware_id: str, device_id: str):
    """Deploy firmware to device"""
    if firmware_id not in firmware_db:
        raise HTTPException(status_code=404, detail="Firmware not found")
    if device_id not in devices_db:
        raise HTTPException(status_code=404, detail="Device not found")
    
    firmware = firmware_db[firmware_id]
    device = devices_db[device_id]
    
    # Simulate firmware deployment
    deployment_id = str(uuid.uuid4())
    
    await manager.broadcast({
        "type": "firmware_deployment",
        "deployment_id": deployment_id,
        "device_id": device_id,
        "firmware_version": firmware['version'],
        "status": "initiated"
    })
    
    logger.info(f"Firmware deployment initiated: {firmware['version']} to {device_id}")
    
    return {
        "deployment_id": deployment_id,
        "status": "initiated",
        "device_id": device_id,
        "firmware_version": firmware['version']
    }

# Command Execution
@app.post("/api/command")
async def send_command(cmd: CommandRequest):
    """Send command to device"""
    if cmd.device_id not in devices_db:
        raise HTTPException(status_code=404, detail="Device not found")
    
    command_id = str(uuid.uuid4())
    
    # Broadcast command
    await manager.broadcast({
        "type": "command_sent",
        "command_id": command_id,
        "device_id": cmd.device_id,
        "command": cmd.command,
        "parameters": cmd.parameters
    })
    
    logger.info(f"Command sent to {cmd.device_id}: {cmd.command}")
    
    return {
        "command_id": command_id,
        "status": "sent",
        "device_id": cmd.device_id
    }

# Plugin Management
@app.get("/api/plugins")
async def get_plugins():
    """Get loaded plugins"""
    return {
        "plugins": list(plugins_loaded.keys()),
        "count": len(plugins_loaded)
    }

@app.post("/api/plugins/reload")
async def reload_plugins():
    """Reload all plugins"""
    loaded = load_plugins()
    return {
        "message": "Plugins reloaded",
        "loaded": loaded
    }

# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Handle incoming WebSocket messages
            if message.get('type') == 'ping':
                await websocket.send_json({'type': 'pong'})
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# Plugin loader
def load_plugins():
    """Load all plugins from plugins directory"""
    plugins_dir = Path(__file__).parent / "plugins"
    if not plugins_dir.exists():
        logger.warning("Plugins directory not found")
        return []
    
    loaded = []
    for plugin_file in plugins_dir.glob("*.py"):
        if plugin_file.name.startswith("__"):
            continue
        
        try:
            spec = importlib.util.spec_from_file_location(plugin_file.stem, plugin_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            if hasattr(module, 'register'):
                plugin_name = module.register(app)
                plugins_loaded[plugin_name] = module
                loaded.append(plugin_name)
                logger.info(f"Plugin loaded: {plugin_name}")
        except Exception as e:
            logger.error(f"Failed to load plugin {plugin_file.name}: {e}")
    
    return loaded

# Startup event
@app.on_event("startup")
async def startup_event():
    logger.info("Karyx IoT Utils Panel starting up...")
    load_plugins()
    logger.info("IoT Panel ready!")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
