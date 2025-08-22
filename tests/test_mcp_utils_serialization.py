"""
Test suite for MCP server serialization utilities.

Tests the extracted JSON serialization utilities including MCPJSONEncoder
and safe_json_dumps function. Ensures no functionality is lost during
the Phase 1 refactoring extraction.
"""

import json
import pytest
from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from dataclasses import dataclass
from typing import Any

from checkmk_mcp_server.mcp_server.utils.serialization import MCPJSONEncoder, safe_json_dumps


# Test fixtures and helper classes
class SerializationTestEnum(Enum):
    """Test enum for serialization testing."""
    VALUE1 = "test_value_1"
    VALUE2 = "test_value_2" 


@dataclass
class MockPydanticModel:
    """Test class that mimics Pydantic model behavior."""
    name: str
    value: int
    
    def model_dump(self):
        """Mock Pydantic model_dump method."""
        return {"name": self.name, "value": self.value}


@dataclass
class MockDataClass:
    """Test dataclass for __dict__ serialization."""
    name: str
    value: int


class UnsupportedObject:
    """Test class that cannot be serialized by MCPJSONEncoder."""
    __slots__ = ['value']  # No __dict__ attribute
    
    def __init__(self, value=None):
        self.value = value


class TestMCPJSONEncoder:
    """Test cases for MCPJSONEncoder class."""
    
    def test_datetime_serialization(self):
        """Test datetime object serialization."""
        encoder = MCPJSONEncoder()
        dt = datetime(2025, 8, 19, 10, 30, 45, 123456)
        result = encoder.default(dt)
        assert result == "2025-08-19T10:30:45.123456"
        
    def test_date_serialization(self):
        """Test date object serialization."""
        encoder = MCPJSONEncoder()
        d = date(2025, 8, 19)
        result = encoder.default(d)
        assert result == "2025-08-19"
        
    def test_decimal_serialization(self):
        """Test Decimal object serialization."""
        encoder = MCPJSONEncoder()
        decimal_val = Decimal("123.456")
        result = encoder.default(decimal_val)
        assert result == 123.456
        assert isinstance(result, float)
        
    def test_enum_serialization(self):
        """Test Enum object serialization."""
        encoder = MCPJSONEncoder()
        enum_val = SerializationTestEnum.VALUE1
        result = encoder.default(enum_val)
        assert result == "test_value_1"
        
    def test_pydantic_model_serialization(self):
        """Test object with model_dump method serialization."""
        encoder = MCPJSONEncoder()
        model = MockPydanticModel("test", 42)
        result = encoder.default(model)
        assert result == {"name": "test", "value": 42}
        
    def test_object_with_dict_serialization(self):
        """Test object with __dict__ attribute serialization."""
        encoder = MCPJSONEncoder()
        obj = MockDataClass("test", 42)
        result = encoder.default(obj)
        assert result == {"name": "test", "value": 42}
        
    def test_unsupported_object_raises_error(self):
        """Test that unsupported objects raise TypeError."""
        encoder = MCPJSONEncoder()
        unsupported_obj = UnsupportedObject()
        
        with pytest.raises(TypeError):
            encoder.default(unsupported_obj)
            
    def test_full_json_dumps_integration(self):
        """Test full integration with json.dumps."""
        data = {
            "timestamp": datetime(2025, 8, 19, 10, 30, 45),
            "date": date(2025, 8, 19),
            "decimal": Decimal("123.45"),
            "enum": SerializationTestEnum.VALUE2,
            "model": MockPydanticModel("integration", 100),
        }
        
        result = json.dumps(data, cls=MCPJSONEncoder)
        parsed = json.loads(result)
        
        assert parsed["timestamp"] == "2025-08-19T10:30:45"
        assert parsed["date"] == "2025-08-19"
        assert parsed["decimal"] == 123.45
        assert parsed["enum"] == "test_value_2"
        assert parsed["model"] == {"name": "integration", "value": 100}


class TestSafeJsonDumps:
    """Test cases for safe_json_dumps function."""
    
    def test_simple_object_serialization(self):
        """Test serialization of simple Python objects."""
        data = {"string": "test", "number": 42, "boolean": True}
        result = safe_json_dumps(data)
        
        # Should be valid JSON
        parsed = json.loads(result)
        assert parsed == data
        
    def test_datetime_object_serialization(self):
        """Test serialization with datetime objects."""
        dt = datetime(2025, 8, 19, 10, 30, 45)
        data = {"timestamp": dt, "message": "test"}
        result = safe_json_dumps(data)
        
        parsed = json.loads(result)
        assert parsed["timestamp"] == "2025-08-19T10:30:45"
        assert parsed["message"] == "test"
        
    def test_complex_nested_object_serialization(self):
        """Test serialization of complex nested structures."""
        data = {
            "metadata": {
                "created": datetime(2025, 8, 19, 10, 30, 45),
                "version": Decimal("1.5"),
                "status": SerializationTestEnum.VALUE1,
            },
            "data": [
                MockPydanticModel("item1", 10),
                MockPydanticModel("item2", 20),
            ],
            "simple": {"count": 42}
        }
        
        result = safe_json_dumps(data)
        parsed = json.loads(result)
        
        assert parsed["metadata"]["created"] == "2025-08-19T10:30:45"
        assert parsed["metadata"]["version"] == 1.5
        assert parsed["metadata"]["status"] == "test_value_1"
        assert len(parsed["data"]) == 2
        assert parsed["data"][0] == {"name": "item1", "value": 10}
        assert parsed["simple"]["count"] == 42
        
    def test_unicode_support(self):
        """Test that Unicode characters are preserved."""
        data = {"message": "Hello 世界 🌍", "emoji": "🚀"}
        result = safe_json_dumps(data)
        
        parsed = json.loads(result)
        assert parsed["message"] == "Hello 世界 🌍"
        assert parsed["emoji"] == "🚀"
        
    def test_serialization_failure_fallback(self):
        """Test fallback behavior when serialization fails."""
        # Create an object that will cause serialization to fail
        class ProblematicObject:
            def __init__(self):
                self.circular_ref = self
                
        problematic = ProblematicObject()
        data = {"problem": problematic}
        
        result = safe_json_dumps(data)
        parsed = json.loads(result)
        
        # Should contain error information
        assert "error" in parsed
        assert "Serialization failed" in parsed["error"]
        assert "data" in parsed
        
    def test_none_values(self):
        """Test handling of None values."""
        data = {"value": None, "list": [1, None, 3]}
        result = safe_json_dumps(data)
        
        parsed = json.loads(result)
        assert parsed["value"] is None
        assert parsed["list"] == [1, None, 3]
        
    def test_empty_structures(self):
        """Test handling of empty structures."""
        test_cases = [
            {},
            [],
            "",
            {"empty_dict": {}, "empty_list": [], "empty_string": ""},
        ]
        
        for data in test_cases:
            result = safe_json_dumps(data)
            parsed = json.loads(result)
            assert parsed == data
            
    def test_large_decimal_precision(self):
        """Test handling of high-precision Decimal values."""
        decimal_val = Decimal("123.456789012345678901234567890")
        data = {"precision": decimal_val}
        result = safe_json_dumps(data)
        
        parsed = json.loads(result)
        # Should be converted to float (may lose precision)
        assert isinstance(parsed["precision"], float)
        assert abs(parsed["precision"] - 123.456789012345678901234567890) < 1e-10


class TestUtilityIntegration:
    """Integration tests for utility functions."""
    
    def test_backward_compatibility_imports(self):
        """Test that utilities can be imported from utils package."""
        # Test direct imports
        from checkmk_mcp_server.mcp_server.utils import MCPJSONEncoder, safe_json_dumps
        
        # Test that they work
        data = {"timestamp": datetime.now()}
        result = safe_json_dumps(data)
        assert isinstance(result, str)
        
        encoder = MCPJSONEncoder()
        assert encoder is not None
        
    def test_real_world_checkmk_data_structure(self):
        """Test with realistic Checkmk-like data structures."""
        checkmk_data = {
            "hosts": [
                {
                    "name": "server01",
                    "address": "192.168.1.10",
                    "services": [
                        {
                            "name": "CPU load",
                            "state": SerializationTestEnum.VALUE1,  # OK status
                            "last_check": datetime(2025, 8, 19, 10, 0, 0),
                            "performance_data": {
                                "load1": Decimal("0.85"),
                                "load5": Decimal("0.92"),
                                "load15": Decimal("0.88"),
                            }
                        }
                    ]
                }
            ],
            "summary": {
                "total_hosts": 1,
                "total_services": 1,
                "generated_at": datetime.now(),
            }
        }
        
        result = safe_json_dumps(checkmk_data)
        parsed = json.loads(result)
        
        # Validate structure is preserved
        assert len(parsed["hosts"]) == 1
        assert parsed["hosts"][0]["name"] == "server01"
        assert parsed["hosts"][0]["services"][0]["name"] == "CPU load"
        assert parsed["hosts"][0]["services"][0]["state"] == "test_value_1"
        assert isinstance(parsed["hosts"][0]["services"][0]["performance_data"]["load1"], float)
        assert parsed["summary"]["total_hosts"] == 1


if __name__ == "__main__":
    pytest.main([__file__])