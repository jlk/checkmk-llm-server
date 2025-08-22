#!/usr/bin/env python3
"""
Documentation rename script for checkmk_agent to checkmk_mcp_server
Updates all documentation files with new naming
"""
import os
import re
from pathlib import Path

def update_documentation(root_dir):
    """Update documentation files"""
    updated_files = []
    
    # File extensions to process
    doc_extensions = ['*.md', '*.txt', '*.rst', '*.yaml', '*.yml', '*.json']
    
    for ext in doc_extensions:
        for doc_file in Path(root_dir).rglob(ext):
            # Skip binary and generated files
            if any(skip in str(doc_file) for skip in ['.git', '__pycache__', '.pytest_cache', 'node_modules', '.egg-info']):
                continue
                
            with open(doc_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            patterns = [
                # Package names
                (r'checkmk-llm-agent', 'checkmk-mcp-server'),
                (r'checkmk_agent', 'checkmk_mcp_server'),
                (r'checkmk-agent', 'checkmk-mcp-server'),
                
                # Project titles and descriptions
                (r'Checkmk LLM Agent', 'Checkmk MCP Server'),
                (r'checkmk llm agent', 'checkmk mcp server'),
                (r'LLM-powered agent for Checkmk', 'MCP server for Checkmk'),
                (r'LLM agent', 'MCP server'),
                
                # CLI commands
                (r'checkmk-agent\s+(--help|\w+)', r'checkmk-mcp-server \1'),
                
                # File paths and imports
                (r'from checkmk_agent', 'from checkmk_mcp_server'),
                (r'import checkmk_agent', 'import checkmk_mcp_server'),
            ]
            
            modified = False
            for pattern, replacement in patterns:
                new_content = re.sub(pattern, replacement, content)
                if new_content != content:
                    content = new_content
                    modified = True
            
            if modified:
                with open(doc_file, 'w', encoding='utf-8') as f:
                    f.write(content)
                updated_files.append(str(doc_file))
                print(f"Updated: {doc_file}")
    
    return updated_files

if __name__ == '__main__':
    print("Starting documentation rename from checkmk_agent to checkmk_mcp_server...")
    updated_files = update_documentation('.')
    print(f"\nCompleted! Updated {len(updated_files)} files.")
    if updated_files:
        print("\nUpdated files:")
        for file in updated_files:
            print(f"  - {file}")