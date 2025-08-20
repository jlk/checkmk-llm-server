"""
Integration tests for Phase 5 - Refactored MCP Server

This script tests the refactored server architecture to ensure:
1. All tool categories can be instantiated
2. All tools are properly registered
3. All prompts are properly registered
4. Service container works correctly
5. Dependency injection works properly
6. MCP protocol handlers work
7. Backward compatibility is maintained
"""

import asyncio
import logging
import json
import sys
import traceback
from typing import Dict, Any, List
from unittest.mock import AsyncMock, MagicMock
from dataclasses import dataclass

# Set up basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class TestResult:
    """Result of an integration test."""
    name: str
    success: bool
    message: str
    details: Dict[str, Any] = None


class Phase5IntegrationTester:
    """Comprehensive integration tester for Phase 5 refactored server."""
    
    def __init__(self):
        self.results: List[TestResult] = []
        self.server = None
        
    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all integration tests."""
        logger.info("Starting Phase 5 Integration Tests")
        logger.info("=" * 60)
        
        try:
            # Test 1: Import and instantiation
            await self.test_import_and_instantiation()
            
            # Test 2: Service container
            await self.test_service_container()
            
            # Test 3: Tool category initialization
            await self.test_tool_category_initialization()
            
            # Test 4: Tool registration
            await self.test_tool_registration()
            
            # Test 5: Prompt registration
            await self.test_prompt_registration()
            
            # Test 6: Protocol handlers
            await self.test_protocol_handlers()
            
            # Test 7: Backward compatibility
            await self.test_backward_compatibility()
            
        except Exception as e:
            logger.exception("Critical error during testing")
            self.results.append(TestResult(
                name="critical_error",
                success=False,
                message=f"Critical test failure: {str(e)}",
                details={"exception": str(e), "traceback": traceback.format_exc()}
            ))
        
        return self.generate_report()
    
    async def test_import_and_instantiation(self):
        """Test 1: Server import and instantiation."""
        test_name = "import_and_instantiation"
        try:
            # Test import
            from checkmk_agent.mcp_server import CheckmkMCPServer
            from checkmk_agent.mcp_server.container import ServiceContainer
            
            # Test basic instantiation with mock config
            mock_config = self.create_mock_config()
            server = CheckmkMCPServer(mock_config)
            
            # Check basic attributes
            assert hasattr(server, 'server'), "Server should have MCP server instance"
            assert hasattr(server, 'container'), "Server should have service container"
            assert hasattr(server, 'tool_registry'), "Server should have tool registry"
            assert hasattr(server, 'protocol_handlers'), "Server should have protocol handlers"
            
            self.server = server  # Save for later tests
            
            self.results.append(TestResult(
                name=test_name,
                success=True,
                message="Server import and instantiation successful",
                details={
                    "server_name": server.server.name,
                    "container_type": type(server.container).__name__,
                    "initialized": server._initialized
                }
            ))
            
        except Exception as e:
            self.results.append(TestResult(
                name=test_name,
                success=False,
                message=f"Import/instantiation failed: {str(e)}",
                details={"exception": str(e)}
            ))
    
    async def test_service_container(self):
        """Test 2: Service container functionality."""
        test_name = "service_container"
        try:
            if not self.server:
                raise Exception("Server not available from previous test")
            
            # Mock the CheckmkClient and AsyncCheckmkClient
            from unittest.mock import patch
            
            with patch('checkmk_agent.mcp_server.container.CheckmkClient') as mock_sync_client, \
                 patch('checkmk_agent.mcp_server.container.AsyncCheckmkClient') as mock_async_client:
                
                # Initialize container
                await self.server.container.initialize()
                
                # Test container state
                assert self.server.container.is_initialized(), "Container should be initialized"
                
                # Test service retrieval
                services = self.server.container.get_all_services()
                expected_services = [
                    'async_client', 'sync_client', 'host_service', 'status_service',
                    'service_service', 'parameter_service', 'event_service', 
                    'metrics_service', 'bi_service', 'historical_service',
                    'streaming_host_service', 'streaming_service_service',
                    'cached_host_service', 'batch_processor'
                ]
                
                for service_name in expected_services:
                    assert self.server.container.has_service(service_name), f"Container should have {service_name}"
                
                self.results.append(TestResult(
                    name=test_name,
                    success=True,
                    message="Service container works correctly",
                    details={
                        "initialized": self.server.container.is_initialized(),
                        "service_count": len(services),
                        "available_services": list(services.keys())
                    }
                ))
                
        except Exception as e:
            self.results.append(TestResult(
                name=test_name,
                success=False,
                message=f"Service container test failed: {str(e)}",
                details={"exception": str(e)}
            ))
    
    async def test_tool_category_initialization(self):
        """Test 3: Tool category initialization."""
        test_name = "tool_category_initialization"
        try:
            if not self.server or not self.server.container.is_initialized():
                raise Exception("Server/container not properly initialized")
            
            # Initialize tool categories
            self.server._initialize_tool_categories()
            
            # Check that all expected categories are present
            expected_categories = [
                'host', 'service', 'monitoring', 'parameters', 
                'events', 'metrics', 'business', 'advanced'
            ]
            
            for category in expected_categories:
                assert category in self.server._tool_categories, f"Category {category} should be initialized"
                category_instance = self.server._tool_categories[category]
                assert hasattr(category_instance, 'get_tools'), f"Category {category} should have get_tools method"
                assert hasattr(category_instance, 'get_handlers'), f"Category {category} should have get_handlers method"
            
            self.results.append(TestResult(
                name=test_name,
                success=True,
                message="Tool categories initialized successfully",
                details={
                    "category_count": len(self.server._tool_categories),
                    "categories": list(self.server._tool_categories.keys())
                }
            ))
            
        except Exception as e:
            self.results.append(TestResult(
                name=test_name,
                success=False,
                message=f"Tool category initialization failed: {str(e)}",
                details={"exception": str(e)}
            ))
    
    async def test_tool_registration(self):
        """Test 4: Tool registration."""
        test_name = "tool_registration"
        try:
            if not self.server._tool_categories:
                raise Exception("Tool categories not initialized")
            
            # Register all tools
            self.server._register_all_tools()
            
            # Check tool registry
            tool_count = self.server.tool_registry.get_tool_count()
            assert tool_count > 30, f"Expected at least 30 tools, got {tool_count}"
            
            # Get all tools first
            all_tools = self.server.tool_registry.list_tools()
            
            # Check that tools are properly categorized
            tool_stats = self.server.tool_registry.get_tool_stats()
            assert isinstance(tool_stats, dict), "Tool stats should be a dict"
            
            # Verify some specific tools exist
            expected_tools = [
                'list_hosts', 'create_host', 'list_all_services', 
                'get_health_dashboard'
            ]
            available_tool_names = [tool.name for tool in all_tools]
            for tool_name in expected_tools:
                assert tool_name in available_tool_names, f"Tool {tool_name} should be registered. Available: {available_tool_names[:10]}"
            
            self.results.append(TestResult(
                name=test_name,
                success=True,
                message="Tools registered successfully",
                details={
                    "total_tools": tool_count,
                    "tool_stats": tool_stats,
                    "sample_tools": [tool.name for tool in all_tools[:5]]
                }
            ))
            
        except Exception as e:
            self.results.append(TestResult(
                name=test_name,
                success=False,
                message=f"Tool registration failed: {str(e)}",
                details={"exception": str(e)}
            ))
    
    async def test_prompt_registration(self):
        """Test 5: Prompt registration."""
        test_name = "prompt_registration"
        try:
            # Register all prompts
            self.server._register_all_prompts()
            
            # Check prompt registration
            prompt_count = len(self.server.protocol_handlers._prompts)
            assert prompt_count > 5, f"Expected at least 5 prompts, got {prompt_count}"
            
            # Check that specific prompts exist
            expected_prompts = [
                'analyze_host_health', 'troubleshoot_service', 
                'infrastructure_overview', 'optimize_parameters'
            ]
            
            for prompt_name in expected_prompts:
                assert prompt_name in self.server.protocol_handlers._prompts, f"Prompt {prompt_name} should be registered"
            
            # Test prompt handlers are initialized
            assert hasattr(self.server.prompt_handlers, '_services'), "Prompt handlers should have services"
            assert len(self.server.prompt_handlers._services) > 0, "Prompt handlers should have services initialized"
            
            self.results.append(TestResult(
                name=test_name,
                success=True,
                message="Prompts registered successfully",
                details={
                    "total_prompts": prompt_count,
                    "available_prompts": list(self.server.protocol_handlers._prompts.keys()),
                    "handler_services": len(self.server.prompt_handlers._services)
                }
            ))
            
        except Exception as e:
            self.results.append(TestResult(
                name=test_name,
                success=False,
                message=f"Prompt registration failed: {str(e)}",
                details={"exception": str(e)}
            ))
    
    async def test_protocol_handlers(self):
        """Test 6: MCP protocol handlers."""
        test_name = "protocol_handlers"
        try:
            # Test basic resource listing
            basic_resources = self.server.protocol_handlers.get_basic_resources()
            assert len(basic_resources) >= 5, f"Expected at least 5 basic resources, got {len(basic_resources)}"
            
            # Test streaming resources
            streaming_resources = self.server.protocol_handlers.get_streaming_resources()
            assert len(streaming_resources) > 0, f"Expected streaming resources, got {len(streaming_resources)}"
            
            # Test that protocol handlers have the required methods
            assert hasattr(self.server.protocol_handlers, 'handle_read_resource'), "Should have handle_read_resource method"
            assert hasattr(self.server.protocol_handlers, 'register_prompts'), "Should have register_prompts method"
            
            self.results.append(TestResult(
                name=test_name,
                success=True,
                message="Protocol handlers working correctly",
                details={
                    "basic_resources": len(basic_resources),
                    "streaming_resources": len(streaming_resources),
                    "resource_uris": [str(res.uri) for res in basic_resources[:3]]  # Convert AnyUrl to str
                }
            ))
            
        except Exception as e:
            self.results.append(TestResult(
                name=test_name,
                success=False,
                message=f"Protocol handlers test failed: {str(e)}",
                details={"exception": str(e)}
            ))
    
    async def test_backward_compatibility(self):
        """Test 7: Backward compatibility."""
        test_name = "backward_compatibility"
        try:
            # Test that the main import still works
            from checkmk_agent.mcp_server import CheckmkMCPServer as BackwardCompatServer
            
            # Test that it's the same class
            assert BackwardCompatServer == type(self.server), "Backward compatibility import should work"
            
            # Test server info method
            server_info = self.server.get_server_info()
            assert isinstance(server_info, dict), "Server info should be a dict"
            assert 'tool_count' in server_info, "Server info should include tool count"
            assert 'prompt_count' in server_info, "Server info should include prompt count"
            
            self.results.append(TestResult(
                name=test_name,
                success=True,
                message="Backward compatibility maintained",
                details={
                    "server_info": server_info,
                    "import_successful": True
                }
            ))
            
        except Exception as e:
            self.results.append(TestResult(
                name=test_name,
                success=False,
                message=f"Backward compatibility test failed: {str(e)}",
                details={"exception": str(e)}
            ))
    
    def create_mock_config(self):
        """Create a mock configuration for testing."""
        from unittest.mock import MagicMock
        
        # Create a more realistic mock config that services can use
        mock_config = MagicMock()
        
        # Checkmk config
        mock_config.checkmk = MagicMock()
        mock_config.checkmk.server_url = "http://test.example.com"
        mock_config.checkmk.username = "test_user"
        mock_config.checkmk.password = "test_password"
        mock_config.checkmk.site = "test_site"
        
        # Create real config objects for numeric values that services need
        from types import SimpleNamespace
        
        # Batch processing config - use SimpleNamespace for real values
        mock_config.batch = SimpleNamespace()
        mock_config.batch.max_concurrent = 5
        mock_config.batch.max_retries = 3
        mock_config.batch.retry_delay = 1.0
        mock_config.batch.rate_limit = None
        
        # Cache config
        mock_config.cache = SimpleNamespace()
        mock_config.cache.ttl = 300
        mock_config.cache.max_size = 1000
        
        # Streaming config  
        mock_config.streaming = SimpleNamespace()
        mock_config.streaming.buffer_size = 100
        mock_config.streaming.timeout = 60
        
        return mock_config
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate a comprehensive test report."""
        successful_tests = [r for r in self.results if r.success]
        failed_tests = [r for r in self.results if not r.success]
        
        report = {
            "timestamp": "2025-08-20T10:00:00Z",
            "phase": "Phase 5 - Main Server Refactoring",
            "summary": {
                "total_tests": len(self.results),
                "successful": len(successful_tests),
                "failed": len(failed_tests),
                "success_rate": len(successful_tests) / len(self.results) * 100 if self.results else 0
            },
            "tests": {
                "successful": [{"name": r.name, "message": r.message, "details": r.details} for r in successful_tests],
                "failed": [{"name": r.name, "message": r.message, "details": r.details} for r in failed_tests]
            },
            "recommendations": self.generate_recommendations(failed_tests)
        }
        
        return report
    
    def generate_recommendations(self, failed_tests: List[TestResult]) -> List[str]:
        """Generate recommendations based on failed tests."""
        recommendations = []
        
        if not failed_tests:
            recommendations.append("All tests passed! The refactored server is working correctly.")
            recommendations.append("Ready to proceed with Phase 6 (Integration and Testing).")
        else:
            recommendations.append("Some tests failed. Please address the following issues:")
            for test in failed_tests:
                recommendations.append(f"- Fix {test.name}: {test.message}")
        
        return recommendations


async def main():
    """Run the Phase 5 integration tests."""
    tester = Phase5IntegrationTester()
    
    try:
        report = await tester.run_all_tests()
        
        # Print summary
        print("\n" + "=" * 60)
        print("PHASE 5 INTEGRATION TEST RESULTS")
        print("=" * 60)
        print(f"Total Tests: {report['summary']['total_tests']}")
        print(f"Successful: {report['summary']['successful']}")
        print(f"Failed: {report['summary']['failed']}")
        print(f"Success Rate: {report['summary']['success_rate']:.1f}%")
        
        # Print failed tests
        if report['tests']['failed']:
            print("\nFAILED TESTS:")
            print("-" * 30)
            for test in report['tests']['failed']:
                print(f"❌ {test['name']}: {test['message']}")
        
        # Print successful tests
        if report['tests']['successful']:
            print("\nSUCCESSFUL TESTS:")
            print("-" * 30)
            for test in report['tests']['successful']:
                print(f"✅ {test['name']}: {test['message']}")
        
        # Print recommendations
        print("\nRECOMMENDATIONS:")
        print("-" * 30)
        for rec in report['recommendations']:
            print(f"• {rec}")
        
        # Save detailed report
        report_file = f"phase5_integration_report_{report['timestamp'].replace(':', '').replace('-', '')}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\nDetailed report saved to: {report_file}")
        
        # Exit with appropriate code
        sys.exit(0 if report['summary']['failed'] == 0 else 1)
        
    except Exception as e:
        print(f"Critical error during testing: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())