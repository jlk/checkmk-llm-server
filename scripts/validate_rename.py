#!/usr/bin/env python3
"""
Validation script for checkmk_agent to checkmk_mcp_server rename
Validates that no old references remain
"""
import subprocess
import sys
from pathlib import Path

def validate_no_old_references():
    """Validate that no old references remain"""
    patterns = ['checkmk_agent', 'checkmk-agent', 'checkmk-llm-agent']
    exclude_dirs = ['__pycache__', '.git', '.pytest_cache', 'node_modules', 'venv', '.mypy_cache']
    
    found_issues = False
    
    for pattern in patterns:
        print(f"\nChecking for pattern: '{pattern}'")
        
        # Use rg (ripgrep) for better performance and features
        cmd = ['rg', pattern, '.', '--type', 'py', '--type', 'md', '--type', 'yaml', '--type', 'json']
        for exclude_dir in exclude_dirs:
            cmd.extend(['--glob', f'!{exclude_dir}/**'])
        
        # Also exclude scripts that legitimately contain old references
        cmd.extend(['--glob', '!scripts/rename_*.py'])
        cmd.extend(['--glob', '!scripts/validate_rename.py'])
        cmd.extend(['--glob', '!scripts/rollback_validation.py'])
        cmd.extend(['--glob', '!specs/rename-checkmk-agent-to-mcp-server.md'])
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0 and result.stdout.strip():
            print(f"❌ Found remaining references to '{pattern}':")
            print(result.stdout)
            found_issues = True
        else:
            print(f"✅ No references to '{pattern}' found")
    
    if not found_issues:
        print("\n🎉 All validation checks passed! No old references found.")
        return True
    else:
        print("\n⚠️  Validation failed: Old references still exist")
        return False

def validate_python_syntax():
    """Validate that all Python files compile correctly"""
    print("\nValidating Python syntax...")
    
    failed_files = []
    compiled_count = 0
    
    for py_file in Path('.').rglob('*.py'):
        # Skip virtual environment and cache directories
        if any(part in str(py_file) for part in ['venv', '__pycache__', '.pytest_cache', '.mypy_cache']):
            continue
            
        try:
            subprocess.run(['python', '-m', 'py_compile', str(py_file)], 
                          check=True, capture_output=True)
            compiled_count += 1
        except subprocess.CalledProcessError as e:
            failed_files.append((str(py_file), e.stderr.decode()))
    
    if not failed_files:
        print(f"✅ All {compiled_count} Python files compiled successfully")
        return True
    else:
        print(f"❌ {len(failed_files)} Python files failed to compile:")
        for file, error in failed_files:
            print(f"  {file}: {error}")
        return False

def test_package_import():
    """Test that the renamed package can be imported"""
    print("\nTesting package import...")
    
    try:
        result = subprocess.run(['python', '-c', 'import checkmk_mcp_server; print("✅ Package imports successfully")'], 
                               capture_output=True, text=True, check=True)
        print(result.stdout.strip())
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Package import failed: {e.stderr}")
        return False

if __name__ == '__main__':
    print("Starting validation of checkmk_agent to checkmk_mcp_server rename...")
    
    all_passed = True
    
    # Run all validation checks
    all_passed &= validate_no_old_references()
    all_passed &= validate_python_syntax()  
    all_passed &= test_package_import()
    
    if all_passed:
        print("\n🎉 ALL VALIDATION CHECKS PASSED!")
        print("The rename operation completed successfully.")
        sys.exit(0)
    else:
        print("\n❌ VALIDATION FAILED!")
        print("Some checks failed. Please review the issues above.")
        sys.exit(1)