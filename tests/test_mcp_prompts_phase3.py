"""Test Phase 3 prompt extraction functionality."""

import pytest
from mcp.types import Prompt, PromptArgument

from checkmk_mcp_server.mcp_server.prompts.definitions import PromptDefinitions
from checkmk_mcp_server.mcp_server.prompts.validators import PromptValidators


class TestPromptDefinitions:
    """Test prompt definitions module."""

    def test_get_all_prompts(self):
        """Test getting all prompt definitions."""
        prompts = PromptDefinitions.get_all_prompts()
        
        # Should have exactly 7 prompts
        assert len(prompts) == 7
        
        # Check prompt names
        expected_prompts = {
            'analyze_host_health',
            'troubleshoot_service', 
            'infrastructure_overview',
            'optimize_parameters',
            'adjust_host_check_attempts',
            'adjust_host_retry_interval',
            'adjust_host_check_timeout'
        }
        assert set(prompts.keys()) == expected_prompts
        
        # Check that all are Prompt objects
        for prompt in prompts.values():
            assert isinstance(prompt, Prompt)
            assert hasattr(prompt, 'name')
            assert hasattr(prompt, 'description')
            assert hasattr(prompt, 'arguments')

    def test_get_prompt_categories(self):
        """Test getting prompt categories."""
        categories = PromptDefinitions.get_prompt_categories()
        
        # Should have 4 categories
        assert len(categories) == 4
        
        expected_categories = {
            'health_analysis',
            'troubleshooting', 
            'optimization',
            'host_configuration'
        }
        assert set(categories.keys()) == expected_categories
        
        # Check total prompts across categories
        total_prompts = sum(len(prompts) for prompts in categories.values())
        assert total_prompts == 7

    def test_get_prompt_names(self):
        """Test getting prompt names."""
        names = PromptDefinitions.get_prompt_names()
        assert len(names) == 7
        assert isinstance(names, list)

    def test_get_prompt_by_name(self):
        """Test getting individual prompts by name."""
        # Test valid prompt
        prompt = PromptDefinitions.get_prompt_by_name('analyze_host_health')
        assert isinstance(prompt, Prompt)
        assert prompt.name == 'analyze_host_health'
        
        # Test invalid prompt
        with pytest.raises(KeyError, match="Prompt 'invalid_prompt' not found"):
            PromptDefinitions.get_prompt_by_name('invalid_prompt')


class TestPromptValidators:
    """Test prompt validators module."""

    def test_validate_analyze_host_health(self):
        """Test validate_analyze_host_health method."""
        # Test valid input
        result = PromptValidators.validate_analyze_host_health({
            'host_name': 'test-host',
            'include_grade': 'true'
        })
        expected = {'host_name': 'test-host', 'include_grade': True}
        assert result == expected
        
        # Test missing required field
        with pytest.raises(ValueError, match="host_name is required"):
            PromptValidators.validate_analyze_host_health({})
        
        # Test boolean conversion
        result = PromptValidators.validate_analyze_host_health({
            'host_name': 'test-host',
            'include_grade': 'false'
        })
        assert result['include_grade'] is False

    def test_validate_troubleshoot_service(self):
        """Test validate_troubleshoot_service method."""
        # Test valid input
        result = PromptValidators.validate_troubleshoot_service({
            'host_name': 'test-host',
            'service_name': 'CPU load'
        })
        expected = {'host_name': 'test-host', 'service_name': 'CPU load'}
        assert result == expected
        
        # Test missing required fields
        with pytest.raises(ValueError, match="host_name is required"):
            PromptValidators.validate_troubleshoot_service({'service_name': 'CPU load'})
        
        with pytest.raises(ValueError, match="service_name is required"):
            PromptValidators.validate_troubleshoot_service({'host_name': 'test-host'})

    def test_validate_adjust_host_check_attempts(self):
        """Test validate_adjust_host_check_attempts method."""
        # Test valid input
        result = PromptValidators.validate_adjust_host_check_attempts({
            'host_name': 'test-host',
            'max_attempts': '5',
            'reason': 'unreliable network'
        })
        expected = {
            'host_name': 'test-host', 
            'max_attempts': 5,
            'reason': 'unreliable network'
        }
        assert result == expected
        
        # Test 'all' host name
        result = PromptValidators.validate_adjust_host_check_attempts({
            'host_name': 'ALL',
            'max_attempts': '3'
        })
        assert result['host_name'] == 'all'
        
        # Test invalid max_attempts
        with pytest.raises(ValueError, match="max_attempts must be a valid integer between 1 and 10"):
            PromptValidators.validate_adjust_host_check_attempts({
                'host_name': 'test-host',
                'max_attempts': '15'
            })

    def test_validate_prompt_arguments_dispatcher(self):
        """Test central validation dispatcher."""
        # Test valid dispatch
        result = PromptValidators.validate_prompt_arguments(
            'analyze_host_health',
            {'host_name': 'test-host'}
        )
        assert result['host_name'] == 'test-host'
        
        # Test unknown prompt
        with pytest.raises(KeyError, match="Unknown prompt 'invalid_prompt'"):
            PromptValidators.validate_prompt_arguments('invalid_prompt', {})

    def test_get_validation_schema(self):
        """Test getting validation schemas."""
        schema = PromptValidators.get_validation_schema('analyze_host_health')
        
        assert 'host_name' in schema
        assert 'include_grade' in schema
        assert schema['host_name']['required'] is True
        assert schema['include_grade']['required'] is False
        
        # Test unknown prompt
        with pytest.raises(KeyError, match="No schema for prompt 'invalid_prompt'"):
            PromptValidators.get_validation_schema('invalid_prompt')


class TestPromptIntegration:
    """Test integration between prompt modules."""

    def test_definitions_match_validators(self):
        """Test that all prompts in definitions have validators."""
        prompts = PromptDefinitions.get_all_prompts()
        
        # Test that each prompt has a validation schema
        for prompt_name in prompts.keys():
            schema = PromptValidators.get_validation_schema(prompt_name)
            assert isinstance(schema, dict)
            
            # Test that validation works for each prompt
            try:
                # Create minimal valid args for each prompt
                if prompt_name == 'analyze_host_health':
                    args = {'host_name': 'test'}
                elif prompt_name == 'troubleshoot_service':
                    args = {'host_name': 'test', 'service_name': 'test'}
                elif prompt_name == 'infrastructure_overview':
                    args = {}
                elif prompt_name == 'optimize_parameters':
                    args = {'host_name': 'test', 'service_name': 'test'}
                elif prompt_name in ['adjust_host_check_attempts', 'adjust_host_retry_interval', 'adjust_host_check_timeout']:
                    if 'attempts' in prompt_name:
                        args = {'host_name': 'test', 'max_attempts': '3'}
                    elif 'retry' in prompt_name:
                        args = {'host_name': 'test', 'retry_interval': '2.0'}
                    elif 'timeout' in prompt_name:
                        args = {'host_name': 'test', 'timeout_seconds': '10'}
                
                result = PromptValidators.validate_prompt_arguments(prompt_name, args)
                assert isinstance(result, dict)
                
            except Exception as e:
                pytest.fail(f"Validation failed for prompt {prompt_name}: {e}")

    def test_category_coverage(self):
        """Test that all prompts are covered by categories."""
        all_prompts = set(PromptDefinitions.get_prompt_names())
        categories = PromptDefinitions.get_prompt_categories()
        
        categorized_prompts = set()
        for prompts in categories.values():
            categorized_prompts.update(prompts)
        
        assert all_prompts == categorized_prompts, "All prompts should be categorized"