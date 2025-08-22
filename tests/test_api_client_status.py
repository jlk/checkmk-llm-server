"""Tests for API client service status methods."""

import pytest
from unittest.mock import Mock, patch
import json

from checkmk_mcp_server.api_client import CheckmkClient, CheckmkAPIError
from checkmk_mcp_server.config import CheckmkConfig


class TestCheckMkClientStatusMethods:
    """Test cases for CheckmkClient service status methods."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_config = Mock(spec=CheckmkConfig)
        self.mock_config.server_url = "http://test-checkmk.local"
        self.mock_config.site = "test"
        self.mock_config.username = "test_user"
        self.mock_config.password = "test_password"
        self.mock_config.request_timeout = 30

        self.client = CheckmkClient(self.mock_config)

    def test_livestatus_query_builder(self):
        """Test Livestatus query building methods."""
        # Test simple query
        query = self.client._build_livestatus_query("=", "state", "2")
        expected = {"op": "=", "left": "state", "right": "2"}
        assert query == expected

        # Test combined query with single expression
        expressions = [{"op": "=", "left": "state", "right": "2"}]
        combined = self.client._build_combined_query(expressions)
        assert combined == expressions[0]

        # Test combined query with multiple expressions
        expressions = [
            {"op": "=", "left": "state", "right": "2"},
            {"op": "=", "left": "host_name", "right": "server01"},
        ]
        combined = self.client._build_combined_query(expressions)
        expected = {"op": "and", "expr": expressions}
        assert combined == expected

        # Test combined query with OR operator
        combined = self.client._build_combined_query(expressions, "or")
        expected = {"op": "or", "expr": expressions}
        assert combined == expected

    @patch("checkmk_mcp_server.api_client.CheckmkClient._make_request")
    def test_get_service_status_specific_service_found(self, mock_request):
        """Test getting status for a specific service that exists."""
        mock_response = {
            "value": [
                {
                    "extensions": {
                        "host_name": "server01",
                        "description": "CPU Load",
                        "state": 1,
                        "plugin_output": "Load average: 3.5",
                        "last_check": 1642680000,
                    }
                }
            ]
        }
        mock_request.return_value = mock_response

        result = self.client.get_service_status("server01", "CPU Load")

        # Verify API call
        mock_request.assert_called_once_with(
            "GET",
            "/objects/host/server01/collections/services",
            params={"columns": self.client.STATUS_COLUMNS},
        )

        # Verify result structure
        assert result["host_name"] == "server01"
        assert result["service_description"] == "CPU Load"
        assert result["found"] is True
        assert "status" in result
        assert result["status"]["extensions"]["description"] == "CPU Load"

    @patch("checkmk_mcp_server.api_client.CheckmkClient._make_request")
    def test_get_service_status_specific_service_not_found(self, mock_request):
        """Test getting status for a specific service that doesn't exist."""
        mock_response = {"value": []}
        mock_request.return_value = mock_response

        result = self.client.get_service_status("server01", "NonExistent")

        # Verify result structure for not found
        assert result["host_name"] == "server01"
        assert result["service_description"] == "NonExistent"
        assert result["found"] is False
        assert result["status"] is None

    @patch("checkmk_mcp_server.api_client.CheckmkClient.list_host_services")
    def test_get_service_status_all_services(self, mock_list_services):
        """Test getting status for all services on a host."""
        mock_services = [
            {"extensions": {"description": "CPU Load", "state": 0}},
            {"extensions": {"description": "Memory", "state": 1}},
            {"extensions": {"description": "Disk Space", "state": 2}},
        ]
        mock_list_services.return_value = mock_services

        result = self.client.get_service_status("server01")

        # Verify API call
        mock_list_services.assert_called_once_with(
            host_name="server01", columns=self.client.STATUS_COLUMNS
        )

        # Verify result structure
        assert result["host_name"] == "server01"
        assert result["services"] == mock_services
        assert result["service_count"] == 3

    @patch("checkmk_mcp_server.api_client.CheckmkClient._make_request")
    def test_list_problem_services_no_filter(self, mock_request):
        """Test listing problem services without host filter."""
        mock_response = {
            "value": [
                {
                    "extensions": {
                        "host_name": "server01",
                        "description": "Database",
                        "state": 2,
                    }
                },
                {
                    "extensions": {
                        "host_name": "server02",
                        "description": "Web Server",
                        "state": 1,
                    }
                },
            ]
        }
        mock_request.return_value = mock_response

        result = self.client.list_problem_services()

        # Verify API call - updated for Checkmk 2.4 POST with JSON format
        mock_request.assert_called_once_with(
            "POST",
            "/domain-types/service/collections/all",
            json={
                "columns": [
                    "host_name",
                    "description",
                    "state",
                    "acknowledged",
                    "scheduled_downtime_depth",
                ]
            },
        )

        # Verify result
        assert len(result) == 2
        assert result[0]["extensions"]["state"] == 2
        assert result[1]["extensions"]["state"] == 1

    @patch("checkmk_mcp_server.api_client.CheckmkClient._make_request")
    def test_list_problem_services_with_host_filter(self, mock_request):
        """Test listing problem services with host filter."""
        mock_response = {"value": []}
        mock_request.return_value = mock_response

        self.client.list_problem_services("server01")

        # Verify API call - updated for Checkmk 2.4 POST with JSON format
        mock_request.assert_called_once_with(
            "POST",
            "/objects/host/server01/collections/services",
            json={
                "columns": [
                    "host_name",
                    "description",
                    "state",
                    "acknowledged",
                    "scheduled_downtime_depth",
                ],
                "host_name": "server01",
            },
        )

    @patch("checkmk_mcp_server.api_client.CheckmkClient._make_request")
    def test_get_service_health_summary(self, mock_request):
        """Test getting service health summary."""
        mock_response = {
            "value": [
                {
                    "extensions": {
                        "state": 0,
                        "acknowledged": 0,
                        "scheduled_downtime_depth": 0,
                    }
                },
                {
                    "extensions": {
                        "state": 0,
                        "acknowledged": 0,
                        "scheduled_downtime_depth": 0,
                    }
                },
                {
                    "extensions": {
                        "state": 1,
                        "acknowledged": 0,
                        "scheduled_downtime_depth": 0,
                    }
                },
                {
                    "extensions": {
                        "state": 2,
                        "acknowledged": 1,
                        "scheduled_downtime_depth": 0,
                    }
                },
                {
                    "extensions": {
                        "state": 3,
                        "acknowledged": 0,
                        "scheduled_downtime_depth": 1,
                    }
                },
            ]
        }
        mock_request.return_value = mock_response

        result = self.client.get_service_health_summary()

        # Verify API call - updated for Checkmk 2.4 POST with JSON format
        expected_columns = [
            "host_name",
            "description",
            "state",
            "acknowledged",
            "scheduled_downtime_depth",
        ]
        mock_request.assert_called_once_with(
            "POST",
            "/domain-types/service/collections/all",
            json={"columns": expected_columns},
        )

        # Verify summary calculations
        assert result["total_services"] == 5
        assert result["states"]["ok"] == 2
        assert result["states"]["warning"] == 1
        assert result["states"]["critical"] == 1
        assert result["states"]["unknown"] == 1
        assert result["acknowledged"] == 1
        assert result["in_downtime"] == 1
        assert result["problems"] == 3  # warning + critical + unknown
        assert result["health_percentage"] == 40.0  # 2/5 * 100

    @patch("checkmk_mcp_server.api_client.CheckmkClient._make_request")
    def test_get_service_health_summary_empty(self, mock_request):
        """Test getting service health summary with no services."""
        mock_response = {"value": []}
        mock_request.return_value = mock_response

        result = self.client.get_service_health_summary()

        # Verify empty result
        assert result["total_services"] == 0
        assert result["health_percentage"] == 100.0  # Default when no services
        assert result["problems"] == 0

    @patch("checkmk_mcp_server.api_client.CheckmkClient._make_request")
    def test_get_services_by_state(self, mock_request):
        """Test getting services by specific state."""
        mock_response = {
            "value": [
                {
                    "extensions": {
                        "host_name": "server01",
                        "description": "Critical Service",
                        "state": 2,
                    }
                }
            ]
        }
        mock_request.return_value = mock_response

        result = self.client.get_services_by_state(2)

        # Verify API call - updated for simplified fallback approach
        mock_request.assert_called_once_with(
            "POST",
            "/domain-types/service/collections/all",
            json={
                "columns": [
                    "host_name",
                    "description",
                    "state",
                    "acknowledged",
                    "scheduled_downtime_depth",
                ]
            },
        )

        # Verify result
        assert len(result) == 1
        assert result[0]["extensions"]["state"] == 2

    @patch("checkmk_mcp_server.api_client.CheckmkClient._make_request")
    def test_get_services_by_state_with_host_filter(self, mock_request):
        """Test getting services by state with host filter."""
        mock_response = {"value": []}
        mock_request.return_value = mock_response

        self.client.get_services_by_state(1, "server01")

        # Verify API call - updated for Checkmk 2.4 POST with JSON format
        mock_request.assert_called_once_with(
            "POST",
            "/objects/host/server01/collections/services",
            json={
                "columns": [
                    "host_name",
                    "description",
                    "state",
                    "acknowledged",
                    "scheduled_downtime_depth",
                ],
                "host_name": "server01",
            },
        )

    @patch("checkmk_mcp_server.api_client.CheckmkClient._make_request")
    def test_get_acknowledged_services(self, mock_request):
        """Test getting acknowledged services."""
        mock_response = {
            "value": [
                {
                    "extensions": {
                        "host_name": "server01",
                        "description": "Acknowledged Service",
                        "acknowledged": 1,
                    }
                }
            ]
        }
        mock_request.return_value = mock_response

        result = self.client.get_acknowledged_services()

        # Verify API call - updated for simplified fallback approach
        mock_request.assert_called_once_with(
            "POST",
            "/domain-types/service/collections/all",
            json={
                "columns": [
                    "host_name",
                    "description",
                    "state",
                    "acknowledged",
                    "scheduled_downtime_depth",
                ]
            },
        )

        # Verify result
        assert len(result) == 1
        assert result[0]["extensions"]["acknowledged"] == 1

    @patch("checkmk_mcp_server.api_client.CheckmkClient._make_request")
    def test_get_services_in_downtime(self, mock_request):
        """Test getting services in downtime."""
        mock_response = {
            "value": [
                {
                    "extensions": {
                        "host_name": "server01",
                        "description": "Downtime Service",
                        "scheduled_downtime_depth": 1,
                    }
                }
            ]
        }
        mock_request.return_value = mock_response

        result = self.client.get_services_in_downtime()

        # Verify API call - updated for simplified fallback approach
        mock_request.assert_called_once_with(
            "POST",
            "/domain-types/service/collections/all",
            json={
                "columns": [
                    "host_name",
                    "description",
                    "state",
                    "acknowledged",
                    "scheduled_downtime_depth",
                ]
            },
        )

        # Verify result
        assert len(result) == 1
        assert result[0]["extensions"]["scheduled_downtime_depth"] == 1

    @patch("checkmk_mcp_server.api_client.CheckmkClient._make_request")
    def test_status_columns_constant(self, mock_request):
        """Test that STATUS_COLUMNS constant contains expected columns."""
        expected_columns = [
            "host_name",
            "description",
            "state",
            "state_type",
            "acknowledged",
            "plugin_output",
            "last_check",
            "scheduled_downtime_depth",
            "perf_data",
            "check_interval",
            "current_attempt",
            "max_check_attempts",
            "notifications_enabled",
        ]

        assert self.client.STATUS_COLUMNS == expected_columns

    @patch("checkmk_mcp_server.api_client.CheckmkClient._make_request")
    def test_api_error_handling(self, mock_request):
        """Test error handling in status methods."""
        mock_request.side_effect = CheckmkAPIError("API Error", 500)

        # Test that CheckmkAPIError is properly raised
        with pytest.raises(CheckmkAPIError):
            self.client.get_service_health_summary()

        with pytest.raises(CheckmkAPIError):
            self.client.list_problem_services()

        with pytest.raises(CheckmkAPIError):
            self.client.get_services_by_state(2)

        with pytest.raises(CheckmkAPIError):
            self.client.get_acknowledged_services()

        with pytest.raises(CheckmkAPIError):
            self.client.get_services_in_downtime()

    def test_service_status_integration_workflow(self):
        """Test integration workflow using multiple status methods."""
        with patch.object(self.client, "_make_request") as mock_request:
            # Setup mock responses for workflow
            health_response = {
                "value": [
                    {
                        "extensions": {
                            "state": 0,
                            "acknowledged": 0,
                            "scheduled_downtime_depth": 0,
                        }
                    },
                    {
                        "extensions": {
                            "state": 2,
                            "acknowledged": 0,
                            "scheduled_downtime_depth": 0,
                        }
                    },
                    {
                        "extensions": {
                            "state": 1,
                            "acknowledged": 1,
                            "scheduled_downtime_depth": 0,
                        }
                    },
                ]
            }

            problems_response = {
                "value": [
                    {
                        "extensions": {
                            "host_name": "server01",
                            "description": "Critical Service",
                            "state": 2,
                        }
                    },
                    {
                        "extensions": {
                            "host_name": "server02",
                            "description": "Warning Service",
                            "state": 1,
                        }
                    },
                ]
            }

            critical_response = {
                "value": [
                    {
                        "extensions": {
                            "host_name": "server01",
                            "description": "Critical Service",
                            "state": 2,
                        }
                    }
                ]
            }

            ack_response = {
                "value": [
                    {
                        "extensions": {
                            "host_name": "server02",
                            "description": "Warning Service",
                            "acknowledged": 1,
                        }
                    }
                ]
            }

            # Set up mock to return different responses for different calls
            mock_request.side_effect = [
                health_response,
                problems_response,
                critical_response,
                ack_response,
            ]

            # Execute workflow
            health = self.client.get_service_health_summary()
            problems = self.client.list_problem_services()
            critical = self.client.get_services_by_state(2)
            acknowledged = self.client.get_acknowledged_services()

            # Verify workflow results
            assert health["total_services"] == 3
            assert health["problems"] == 2
            assert len(problems) == 2
            assert len(critical) == 1
            assert len(acknowledged) == 1

            # Verify all API calls were made
            assert mock_request.call_count == 4


class TestCheckMkClientStatusIntegration:
    """Integration tests for status methods."""

    def setup_method(self):
        """Set up integration test fixtures."""
        self.mock_config = Mock(spec=CheckmkConfig)
        self.mock_config.server_url = "http://test-checkmk.local"
        self.mock_config.site = "test"
        self.mock_config.username = "test_user"
        self.mock_config.password = "test_password"
        self.mock_config.request_timeout = 30

        self.client = CheckmkClient(self.mock_config)

    @patch("checkmk_mcp_server.api_client.CheckmkClient._make_request")
    def test_complete_status_monitoring_scenario(self, mock_request):
        """Test complete status monitoring scenario."""
        # Simulate a realistic Checkmk environment response
        services_data = []

        # Generate 100 services across 10 hosts
        for host_num in range(1, 11):
            host_name = f"server{host_num:02d}"
            for svc_num in range(1, 11):
                # Simulate realistic service distribution
                if svc_num <= 8:
                    state = 0  # 80% OK
                elif svc_num == 9:
                    state = 1  # 10% WARNING
                else:
                    state = 2  # 10% CRITICAL

                # Some services are acknowledged or in downtime
                acknowledged = 1 if (host_num + svc_num) % 7 == 0 else 0
                downtime_depth = 1 if (host_num + svc_num) % 13 == 0 else 0

                services_data.append(
                    {
                        "extensions": {
                            "host_name": host_name,
                            "description": f"Service {svc_num}",
                            "state": state,
                            "acknowledged": acknowledged,
                            "scheduled_downtime_depth": downtime_depth,
                            "plugin_output": f"Service {svc_num} output",
                            "last_check": 1642680000 + (host_num * 60) + svc_num,
                        }
                    }
                )

        mock_request.return_value = {"value": services_data}

        # Test health summary
        health = self.client.get_service_health_summary()

        # Verify realistic calculations
        assert health["total_services"] == 100
        assert health["states"]["ok"] == 80
        assert health["states"]["warning"] == 10
        assert health["states"]["critical"] == 10
        assert health["problems"] == 20
        assert health["health_percentage"] == 80.0

        # Test problem services (should return only non-OK services)
        mock_request.return_value = {
            "value": [s for s in services_data if s["extensions"]["state"] != 0]
        }
        problems = self.client.list_problem_services()
        assert len(problems) == 20

        # Test critical services only
        mock_request.return_value = {
            "value": [s for s in services_data if s["extensions"]["state"] == 2]
        }
        critical = self.client.get_services_by_state(2)
        assert len(critical) == 10

        # Test acknowledged services
        mock_request.return_value = {
            "value": [s for s in services_data if s["extensions"]["acknowledged"] == 1]
        }
        acknowledged = self.client.get_acknowledged_services()
        ack_count = len(
            [s for s in services_data if s["extensions"]["acknowledged"] == 1]
        )
        assert len(acknowledged) == ack_count

        # Test services in downtime
        mock_request.return_value = {
            "value": [
                s
                for s in services_data
                if s["extensions"]["scheduled_downtime_depth"] > 0
            ]
        }
        downtime = self.client.get_services_in_downtime()
        downtime_count = len(
            [
                s
                for s in services_data
                if s["extensions"]["scheduled_downtime_depth"] > 0
            ]
        )
        assert len(downtime) == downtime_count
