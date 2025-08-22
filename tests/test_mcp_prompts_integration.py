"""Integration tests for the prompt system to ensure all prompts function identically."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from mcp.types import GetPromptResult, PromptMessage, TextContent

from checkmk_mcp_server.mcp_server.prompts.definitions import PromptDefinitions
from checkmk_mcp_server.mcp_server.prompts.handlers import PromptHandlers
from checkmk_mcp_server.mcp_server.prompts.validators import PromptValidators


class TestPromptIntegrationComplete:
    """Test complete integration of prompt system."""

    @pytest.fixture
    def mock_services(self):
        """Create mock services for testing."""
        return {
            'host_service': AsyncMock(),
            'status_service': AsyncMock(),
            'service_service': AsyncMock(),
            'parameter_service': AsyncMock(),
            'checkmk_client': AsyncMock()
        }

    @pytest.mark.asyncio
    async def test_analyze_host_health_complete_flow(self, mock_services):
        """Test complete analyze_host_health flow."""
        # Setup mock responses
        mock_services['host_service'].get_host.return_value = MagicMock(
            success=True,
            data=MagicMock(model_dump=lambda: {'host_name': 'test-host', 'state': 0})
        )
        mock_services['status_service'].analyze_host_health.return_value = MagicMock(
            success=True,
            data={'grade': 'A', 'issues': []}
        )
        
        # Test the complete flow
        args = {'host_name': 'test-host', 'include_grade': 'true'}
        
        # 1. Validate arguments
        validated_args = PromptValidators.validate_prompt_arguments('analyze_host_health', args)
        assert validated_args['host_name'] == 'test-host'
        assert validated_args['include_grade'] is True
        
        # 2. Execute handler
        result = await PromptHandlers.handle_analyze_host_health(
            validated_args, 
            mock_services['host_service'],
            mock_services['status_service']
        )
        
        # 3. Verify result
        assert isinstance(result, GetPromptResult)
        assert len(result.messages) == 1
        assert isinstance(result.messages[0], PromptMessage)
        assert isinstance(result.messages[0].content, TextContent)
        assert 'test-host' in result.messages[0].content.text

    @pytest.mark.asyncio
    async def test_troubleshoot_service_complete_flow(self, mock_services):
        """Test complete troubleshoot_service flow."""
        # Setup mock responses
        mock_services['service_service'].list_host_services.return_value = MagicMock(
            success=True,
            data=MagicMock(services=[
                MagicMock(service_name='CPU load', model_dump=lambda: {'state': 2, 'output': 'CRITICAL'})
            ])
        )
        
        # Test the complete flow
        args = {'host_name': 'test-host', 'service_name': 'CPU load'}
        
        # 1. Validate arguments
        validated_args = PromptValidators.validate_prompt_arguments('troubleshoot_service', args)
        assert validated_args['host_name'] == 'test-host'
        assert validated_args['service_name'] == 'CPU load'
        
        # 2. Execute handler
        result = await PromptHandlers.handle_troubleshoot_service(
            validated_args, 
            mock_services['service_service']
        )
        
        # 3. Verify result
        assert isinstance(result, GetPromptResult)
        assert len(result.messages) == 1
        assert 'CPU load' in result.messages[0].content.text
        assert 'test-host' in result.messages[0].content.text

    @pytest.mark.asyncio
    async def test_adjust_host_check_attempts_complete_flow(self, mock_services):
        """Test complete adjust_host_check_attempts flow."""
        # Setup mock responses
        mock_services['host_service'].get_host.return_value = MagicMock(
            success=True,
            data=MagicMock(host_max_check_attempts=3, host_retry_interval=1.0, host_check_interval=1.0)
        )
        mock_services['checkmk_client'].create_rule.return_value = {'id': 'rule_123'}
        
        # Test the complete flow
        args = {'host_name': 'test-host', 'max_attempts': '5', 'reason': 'unreliable network'}
        
        # 1. Validate arguments
        validated_args = PromptValidators.validate_prompt_arguments('adjust_host_check_attempts', args)
        assert validated_args['host_name'] == 'test-host'
        assert validated_args['max_attempts'] == 5
        assert validated_args['reason'] == 'unreliable network'
        
        # 2. Execute handler
        result = await PromptHandlers.handle_adjust_host_check_attempts(
            validated_args, 
            mock_services['host_service'],
            mock_services['checkmk_client']
        )
        
        # 3. Verify result
        assert isinstance(result, GetPromptResult)
        assert len(result.messages) == 1
        assert 'test-host' in result.messages[0].content.text
        assert '5' in result.messages[0].content.text

    def test_all_prompts_have_complete_implementation(self):
        """Test that all prompts have complete implementation."""
        prompts = PromptDefinitions.get_all_prompts()
        
        for prompt_name in prompts.keys():
            # 1. Check prompt definition exists
            prompt = PromptDefinitions.get_prompt_by_name(prompt_name)
            assert prompt.name == prompt_name
            assert prompt.description
            assert isinstance(prompt.arguments, list)
            
            # 2. Check validation schema exists
            schema = PromptValidators.get_validation_schema(prompt_name)
            assert isinstance(schema, dict)
            
            # 3. Check handler method exists
            handler_name = f'handle_{prompt_name}'
            assert hasattr(PromptHandlers, handler_name)
            handler = getattr(PromptHandlers, handler_name)
            assert callable(handler)

    def test_prompt_argument_consistency(self):
        """Test that prompt arguments are consistent across definitions and validators."""
        prompts = PromptDefinitions.get_all_prompts()
        
        for prompt_name, prompt in prompts.items():
            schema = PromptValidators.get_validation_schema(prompt_name)
            
            # Check that all required arguments in definition have schemas
            for arg in prompt.arguments:
                if arg.required:
                    assert arg.name in schema, f"Required argument {arg.name} missing from {prompt_name} schema"
                    assert schema[arg.name].get('required', False), f"Argument {arg.name} should be required in {prompt_name} schema"

    @pytest.mark.asyncio 
    async def test_error_handling_consistency(self, mock_services):
        """Test that all handlers handle errors consistently."""
        # Test invalid arguments for each prompt
        prompts = PromptDefinitions.get_all_prompts()
        
        for prompt_name in prompts.keys():
            # Test validation error handling - use completely empty args to trigger validation errors
            if prompt_name == 'infrastructure_overview':
                # This prompt has no required args, so skip it
                continue
            with pytest.raises((ValueError, KeyError)):
                PromptValidators.validate_prompt_arguments(prompt_name, {})

    def test_prompt_categories_coverage(self):
        """Test that prompt categories provide complete coverage."""
        all_prompts = set(PromptDefinitions.get_prompt_names())
        categories = PromptDefinitions.get_prompt_categories()
        
        # Check that every prompt is in at least one category
        categorized_prompts = set()
        for category_prompts in categories.values():
            categorized_prompts.update(category_prompts)
        
        missing_prompts = all_prompts - categorized_prompts
        assert not missing_prompts, f"Prompts not categorized: {missing_prompts}"
        
        # Check that no prompt is duplicated across categories
        all_categorized = []
        for category_prompts in categories.values():
            all_categorized.extend(category_prompts)
        
        duplicates = set([p for p in all_categorized if all_categorized.count(p) > 1])
        assert not duplicates, f"Prompts in multiple categories: {duplicates}"

    def test_prompt_naming_consistency(self):
        """Test that prompt names follow consistent conventions."""
        prompts = PromptDefinitions.get_all_prompts()
        
        for prompt_name in prompts.keys():
            # Names should be lowercase with underscores
            assert prompt_name.islower(), f"Prompt name {prompt_name} should be lowercase"
            assert ' ' not in prompt_name, f"Prompt name {prompt_name} should not contain spaces"
            
            # Handler should exist with expected name
            handler_name = f'handle_{prompt_name}'
            assert hasattr(PromptHandlers, handler_name), f"Handler {handler_name} not found"

    def test_validation_error_messages(self):
        """Test that validation error messages are helpful."""
        # Test some specific validation error cases
        test_cases = [
            ('analyze_host_health', {}, 'host_name is required'),
            ('troubleshoot_service', {'host_name': 'test'}, 'service_name is required'),
            ('adjust_host_check_attempts', {'host_name': 'test', 'max_attempts': '15'}, 'between 1 and 10'),
        ]
        
        for prompt_name, args, expected_error in test_cases:
            with pytest.raises(ValueError) as exc_info:
                PromptValidators.validate_prompt_arguments(prompt_name, args)
            assert expected_error in str(exc_info.value)

    def test_prompt_descriptions_quality(self):
        """Test that prompt descriptions are meaningful."""
        prompts = PromptDefinitions.get_all_prompts()
        
        for prompt_name, prompt in prompts.items():
            # Description should be meaningful
            assert len(prompt.description) > 20, f"Prompt {prompt_name} description too short"
            assert not prompt.description.endswith('.'), f"Prompt {prompt_name} description should not end with period"
            
            # Should contain action words
            action_words = ['analyze', 'troubleshoot', 'configure', 'adjust', 'get', 'optimize']
            description_lower = prompt.description.lower()
            has_action = any(word in description_lower for word in action_words)
            assert has_action, f"Prompt {prompt_name} description should contain action word"


class TestPromptSystemMetrics:
    """Test metrics and statistics about the prompt system."""

    def test_prompt_count_target(self):
        """Test that we have implemented a reasonable number of prompts."""
        prompts = PromptDefinitions.get_all_prompts()
        
        # We currently have 7 prompts - this is the baseline
        assert len(prompts) >= 7, f"Expected at least 7 prompts, got {len(prompts)}"
        
        print(f"✅ Current prompt count: {len(prompts)}")
        for prompt_name in sorted(prompts.keys()):
            print(f"   - {prompt_name}")

    def test_prompt_category_distribution(self):
        """Test distribution of prompts across categories."""
        categories = PromptDefinitions.get_prompt_categories()
        
        print(f"✅ Prompt categories: {len(categories)}")
        for category, prompts in categories.items():
            print(f"   - {category}: {len(prompts)} prompts")
            for prompt in prompts:
                print(f"     * {prompt}")

    def test_validation_coverage(self):
        """Test validation coverage across prompt types."""
        prompts = PromptDefinitions.get_all_prompts()
        
        validation_stats = {
            'total_prompts': len(prompts),
            'with_required_args': 0,
            'with_optional_args': 0,
            'total_arguments': 0
        }
        
        for prompt in prompts.values():
            has_required = any(arg.required for arg in prompt.arguments)
            has_optional = any(not arg.required for arg in prompt.arguments)
            
            if has_required:
                validation_stats['with_required_args'] += 1
            if has_optional:
                validation_stats['with_optional_args'] += 1
            
            validation_stats['total_arguments'] += len(prompt.arguments)
        
        print(f"✅ Validation coverage:")
        print(f"   - Total prompts: {validation_stats['total_prompts']}")
        print(f"   - With required args: {validation_stats['with_required_args']}")
        print(f"   - With optional args: {validation_stats['with_optional_args']}")
        print(f"   - Total arguments: {validation_stats['total_arguments']}")
        
        # Basic sanity checks
        assert validation_stats['with_required_args'] > 0
        assert validation_stats['total_arguments'] > validation_stats['total_prompts']