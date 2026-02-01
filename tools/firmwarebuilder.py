#!/usr/bin/env python3
"""Firmware Builder Tool for Karyx IoT Devices

Builds and packages firmware for different device types with:
- Version management
- Checksum generation
- Packaging and compression
- Build manifest creation
"""

import argparse
import hashlib
import json
import logging
import os
import shutil
import subprocess
import tarfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class FirmwareBuilder:
    """Firmware building and packaging tool"""
    
    def __init__(self, source_dir: str, output_dir: str = "build"):
        self.source_dir = Path(source_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        if not self.source_dir.exists():
            raise ValueError(f"Source directory not found: {source_dir}")
    
    def build_firmware(self, 
                      device_type: str,
                      version: str,
                      config: Optional[Dict] = None) -> Dict:
        """Build firmware package
        
        Args:
            device_type: Type of device (sensor, actuator, etc.)
            version: Firmware version
            config: Optional build configuration
        
        Returns:
            Build manifest with metadata
        """
        logger.info(f"Building firmware for {device_type} v{version}...")
        
        # Create build directory
        build_dir = self.output_dir / f"{device_type}-{version}"
        build_dir.mkdir(parents=True, exist_ok=True)
        
        # Build steps
        manifest = {
            'device_type': device_type,
            'version': version,
            'build_time': datetime.now(timezone.utc).isoformat(),
            'files': [],
            'checksums': {}
        }
        
        try:
            # Copy source files
            logger.info("Copying source files...")
            self._copy_sources(build_dir, manifest)
            
            # Compile if needed
            if config and config.get('compile'):
                logger.info("Compiling firmware...")
                self._compile_firmware(build_dir, config)
            
            # Generate checksums
            logger.info("Generating checksums...")
            self._generate_checksums(build_dir, manifest)
            
            # Create package
            logger.info("Creating firmware package...")
            package_path = self._create_package(build_dir, device_type, version)
            manifest['package_file'] = package_path.name
            manifest['package_size'] = package_path.stat().st_size
            manifest['package_checksum'] = self._calculate_checksum(package_path)
            
            # Save manifest
            manifest_path = build_dir / 'manifest.json'
            with open(manifest_path, 'w') as f:
                json.dump(manifest, f, indent=2)
            
            logger.info(f"Firmware build complete: {package_path}")
            logger.info(f"Package size: {manifest['package_size'] / 1024:.2f} KB")
            logger.info(f"Checksum: {manifest['package_checksum']}")
            
            return manifest
            
        except Exception as e:
            logger.error(f"Build failed: {e}")
            raise
    
    def _copy_sources(self, build_dir: Path, manifest: Dict):
        """Copy source files to build directory"""
        # Copy all Python files from source
        for source_file in self.source_dir.rglob('*.py'):
            if '__pycache__' in str(source_file):
                continue
            
            rel_path = source_file.relative_to(self.source_dir)
            dest_path = build_dir / rel_path
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            shutil.copy2(source_file, dest_path)
            manifest['files'].append(str(rel_path))
        
        # Copy configuration files
        for config_file in self.source_dir.glob('*.yaml'):
            shutil.copy2(config_file, build_dir / config_file.name)
            manifest['files'].append(config_file.name)
        
        for config_file in self.source_dir.glob('*.json'):
            shutil.copy2(config_file, build_dir / config_file.name)
            manifest['files'].append(config_file.name)
    
    def _compile_firmware(self, build_dir: Path, config: Dict):
        """Compile firmware (placeholder for actual compilation)"""
        # This would contain actual compilation steps
        # For example: gcc, make, platformio, etc.
        compiler = config.get('compiler', 'python')
        
        if compiler == 'python':
            # Compile Python to bytecode
            import py_compile
            for py_file in build_dir.rglob('*.py'):
                try:
                    py_compile.compile(py_file, doraise=True)
                    logger.debug(f"Compiled: {py_file.name}")
                except Exception as e:
                    logger.warning(f"Failed to compile {py_file.name}: {e}")
        
        elif compiler in ['gcc', 'make']:
            # Example for C/C++ compilation
            logger.info(f"Running {compiler}...")
            result = subprocess.run(
                [compiler] + config.get('compiler_flags', []),
                cwd=build_dir,
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                raise RuntimeError(f"Compilation failed: {result.stderr}")
    
    def _generate_checksums(self, build_dir: Path, manifest: Dict):
        """Generate checksums for all files"""
        for file_path in build_dir.rglob('*'):
            if file_path.is_file():
                rel_path = file_path.relative_to(build_dir)
                checksum = self._calculate_checksum(file_path)
                manifest['checksums'][str(rel_path)] = checksum
    
    def _calculate_checksum(self, file_path: Path, algorithm: str = 'sha256') -> str:
        """Calculate file checksum"""
        hash_obj = hashlib.new(algorithm)
        
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                hash_obj.update(chunk)
        
        return hash_obj.hexdigest()
    
    def _create_package(self, build_dir: Path, device_type: str, version: str) -> Path:
        """Create firmware package (tar.gz)"""
        package_name = f"{device_type}-firmware-{version}.tar.gz"
        package_path = self.output_dir / package_name
        
        with tarfile.open(package_path, 'w:gz') as tar:
            tar.add(build_dir, arcname=f"{device_type}-{version}")
        
        return package_path
    
    def verify_package(self, package_path: str, expected_checksum: str) -> bool:
        """Verify firmware package integrity"""
        actual_checksum = self._calculate_checksum(Path(package_path))
        
        if actual_checksum == expected_checksum:
            logger.info("Package verification successful")
            return True
        else:
            logger.error("Package verification failed")
            logger.error(f"Expected: {expected_checksum}")
            logger.error(f"Actual: {actual_checksum}")
            return False

def main():
    parser = argparse.ArgumentParser(description="Karyx Firmware Builder")
    parser.add_argument('source', help='Source directory')
    parser.add_argument('--device-type', '-t', required=True, help='Device type')
    parser.add_argument('--version', '-v', required=True, help='Firmware version')
    parser.add_argument('--output', '-o', default='build', help='Output directory')
    parser.add_argument('--compile', action='store_true', help='Compile firmware')
    parser.add_argument('--compiler', default='python', help='Compiler to use')
    
    args = parser.parse_args()
    
    config = {
        'compile': args.compile,
        'compiler': args.compiler
    }
    
    try:
        builder = FirmwareBuilder(args.source, args.output)
        manifest = builder.build_firmware(args.device_type, args.version, config)
        
        print("\n" + "="*50)
        print("BUILD SUCCESSFUL")
        print("="*50)
        print(f"Device Type: {manifest['device_type']}")
        print(f"Version: {manifest['version']}")
        print(f"Package: {manifest['package_file']}")
        print(f"Size: {manifest['package_size'] / 1024:.2f} KB")
        print(f"Checksum: {manifest['package_checksum']}")
        print("="*50 + "\n")
        
    except Exception as e:
        logger.error(f"Build failed: {e}")
        return 1
    
    return 0

if __name__ == '__main__':
    exit(main())
