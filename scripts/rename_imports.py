#!/usr/bin/env python3
"""
Import rename script for checkmk_agent to checkmk_mcp_server
Updates all Python imports from checkmk_mcp_server to checkmk_mcp_server
"""
import os
import re
from pathlib import Path

def update_python_imports(root_dir):
    """Update all Python imports from checkmk_mcp_server to checkmk_mcp_server"""
    updated_files = []
    
    for py_file in Path(root_dir).rglob('*.py'):
        with open(py_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Update import statements
        patterns = [
            (r'from checkmk_mcp_server', 'from checkmk_mcp_server'),
            (r'import checkmk_mcp_server', 'import checkmk_mcp_server'),
            (r'checkmk_agent\.', 'checkmk_mcp_server.')
        ]
        
        modified = False
        for pattern, replacement in patterns:
            new_content = re.sub(pattern, replacement, content)
            if new_content != content:
                content = new_content
                modified = True
        
        if modified:
            with open(py_file, 'w', encoding='utf-8') as f:
                f.write(content)
            updated_files.append(str(py_file))
            print(f"Updated: {py_file}")
    
    return updated_files

if __name__ == '__main__':
    print("Starting import rename from checkmk_mcp_server to checkmk_mcp_server...")
    updated_files = update_python_imports('.')
    print(f"\nCompleted! Updated {len(updated_files)} files.")
    if updated_files:
        print("\nUpdated files:")
        for file in updated_files:
            print(f"  - {file}")