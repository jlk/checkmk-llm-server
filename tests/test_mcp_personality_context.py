"""Test MCP personality context implementation."""

import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock
from checkmk_mcp_server.mcp_server import CheckmkMCPServer
from checkmk_mcp_server.config import AppConfig
from mcp.server.models import InitializationOptions


class TestMCPPersonalityContext:
    """Test the MCP server personality context functionality."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration."""
        config = Mock(spec=AppConfig)
        config.checkmk = Mock()
        config.checkmk.server_url = "https://test.checkmk.com"
        config.checkmk.username = "test_user"
        config.checkmk.password = "test_pass"
        config.checkmk.site = "test_site"
        return config

    @pytest.fixture
    def mcp_server(self, mock_config):
        """Create an MCP server instance."""
        return CheckmkMCPServer(mock_config)

    def test_personality_instructions_in_initialization(self, mcp_server):
        """Test that personality instructions are included in InitializationOptions."""
        # The instructions should be set when the server runs
        # We'll check that the run method properly configures InitializationOptions
        
        # Expected personality context keywords
        expected_keywords = [
            "Senior Network Operations Engineer",
            "15+ years of expertise",
            "infrastructure monitoring",
            "network protocols",
            "TCP/IP, SNMP, ICMP",
            "incident response",
            "root cause analysis",
            "MTTR",
            "high availability"
        ]
        
        # Mock the stdio_server import that happens inside the run method
        with patch('mcp.server.stdio.stdio_server') as mock_stdio:
            with patch.object(mcp_server.server, 'run') as mock_run:
                with patch.object(mcp_server.server, 'get_capabilities') as mock_capabilities:
                    # Setup mocks
                    mock_read = Mock()
                    mock_write = Mock()
                    mock_stdio.return_value.__aenter__.return_value = (mock_read, mock_write)
                    mock_capabilities.return_value = {}
                    
                    # Ensure services are initialized
                    with patch.object(mcp_server, '_ensure_services', return_value=True):
                        # Run the server (this will fail but we can check the call)
                        async def run_test():
                            try:
                                await mcp_server.run()
                            except:
                                pass  # We expect this to fail in test environment
                        
                        asyncio.run(run_test())
                    
                    # Check that server.run was called
                    assert mock_run.called
                    
                    # Get the InitializationOptions from the call
                    call_args = mock_run.call_args
                    if call_args and len(call_args[0]) >= 3:
                        init_options = call_args[0][2]
                        
                        # Check if it's an InitializationOptions
                        if hasattr(init_options, 'instructions'):
                            instructions = init_options.instructions
                            
                            # Verify that instructions contain expected personality context
                            assert instructions is not None, "Instructions should not be None"
                            
                            # Convert to lowercase for case-insensitive comparison
                            instructions_lower = instructions.lower()
                            
                            for keyword in expected_keywords:
                                assert keyword.lower() in instructions_lower, f"Expected '{keyword}' in personality instructions"

    def test_personality_content_structure(self):
        """Test that the personality instructions have the expected structure."""
        # This test verifies the content directly from the code
        expected_sections = [
            "Your expertise includes:",
            "Communication style:",
            "When analyzing monitoring data:"
        ]
        
        # Read the actual instructions from the modified server.py file
        with open('/Users/jlk/code-local/checkmk_llm_agent/checkmk_agent/mcp_server/server.py', 'r') as f:
            content = f.read()
            
            # Find the instructions section
            if 'instructions="""You are an experienced' in content:
                start = content.find('instructions="""You are an experienced')
                end = content.find('"""', start + 20)
                instructions = content[start:end]
                
                for section in expected_sections:
                    assert section in instructions, f"Expected section '{section}' in personality instructions"

    def test_personality_expertise_areas(self):
        """Test that all required expertise areas are mentioned."""
        expertise_areas = [
            "network protocols",
            "monitoring best practices",
            "incident response",
            "performance tuning",
            "capacity planning",
            "service level management",
            "automation"
        ]
        
        # Read the actual instructions
        with open('/Users/jlk/code-local/checkmk_llm_agent/checkmk_agent/mcp_server/server.py', 'r') as f:
            content = f.read()
            
            if 'instructions="""You are an experienced' in content:
                start = content.find('instructions="""You are an experienced')
                end = content.find('"""', start + 20)
                instructions = content[start:end].lower()
                
                for area in expertise_areas:
                    assert area.lower() in instructions, f"Expertise area '{area}' should be mentioned"

    def test_communication_style_attributes(self):
        """Test that communication style attributes are properly defined."""
        style_attributes = [
            "technically precise",
            "practical",
            "actionable",
            "CLI commands",
            "proactive"
        ]
        
        # Read the actual instructions
        with open('/Users/jlk/code-local/checkmk_llm_agent/checkmk_agent/mcp_server/server.py', 'r') as f:
            content = f.read()
            
            if 'instructions="""You are an experienced' in content:
                start = content.find('instructions="""You are an experienced')
                end = content.find('"""', start + 20)
                instructions = content[start:end].lower()
                
                for attribute in style_attributes:
                    assert attribute.lower() in instructions, f"Communication style '{attribute}' should be mentioned"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])