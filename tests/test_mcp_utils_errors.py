"""
Test suite for MCP server error handling utilities.

Tests the extracted error sanitization utilities including sanitize_error
function. Ensures no functionality is lost during the Phase 1 refactoring
extraction and validates security aspects of error sanitization.
"""

import pytest
from pathlib import Path
from unittest.mock import patch

from checkmk_mcp_server.mcp_server.utils.errors import sanitize_error


class TestSanitizeError:
    """Test cases for sanitize_error function."""
    
    def test_simple_error_message(self):
        """Test sanitization of simple error messages."""
        error = ValueError("Simple error message")
        result = sanitize_error(error)
        assert result == "Simple error message"
        
    def test_home_directory_replacement(self):
        """Test that home directory paths are replaced with ~."""
        home_path = str(Path.home())
        error = FileNotFoundError(f"{home_path}/secret/file.txt not found")
        result = sanitize_error(error)
        assert home_path not in result
        # After home replacement and path removal, only filename should remain
        assert "file.txt not found" in result
        
    def test_full_path_removal(self):
        """Test removal of full file paths."""
        error = FileNotFoundError("/usr/local/bin/secret/file.txt not found")
        result = sanitize_error(error)
        # Should remove the path, keeping only filename
        assert "/usr/local/bin/secret/" not in result
        assert "file.txt not found" in result
        
    def test_multiple_path_removal(self):
        """Test removal of multiple paths in same error message."""
        error = IOError("Could not copy /home/user/src/file1.txt to /var/log/app/file2.txt")
        result = sanitize_error(error)
        # Both paths should be sanitized
        assert "/home/user/src/" not in result
        assert "/var/log/app/" not in result
        assert "file1.txt" in result
        assert "file2.txt" in result
        
    def test_long_error_message_truncation(self):
        """Test truncation of overly long error messages."""
        long_message = "Error: " + "A" * 300  # 306 characters total
        error = RuntimeError(long_message)
        result = sanitize_error(error)
        
        assert len(result) <= 203  # 200 + "..." = 203
        assert result.endswith("...")
        assert "Error: " + "A" * 193 in result  # First part should be preserved
        
    def test_exact_200_character_message(self):
        """Test that exactly 200-character messages are not truncated."""
        exact_message = "A" * 200
        error = RuntimeError(exact_message)
        result = sanitize_error(error)
        
        assert len(result) == 200
        assert not result.endswith("...")
        assert result == exact_message
        
    def test_windows_paths(self):
        """Test handling of Windows-style paths."""
        error = FileNotFoundError(r"C:\Users\username\Documents\secret\file.txt not found")
        result = sanitize_error(error)
        # Should still work with Windows paths
        assert r"C:\Users\username\Documents\secret\\" not in result
        assert "file.txt not found" in result
        
    def test_mixed_path_styles(self):
        """Test handling of mixed Unix/Windows path styles."""
        error = IOError(r"Failed to sync /home/user/data to C:\backup\files\data")
        result = sanitize_error(error)
        assert "/home/user/" not in result
        assert r"C:\backup\files\\" not in result
        assert "data" in result
        
    def test_nested_path_structures(self):
        """Test removal of deeply nested path structures."""
        deep_path = "/very/deeply/nested/path/structure/with/many/levels/file.txt"
        error = PermissionError(f"Access denied: {deep_path}")
        result = sanitize_error(error)
        assert "very/deeply/nested" not in result
        assert "file.txt" in result
        
    def test_error_without_paths(self):
        """Test that errors without paths are unchanged."""
        error = ValueError("Invalid parameter value: must be positive integer")
        result = sanitize_error(error)
        assert result == "Invalid parameter value: must be positive integer"
        
    def test_empty_error_message(self):
        """Test handling of empty error messages."""
        error = RuntimeError("")
        result = sanitize_error(error)
        assert result == ""
        
    def test_none_error_message(self):
        """Test handling of error that converts to empty string."""
        class EmptyError(Exception):
            def __str__(self):
                return ""
                
        error = EmptyError()
        result = sanitize_error(error)
        assert result == ""
        
    def test_error_with_special_characters(self):
        """Test handling of errors with special characters."""
        error = UnicodeError("Failed to decode file: /tmp/测试文件.txt with encoding")
        result = sanitize_error(error)
        assert "/tmp/" not in result
        assert "测试文件.txt" in result
        
    def test_path_with_numbers_and_underscores(self):
        """Test that regex correctly handles paths with numbers and underscores."""
        error = IOError("/opt/app_v1.2.3/logs_2025/error.log permission denied")
        result = sanitize_error(error)
        assert "/opt/app_v1.2.3/logs_2025/" not in result
        assert "error.log" in result
        
    def test_path_with_dots_and_dashes(self):
        """Test that regex correctly handles paths with dots and dashes."""
        error = FileNotFoundError("/usr/local/my-app.v2/config.d/settings.yml not found")
        result = sanitize_error(error)
        assert "/usr/local/my-app.v2/config.d/" not in result
        assert "settings.yml" in result
        
    @patch('pathlib.Path.home')
    def test_home_directory_replacement_with_mock(self, mock_home):
        """Test home directory replacement with mocked Path.home()."""
        mock_home.return_value = Path("/custom/home/dir")
        error = FileNotFoundError("/custom/home/dir/private/file.txt not found")
        result = sanitize_error(error)
        assert "/custom/home/dir" not in result
        # After home replacement and path removal, only filename should remain
        assert "file.txt not found" in result
        
    def test_sanitization_exception_fallback(self):
        """Test fallback behavior when sanitization itself fails."""
        # Mock str() to raise an exception
        class ProblematicError(Exception):
            def __str__(self):
                raise RuntimeError("Cannot convert to string")
                
        error = ProblematicError()
        result = sanitize_error(error)
        assert result == "Internal server error occurred"
        
    def test_regex_exception_fallback(self):
        """Test fallback when regex operations fail."""
        with patch('re.sub', side_effect=Exception("Regex failed")):
            error = FileNotFoundError("/some/path/file.txt not found")
            result = sanitize_error(error)
            assert result == "Internal server error occurred"
            
    def test_path_home_exception_fallback(self):
        """Test fallback when Path.home() raises exception."""
        with patch('checkmk_mcp_server.mcp_server.utils.errors.Path.home', side_effect=OSError("No home directory")):
            error = FileNotFoundError("/home/user/file.txt not found")
            result = sanitize_error(error)
            # Should return generic error message when Path.home() fails
            assert result == "Internal server error occurred"
            
    def test_common_checkmk_error_patterns(self):
        """Test sanitization of common Checkmk error patterns."""
        test_cases = [
            (
                ConnectionError("Failed to connect to /opt/omd/sites/mysite/tmp/check_mk/api"),
                "api"
            ),
            (
                PermissionError("Cannot write to /opt/omd/sites/mysite/var/check_mk/log/cmk.log"),
                "cmk.log"
            ),
            (
                FileNotFoundError("Config file /etc/check_mk/main.mk not found"),
                "main.mk not found"
            ),
            (
                RuntimeError("Check script /usr/lib/check_mk_agent/plugins/mk_docker failed"),
                "mk_docker failed"
            ),
        ]
        
        for error, expected_content in test_cases:
            result = sanitize_error(error)
            assert expected_content in result
            # Verify no sensitive paths remain
            assert "/opt/omd/sites/" not in result
            assert "/etc/check_mk/" not in result
            assert "/usr/lib/check_mk_agent/" not in result
            
    def test_security_information_disclosure_prevention(self):
        """Test that sensitive information is properly removed."""
        sensitive_errors = [
            FileNotFoundError(f"{Path.home()}/.ssh/id_rsa not found"),
            PermissionError("/etc/passwd permission denied"),
            IOError("/var/log/auth.log cannot be read"),
            RuntimeError("/home/admin/secrets/api_keys.txt processing failed"),
        ]
        
        for error in sensitive_errors:
            result = sanitize_error(error)
            # No home directory paths
            assert str(Path.home()) not in result
            # No system paths
            assert "/etc/" not in result
            assert "/var/log/" not in result
            assert "/home/admin/secrets/" not in result
            # But filenames should be preserved for debugging
            assert any(filename in result for filename in ["id_rsa", "passwd", "auth.log", "api_keys.txt"])


class TestErrorUtilityIntegration:
    """Integration tests for error handling utilities."""
    
    def test_backward_compatibility_import(self):
        """Test that error utilities can be imported from utils package."""
        from checkmk_mcp_server.mcp_server.utils import sanitize_error
        
        # Test that it works
        error = RuntimeError("Test error")
        result = sanitize_error(error)
        assert result == "Test error"
        
    def test_integration_with_real_exceptions(self):
        """Test with real exception types that might occur in Checkmk agent."""
        import requests
        import json
        
        # Simulate common exceptions
        exceptions_to_test = [
            requests.ConnectionError("Connection failed to http://localhost:8000/check_mk/api/v1"),
            json.JSONDecodeError("Invalid JSON", "response", 0),
            FileNotFoundError("/opt/omd/sites/mysite/etc/check_mk/main.mk"),
            PermissionError("Permission denied: /var/log/check_mk/web.log"),
            ValueError("Invalid host name: contains illegal characters"),
            TimeoutError("Request timeout after 30 seconds"),
        ]
        
        for exc in exceptions_to_test:
            result = sanitize_error(exc)
            # Should not raise any exceptions
            assert isinstance(result, str)
            # Should not contain sensitive paths
            assert "/opt/omd/sites/" not in result
            assert "/var/log/" not in result


if __name__ == "__main__":
    pytest.main([__file__])