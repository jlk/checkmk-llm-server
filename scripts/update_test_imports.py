#!/usr/bin/env python3
"""Script to update test file imports to use the new modular structure.

This script updates all test files that import CheckmkMCPServer from the old
direct server import to use the backward-compatible import path.
"""

import os
import re
import sys
from pathlib import Path
from typing import List, Tuple, Dict

def find_test_files_to_update() -> List[Path]:
    """Find all test files that need import updates."""
    test_dir = Path("tests")
    files_to_update = []
    
    if not test_dir.exists():
        print(f"Error: Test directory {test_dir} not found")
        return []
    
    # Pattern to match imports from server.py
    server_import_pattern = re.compile(r'from checkmk_mcp_server\.mcp_server\.server import')
    
    for test_file in test_dir.glob("test_*.py"):
        try:
            with open(test_file, 'r', encoding='utf-8') as f:
                content = f.read()
                if server_import_pattern.search(content):
                    files_to_update.append(test_file)
        except Exception as e:
            print(f"Warning: Could not read {test_file}: {e}")
    
    return files_to_update

def update_import_in_file(file_path: Path) -> Tuple[bool, str]:
    """Update imports in a single file.
    
    Returns:
        Tuple of (success, message)
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            original_content = f.read()
        
        # Replace the old import pattern with the new one
        updated_content = re.sub(
            r'from checkmk_mcp_server\.mcp_server\.server import CheckmkMCPServer',
            'from checkmk_mcp_server.mcp_server import CheckmkMCPServer',
            original_content
        )
        
        # Check if changes were made
        if updated_content == original_content:
            return True, "No changes needed"
        
        # Write the updated content
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(updated_content)
        
        return True, "Successfully updated imports"
        
    except Exception as e:
        return False, f"Error updating file: {e}"

def validate_import_changes() -> bool:
    """Validate that the updated imports still work."""
    try:
        # Test the import path that we're updating to
        from checkmk_mcp_server.mcp_server import CheckmkMCPServer
        return True
    except ImportError as e:
        print(f"Error: Import validation failed: {e}")
        return False

def main():
    """Main execution function."""
    print("🔄 Starting test import updates...")
    
    # Validate that the target import path works
    if not validate_import_changes():
        print("❌ Import validation failed. Cannot proceed with updates.")
        sys.exit(1)
    
    # Find files to update
    files_to_update = find_test_files_to_update()
    
    if not files_to_update:
        print("✅ No test files need import updates")
        return
    
    print(f"📋 Found {len(files_to_update)} test files to update:")
    for file_path in files_to_update:
        print(f"  - {file_path}")
    
    # Update each file
    results: Dict[str, str] = {}
    for file_path in files_to_update:
        success, message = update_import_in_file(file_path)
        results[str(file_path)] = message
        status = "✅" if success else "❌"
        print(f"{status} {file_path}: {message}")
    
    # Summary
    successful_updates = sum(1 for msg in results.values() if "Successfully updated" in msg)
    print(f"\n📊 Summary:")
    print(f"  - Files processed: {len(files_to_update)}")
    print(f"  - Successful updates: {successful_updates}")
    print(f"  - No changes needed: {len(files_to_update) - successful_updates}")
    
    if successful_updates > 0:
        print("\n🎉 Test import updates completed successfully!")
    else:
        print("\n✅ All test files already using correct import paths")

if __name__ == "__main__":
    main()