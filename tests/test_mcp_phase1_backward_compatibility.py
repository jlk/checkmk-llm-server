"""
Test suite for Phase 1 backward compatibility.

Ensures that all imports that worked before the Phase 1 refactoring 
continue to work after the extraction of utilities and configuration.
"""

import pytest
from datetime import datetime
from decimal import Decimal


class TestBackwardCompatibility:
    """Test backward compatibility of imports after Phase 1 refactoring."""
    
    def test_main_server_import_still_works(self):
        """Test that the main server class import still works."""
        from checkmk_agent.mcp_server import CheckmkMCPServer
        
        assert CheckmkMCPServer is not None
        assert hasattr(CheckmkMCPServer, '__init__')
        
    def test_direct_server_import_still_works(self):
        """Test that direct server module import still works.""" 
        from checkmk_agent.mcp_server import CheckmkMCPServer
        
        assert CheckmkMCPServer is not None
        
    def test_utilities_backward_compatibility_import(self):
        """Test that utilities can still be imported from main package."""
        # These imports should work for backward compatibility
        from checkmk_agent.mcp_server import (
            MCPJSONEncoder,
            safe_json_dumps,
            sanitize_error
        )
        
        # Test that they actually work
        encoder = MCPJSONEncoder()
        assert encoder is not None
        
        data = {"timestamp": datetime.now(), "value": 42}
        json_str = safe_json_dumps(data)
        assert isinstance(json_str, str)
        
        error = RuntimeError("Test error")
        sanitized = sanitize_error(error)
        assert sanitized == "Test error"
        
    def test_utilities_preferred_import_path(self):
        """Test that utilities can be imported from utils package."""
        from checkmk_agent.mcp_server.utils import (
            MCPJSONEncoder,
            safe_json_dumps,
            sanitize_error
        )
        
        # Test that they work the same way
        encoder = MCPJSONEncoder()
        assert encoder is not None
        
    def test_configuration_import_from_main_package(self):
        """Test that configuration can be imported from main package."""
        from checkmk_agent.mcp_server import (
            ALL_TOOL_SCHEMAS,
            TOOL_CATEGORIES,
            validate_tool_definitions
        )
        
        assert isinstance(ALL_TOOL_SCHEMAS, dict)
        assert len(ALL_TOOL_SCHEMAS) > 0
        assert isinstance(TOOL_CATEGORIES, dict)
        assert callable(validate_tool_definitions)
        assert validate_tool_definitions() is True
        
    def test_configuration_preferred_import_path(self):
        """Test that configuration can be imported from config package."""
        from checkmk_agent.mcp_server.config import (
            ALL_TOOL_SCHEMAS,
            TOOL_CATEGORIES,
            validate_tool_definitions
        )
        
        assert isinstance(ALL_TOOL_SCHEMAS, dict)
        assert len(ALL_TOOL_SCHEMAS) > 0
        
    def test_same_objects_across_import_paths(self):
        """Test that the same objects are returned regardless of import path."""
        # Import from main package
        from checkmk_agent.mcp_server import (
            MCPJSONEncoder as MainEncoder,
            safe_json_dumps as main_dumps,
            ALL_TOOL_SCHEMAS as main_schemas
        )
        
        # Import from specific packages
        from checkmk_agent.mcp_server.utils import (
            MCPJSONEncoder as UtilsEncoder,
            safe_json_dumps as utils_dumps
        )
        from checkmk_agent.mcp_server.config import (
            ALL_TOOL_SCHEMAS as config_schemas
        )
        
        # Should be the same objects
        assert MainEncoder is UtilsEncoder
        assert main_dumps is utils_dumps
        assert main_schemas is config_schemas
        
    def test_entry_point_still_works(self):
        """Test that the entry point import pattern still works."""
        # This is the pattern used in mcp_checkmk_server.py
        from checkmk_agent.mcp_server import CheckmkMCPServer
        
        # Should be able to instantiate (though we won't fully initialize)
        assert CheckmkMCPServer is not None
        assert hasattr(CheckmkMCPServer, '__init__')
        
    def test_all_exports_are_available(self):
        """Test that all exported items are available from main package."""
        import checkmk_agent.mcp_server as mcp
        
        expected_exports = [
            "CheckmkMCPServer",
            "MCPJSONEncoder",
            "safe_json_dumps", 
            "sanitize_error",
            "ALL_TOOL_SCHEMAS",
            "TOOL_CATEGORIES",
            "validate_tool_definitions",
        ]
        
        for export in expected_exports:
            assert hasattr(mcp, export), f"Missing export: {export}"
            assert export in mcp.__all__, f"Export {export} not in __all__"


class TestExtractedUtilityFunctionality:
    """Test that extracted utilities maintain their functionality."""
    
    def test_json_encoder_maintains_functionality(self):
        """Test that MCPJSONEncoder works the same after extraction."""
        from checkmk_agent.mcp_server import MCPJSONEncoder
        
        encoder = MCPJSONEncoder()
        
        # Test various data types
        assert encoder.default(datetime(2025, 8, 19, 10, 30, 45)) == "2025-08-19T10:30:45"
        assert encoder.default(Decimal("123.45")) == 123.45
        
    def test_safe_json_dumps_maintains_functionality(self):
        """Test that safe_json_dumps works the same after extraction."""
        from checkmk_agent.mcp_server import safe_json_dumps
        import json
        
        data = {
            "timestamp": datetime(2025, 8, 19, 10, 30, 45),
            "value": Decimal("123.45"),
            "message": "test"
        }
        
        result = safe_json_dumps(data)
        parsed = json.loads(result)
        
        assert parsed["timestamp"] == "2025-08-19T10:30:45"
        assert parsed["value"] == 123.45
        assert parsed["message"] == "test"
        
    def test_sanitize_error_maintains_functionality(self):
        """Test that sanitize_error works the same after extraction."""
        from checkmk_agent.mcp_server import sanitize_error
        
        # Test basic functionality
        error = RuntimeError("Simple error message")
        result = sanitize_error(error)
        assert result == "Simple error message"
        
        # Test path sanitization
        error = FileNotFoundError("/usr/local/bin/secret/file.txt not found")
        result = sanitize_error(error)
        assert "/usr/local/bin/secret/" not in result
        assert "file.txt not found" in result


class TestConfigurationFunctionality:
    """Test that configuration functionality works correctly."""
    
    def test_tool_schemas_are_valid(self):
        """Test that tool schemas are valid and complete."""
        from checkmk_agent.mcp_server import ALL_TOOL_SCHEMAS, validate_tool_definitions
        
        assert len(ALL_TOOL_SCHEMAS) >= 7  # At least sample tools from each category
        assert validate_tool_definitions() is True
        
        # Test specific critical tools
        critical_tools = ["list_hosts", "create_host", "list_all_services"]
        for tool in critical_tools:
            assert tool in ALL_TOOL_SCHEMAS
            schema = ALL_TOOL_SCHEMAS[tool]
            assert "name" in schema
            assert "description" in schema
            assert schema["name"] == tool
            
    def test_tool_categories_are_complete(self):
        """Test that tool categories are properly organized."""
        from checkmk_agent.mcp_server import TOOL_CATEGORIES
        
        expected_categories = [
            "host_tools",
            "service_tools",
            "parameter_tools", 
            "status_tools",
            "event_tools",
            "metrics_tools",
            "advanced_tools"
        ]
        
        for category in expected_categories:
            assert category in TOOL_CATEGORIES
            assert isinstance(TOOL_CATEGORIES[category], list)
            assert len(TOOL_CATEGORIES[category]) > 0


class TestDirectoryStructure:
    """Test that the new directory structure is properly set up."""
    
    def test_all_new_packages_are_importable(self):
        """Test that all new packages can be imported."""
        packages = [
            "checkmk_agent.mcp_server.tools",
            "checkmk_agent.mcp_server.handlers", 
            "checkmk_agent.mcp_server.utils",
            "checkmk_agent.mcp_server.validation",
            "checkmk_agent.mcp_server.config"
        ]
        
        for package in packages:
            try:
                __import__(package)
            except ImportError as e:
                pytest.fail(f"Failed to import package {package}: {e}")
                
    def test_utils_package_exports(self):
        """Test that utils package exports are correct."""
        import checkmk_agent.mcp_server.utils as utils
        
        expected_exports = ["MCPJSONEncoder", "safe_json_dumps", "sanitize_error"]
        
        for export in expected_exports:
            assert hasattr(utils, export)
            assert export in utils.__all__
            
    def test_config_package_exports(self):
        """Test that config package exports are correct.""" 
        import checkmk_agent.mcp_server.config as config
        
        expected_exports = [
            "ALL_TOOL_SCHEMAS",
            "TOOL_CATEGORIES", 
            "validate_tool_definitions"
        ]
        
        for export in expected_exports:
            assert hasattr(config, export)
            assert export in config.__all__


if __name__ == "__main__":
    pytest.main([__file__])