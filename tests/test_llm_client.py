"""Unit tests for LLM clients."""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock

from checkmk_mcp_server.llm_client import (
    LLMClient,
    OpenAIClient,
    AnthropicClient,
    ParsedCommand,
    HostOperation,
    LLMProvider,
    create_llm_client,
)
from checkmk_mcp_server.config import LLMConfig


@pytest.fixture
def llm_config():
    """Create test LLM configuration."""
    return LLMConfig(
        openai_api_key="test-openai-key",
        anthropic_api_key="test-anthropic-key",
        default_model="gpt-3.5-turbo",
    )


@pytest.fixture
def llm_config_openai_only():
    """Create test LLM configuration with only OpenAI."""
    return LLMConfig(
        openai_api_key="test-openai-key",
        anthropic_api_key=None,
        default_model="gpt-3.5-turbo",
    )


@pytest.fixture
def llm_config_anthropic_only():
    """Create test LLM configuration with only Anthropic."""
    return LLMConfig(
        openai_api_key=None,
        anthropic_api_key="test-anthropic-key",
        default_model="gpt-3.5-turbo",
    )


class TestParsedCommand:
    """Test ParsedCommand class."""

    def test_basic_command(self):
        """Test basic command creation."""
        cmd = ParsedCommand(
            operation=HostOperation.LIST,
            parameters={"search_term": "web"},
            confidence=0.9,
            raw_text="list web hosts",
        )

        assert cmd.operation == HostOperation.LIST
        assert cmd.parameters["search_term"] == "web"
        assert cmd.confidence == 0.9
        assert cmd.raw_text == "list web hosts"

    def test_default_values(self):
        """Test command with default values."""
        cmd = ParsedCommand(
            operation=HostOperation.CREATE, parameters={"host_name": "test"}
        )

        assert cmd.operation == HostOperation.CREATE
        assert cmd.parameters["host_name"] == "test"
        assert cmd.confidence == 1.0
        assert cmd.raw_text == ""

    def test_repr(self):
        """Test string representation."""
        cmd = ParsedCommand(HostOperation.DELETE, {"host_name": "test"})
        repr_str = repr(cmd)

        assert "ParsedCommand" in repr_str
        assert "DELETE" in repr_str
        assert "test" in repr_str


class TestOpenAIClient:
    """Test OpenAI client functionality."""

    @patch("checkmk_mcp_server.llm_client.openai.OpenAI")
    def test_initialization_success(self, mock_openai, llm_config):
        """Test successful OpenAI client initialization."""
        mock_client = Mock()
        mock_openai.return_value = mock_client

        with patch("checkmk_mcp_server.llm_client.OPENAI_AVAILABLE", True):
            client = OpenAIClient(llm_config)

        assert client.client == mock_client
        assert client.model == "gpt-3.5-turbo"
        mock_openai.assert_called_once_with(api_key="test-openai-key")

    def test_initialization_missing_library(self, llm_config):
        """Test initialization with missing OpenAI library."""
        with patch("checkmk_mcp_server.llm_client.OPENAI_AVAILABLE", False):
            with pytest.raises(ImportError, match="OpenAI library not installed"):
                OpenAIClient(llm_config)

    def test_initialization_missing_api_key(self):
        """Test initialization with missing API key."""
        config = LLMConfig(openai_api_key=None)

        with patch("checkmk_mcp_server.llm_client.OPENAI_AVAILABLE", True):
            with pytest.raises(ValueError, match="OpenAI API key not provided"):
                OpenAIClient(config)

    @patch("checkmk_mcp_server.llm_client.openai.OpenAI")
    def test_parse_command_success(self, mock_openai, llm_config):
        """Test successful command parsing."""
        # Setup mock response
        mock_response = Mock()
        mock_choice = Mock()
        mock_choice.message.content = json.dumps(
            {
                "operation": "list",
                "parameters": {"search_term": "web"},
                "confidence": 0.9,
            }
        )
        mock_response.choices = [mock_choice]

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        with patch("checkmk_mcp_server.llm_client.OPENAI_AVAILABLE", True):
            client = OpenAIClient(llm_config)
            result = client.parse_command("list web hosts")

        assert result.operation == HostOperation.LIST
        assert result.parameters["search_term"] == "web"
        assert result.confidence == 0.9
        assert result.raw_text == "list web hosts"

    @patch("checkmk_mcp_server.llm_client.openai.OpenAI")
    def test_parse_command_fallback(self, mock_openai, llm_config):
        """Test command parsing with fallback when API fails."""
        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = Exception("API error")
        mock_openai.return_value = mock_client

        with patch("checkmk_mcp_server.llm_client.OPENAI_AVAILABLE", True):
            client = OpenAIClient(llm_config)
            result = client.parse_command("list all hosts")

        # Should fallback to keyword matching
        assert result.operation == HostOperation.LIST
        assert result.confidence == 0.6  # Fallback confidence

    @patch("checkmk_mcp_server.llm_client.openai.OpenAI")
    def test_fallback_parse_create(self, mock_openai, llm_config):
        """Test fallback parsing for create commands."""
        mock_openai.return_value = Mock()

        with patch("checkmk_mcp_server.llm_client.OPENAI_AVAILABLE", True):
            client = OpenAIClient(llm_config)
            result = client._fallback_parse("create host server01")

        assert result.operation == HostOperation.CREATE
        assert result.parameters.get("host_name") == "server01"
        assert result.confidence == 0.7

    @patch("checkmk_mcp_server.llm_client.openai.OpenAI")
    def test_fallback_parse_delete(self, mock_openai, llm_config):
        """Test fallback parsing for delete commands."""
        mock_openai.return_value = Mock()

        with patch("checkmk_mcp_server.llm_client.OPENAI_AVAILABLE", True):
            client = OpenAIClient(llm_config)
            result = client._fallback_parse("delete host web01")

        assert result.operation == HostOperation.DELETE
        assert result.parameters.get("host_name") == "web01"
        assert result.confidence == 0.7

    @patch("checkmk_mcp_server.llm_client.openai.OpenAI")
    def test_format_response_list_success(self, mock_openai, llm_config):
        """Test response formatting for successful list operation."""
        mock_openai.return_value = Mock()

        with patch("checkmk_mcp_server.llm_client.OPENAI_AVAILABLE", True):
            client = OpenAIClient(llm_config)

            hosts_data = [
                {"id": "web01", "extensions": {"folder": "/web"}},
                {"id": "db01", "extensions": {"folder": "/database"}},
            ]

            result = client.format_response(
                HostOperation.LIST, hosts_data, success=True
            )

        assert "Found 2 hosts" in result
        assert "web01 (folder: /web)" in result
        assert "db01 (folder: /database)" in result

    @patch("checkmk_mcp_server.llm_client.openai.OpenAI")
    def test_format_response_list_empty(self, mock_openai, llm_config):
        """Test response formatting for empty list."""
        mock_openai.return_value = Mock()

        with patch("checkmk_mcp_server.llm_client.OPENAI_AVAILABLE", True):
            client = OpenAIClient(llm_config)
            result = client.format_response(HostOperation.LIST, [], success=True)

        assert result == "No hosts found."

    @patch("checkmk_mcp_server.llm_client.openai.OpenAI")
    def test_format_response_create_success(self, mock_openai, llm_config):
        """Test response formatting for successful create operation."""
        mock_openai.return_value = Mock()

        with patch("checkmk_mcp_server.llm_client.OPENAI_AVAILABLE", True):
            client = OpenAIClient(llm_config)

            create_data = {"id": "new-host"}
            result = client.format_response(
                HostOperation.CREATE, create_data, success=True
            )

        assert "Successfully created host: new-host" in result

    @patch("checkmk_mcp_server.llm_client.openai.OpenAI")
    def test_format_response_error(self, mock_openai, llm_config):
        """Test response formatting for error."""
        mock_openai.return_value = Mock()

        with patch("checkmk_mcp_server.llm_client.OPENAI_AVAILABLE", True):
            client = OpenAIClient(llm_config)
            result = client.format_response(
                HostOperation.LIST, None, success=False, error="API connection failed"
            )

        assert result == "Error: API connection failed"


class TestAnthropicClient:
    """Test Anthropic client functionality."""

    @patch("checkmk_mcp_server.llm_client.anthropic.Anthropic")
    def test_initialization_success(self, mock_anthropic, llm_config):
        """Test successful Anthropic client initialization."""
        mock_client = Mock()
        mock_anthropic.return_value = mock_client

        with patch("checkmk_mcp_server.llm_client.ANTHROPIC_AVAILABLE", True):
            client = AnthropicClient(llm_config)

        assert client.client == mock_client
        assert client.model == "claude-3-haiku-20240307"
        mock_anthropic.assert_called_once_with(api_key="test-anthropic-key")

    def test_initialization_missing_library(self, llm_config):
        """Test initialization with missing Anthropic library."""
        with patch("checkmk_mcp_server.llm_client.ANTHROPIC_AVAILABLE", False):
            with pytest.raises(ImportError, match="Anthropic library not installed"):
                AnthropicClient(llm_config)

    def test_initialization_missing_api_key(self):
        """Test initialization with missing API key."""
        config = LLMConfig(anthropic_api_key=None)

        with patch("checkmk_mcp_server.llm_client.ANTHROPIC_AVAILABLE", True):
            with pytest.raises(ValueError, match="Anthropic API key not provided"):
                AnthropicClient(config)

    @patch("checkmk_mcp_server.llm_client.anthropic.Anthropic")
    def test_parse_command_success(self, mock_anthropic, llm_config):
        """Test successful command parsing with Anthropic."""
        # Setup mock response
        mock_content = Mock()
        mock_content.text = json.dumps(
            {
                "operation": "create",
                "parameters": {"host_name": "server01", "folder": "/"},
                "confidence": 0.95,
            }
        )

        mock_response = Mock()
        mock_response.content = [mock_content]

        mock_client = Mock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        with patch("checkmk_mcp_server.llm_client.ANTHROPIC_AVAILABLE", True):
            client = AnthropicClient(llm_config)
            result = client.parse_command("create server01")

        assert result.operation == HostOperation.CREATE
        assert result.parameters["host_name"] == "server01"
        assert result.confidence == 0.95


class TestCreateLLMClient:
    """Test LLM client factory function."""

    def test_create_openai_client_explicit(self, llm_config):
        """Test creating OpenAI client explicitly."""
        with patch("checkmk_mcp_server.llm_client.OPENAI_AVAILABLE", True):
            with patch("checkmk_mcp_server.llm_client.openai.OpenAI"):
                client = create_llm_client(llm_config, LLMProvider.OPENAI)
                assert isinstance(client, OpenAIClient)

    def test_create_anthropic_client_explicit(self, llm_config):
        """Test creating Anthropic client explicitly."""
        with patch("checkmk_mcp_server.llm_client.ANTHROPIC_AVAILABLE", True):
            with patch("checkmk_mcp_server.llm_client.anthropic.Anthropic"):
                client = create_llm_client(llm_config, LLMProvider.ANTHROPIC)
                assert isinstance(client, AnthropicClient)

    def test_auto_detect_openai(self, llm_config_openai_only):
        """Test auto-detection of OpenAI when only OpenAI key available."""
        with patch("checkmk_mcp_server.llm_client.OPENAI_AVAILABLE", True):
            with patch("checkmk_mcp_server.llm_client.openai.OpenAI"):
                client = create_llm_client(llm_config_openai_only)
                assert isinstance(client, OpenAIClient)

    def test_auto_detect_anthropic(self, llm_config_anthropic_only):
        """Test auto-detection of Anthropic when only Anthropic key available."""
        with patch("checkmk_mcp_server.llm_client.ANTHROPIC_AVAILABLE", True):
            with patch("checkmk_mcp_server.llm_client.anthropic.Anthropic"):
                client = create_llm_client(llm_config_anthropic_only)
                assert isinstance(client, AnthropicClient)

    def test_no_api_keys(self):
        """Test error when no API keys provided."""
        config = LLMConfig(openai_api_key=None, anthropic_api_key=None)

        with pytest.raises(ValueError, match="No LLM API key provided"):
            create_llm_client(config)

    def test_unsupported_provider(self, llm_config):
        """Test error for unsupported provider."""
        with pytest.raises(ValueError, match="Unsupported LLM provider"):
            create_llm_client(llm_config, "unsupported_provider")


class TestHostOperation:
    """Test HostOperation enum."""

    def test_enum_values(self):
        """Test enum values."""
        assert HostOperation.LIST.value == "list"
        assert HostOperation.CREATE.value == "create"
        assert HostOperation.DELETE.value == "delete"
        assert HostOperation.GET.value == "get"
        assert HostOperation.UPDATE.value == "update"


class TestLLMProvider:
    """Test LLMProvider enum."""

    def test_enum_values(self):
        """Test enum values."""
        assert LLMProvider.OPENAI.value == "openai"
        assert LLMProvider.ANTHROPIC.value == "anthropic"
