#!/usr/bin/env python3
"""
Parameter System Validation Script

This script validates that the specialized parameter handler system is working
correctly and all MCP tools are accessible.

Usage:
    python validate_parameter_system.py --config config.yaml
    python validate_parameter_system.py --config config.yaml --detailed
"""

import asyncio
import argparse
import json
import time
from typing import Dict, List, Any, Optional
from pathlib import Path

from checkmk_agent.services.parameter_service import ParameterService
from checkmk_agent.services.handlers import get_handler_registry
from checkmk_agent.api_client import CheckmkClient
from checkmk_agent.config import Config
from checkmk_agent.mcp_server.server import CheckmkMCPServer


class ParameterSystemValidator:
    """Validates the parameter management system."""
    
    def __init__(self, config: Config):
        self.config = config
        self.client = CheckmkClient(config.checkmk)
        self.parameter_service = ParameterService(self.client, config)
        self.mcp_server = CheckmkMCPServer(self.client, config)
        self.handler_registry = get_handler_registry()
        
        self.validation_results = {
            "overall_status": "pass",
            "tests_run": 0,
            "tests_passed": 0,
            "tests_failed": 0,
            "test_results": [],
            "performance_metrics": {}
        }
    
    def log_test(self, test_name: str, status: str, details: Optional[Dict[str, Any]] = None):
        """Log a test result."""
        self.validation_results["tests_run"] += 1
        
        if status == "pass":
            self.validation_results["tests_passed"] += 1
            print(f"✅ {test_name}")
        else:
            self.validation_results["tests_failed"] += 1
            self.validation_results["overall_status"] = "fail"
            print(f"❌ {test_name}")
            if details:
                for key, value in details.items():
                    print(f"   {key}: {value}")
        
        self.validation_results["test_results"].append({
            "test_name": test_name,
            "status": status,
            "details": details or {}
        })
    
    async def test_handler_registry(self):
        """Test handler registry functionality."""
        print("🔍 Testing Handler Registry...")
        
        try:
            # Test registry initialization
            assert self.handler_registry is not None
            self.log_test("Handler registry initialized", "pass")
            
            # Test handler registration
            handlers_info = self.handler_registry.list_handlers()
            expected_handlers = {"temperature", "custom_checks", "database", "network_services"}
            
            if expected_handlers.issubset(set(handlers_info.keys())):
                self.log_test("All expected handlers registered", "pass")
            else:
                missing = expected_handlers - set(handlers_info.keys())
                self.log_test("All expected handlers registered", "fail", 
                            {"missing_handlers": list(missing)})
            
            # Test handler selection
            test_cases = [
                ("CPU Temperature", "temperature"),
                ("MySQL Connections", "database"),
                ("HTTP Health Check", "network_services"),
                ("MRPE check_disk", "custom_checks")
            ]
            
            for service_name, expected_handler in test_cases:
                handler = self.handler_registry.get_best_handler(service_name=service_name)
                if handler and handler.name == expected_handler:
                    self.log_test(f"Handler selection for {service_name}", "pass")
                else:
                    actual_handler = handler.name if handler else None
                    self.log_test(f"Handler selection for {service_name}", "fail",
                                {"expected": expected_handler, "actual": actual_handler})
        
        except Exception as e:
            self.log_test("Handler registry functionality", "fail", {"error": str(e)})
    
    async def test_parameter_generation(self):
        """Test parameter generation for all handler types."""
        print("🔧 Testing Parameter Generation...")
        
        test_services = [
            ("CPU Temperature", "temperature"),
            ("GPU Temperature", "temperature"),
            ("MySQL Connections", "database"),
            ("Oracle Tablespace USERS", "database"),
            ("PostgreSQL Locks", "database"),
            ("HTTPS API Health", "network_services"),
            ("TCP Port 443", "network_services"),
            ("DNS Lookup", "network_services"),
            ("MRPE check_disk", "custom_checks"),
            ("Local check_memory", "custom_checks"),
            ("check_mysql", "custom_checks")
        ]
        
        for service_name, expected_handler in test_services:
            try:
                result = await self.parameter_service.get_specialized_defaults(service_name)
                
                if result.success:
                    handler_used = result.data.get("handler_used")
                    parameters = result.data.get("parameters")
                    
                    if handler_used == expected_handler and parameters:
                        self.log_test(f"Parameter generation for {service_name}", "pass")
                    else:
                        self.log_test(f"Parameter generation for {service_name}", "fail",
                                    {"expected_handler": expected_handler, 
                                     "actual_handler": handler_used,
                                     "has_parameters": bool(parameters)})
                else:
                    self.log_test(f"Parameter generation for {service_name}", "fail",
                                {"error": result.error})
            
            except Exception as e:
                self.log_test(f"Parameter generation for {service_name}", "fail",
                            {"error": str(e)})
    
    async def test_parameter_validation(self):
        """Test parameter validation functionality."""
        print("🔍 Testing Parameter Validation...")
        
        validation_test_cases = [
            {
                "service_name": "CPU Temperature",
                "parameters": {"levels": (75.0, 85.0), "output_unit": "c"},
                "should_be_valid": True
            },
            {
                "service_name": "CPU Temperature", 
                "parameters": {"levels": (90.0, 80.0)},  # Invalid: warning > critical
                "should_be_valid": False
            },
            {
                "service_name": "MySQL Connections",
                "parameters": {"levels": (80.0, 90.0), "hostname": "db.example.com", "port": 3306},
                "should_be_valid": True
            },
            {
                "service_name": "MySQL Connections",
                "parameters": {"levels": (80.0, 90.0), "port": 99999},  # Invalid port
                "should_be_valid": False
            },
            {
                "service_name": "HTTPS API Health",
                "parameters": {"url": "https://api.example.com/health", "response_time": (2.0, 5.0)},
                "should_be_valid": True
            },
            {
                "service_name": "HTTPS API Health",
                "parameters": {"url": "not-a-url", "response_time": (2.0, 5.0)},
                "should_be_valid": False
            },
            {
                "service_name": "MRPE check_disk",
                "parameters": {"command_line": "check_disk -w 80% -c 90%", "timeout": 30},
                "should_be_valid": True
            }
        ]
        
        for test_case in validation_test_cases:
            try:
                result = await self.parameter_service.validate_specialized_parameters(
                    test_case["parameters"], test_case["service_name"]
                )
                
                if result.success:
                    is_valid = result.data.get("is_valid")
                    
                    if is_valid == test_case["should_be_valid"]:
                        self.log_test(f"Validation for {test_case['service_name']} (valid={test_case['should_be_valid']})", "pass")
                    else:
                        self.log_test(f"Validation for {test_case['service_name']} (valid={test_case['should_be_valid']})", "fail",
                                    {"expected_valid": test_case["should_be_valid"], 
                                     "actual_valid": is_valid,
                                     "errors": result.data.get("errors", [])})
                else:
                    self.log_test(f"Validation for {test_case['service_name']}", "fail",
                                {"error": result.error})
            
            except Exception as e:
                self.log_test(f"Validation for {test_case['service_name']}", "fail",
                            {"error": str(e)})
    
    async def test_mcp_parameter_tools(self):
        """Test MCP parameter management tools."""
        print("🌐 Testing MCP Parameter Tools...")
        
        mcp_tools_to_test = [
            {
                "tool_name": "get_specialized_defaults",
                "arguments": {"service_name": "CPU Temperature"},
                "expected_keys": ["success", "data"]
            },
            {
                "tool_name": "validate_specialized_parameters", 
                "arguments": {
                    "parameters": {"levels": (75.0, 85.0), "output_unit": "c"},
                    "service_name": "CPU Temperature"
                },
                "expected_keys": ["success", "data"]
            },
            {
                "tool_name": "get_parameter_suggestions",
                "arguments": {
                    "service_name": "MySQL Connections",
                    "current_parameters": {"levels": (50.0, 60.0)}
                },
                "expected_keys": ["success", "data"]
            },
            {
                "tool_name": "discover_parameter_handlers",
                "arguments": {"service_name": "Oracle Tablespace USERS"},
                "expected_keys": ["success", "data"]
            },
            {
                "tool_name": "get_handler_info",
                "arguments": {"handler_name": "temperature"},
                "expected_keys": ["success", "data"]
            },
            {
                "tool_name": "bulk_parameter_operations",
                "arguments": {
                    "service_names": ["CPU Temperature", "MySQL Connections"],
                    "operation": "get_defaults"
                },
                "expected_keys": ["success", "data"]
            }
        ]
        
        for tool_test in mcp_tools_to_test:
            try:
                result = await self.mcp_server.call_tool(
                    tool_test["tool_name"], 
                    tool_test["arguments"]
                )
                
                if result and result.content:
                    response_data = json.loads(result.content[0].text)
                    
                    # Check if response has expected structure
                    has_expected_keys = all(key in response_data for key in tool_test["expected_keys"])
                    
                    if has_expected_keys and response_data.get("success"):
                        self.log_test(f"MCP tool {tool_test['tool_name']}", "pass")
                    else:
                        self.log_test(f"MCP tool {tool_test['tool_name']}", "fail",
                                    {"response": response_data})
                else:
                    self.log_test(f"MCP tool {tool_test['tool_name']}", "fail",
                                {"error": "No response or empty content"})
            
            except Exception as e:
                self.log_test(f"MCP tool {tool_test['tool_name']}", "fail",
                            {"error": str(e)})
    
    async def test_performance_benchmarks(self):
        """Test performance of parameter operations."""
        print("⚡ Testing Performance Benchmarks...")
        
        # Handler selection performance
        start_time = time.perf_counter()
        for _ in range(1000):
            handler = self.handler_registry.get_best_handler(service_name="CPU Temperature")
            assert handler is not None
        handler_selection_time = time.perf_counter() - start_time
        
        ops_per_second = 1000 / handler_selection_time
        if ops_per_second > 5000:
            self.log_test("Handler selection performance (>5000 ops/sec)", "pass")
            self.validation_results["performance_metrics"]["handler_selection_ops_per_sec"] = ops_per_second
        else:
            self.log_test("Handler selection performance (>5000 ops/sec)", "fail",
                        {"actual_ops_per_sec": ops_per_second})
        
        # Parameter generation performance
        test_services = ["CPU Temperature", "MySQL Connections", "HTTP Health Check"] * 100
        
        start_time = time.perf_counter()
        tasks = []
        for service_name in test_services:
            task = self.parameter_service.get_specialized_defaults(service_name)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        param_generation_time = time.perf_counter() - start_time
        
        successful_results = [r for r in results if not isinstance(r, Exception) and r.success]
        ops_per_second = len(successful_results) / param_generation_time
        
        if ops_per_second > 100:
            self.log_test("Parameter generation performance (>100 ops/sec)", "pass")
            self.validation_results["performance_metrics"]["parameter_generation_ops_per_sec"] = ops_per_second
        else:
            self.log_test("Parameter generation performance (>100 ops/sec)", "fail",
                        {"actual_ops_per_sec": ops_per_second})
    
    async def test_context_awareness(self):
        """Test context-aware parameter generation."""
        print("🎯 Testing Context Awareness...")
        
        # Test environment-specific parameters
        base_result = await self.parameter_service.get_specialized_defaults("CPU Temperature")
        
        prod_result = await self.parameter_service.get_specialized_defaults(
            "CPU Temperature", 
            {"environment": "production", "criticality": "high"}
        )
        
        dev_result = await self.parameter_service.get_specialized_defaults(
            "CPU Temperature",
            {"environment": "development", "criticality": "low"}
        )
        
        if all(r.success for r in [base_result, prod_result, dev_result]):
            base_levels = base_result.data["parameters"]["levels"]
            prod_levels = prod_result.data["parameters"]["levels"]
            dev_levels = dev_result.data["parameters"]["levels"]
            
            # Production should have stricter (lower) or equal thresholds
            if prod_levels[0] <= base_levels[0]:
                self.log_test("Context-aware production parameters", "pass")
            else:
                self.log_test("Context-aware production parameters", "fail",
                            {"base_levels": base_levels, "prod_levels": prod_levels})
            
            # Parameters should be different based on context
            contexts_differ = (prod_levels != base_levels) or (dev_levels != base_levels)
            if contexts_differ:
                self.log_test("Context differentiation", "pass")
            else:
                self.log_test("Context differentiation", "fail",
                            {"base": base_levels, "prod": prod_levels, "dev": dev_levels})
        else:
            self.log_test("Context-aware parameter generation", "fail",
                        {"base_success": base_result.success,
                         "prod_success": prod_result.success,
                         "dev_success": dev_result.success})
    
    async def test_bulk_operations(self):
        """Test bulk parameter operations.""" 
        print("📦 Testing Bulk Operations...")
        
        service_names = [
            "CPU Temperature",
            "GPU Temperature", 
            "MySQL Connections",
            "PostgreSQL Locks",
            "HTTP Health Check",
            "HTTPS API Monitoring",
            "MRPE check_disk",
            "Local check_memory"
        ]
        
        try:
            # Test bulk defaults generation
            bulk_result = await self.mcp_server.call_tool("bulk_parameter_operations", {
                "service_names": service_names,
                "operation": "get_defaults"
            })
            
            if bulk_result and bulk_result.content:
                response_data = json.loads(bulk_result.content[0].text)
                
                if response_data.get("success"):
                    results = response_data["data"]["results"]
                    successful_count = sum(1 for r in results if r["success"])
                    
                    if successful_count >= len(service_names) * 0.8:  # At least 80% success
                        self.log_test("Bulk parameter operations", "pass")
                    else:
                        self.log_test("Bulk parameter operations", "fail",
                                    {"successful": successful_count, "total": len(service_names)})
                else:
                    self.log_test("Bulk parameter operations", "fail",
                                {"error": response_data.get("error", "Unknown error")})
            else:
                self.log_test("Bulk parameter operations", "fail",
                            {"error": "No response from MCP tool"})
        
        except Exception as e:
            self.log_test("Bulk parameter operations", "fail", {"error": str(e)})
    
    async def test_error_handling(self):
        """Test error handling scenarios."""
        print("🛡️  Testing Error Handling...")
        
        error_test_cases = [
            {
                "test_name": "Invalid service name",
                "service_name": "",
                "should_succeed": False
            },
            {
                "test_name": "Non-existent service type",
                "service_name": "Unknown Service Type That Does Not Exist",
                "should_succeed": True  # Should fall back to generic handling
            },
            {
                "test_name": "Malformed parameters validation",
                "service_name": "CPU Temperature",
                "parameters": {"invalid": "structure"},
                "operation": "validate",
                "should_succeed": True  # Should succeed but mark as invalid
            }
        ]
        
        for test_case in error_test_cases:
            try:
                if test_case.get("operation") == "validate":
                    result = await self.parameter_service.validate_specialized_parameters(
                        test_case["parameters"], test_case["service_name"]
                    )
                else:
                    result = await self.parameter_service.get_specialized_defaults(
                        test_case["service_name"]
                    )
                
                if result.success == test_case["should_succeed"]:
                    self.log_test(f"Error handling: {test_case['test_name']}", "pass")
                else:
                    self.log_test(f"Error handling: {test_case['test_name']}", "fail",
                                {"expected_success": test_case["should_succeed"],
                                 "actual_success": result.success,
                                 "error": result.error if not result.success else None})
            
            except Exception as e:
                if test_case["should_succeed"]:
                    self.log_test(f"Error handling: {test_case['test_name']}", "fail",
                                {"unexpected_exception": str(e)})
                else:
                    self.log_test(f"Error handling: {test_case['test_name']}", "pass")
    
    async def run_all_tests(self, detailed: bool = False):
        """Run all validation tests."""
        print("🚀 Starting Parameter System Validation...\n")
        
        start_time = time.perf_counter()
        
        # Core functionality tests
        await self.test_handler_registry()
        await self.test_parameter_generation()
        await self.test_parameter_validation()
        
        # MCP integration tests
        await self.test_mcp_parameter_tools()
        
        # Advanced feature tests
        await self.test_context_awareness()
        await self.test_bulk_operations()
        await self.test_error_handling()
        
        # Performance tests
        if detailed:
            await self.test_performance_benchmarks()
        
        end_time = time.perf_counter()
        total_time = end_time - start_time
        
        # Final summary
        print(f"\n📊 Validation Summary:")
        print(f"   - Total tests: {self.validation_results['tests_run']}")
        print(f"   - Passed: {self.validation_results['tests_passed']}")
        print(f"   - Failed: {self.validation_results['tests_failed']}")
        print(f"   - Success rate: {self.validation_results['tests_passed']/self.validation_results['tests_run']*100:.1f}%")
        print(f"   - Total time: {total_time:.2f}s")
        print(f"   - Overall status: {self.validation_results['overall_status'].upper()}")
        
        if self.validation_results["performance_metrics"]:
            print(f"\n⚡ Performance Metrics:")
            for metric, value in self.validation_results["performance_metrics"].items():
                print(f"   - {metric}: {value:.1f}")
        
        if self.validation_results["overall_status"] == "fail":
            print(f"\n❌ Some tests failed. Check the detailed results for more information.")
            return False
        else:
            print(f"\n✅ All tests passed! Parameter system is working correctly.")
            return True


async def main():
    """Main validation function."""
    parser = argparse.ArgumentParser(description="Parameter System Validation")
    parser.add_argument("--config", required=True, help="Configuration file path")
    parser.add_argument("--detailed", action="store_true", help="Run detailed performance tests")
    parser.add_argument("--output", help="Output file for validation results")
    parser.add_argument("--output-format", default="json", choices=["json", "yaml"],
                       help="Output format")
    
    args = parser.parse_args()
    
    # Load configuration
    config = Config.from_file(args.config)
    
    # Initialize validator
    validator = ParameterSystemValidator(config)
    
    try:
        # Run validation
        success = await validator.run_all_tests(detailed=args.detailed)
        
        # Export results if requested
        if args.output:
            if args.output_format == "json":
                with open(args.output, 'w') as f:
                    json.dump(validator.validation_results, f, indent=2)
            elif args.output_format == "yaml":
                import yaml
                with open(args.output, 'w') as f:
                    yaml.dump(validator.validation_results, f, default_flow_style=False)
            
            print(f"📁 Validation results saved to {args.output}")
        
        return 0 if success else 1
    
    except Exception as e:
        print(f"❌ Validation failed with error: {e}")
        return 1


if __name__ == "__main__":
    exit(asyncio.run(main()))