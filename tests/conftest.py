"""Pytest configuration and shared fixtures."""

import pytest
import os
import logging
from unittest.mock import Mock, patch

# Disable logging during tests to reduce noise
logging.disable(logging.CRITICAL)


@pytest.fixture(autouse=True)
def clean_env():
    """Clean environment variables before each test."""
    env_vars_to_clean = [
        "CHECKMK_SERVER_URL",
        "CHECKMK_USERNAME",
        "CHECKMK_PASSWORD",
        "CHECKMK_SITE",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "DEFAULT_FOLDER",
        "LOG_LEVEL",
        "MAX_RETRIES",
        "REQUEST_TIMEOUT",
    ]

    # Store original values
    original_values = {}
    for var in env_vars_to_clean:
        original_values[var] = os.environ.get(var)
        if var in os.environ:
            del os.environ[var]

    yield

    # Restore original values
    for var, value in original_values.items():
        if value is not None:
            os.environ[var] = value
        elif var in os.environ:
            del os.environ[var]


@pytest.fixture
def mock_requests():
    """Mock requests module to prevent actual HTTP calls."""
    with patch("requests.Session") as mock_session:
        mock_instance = Mock()
        mock_session.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def sample_host_data():
    """Sample host data for testing."""
    return {
        "id": "test-host",
        "title": "Test Host",
        "domainType": "host_config",
        "links": [],
        "members": {},
        "extensions": {
            "folder": "/test",
            "attributes": {
                "ipaddress": "192.168.1.100",
                "alias": "Test Host for Unit Tests",
                "tag_criticality": "test",
            },
            "effective_attributes": {
                "ipaddress": "192.168.1.100",
                "alias": "Test Host for Unit Tests",
                "tag_criticality": "test",
                "inherited_attr": "inherited_value",
            },
            "is_cluster": False,
            "is_offline": False,
            "cluster_nodes": [],
        },
    }


@pytest.fixture
def sample_hosts_list():
    """Sample list of hosts for testing."""
    return [
        {
            "id": "web01",
            "extensions": {
                "folder": "/web",
                "attributes": {"ipaddress": "192.168.1.10", "alias": "Web Server 1"},
                "is_cluster": False,
                "is_offline": False,
            },
        },
        {
            "id": "web02",
            "extensions": {
                "folder": "/web",
                "attributes": {"ipaddress": "192.168.1.11", "alias": "Web Server 2"},
                "is_cluster": False,
                "is_offline": True,
            },
        },
        {
            "id": "db01",
            "extensions": {
                "folder": "/database",
                "attributes": {"ipaddress": "192.168.1.20", "alias": "Database Server"},
                "is_cluster": False,
                "is_offline": False,
            },
        },
        {
            "id": "cluster01",
            "extensions": {
                "folder": "/clusters",
                "attributes": {"alias": "Web Cluster"},
                "is_cluster": True,
                "is_offline": False,
                "cluster_nodes": ["web01", "web02"],
            },
        },
    ]


@pytest.fixture
def mock_openai_response():
    """Mock OpenAI API response."""

    def _create_response(operation, parameters, confidence=0.9):
        import json

        mock_response = Mock()
        mock_choice = Mock()
        mock_choice.message.content = json.dumps(
            {"operation": operation, "parameters": parameters, "confidence": confidence}
        )
        mock_response.choices = [mock_choice]
        return mock_response

    return _create_response


@pytest.fixture
def mock_anthropic_response():
    """Mock Anthropic API response."""

    def _create_response(operation, parameters, confidence=0.9):
        import json

        mock_response = Mock()
        mock_content = Mock()
        mock_content.text = json.dumps(
            {"operation": operation, "parameters": parameters, "confidence": confidence}
        )
        mock_response.content = [mock_content]
        return mock_response

    return _create_response


# Test data constants
TEST_CHECKMK_CONFIG = {
    "server_url": "https://test-checkmk.example.com",
    "username": "test_user",
    "password": "test_password",
    "site": "test_site",
    "max_retries": 2,
    "request_timeout": 10,
}

TEST_LLM_CONFIG = {
    "openai_api_key": "test-openai-key",
    "anthropic_api_key": "test-anthropic-key",
    "default_model": "gpt-3.5-turbo",
}

TEST_APP_CONFIG = {"default_folder": "/test", "log_level": "DEBUG"}


# Pytest configuration
def pytest_configure(config):
    """Configure pytest."""
    # Add custom markers
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "slow: mark test as slow running")
    config.addinivalue_line("markers", "api: mark test as requiring API access")


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers automatically."""
    for item in items:
        # Mark integration tests
        if "test_integration" in item.nodeid:
            item.add_marker(pytest.mark.integration)

        # Mark slow tests
        if any(
            keyword in item.nodeid
            for keyword in ["integration", "end_to_end", "complete_workflow"]
        ):
            item.add_marker(pytest.mark.slow)

        # Mark API tests
        if any(keyword in item.nodeid for keyword in ["api", "client", "checkmk"]):
            item.add_marker(pytest.mark.api)
