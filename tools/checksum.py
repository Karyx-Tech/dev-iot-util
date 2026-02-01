#!/usr/bin/env python3
"""Checksum Utility for Karyx IoT Firmware

Provides checksum calculation and verification for firmware packages.
Supports multiple hash algorithms: MD5, SHA1, SHA256, SHA512
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

class ChecksumTool:
    """Checksum calculation and verification tool"""
    
    SUPPORTED_ALGORITHMS = ['md5', 'sha1', 'sha256', 'sha512']
    
    def __init__(self, algorithm: str = 'sha256'):
        if algorithm not in self.SUPPORTED_ALGORITHMS:
            raise ValueError(f"Unsupported algorithm: {algorithm}")
        self.algorithm = algorithm
    
    def calculate(self, file_path: str) -> str:
        """Calculate checksum for a file
        
        Args:
            file_path: Path to the file
        
        Returns:
            Hexadecimal checksum string
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        hash_obj = hashlib.new(self.algorithm)
        
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                hash_obj.update(chunk)
        
        return hash_obj.hexdigest()
    
    def calculate_multiple(self, file_paths: List[str]) -> Dict[str, str]:
        """Calculate checksums for multiple files
        
        Args:
            file_paths: List of file paths
        
        Returns:
            Dictionary mapping file paths to checksums
        """
        results = {}
        for file_path in file_paths:
            try:
                results[file_path] = self.calculate(file_path)
            except Exception as e:
                results[file_path] = f"ERROR: {str(e)}"
        
        return results
    
    def verify(self, file_path: str, expected_checksum: str) -> bool:
        """Verify file checksum
        
        Args:
            file_path: Path to the file
            expected_checksum: Expected checksum value
        
        Returns:
            True if checksum matches, False otherwise
        """
        actual_checksum = self.calculate(file_path)
        return actual_checksum.lower() == expected_checksum.lower()
    
    def verify_from_file(self, checksum_file: str) -> Dict[str, bool]:
        """Verify checksums from a checksum file
        
        Format: <checksum> <filename>
        
        Args:
            checksum_file: Path to checksum file
        
        Returns:
            Dictionary mapping file paths to verification results
        """
        results = {}
        checksum_path = Path(checksum_file)
        
        if not checksum_path.exists():
            raise FileNotFoundError(f"Checksum file not found: {checksum_file}")
        
        base_dir = checksum_path.parent
        
        with open(checksum_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                parts = line.split(maxsplit=1)
                if len(parts) != 2:
                    continue
                
                expected_checksum, filename = parts
                file_path = base_dir / filename
                
                try:
                    results[filename] = self.verify(str(file_path), expected_checksum)
                except Exception as e:
                    results[filename] = f"ERROR: {str(e)}"
        
        return results
    
    def generate_checksum_file(self, file_paths: List[str], output_file: str):
        """Generate checksum file for multiple files
        
        Args:
            file_paths: List of file paths
            output_file: Output checksum file path
        """
        checksums = self.calculate_multiple(file_paths)
        
        with open(output_file, 'w') as f:
            f.write(f"# Checksums generated using {self.algorithm}\n")
            f.write(f"# Format: <checksum> <filename>\n\n")
            
            for file_path, checksum in checksums.items():
                if not checksum.startswith('ERROR'):
                    filename = Path(file_path).name
                    f.write(f"{checksum}  {filename}\n")
    
    def generate_manifest(self, file_paths: List[str], output_file: str):
        """Generate JSON manifest with checksums
        
        Args:
            file_paths: List of file paths
            output_file: Output manifest file path
        """
        manifest = {
            'algorithm': self.algorithm,
            'files': []
        }
        
        for file_path in file_paths:
            try:
                path = Path(file_path)
                checksum = self.calculate(file_path)
                
                manifest['files'].append({
                    'filename': path.name,
                    'path': str(path),
                    'size': path.stat().st_size,
                    'checksum': checksum
                })
            except Exception as e:
                print(f"Error processing {file_path}: {e}", file=sys.stderr)
        
        with open(output_file, 'w') as f:
            json.dump(manifest, f, indent=2)

def main():
    parser = argparse.ArgumentParser(
        description='Checksum calculation and verification tool for Karyx IoT firmware'
    )
    
    parser.add_argument(
        'files',
        nargs='+',
        help='Files to process'
    )
    
    parser.add_argument(
        '-a', '--algorithm',
        choices=ChecksumTool.SUPPORTED_ALGORITHMS,
        default='sha256',
        help='Hash algorithm to use (default: sha256)'
    )
    
    parser.add_argument(
        '-v', '--verify',
        metavar='CHECKSUM',
        help='Verify file against expected checksum'
    )
    
    parser.add_argument(
        '-o', '--output',
        help='Output file for checksum list'
    )
    
    parser.add_argument(
        '-m', '--manifest',
        help='Generate JSON manifest file'
    )
    
    parser.add_argument(
        '-f', '--verify-file',
        help='Verify files using checksum file'
    )
    
    args = parser.parse_args()
    
    tool = ChecksumTool(args.algorithm)
    
    try:
        # Verify from file
        if args.verify_file:
            results = tool.verify_from_file(args.verify_file)
            all_passed = True
            
            for filename, result in results.items():
                if isinstance(result, bool):
                    status = "✓ PASS" if result else "✗ FAIL"
                    print(f"{status}: {filename}")
                    if not result:
                        all_passed = False
                else:
                    print(f"✗ ERROR: {filename} - {result}")
                    all_passed = False
            
            return 0 if all_passed else 1
        
        # Verify single file
        elif args.verify:
            if len(args.files) != 1:
                print("Error: Verify mode requires exactly one file", file=sys.stderr)
                return 1
            
            result = tool.verify(args.files[0], args.verify)
            if result:
                print(f"✓ Checksum verified: {args.files[0]}")
                return 0
            else:
                print(f"✗ Checksum verification failed: {args.files[0]}")
                return 1
        
        # Generate manifest
        elif args.manifest:
            tool.generate_manifest(args.files, args.manifest)
            print(f"Manifest generated: {args.manifest}")
        
        # Generate checksum file
        elif args.output:
            tool.generate_checksum_file(args.files, args.output)
            print(f"Checksums written to: {args.output}")
        
        # Calculate and display checksums
        else:
            for file_path in args.files:
                try:
                    checksum = tool.calculate(file_path)
                    print(f"{checksum}  {file_path}")
                except Exception as e:
                    print(f"Error: {file_path} - {e}", file=sys.stderr)
                    return 1
        
        return 0
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

if __name__ == '__main__':
    sys.exit(main())
