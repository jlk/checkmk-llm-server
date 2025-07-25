#!/usr/bin/env python3
"""Monitor MCP server logs and identify errors for fixing."""

import time
import os
import re
from datetime import datetime

def monitor_log_file(log_path="mcp-server-checkmk.log"):
    """Monitor the MCP server log file for errors."""
    
    print(f"🔍 Starting to monitor {log_path}")
    print("Press Ctrl+C to stop monitoring")
    print("=" * 60)
    
    # Keep track of file position to only show new content
    last_position = 0
    
    # If file exists, start from the end
    if os.path.exists(log_path):
        with open(log_path, 'r') as f:
            f.seek(0, 2)  # Go to end of file
            last_position = f.tell()
        print(f"📍 Starting from end of existing log file (position {last_position})")
    else:
        print(f"📍 Waiting for {log_path} to be created...")
    
    try:
        while True:
            if os.path.exists(log_path):
                with open(log_path, 'r') as f:
                    f.seek(last_position)
                    new_content = f.read()
                    
                    if new_content:
                        # Process new content line by line
                        lines = new_content.strip().split('\n')
                        for line in lines:
                            if line.strip():
                                process_log_line(line)
                        
                        last_position = f.tell()
            
            time.sleep(0.1)  # Check every 100ms
            
    except KeyboardInterrupt:
        print("\n🛑 Monitoring stopped by user")
    except Exception as e:
        print(f"❌ Error monitoring log: {e}")

def process_log_line(line):
    """Process a single log line and identify errors."""
    
    # Color codes for terminal output
    RED = '\033[91m'
    YELLOW = '\033[93m'
    GREEN = '\033[92m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    
    # Get timestamp
    timestamp = datetime.now().strftime("%H:%M:%S")
    
    # Check for different types of messages
    if "ERROR" in line:
        print(f"{RED}[{timestamp}] 🚨 ERROR: {line}{RESET}")
        analyze_error(line)
    elif "WARNING" in line or "WARN" in line:
        print(f"{YELLOW}[{timestamp}] ⚠️  WARNING: {line}{RESET}")
    elif "Traceback" in line or "File \"" in line and "line" in line:
        print(f"{RED}[{timestamp}] 📋 TRACEBACK: {line}{RESET}")
    elif "Exception" in line or "Error" in line:
        print(f"{RED}[{timestamp}] 💥 EXCEPTION: {line}{RESET}")
        analyze_error(line)
    elif "INFO" in line and ("tool" in line.lower() or "call" in line.lower()):
        print(f"{BLUE}[{timestamp}] 📞 CALL: {line}{RESET}")
    elif "DEBUG" in line:
        # Only show debug messages about tools/calls
        if any(keyword in line.lower() for keyword in ["tool", "call", "handler", "result"]):
            print(f"{GREEN}[{timestamp}] 🔍 DEBUG: {line}{RESET}")
    else:
        # Regular log line
        print(f"[{timestamp}] {line}")

def analyze_error(error_line):
    """Analyze error patterns and suggest fixes."""
    
    error_patterns = {
        r"got an unexpected keyword argument": {
            "type": "Parameter Mismatch",
            "description": "Handler receiving parameters that service method doesn't accept",
            "fix": "Change handler signature to **kwargs or remove parameter passing"
        },
        r"'(\w+)' object has no attribute '(\w+)'": {
            "type": "Attribute Error", 
            "description": "Object missing expected attribute/method",
            "fix": "Check if object is correct type or if method exists"
        },
        r"StatusService\.(\w+)\(\) missing \d+ required positional argument": {
            "type": "Missing Arguments",
            "description": "Service method called without required parameters",
            "fix": "Add missing required parameters to service method call"
        },
        r"TypeError.*'(\w+)' object": {
            "type": "Type Error",
            "description": "Object type mismatch",
            "fix": "Check object types and conversions"
        },
        r"validation errors for CallToolResult": {
            "type": "MCP Response Format Error",
            "description": "CallToolResult not constructed properly",
            "fix": "Check CallToolResult content format - ensure proper TextContent objects"
        },
        r"'dict' object has no attribute 'model_dump'": {
            "type": "Model Dump Error",
            "description": "Trying to call model_dump() on plain dict",
            "fix": "Use conditional: data.model_dump() if hasattr(data, 'model_dump') else data"
        }
    }
    
    print(f"  🔍 Analyzing error pattern...")
    
    for pattern, info in error_patterns.items():
        if re.search(pattern, error_line, re.IGNORECASE):
            print(f"  🎯 Pattern matched: {info['type']}")
            print(f"  📝 Description: {info['description']}")
            print(f"  🔧 Suggested fix: {info['fix']}")
            break
    else:
        print(f"  ❓ Unknown error pattern - needs manual analysis")

if __name__ == "__main__":
    monitor_log_file()