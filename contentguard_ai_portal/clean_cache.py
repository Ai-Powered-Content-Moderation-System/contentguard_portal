#!/usr/bin/env python3
import subprocess
import sys

def clean_python_cache():
    """Run find commands to clean Python cache files"""
    
    commands = [
        'find . -type f -name "*.pyo" -delete',
        'find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null',
        'find . -type f -name "*.pyc" -delete'
    ]
    
    print("🧹 Cleaning Python cache files...")
    
    for cmd in commands:
        print(f"  → {cmd}")
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        # Ignore errors (e.g., no files found)
    
    print("✅ Cache cleaned!")

if __name__ == "__main__":
    clean_python_cache()
