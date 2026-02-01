"""Diagnostics Engine for IoT Devices

Provides comprehensive diagnostic capabilities for IoT devices including:
- Connectivity checks
- Performance metrics
- Health monitoring
- Error detection
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
import time

logger = logging.getLogger(__name__)

class DiagnosticsEngine:
    """Main diagnostics engine for IoT devices"""
    
    def __init__(self):
        self.test_registry = {}
        self._register_default_tests()
    
    def _register_default_tests(self):
        """Register default diagnostic tests"""
        self.register_test("connectivity", self.test_connectivity)
        self.register_test("latency", self.test_latency)
        self.register_test("memory", self.test_memory)
        self.register_test("cpu", self.test_cpu)
        self.register_test("network", self.test_network)
        self.register_test("firmware", self.test_firmware_status)
    
    def register_test(self, name: str, test_func):
        """Register a diagnostic test"""
        self.test_registry[name] = test_func
        logger.info(f"Registered diagnostic test: {name}")
    
    async def run_test(self, test_name: str, device: Dict[str, Any]) -> Dict[str, Any]:
        """Run a specific diagnostic test"""
        if test_name not in self.test_registry:
            return {
                "status": "error",
                "message": f"Test '{test_name}' not found"
            }
        
        try:
            test_func = self.test_registry[test_name]
            result = await test_func(device)
            return {
                "status": "success",
                "test": test_name,
                "result": result,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            logger.error(f"Error running test {test_name}: {e}")
            return {
                "status": "error",
                "test": test_name,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    async def run_full_diagnostics(self, device: Dict[str, Any]) -> Dict[str, Any]:
        """Run all diagnostic tests on a device"""
        results = {}
        start_time = time.time()
        
        for test_name in self.test_registry.keys():
            result = await self.run_test(test_name, device)
            results[test_name] = result
        
        duration = time.time() - start_time
        
        # Calculate overall health score
        health_score = self._calculate_health_score(results)
        
        return {
            "device_id": device.get('id'),
            "device_name": device.get('name'),
            "tests_run": len(results),
            "duration_seconds": round(duration, 2),
            "health_score": health_score,
            "results": results,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    def _calculate_health_score(self, results: Dict[str, Any]) -> int:
        """Calculate overall health score (0-100)"""
        if not results:
            return 0
        
        passed_tests = sum(1 for r in results.values() if r.get('status') == 'success')
        total_tests = len(results)
        
        base_score = (passed_tests / total_tests) * 100
        
        # Adjust based on specific test results
        for test_name, result in results.items():
            if result.get('status') == 'success':
                test_result = result.get('result', {})
                
                # Connectivity is critical
                if test_name == 'connectivity' and not test_result.get('connected', False):
                    base_score *= 0.5
                
                # High latency reduces score
                if test_name == 'latency':
                    latency = test_result.get('latency_ms', 0)
                    if latency > 1000:
                        base_score *= 0.8
                    elif latency > 500:
                        base_score *= 0.9
        
        return min(100, max(0, int(base_score)))
    
    # Individual diagnostic tests
    async def test_connectivity(self, device: Dict[str, Any]) -> Dict[str, Any]:
        """Test device connectivity"""
        # Simulate connectivity check
        await asyncio.sleep(0.1)  # Simulate network delay
        
        status = device.get('status', 'offline')
        ip_address = device.get('ip_address')
        
        connected = status == 'online'
        
        return {
            "connected": connected,
            "status": status,
            "ip_address": ip_address,
            "reachable": connected,
            "message": "Device is reachable" if connected else "Device is not reachable"
        }
    
    async def test_latency(self, device: Dict[str, Any]) -> Dict[str, Any]:
        """Test device response latency"""
        # Simulate latency check
        await asyncio.sleep(0.05)
        
        # Generate simulated latency based on device status
        if device.get('status') == 'online':
            latency_ms = 45 + (hash(device.get('id', '')) % 100)
        else:
            latency_ms = 9999
        
        quality = "excellent" if latency_ms < 100 else "good" if latency_ms < 300 else "poor"
        
        return {
            "latency_ms": latency_ms,
            "quality": quality,
            "acceptable": latency_ms < 500
        }
    
    async def test_memory(self, device: Dict[str, Any]) -> Dict[str, Any]:
        """Test device memory usage"""
        await asyncio.sleep(0.05)
        
        metrics = device.get('metrics', {})
        memory_usage = metrics.get('memory_usage_percent', 45)
        
        status = "critical" if memory_usage > 90 else "warning" if memory_usage > 75 else "healthy"
        
        return {
            "usage_percent": memory_usage,
            "status": status,
            "available": True
        }
    
    async def test_cpu(self, device: Dict[str, Any]) -> Dict[str, Any]:
        """Test device CPU usage"""
        await asyncio.sleep(0.05)
        
        metrics = device.get('metrics', {})
        cpu_usage = metrics.get('cpu_usage_percent', 35)
        
        status = "critical" if cpu_usage > 90 else "warning" if cpu_usage > 75 else "healthy"
        
        return {
            "usage_percent": cpu_usage,
            "status": status,
            "cores": metrics.get('cpu_cores', 1)
        }
    
    async def test_network(self, device: Dict[str, Any]) -> Dict[str, Any]:
        """Test device network performance"""
        await asyncio.sleep(0.1)
        
        metrics = device.get('metrics', {})
        
        return {
            "bandwidth_available": True,
            "packet_loss_percent": metrics.get('packet_loss', 0),
            "download_speed_mbps": metrics.get('download_speed', 100),
            "upload_speed_mbps": metrics.get('upload_speed', 50),
            "status": "healthy"
        }
    
    async def test_firmware_status(self, device: Dict[str, Any]) -> Dict[str, Any]:
        """Test firmware version and update status"""
        await asyncio.sleep(0.05)
        
        current_version = device.get('firmware_version', 'unknown')
        
        # Check if version is known
        version_valid = current_version != 'unknown' and current_version is not None
        
        return {
            "current_version": current_version,
            "version_valid": version_valid,
            "update_available": False,  # Would check against latest version
            "status": "up_to_date" if version_valid else "unknown"
        }

# Additional diagnostic utilities
class DiagnosticReport:
    """Generate formatted diagnostic reports"""
    
    @staticmethod
    def generate_summary(diagnostics_result: Dict[str, Any]) -> str:
        """Generate human-readable summary"""
        health_score = diagnostics_result.get('health_score', 0)
        device_name = diagnostics_result.get('device_name', 'Unknown')
        tests_run = diagnostics_result.get('tests_run', 0)
        
        health_status = "Excellent" if health_score > 80 else "Good" if health_score > 60 else "Poor"
        
        summary = f"""
        Device Diagnostic Report
        ========================
        Device: {device_name}
        Health Score: {health_score}/100 ({health_status})
        Tests Completed: {tests_run}
        Timestamp: {diagnostics_result.get('timestamp', 'N/A')}
        """
        
        return summary
    
    @staticmethod
    def get_issues(diagnostics_result: Dict[str, Any]) -> List[str]:
        """Extract list of issues from diagnostic results"""
        issues = []
        results = diagnostics_result.get('results', {})
        
        for test_name, result in results.items():
            if result.get('status') == 'error':
                issues.append(f"{test_name}: {result.get('error', 'Unknown error')}")
            elif result.get('status') == 'success':
                test_result = result.get('result', {})
                
                # Check for specific issues
                if test_name == 'connectivity' and not test_result.get('connected'):
                    issues.append("Device not connected")
                
                if test_name == 'memory':
                    if test_result.get('status') in ['critical', 'warning']:
                        issues.append(f"Memory usage at {test_result.get('usage_percent')}%")
                
                if test_name == 'cpu':
                    if test_result.get('status') in ['critical', 'warning']:
                        issues.append(f"CPU usage at {test_result.get('usage_percent')}%")
        
        return issues
