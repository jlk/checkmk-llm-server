# Rename Project: checkmk_mcp_server to checkmk_mcp_server

## Overview
This specification outlines the systematic renaming of the project from `checkmk_mcp_server` to `checkmk_mcp_server` to better reflect its primary purpose as an MCP (Model Context Protocol) server for Checkmk monitoring.

## Impact Analysis
- **Python files to modify**: 186 files
- **Markdown files to modify**: 86 files
- **Total occurrences to replace**: ~1,100+ instances
- **Primary areas**: Core package, tests, documentation, configuration files, examples

## Automation Helpers

### Python Scripts for Batch Operations

```python
# scripts/rename_imports.py
import os
import re
from pathlib import Path

def update_python_imports(root_dir):
    """Update all Python imports from checkmk_mcp_server to checkmk_mcp_server"""
    for py_file in Path(root_dir).rglob('*.py'):
        with open(py_file, 'r') as f:
            content = f.read()
        
        # Update import statements
        patterns = [
            (r'from checkmk_mcp_server', 'from checkmk_mcp_server'),
            (r'import checkmk_mcp_server', 'import checkmk_mcp_server'),
            (r'checkmk_mcp_server\.', 'checkmk_mcp_server.')
        ]
        
        modified = False
        for pattern, replacement in patterns:
            new_content = re.sub(pattern, replacement, content)
            if new_content != content:
                content = new_content
                modified = True
        
        if modified:
            with open(py_file, 'w') as f:
                f.write(content)
            print(f"Updated: {py_file}")

# Usage: python scripts/rename_imports.py
if __name__ == '__main__':
    update_python_imports('.')
```

```python
# scripts/rename_docs.py
import re
from pathlib import Path

def update_documentation(root_dir):
    """Update documentation files"""
    for md_file in Path(root_dir).rglob('*.md'):
        with open(md_file, 'r') as f:
            content = f.read()
        
        patterns = [
            (r'checkmk-mcp-server', 'checkmk-mcp-server'),
            (r'checkmk_mcp_server', 'checkmk_mcp_server'),
            (r'checkmk-mcp-server', 'checkmk-mcp-server')
        ]
        
        modified = False
        for pattern, replacement in patterns:
            new_content = re.sub(pattern, replacement, content)
            if new_content != content:
                content = new_content
                modified = True
        
        if modified:
            with open(md_file, 'w') as f:
                f.write(content)
            print(f"Updated: {md_file}")

if __name__ == '__main__':
    update_documentation('.')
```

```python
# scripts/validate_rename.py
import subprocess
from pathlib import Path

def validate_no_old_references():
    """Validate that no old references remain"""
    patterns = ['checkmk_mcp_server', 'checkmk-mcp-server', 'checkmk-mcp-server']
    exclude_dirs = ['__pycache__', '.git', '.pytest_cache', 'node_modules']
    
    for pattern in patterns:
        cmd = ['grep', '-r', pattern, '.'] + [f'--exclude-dir={d}' for d in exclude_dirs]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"Found remaining references to '{pattern}':")
            print(result.stdout)
            return False
        
    print("✅ No old references found")
    return True

if __name__ == '__main__':
    validate_no_old_references()
```

## Python-Specific Considerations

### Import Statement Updates
- **Relative imports**: Update all `from .` and `from ..` statements that reference renamed modules
- **Absolute imports**: Change `from checkmk_mcp_server.module` to `from checkmk_mcp_server.module`
- **Dynamic imports**: Update any `importlib` or `__import__` calls
- **String-based imports**: Check for module names in strings (test mocks, configuration)

### Python Package Structure
- **__init__.py files**: Update package-level imports and exports
- **setup.py**: Change package name, entry points, and console scripts
- **Module paths**: Ensure all internal cross-references are updated
- **Test discovery**: Update pytest configuration for new package structure

### Testing Considerations
- **Mock patches**: Update `@patch` decorators with new module paths
- **Import paths in tests**: Update all test imports
- **Test data**: Update any hardcoded references in test fixtures
- **Coverage configuration**: Update `.coveragerc` if it exists

## Todo List

### Phase 1: Directory and Package Structure
- [x] Rename main package directory from `checkmk_mcp_server/` to `checkmk_mcp_server/`
- [x] Rename workspace file from `checkmk_mcp_server.code-workspace` to `checkmk_mcp_server.code-workspace`
- [x] Update workspace file internal references

### Phase 2: Core Python Package Updates
- [x] Run automated import update script on all 186 Python files
- [x] Rename main package directory from `checkmk_mcp_server/` to `checkmk_mcp_server/`
- [x] Update `setup.py` package configuration
- [x] Update entry point scripts (`mcp_checkmk_server.py`, `checkmk_cli_mcp.py`)
- [x] Verify all internal imports work correctly

### Phase 3: Documentation Updates
- [x] Run automated documentation update script on all 86 Markdown files
- [x] Update main `README.md` project title and installation instructions
- [x] Update `CLAUDE.md` project references and file structure
- [x] Update core documentation files in `docs/` directory
- [x] Review conversation logs in `docs/conversations/` for any needed updates

### Phase 4: Configuration and Examples
- [ ] Update workspace file from `checkmk_mcp_server.code-workspace` to `checkmk_mcp_server.code-workspace`
- [ ] Update configuration files (`.env.example`, `pytest.ini`, etc.)
- [ ] Update all example files and configurations
- [ ] Update any CI/CD configuration files

### Phase 5: Test Suite Updates
- [ ] Update all test imports and mock patches
- [ ] Update test class and function names containing old package name
- [ ] Update test fixtures and data files
- [ ] Verify pytest discovery works with new structure

### Phase 6: Metadata and Memory Updates
- [ ] Update Serena memory files in `.serena/memories/`
- [ ] Update other metadata directories (`.kilocode/`, `.kiro/`)
- [ ] Update any IDE-specific configuration files

### Phase 7: Utility Scripts and Specifications
- [ ] Update utility scripts in `scripts/` directory
- [ ] Update benchmark files
- [ ] Update specification files in `specs/`

### Phase 8: Validation and Testing
- [ ] Run validation script to check for remaining old references
- [ ] Compile all Python files to verify syntax
- [ ] Run full test suite with pytest
- [ ] Test CLI functionality with new command name
- [ ] Test MCP server operation
- [ ] Verify Claude Desktop integration works

### Phase 9: Final Cleanup and Verification
- [ ] Clean build artifacts and caches
- [ ] Test installation in clean environment
- [ ] Verify all functionality works as expected
- [ ] Document breaking changes for users

## Safety Procedures

### Before Starting
- [ ] Create complete backup of current working directory
- [ ] Commit all current changes to git
- [ ] Create a new branch for the rename operation
- [ ] Document current working state

### During Operation
- [ ] Work in small, atomic commits
- [ ] Test functionality after each major phase
- [ ] Keep detailed log of changes made
- [ ] Verify imports work before proceeding to next phase

### Validation Commands

```bash
# Validate no old references remain
rg "checkmk_mcp_server|checkmk-mcp-server|checkmk-mcp-server" --type py --type md

# Check Python import syntax
find . -name "*.py" -exec python -m py_compile {} \;

# Test package imports
python -c "import checkmk_mcp_server; print('Package imports successfully')"

# Run test suite
pytest -v --tb=short

# Test CLI entry point
checkmk-mcp-server --help

# Test MCP server startup
python mcp_checkmk_server.py --version
```

## Breaking Changes

Users will need to:
1. Update their Claude Desktop configuration to use `checkmk-mcp-server` command
2. Update any scripts using the old `checkmk-mcp-server` command
3. Reinstall the package with the new name
4. Update any imports if they're using this as a library

## Rollback Plan

If issues arise:
1. Git revert all commits related to the rename
2. Restore original `checkmk_mcp_server/` directory name
3. Restore original setup.py configuration
4. Clean and rebuild environment
5. Verify original functionality is restored

## Notes

- This is a breaking change requiring semantic version bump
- Consider creating migration guide for existing users
- May want to temporarily maintain compatibility alias
- Update any external documentation or references

## Completion Status

**Started**: 2025-08-22  
**Branch**: feature/rename-to-mcp-server  
**Current Status**: Safety procedures completed, ready for Phase 1  

**Pre-rename State**:
- Main package: `checkmk_mcp_server/` (191 files)
- Tests pass with basic import functionality
- Git branch created: feature/rename-to-mcp-server
- All changes committed to main branch

**Completed**: [Date]  
**Issues Encountered**: [List any problems]  
**Resolution**: [How issues were resolved]