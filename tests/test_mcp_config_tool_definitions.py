"""
Test suite for MCP server tool definitions configuration.

Tests the extracted tool definition schemas and validation logic.
Ensures no functionality is lost during the Phase 1 refactoring
extraction and validates tool schema consistency.
"""

import pytest
from typing import Dict, Any

from checkmk_agent.mcp_server.config.tool_definitions import (
    ALL_TOOL_SCHEMAS,
    TOOL_CATEGORIES,
    HOST_TOOLS_SCHEMAS,
    SERVICE_TOOLS_SCHEMAS,
    PARAMETER_TOOLS_SCHEMAS,
    STATUS_TOOLS_SCHEMAS,
    EVENT_TOOLS_SCHEMAS,
    METRICS_TOOLS_SCHEMAS,
    ADVANCED_TOOLS_SCHEMAS,
    validate_tool_definitions,
)


class TestToolSchemaStructure:
    """Test the structure and content of tool schemas."""
    
    def test_all_schemas_have_required_fields(self):
        """Test that all tool schemas have required name and description fields."""
        for tool_name, schema in ALL_TOOL_SCHEMAS.items():
            assert "name" in schema, f"Tool {tool_name} missing 'name' field"
            assert "description" in schema, f"Tool {tool_name} missing 'description' field"
            assert schema["name"] == tool_name, f"Tool name mismatch for {tool_name}"
            assert isinstance(schema["description"], str), f"Tool {tool_name} description must be string"
            assert len(schema["description"]) > 0, f"Tool {tool_name} description cannot be empty"
            
    def test_schemas_have_valid_input_schemas(self):
        """Test that tool schemas have valid inputSchema structures."""
        for tool_name, schema in ALL_TOOL_SCHEMAS.items():
            if "inputSchema" in schema:
                input_schema = schema["inputSchema"]
                assert isinstance(input_schema, dict), f"Tool {tool_name} inputSchema must be dict"
                assert "type" in input_schema, f"Tool {tool_name} inputSchema missing type"
                assert input_schema["type"] == "object", f"Tool {tool_name} inputSchema type must be 'object'"
                
                if "properties" in input_schema:
                    properties = input_schema["properties"]
                    assert isinstance(properties, dict), f"Tool {tool_name} properties must be dict"
                    
                    # Each property should have a type
                    for prop_name, prop_def in properties.items():
                        assert isinstance(prop_def, dict), f"Tool {tool_name} property {prop_name} must be dict"
                        assert "type" in prop_def, f"Tool {tool_name} property {prop_name} missing type"
                        assert "description" in prop_def, f"Tool {tool_name} property {prop_name} missing description"
                        
    def test_required_fields_are_valid(self):
        """Test that required fields reference existing properties."""
        for tool_name, schema in ALL_TOOL_SCHEMAS.items():
            if "inputSchema" in schema and "required" in schema["inputSchema"]:
                required = schema["inputSchema"]["required"]
                properties = schema["inputSchema"].get("properties", {})
                
                assert isinstance(required, list), f"Tool {tool_name} required must be list"
                for req_field in required:
                    assert req_field in properties, f"Tool {tool_name} required field '{req_field}' not in properties"
                    
    def test_enum_values_are_valid(self):
        """Test that enum properties have valid enum values."""
        for tool_name, schema in ALL_TOOL_SCHEMAS.items():
            if "inputSchema" in schema and "properties" in schema["inputSchema"]:
                properties = schema["inputSchema"]["properties"]
                for prop_name, prop_def in properties.items():
                    if "enum" in prop_def:
                        enum_values = prop_def["enum"]
                        assert isinstance(enum_values, list), f"Tool {tool_name} property {prop_name} enum must be list"
                        assert len(enum_values) > 0, f"Tool {tool_name} property {prop_name} enum cannot be empty"
                        assert len(set(enum_values)) == len(enum_values), f"Tool {tool_name} property {prop_name} enum has duplicates"


class TestToolCategories:
    """Test tool categorization and organization."""
    
    def test_tool_categories_structure(self):
        """Test that TOOL_CATEGORIES has expected structure."""
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
            assert category in TOOL_CATEGORIES, f"Missing category: {category}"
            assert isinstance(TOOL_CATEGORIES[category], list), f"Category {category} must be list"
            
    def test_all_tools_are_categorized(self):
        """Test that all tools in ALL_TOOL_SCHEMAS are categorized."""
        categorized_tools = set()
        for category_tools in TOOL_CATEGORIES.values():
            categorized_tools.update(category_tools)
            
        schema_tools = set(ALL_TOOL_SCHEMAS.keys())
        
        assert categorized_tools == schema_tools, f"Mismatch between categorized and schema tools"
        
    def test_no_duplicate_tools_across_categories(self):
        """Test that no tool appears in multiple categories."""
        all_tools = []
        for category_tools in TOOL_CATEGORIES.values():
            all_tools.extend(category_tools)
            
        assert len(all_tools) == len(set(all_tools)), "Tools appear in multiple categories"
        
    def test_category_specific_schemas_consistency(self):
        """Test that category-specific schema dictionaries are consistent."""
        category_schemas = {
            "host_tools": HOST_TOOLS_SCHEMAS,
            "service_tools": SERVICE_TOOLS_SCHEMAS,
            "parameter_tools": PARAMETER_TOOLS_SCHEMAS,
            "status_tools": STATUS_TOOLS_SCHEMAS,
            "event_tools": EVENT_TOOLS_SCHEMAS,
            "metrics_tools": METRICS_TOOLS_SCHEMAS,
            "advanced_tools": ADVANCED_TOOLS_SCHEMAS,
        }
        
        for category, expected_tools in TOOL_CATEGORIES.items():
            if category in category_schemas:
                schema_dict = category_schemas[category]
                schema_tools = set(schema_dict.keys())
                category_tool_set = set(expected_tools)
                
                assert schema_tools == category_tool_set, f"Category {category} schema mismatch"
                
                # Verify schemas are in ALL_TOOL_SCHEMAS
                for tool_name in schema_tools:
                    assert tool_name in ALL_TOOL_SCHEMAS, f"Tool {tool_name} missing from ALL_TOOL_SCHEMAS"
                    assert ALL_TOOL_SCHEMAS[tool_name] == schema_dict[tool_name], f"Schema mismatch for {tool_name}"


class TestSpecificToolSchemas:
    """Test specific tool schemas for critical tools."""
    
    def test_list_hosts_schema(self):
        """Test the list_hosts tool schema."""
        schema = ALL_TOOL_SCHEMAS["list_hosts"]
        assert schema["name"] == "list_hosts"
        assert "List Checkmk hosts" in schema["description"]
        
        # Check input schema
        input_schema = schema["inputSchema"]
        properties = input_schema["properties"]
        
        expected_props = {"search", "folder", "limit"}
        assert set(properties.keys()) == expected_props
        
        # Check limit property has correct constraints
        limit_prop = properties["limit"]
        assert limit_prop["type"] == "integer"
        assert limit_prop["minimum"] == 1
        assert limit_prop["maximum"] == 1000
        assert limit_prop["default"] == 100
        
    def test_create_host_schema(self):
        """Test the create_host tool schema."""
        schema = ALL_TOOL_SCHEMAS["create_host"]
        assert schema["name"] == "create_host"
        
        # Check required fields
        required = schema["inputSchema"]["required"]
        assert "host_name" in required
        
        # Check properties
        properties = schema["inputSchema"]["properties"]
        assert "host_name" in properties
        assert "folder" in properties
        assert properties["folder"]["default"] == "/"
        
    def test_acknowledge_service_problem_schema(self):
        """Test the acknowledge_service_problem tool schema."""
        schema = ALL_TOOL_SCHEMAS["acknowledge_service_problem"]
        assert schema["name"] == "acknowledge_service_problem"
        
        # Check required fields
        required = schema["inputSchema"]["required"]
        expected_required = {"host_name", "service_name", "comment"}
        assert set(required) == expected_required
        
        # Check sticky default
        properties = schema["inputSchema"]["properties"]
        assert properties["sticky"]["default"] is False
        
    def test_get_service_metrics_schema(self):
        """Test the get_service_metrics tool schema.""" 
        schema = ALL_TOOL_SCHEMAS["get_service_metrics"]
        assert schema["name"] == "get_service_metrics"
        
        # Check timeframe enum
        properties = schema["inputSchema"]["properties"]
        timeframe_enum = properties["timeframe"]["enum"]
        expected_values = ["1h", "4h", "24h", "7d", "30d"]
        assert timeframe_enum == expected_values
        assert properties["timeframe"]["default"] == "1h"


class TestValidationFunction:
    """Test the validate_tool_definitions function."""
    
    def test_validate_returns_true_for_current_definitions(self):
        """Test that validate_tool_definitions returns True for current state."""
        assert validate_tool_definitions() is True
        
    def test_validate_detects_missing_tools_in_schemas(self):
        """Test that validation detects when tools are missing from schemas."""
        # Temporarily modify TOOL_CATEGORIES to include a non-existent tool
        original_host_tools = TOOL_CATEGORIES["host_tools"].copy()
        TOOL_CATEGORIES["host_tools"].append("non_existent_tool")
        
        try:
            assert validate_tool_definitions() is False
        finally:
            # Restore original state
            TOOL_CATEGORIES["host_tools"] = original_host_tools
            
    def test_validate_detects_invalid_schema_structure(self):
        """Test that validation detects invalid schema structures."""
        # Temporarily modify a schema to be invalid
        original_schema = ALL_TOOL_SCHEMAS["list_hosts"].copy()
        del ALL_TOOL_SCHEMAS["list_hosts"]["name"]
        
        try:
            assert validate_tool_definitions() is False
        finally:
            # Restore original state
            ALL_TOOL_SCHEMAS["list_hosts"] = original_schema


class TestBackwardCompatibility:
    """Test backward compatibility of tool definitions."""
    
    def test_imports_work_from_config_package(self):
        """Test that imports work from the config package."""
        from checkmk_agent.mcp_server.config import (
            ALL_TOOL_SCHEMAS,
            TOOL_CATEGORIES,
            validate_tool_definitions,
        )
        
        # Verify they are the same objects
        assert len(ALL_TOOL_SCHEMAS) > 0
        assert len(TOOL_CATEGORIES) > 0
        assert callable(validate_tool_definitions)
        
    def test_schema_format_matches_mcp_tool_expectations(self):
        """Test that schemas match expected MCP Tool format."""
        from mcp.types import Tool
        
        # Test that we can create MCP Tool objects from our schemas
        for tool_name, schema in ALL_TOOL_SCHEMAS.items():
            try:
                tool = Tool(
                    name=schema["name"],
                    description=schema["description"],
                    inputSchema=schema.get("inputSchema", {})
                )
                assert tool.name == tool_name
                assert tool.description == schema["description"]
            except Exception as e:
                pytest.fail(f"Failed to create MCP Tool from schema for {tool_name}: {e}")


class TestSchemaCompleteness:
    """Test that schema definitions are reasonably complete."""
    
    def test_minimum_number_of_tools(self):
        """Test that we have a reasonable number of tools defined."""
        # Based on the spec, we should have at least these sample tools
        assert len(ALL_TOOL_SCHEMAS) >= 7  # At least one from each category
        
    def test_critical_tools_are_present(self):
        """Test that critical tools are present in schemas."""
        critical_tools = [
            "list_hosts",
            "create_host", 
            "list_all_services",
            "acknowledge_service_problem",
            "get_effective_parameters",
            "set_service_parameters",
        ]
        
        for tool in critical_tools:
            assert tool in ALL_TOOL_SCHEMAS, f"Critical tool {tool} missing from schemas"
            
    def test_parameter_tools_have_host_service_fields(self):
        """Test that parameter tools have expected host/service fields."""
        parameter_tools = TOOL_CATEGORIES["parameter_tools"]
        
        for tool_name in parameter_tools:
            if tool_name in ["get_effective_parameters", "set_service_parameters"]:
                schema = ALL_TOOL_SCHEMAS[tool_name]
                properties = schema["inputSchema"]["properties"]
                
                assert "host_name" in properties, f"Tool {tool_name} missing host_name"
                assert "service_name" in properties, f"Tool {tool_name} missing service_name"
                
                required = schema["inputSchema"]["required"]
                assert "host_name" in required, f"Tool {tool_name} host_name not required"
                assert "service_name" in required, f"Tool {tool_name} service_name not required"


if __name__ == "__main__":
    pytest.main([__file__])