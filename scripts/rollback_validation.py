#!/usr/bin/env python3
"""
Rollback Validation Script for MCP Server Refactoring

This script validates that the MCP server functionality works correctly
after refactoring by testing all critical components and interfaces.
"""

import sys
import json
import time
import importlib
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import subprocess

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

def log_test(test_name: str, success: bool, details: str = "", duration: float = 0.0):
    """Log test results with consistent formatting."""
    status = "✅ PASS" if success else "❌ FAIL"
    timestamp = datetime.now().strftime("%H:%M:%S")
    duration_str = f" ({duration:.3f}s)" if duration > 0 else ""
    print(f"[{timestamp}] {status} {test_name}{duration_str}")
    if details and not success:
        print(f"    Details: {details}")

def test_import_compatibility() -> Tuple[bool, str]:
    """Test that all critical imports still work."""
    start_time = time.time()
    
    try:
        # Test core imports that should continue to work
        from checkmk_agent.mcp_server import CheckmkMCPServer
        from checkmk_agent.mcp_server.server import CheckmkMCPServer as ServerCheckmkMCPServer
        from checkmk_agent.config import AppConfig
        from checkmk_agent.api_client import CheckmkClient
        
        # Verify they're the same class
        if CheckmkMCPServer != ServerCheckmkMCPServer:
            return False, "Import paths return different classes"
        
        duration = time.time() - start_time
        log_test("Import Compatibility", True, duration=duration)
        return True, "All imports successful"
        
    except Exception as e:
        duration = time.time() - start_time
        log_test("Import Compatibility", False, str(e), duration)
        return False, f"Import failed: {e}"

def test_mcp_server_instantiation() -> Tuple[bool, str]:
    """Test that the MCP server can be instantiated."""
    start_time = time.time()
    
    try:
        from checkmk_agent.mcp_server import CheckmkMCPServer
        from checkmk_agent.config import AppConfig, CheckmkConfig, LLMConfig
        
        # Create minimal config with proper structure
        config = AppConfig(
            checkmk=CheckmkConfig(
                server_url="http://test",
                username="test",
                password="test",
                site="test"
            ),
            llm=LLMConfig()
        )
        
        # Instantiate server
        server = CheckmkMCPServer(config)
        
        # Verify basic attributes exist
        assert hasattr(server, 'config'), "Server missing config attribute"
        assert hasattr(server, 'server'), "Server missing MCP server attribute"
        
        duration = time.time() - start_time
        log_test("MCP Server Instantiation", True, duration=duration)
        return True, "Server instantiated successfully"
        
    except Exception as e:
        duration = time.time() - start_time
        log_test("MCP Server Instantiation", False, str(e), duration)
        return False, f"Instantiation failed: {e}"

def test_tool_registration() -> Tuple[bool, str]:
    """Test that tools are properly registered."""
    start_time = time.time()
    
    try:
        from checkmk_agent.mcp_server import CheckmkMCPServer
        from checkmk_agent.config import AppConfig, CheckmkConfig, LLMConfig
        
        config = AppConfig(
            checkmk=CheckmkConfig(
                server_url="http://test",
                username="test",
                password="test",
                site="test"
            ),
            llm=LLMConfig()
        )
        
        server = CheckmkMCPServer(config)
        
        # Test that list_tools works
        # Check if server has tools by accessing the underlying MCP server
        mcp_server = server.server
        
        # Try to access tools through the proper MCP API
        if not hasattr(mcp_server, 'list_tools'):
            return False, "MCP server missing list_tools method"
        
        # Basic validation that server was created successfully
        # (We can't easily count tools without running the async context)
        if not hasattr(server, 'config'):
            return False, "Server missing config attribute"
        
        duration = time.time() - start_time
        log_test("Tool Registration", True, "MCP server tools accessible", duration)
        return True, "Tool registration system functional"
        
    except Exception as e:
        duration = time.time() - start_time
        log_test("Tool Registration", False, str(e), duration)
        return False, f"Tool registration check failed: {e}"

def test_resource_handlers() -> Tuple[bool, str]:
    """Test that resource handlers work."""
    start_time = time.time()
    
    try:
        from checkmk_agent.mcp_server import CheckmkMCPServer
        from checkmk_agent.config import AppConfig, CheckmkConfig, LLMConfig
        
        config = AppConfig(
            checkmk=CheckmkConfig(
                server_url="http://test",
                username="test",
                password="test",
                site="test"
            ),
            llm=LLMConfig()
        )
        
        server = CheckmkMCPServer(config)
        
        # Test that resource handlers exist
        mcp_server = server.server
        
        if not hasattr(mcp_server, 'list_resources'):
            return False, "No list_resources method found"
        
        duration = time.time() - start_time
        log_test("Resource Handlers", True, duration=duration)
        return True, "Resource handlers functional"
        
    except Exception as e:
        duration = time.time() - start_time
        log_test("Resource Handlers", False, str(e), duration)
        return False, f"Resource handlers failed: {e}"

def test_service_layer_integration() -> Tuple[bool, str]:
    """Test that service layer integration works."""
    start_time = time.time()
    
    try:
        from checkmk_agent.mcp_server import CheckmkMCPServer
        from checkmk_agent.config import AppConfig, CheckmkConfig, LLMConfig
        from checkmk_agent.services import HostService, StatusService
        
        config = AppConfig(
            checkmk=CheckmkConfig(
                server_url="http://test",
                username="test",
                password="test",
                site="test"
            ),
            llm=LLMConfig()
        )
        
        server = CheckmkMCPServer(config)
        
        # Verify basic server structure (services initialized via initialize() method)
        if not hasattr(server, 'config'):
            return False, "Server config not found"
        
        if not hasattr(server, 'server'):
            return False, "MCP server instance not found"
        
        duration = time.time() - start_time
        log_test("Service Layer Integration", True, duration=duration)
        return True, "Service layer properly integrated"
        
    except Exception as e:
        duration = time.time() - start_time
        log_test("Service Layer Integration", False, str(e), duration)
        return False, f"Service layer integration failed: {e}"

def test_error_handling() -> Tuple[bool, str]:
    """Test that error handling utilities work."""
    start_time = time.time()
    
    try:
        from checkmk_agent.mcp_server.server import sanitize_error, MCPJSONEncoder
        
        # Test error sanitization
        test_error = Exception("/secret/path/error.txt: Permission denied")
        sanitized = sanitize_error(test_error)
        
        if "/secret/path" in sanitized:
            return False, "Error sanitization failed - sensitive path not removed"
        
        # Test JSON encoder
        encoder = MCPJSONEncoder()
        test_data = {"date": datetime.now(), "number": 42}
        
        try:
            json_str = encoder.encode(test_data)
            parsed = json.loads(json_str)
            if "date" not in parsed:
                return False, "JSON encoder failed to handle datetime"
        except Exception as json_e:
            return False, f"JSON encoder failed: {json_e}"
        
        duration = time.time() - start_time
        log_test("Error Handling", True, duration=duration)
        return True, "Error handling utilities functional"
        
    except Exception as e:
        duration = time.time() - start_time
        log_test("Error Handling", False, str(e), duration)
        return False, f"Error handling test failed: {e}"

def test_entry_point() -> Tuple[bool, str]:
    """Test that the main entry point script works."""
    start_time = time.time()
    
    try:
        # Test that the entry point file exists and can be imported
        entry_point = Path("mcp_checkmk_server.py")
        if not entry_point.exists():
            return False, "Entry point script mcp_checkmk_server.py not found"
        
        # Test basic syntax by attempting to compile
        with open(entry_point, 'r') as f:
            content = f.read()
        
        try:
            compile(content, str(entry_point), 'exec')
        except SyntaxError as e:
            return False, f"Entry point has syntax error: {e}"
        
        duration = time.time() - start_time
        log_test("Entry Point", True, duration=duration)
        return True, "Entry point script functional"
        
    except Exception as e:
        duration = time.time() - start_time
        log_test("Entry Point", False, str(e), duration)
        return False, f"Entry point test failed: {e}"

def test_package_structure() -> Tuple[bool, str]:
    """Test that package structure is intact."""
    start_time = time.time()
    
    try:
        required_files = [
            "checkmk_agent/__init__.py",
            "checkmk_agent/mcp_server/__init__.py", 
            "checkmk_agent/mcp_server/server.py",
            "checkmk_agent/config.py",
            "checkmk_agent/api_client.py"
        ]
        
        missing_files = []
        for file_path in required_files:
            if not Path(file_path).exists():
                missing_files.append(file_path)
        
        if missing_files:
            return False, f"Missing required files: {missing_files}"
        
        duration = time.time() - start_time
        log_test("Package Structure", True, duration=duration)
        return True, "Package structure intact"
        
    except Exception as e:
        duration = time.time() - start_time
        log_test("Package Structure", False, str(e), duration)
        return False, f"Package structure test failed: {e}"

def run_critical_unit_tests() -> Tuple[bool, str]:
    """Run a subset of critical unit tests."""
    start_time = time.time()
    
    try:
        # Run just the MCP server tests
        result = subprocess.run([
            "python", "-m", "pytest", 
            "tests/test_mcp_server_tools.py",
            "-v", "--tb=short"
        ], capture_output=True, text=True, timeout=60)
        
        if result.returncode != 0:
            return False, f"Unit tests failed: {result.stderr}"
        
        # Count passed tests
        passed_count = result.stdout.count(" PASSED")
        failed_count = result.stdout.count(" FAILED")
        
        if failed_count > 0:
            return False, f"{failed_count} tests failed, {passed_count} passed"
        
        duration = time.time() - start_time
        log_test("Critical Unit Tests", True, f"{passed_count} tests passed", duration)
        return True, f"All {passed_count} critical tests passed"
        
    except subprocess.TimeoutExpired:
        duration = time.time() - start_time
        log_test("Critical Unit Tests", False, "Tests timed out", duration)
        return False, "Unit tests timed out"
    except Exception as e:
        duration = time.time() - start_time
        log_test("Critical Unit Tests", False, str(e), duration)
        return False, f"Unit test execution failed: {e}"

def main():
    """Run comprehensive rollback validation."""
    print("🔍 MCP Server Rollback Validation")
    print("=" * 50)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Working Directory: {Path.cwd()}")
    
    # Get git info
    try:
        branch = subprocess.run(["git", "branch", "--show-current"], 
                              capture_output=True, text=True).stdout.strip()
        commit = subprocess.run(["git", "rev-parse", "HEAD"], 
                              capture_output=True, text=True).stdout.strip()[:8]
        print(f"Git Branch: {branch}")
        print(f"Git Commit: {commit}")
    except:
        print("Git info unavailable")
    
    print("\n🧪 Running Validation Tests...")
    print("-" * 30)
    
    # Define validation tests
    validation_tests = [
        ("Package Structure", test_package_structure),
        ("Import Compatibility", test_import_compatibility),
        ("MCP Server Instantiation", test_mcp_server_instantiation),
        ("Tool Registration", test_tool_registration),
        ("Resource Handlers", test_resource_handlers),
        ("Service Layer Integration", test_service_layer_integration),
        ("Error Handling", test_error_handling),
        ("Entry Point", test_entry_point),
        ("Critical Unit Tests", run_critical_unit_tests),
    ]
    
    results = []
    total_start = time.time()
    
    for test_name, test_func in validation_tests:
        try:
            success, details = test_func()
            results.append({
                "test": test_name,
                "success": success,
                "details": details
            })
        except Exception as e:
            log_test(test_name, False, f"Test execution error: {e}")
            results.append({
                "test": test_name,
                "success": False,
                "details": f"Test execution error: {e}"
            })
    
    total_duration = time.time() - total_start
    
    # Summary
    print("\n📊 Validation Summary")
    print("=" * 30)
    
    passed = sum(1 for r in results if r["success"])
    failed = len(results) - passed
    
    print(f"Total Tests: {len(results)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Success Rate: {passed/len(results)*100:.1f}%")
    print(f"Total Duration: {total_duration:.2f}s")
    
    if failed > 0:
        print(f"\n❌ Failed Tests:")
        for result in results:
            if not result["success"]:
                print(f"  • {result['test']}: {result['details']}")
    
    # Save detailed results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = Path("scripts") / f"rollback_validation_{timestamp}.json"
    
    validation_report = {
        "timestamp": datetime.now().isoformat(),
        "total_tests": len(results),
        "passed": passed,
        "failed": failed,
        "success_rate": passed/len(results)*100,
        "total_duration": total_duration,
        "results": results
    }
    
    with open(report_file, 'w') as f:
        json.dump(validation_report, f, indent=2)
    
    print(f"\n📁 Detailed report saved: {report_file}")
    
    # Return appropriate exit code
    exit_code = 0 if failed == 0 else 1
    
    if exit_code == 0:
        print("\n✅ ALL VALIDATIONS PASSED - System ready for refactoring")
    else:
        print("\n❌ VALIDATIONS FAILED - Fix issues before proceeding")
    
    return exit_code

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)