"""Tests for service status functionality."""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from checkmk_agent.service_status import ServiceStatusManager
from checkmk_agent.api_client import CheckmkClient
from checkmk_agent.config import AppConfig


class TestServiceStatusManager:
    """Test cases for ServiceStatusManager."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_client = Mock(spec=CheckmkClient)
        self.mock_config = Mock(spec=AppConfig)
        self.status_manager = ServiceStatusManager(self.mock_client, self.mock_config)

    def test_service_health_dashboard(self):
        """Test service health dashboard generation."""
        # Mock API responses
        health_summary = {
            "total_services": 100,
            "health_percentage": 85.5,
            "problems": 5,
            "states": {"ok": 95, "warning": 3, "critical": 2, "unknown": 0},
            "acknowledged": 1,
            "in_downtime": 0,
        }

        problem_services = [
            {
                "extensions": {
                    "host_name": "server01",
                    "description": "CPU Load",
                    "state": 2,
                    "acknowledged": 0,
                    "scheduled_downtime_depth": 0,
                    "plugin_output": "CPU load is 95%",
                }
            },
            {
                "extensions": {
                    "host_name": "server02",
                    "description": "Memory",
                    "state": 1,
                    "acknowledged": 0,
                    "scheduled_downtime_depth": 0,
                    "plugin_output": "Memory usage 85%",
                }
            },
        ]

        self.mock_client.get_service_health_summary.return_value = health_summary
        self.mock_client.list_problem_services.return_value = problem_services
        self.mock_client.get_acknowledged_services.return_value = []
        self.mock_client.get_services_in_downtime.return_value = []

        # Test dashboard generation
        dashboard = self.status_manager.get_service_health_dashboard()

        # Verify structure
        assert "overall_health" in dashboard
        assert "problem_analysis" in dashboard
        assert "host_distribution" in dashboard
        assert "urgent_problems" in dashboard
        assert "summary_message" in dashboard

        # Verify health data
        assert dashboard["overall_health"]["total_services"] == 100
        assert dashboard["overall_health"]["health_percentage"] == 85.5
        assert dashboard["overall_health"]["problems"] == 5

        # Verify problem analysis
        problem_analysis = dashboard["problem_analysis"]
        assert len(problem_analysis["critical"]) == 1
        assert len(problem_analysis["warning"]) == 1
        assert problem_analysis["critical"][0]["host_name"] == "server01"
        assert problem_analysis["warning"][0]["host_name"] == "server02"

    def test_analyze_service_problems(self):
        """Test service problem analysis."""
        problem_services = [
            {
                "extensions": {
                    "host_name": "server01",
                    "description": "Disk Space /",
                    "state": 2,
                    "acknowledged": 0,
                    "scheduled_downtime_depth": 0,
                    "plugin_output": "Disk full",
                }
            },
            {
                "extensions": {
                    "host_name": "server02",
                    "description": "Network Interface eth0",
                    "state": 1,
                    "acknowledged": 1,
                    "scheduled_downtime_depth": 0,
                    "plugin_output": "High utilization",
                }
            },
        ]

        self.mock_client.list_problem_services.return_value = problem_services

        # Test analysis
        analysis = self.status_manager.analyze_service_problems()

        # Verify structure
        assert "total_problems" in analysis
        assert "categories" in analysis
        assert "recommendations" in analysis

        # Verify problem count
        assert analysis["total_problems"] == 2
        assert analysis["critical_count"] == 1
        assert analysis["warning_count"] == 1
        assert analysis["unhandled_count"] == 1  # Only server01 is unhandled

        # Verify categories
        categories = analysis["categories"]
        assert "critical_issues" in categories
        assert "warning_issues" in categories
        assert "disk_problems" in categories
        assert "network_problems" in categories

        # Check categorization
        assert "server01/Disk Space /" in categories["disk_problems"]
        assert "server02/Network Interface eth0" in categories["network_problems"]

    def test_get_service_status_details_found(self):
        """Test getting details for an existing service."""
        service_info = {
            "found": True,
            "status": {
                "extensions": {
                    "description": "CPU Load",
                    "state": 1,
                    "acknowledged": 0,
                    "scheduled_downtime_depth": 0,
                    "plugin_output": "CPU load is 75%",
                    "last_check": 1642680000,  # Unix timestamp
                    "current_attempt": 1,
                    "max_check_attempts": 3,
                }
            },
        }

        self.mock_client.get_service_status.return_value = service_info

        # Test service details
        details = self.status_manager.get_service_status_details("server01", "CPU Load")

        # Verify structure
        assert details["found"] is True
        assert details["host_name"] == "server01"
        assert details["service_description"] == "CPU Load"
        assert details["state"] == 1
        assert details["state_name"] == "WARNING"
        assert details["acknowledged"] is False
        assert details["in_downtime"] is False

        # Verify analysis
        analysis = details["analysis"]
        assert analysis["is_problem"] is True
        assert analysis["severity"] == "Warning"
        assert analysis["requires_action"] is True
        assert "last_check_ago" in analysis

    def test_get_service_status_details_not_found(self):
        """Test getting details for a non-existent service."""
        service_info = {
            "found": False,
            "host_name": "server01",
            "service_description": "NonExistent",
        }

        self.mock_client.get_service_status.return_value = service_info

        # Test service details
        details = self.status_manager.get_service_status_details(
            "server01", "NonExistent"
        )

        # Verify not found response
        assert details["found"] is False
        assert "message" in details
        assert "NonExistent" in details["message"]

    def test_generate_status_summary(self):
        """Test status summary generation."""
        health_summary = {
            "total_services": 50,
            "health_percentage": 92.0,
            "problems": 4,
            "states": {"ok": 46, "warning": 3, "critical": 1, "unknown": 0},
            "acknowledged": 2,
            "in_downtime": 0,
        }

        self.mock_client.get_service_health_summary.return_value = health_summary

        # Test summary generation
        summary = self.status_manager.generate_status_summary()

        # Verify structure
        assert "total_services" in summary
        assert "health_percentage" in summary
        assert "problems" in summary
        assert "status_icon" in summary
        assert "status_message" in summary

        # Verify values
        assert summary["total_services"] == 50
        assert summary["health_percentage"] == 92.0
        assert summary["problems"] == 4
        assert summary["status_icon"] == "🔴"  # Has critical (1), so red icon
        assert "4 service problems" in summary["status_message"]

    def test_find_services_by_criteria_state(self):
        """Test finding services by state criteria."""
        critical_services = [
            {
                "extensions": {
                    "host_name": "server01",
                    "description": "Database",
                    "state": 2,
                }
            }
        ]

        self.mock_client.get_services_by_state.return_value = critical_services

        # Test finding critical services
        criteria = {"state": 2}
        services = self.status_manager.find_services_by_criteria(criteria)

        # Verify API call and result
        self.mock_client.get_services_by_state.assert_called_once_with(2, None)
        assert len(services) == 1
        assert services[0]["extensions"]["description"] == "Database"

    def test_find_services_by_criteria_acknowledged(self):
        """Test finding acknowledged services."""
        ack_services = [
            {
                "extensions": {
                    "host_name": "server01",
                    "description": "Web Server",
                    "state": 1,
                    "acknowledged": 1,
                }
            }
        ]

        self.mock_client.get_acknowledged_services.return_value = ack_services

        # Test finding acknowledged services
        criteria = {"acknowledged": True}
        services = self.status_manager.find_services_by_criteria(criteria)

        # Verify API call and result
        self.mock_client.get_acknowledged_services.assert_called_once()
        assert len(services) == 1
        assert services[0]["extensions"]["description"] == "Web Server"

    def test_urgency_score_calculation(self):
        """Test urgency score calculation."""
        # Test critical unacknowledged service
        extensions = {
            "state": 2,
            "acknowledged": 0,
            "scheduled_downtime_depth": 0,
            "current_attempt": 3,
            "max_check_attempts": 3,
        }

        score = self.status_manager._calculate_urgency_score(extensions)

        # Critical (5) + not ack (2) + not downtime (1) + max attempts (2) = 10
        assert score == 10

    def test_urgency_score_calculation_handled(self):
        """Test urgency score for handled service."""
        # Test critical but acknowledged service
        extensions = {
            "state": 2,
            "acknowledged": 1,
            "scheduled_downtime_depth": 0,
            "current_attempt": 1,
            "max_check_attempts": 3,
        }

        score = self.status_manager._calculate_urgency_score(extensions)

        # Critical (5) + ack (0) + not downtime (1) + not max attempts (0) = 6
        assert score == 6

    def test_problem_categorization(self):
        """Test service problem categorization."""
        problem_services = [
            {
                "extensions": {
                    "host_name": "web01",
                    "description": "Disk Space /",
                    "state": 2,
                    "plugin_output": "Filesystem full",
                }
            },
            {
                "extensions": {
                    "host_name": "db01",
                    "description": "Network Interface eth0",
                    "state": 1,
                    "plugin_output": "High traffic",
                }
            },
            {
                "extensions": {
                    "host_name": "app01",
                    "description": "CPU Load",
                    "state": 1,
                    "plugin_output": "High utilization",
                }
            },
        ]

        categories = self.status_manager._categorize_problems(problem_services)

        # Verify categorization
        assert len(categories["critical_issues"]) == 1
        assert len(categories["warning_issues"]) == 2
        assert len(categories["disk_problems"]) == 1
        assert len(categories["network_problems"]) == 1
        assert len(categories["performance_issues"]) == 1

        # Check specific categorizations
        assert "web01/Disk Space /" in categories["disk_problems"]
        assert "db01/Network Interface eth0" in categories["network_problems"]
        assert "app01/CPU Load" in categories["performance_issues"]

    def test_rule_precedence_sorting(self):
        """Test rule precedence sorting - skipped as this method is not yet implemented."""
        # This test is for future rule precedence functionality
        # The _sort_rules_by_precedence method would be used for rule-based service configuration
        pytest.skip("Rule precedence sorting not yet implemented")

    def test_health_message_generation(self):
        """Test health message generation."""
        # Test excellent health
        health_summary = {"health_percentage": 97.5, "problems": 0}
        problem_analysis = {}

        message = self.status_manager._generate_health_message(
            health_summary, problem_analysis
        )
        assert "Excellent health" in message
        assert "97.5%" in message

        # Test moderate issues
        health_summary = {"health_percentage": 82.0, "problems": 12}
        message = self.status_manager._generate_health_message(
            health_summary, problem_analysis
        )
        assert "Moderate issues" in message
        assert "12 service problems" in message

        # Test multiple issues
        health_summary = {"health_percentage": 65.0, "problems": 25}
        message = self.status_manager._generate_health_message(
            health_summary, problem_analysis
        )
        assert "Multiple issues" in message
        assert "25 service problems" in message

    def test_time_formatting(self):
        """Test time delta formatting."""
        from datetime import timedelta

        # Test seconds
        delta = timedelta(seconds=30)
        formatted = self.status_manager._format_time_ago(delta)
        assert formatted == "30s ago"

        # Test minutes
        delta = timedelta(minutes=5, seconds=30)
        formatted = self.status_manager._format_time_ago(delta)
        assert formatted == "5m ago"

        # Test hours
        delta = timedelta(hours=2, minutes=30)
        formatted = self.status_manager._format_time_ago(delta)
        assert formatted == "2h ago"

        # Test days
        delta = timedelta(days=3, hours=12)
        formatted = self.status_manager._format_time_ago(delta)
        assert formatted == "3d ago"


class TestServiceStatusManagerIntegration:
    """Integration tests for ServiceStatusManager."""

    def setup_method(self):
        """Set up integration test fixtures."""
        self.mock_client = Mock(spec=CheckmkClient)
        self.mock_config = Mock(spec=AppConfig)
        self.status_manager = ServiceStatusManager(self.mock_client, self.mock_config)

    def test_full_dashboard_workflow(self):
        """Test complete dashboard generation workflow."""
        # Setup comprehensive mock data
        health_summary = {
            "total_services": 200,
            "health_percentage": 88.5,
            "problems": 23,
            "states": {"ok": 177, "warning": 18, "critical": 5, "unknown": 0},
            "acknowledged": 8,
            "in_downtime": 2,
        }

        problem_services = []
        for i in range(23):
            state = 2 if i < 5 else 1  # 5 critical, 18 warning
            problem_services.append(
                {
                    "extensions": {
                        "host_name": f"server{i:02d}",
                        "description": f"Service {i}",
                        "state": state,
                        "acknowledged": 1 if i < 8 else 0,
                        "scheduled_downtime_depth": 1 if i < 2 else 0,
                        "plugin_output": f"Problem output {i}",
                    }
                }
            )

        ack_services = problem_services[:8]
        downtime_services = problem_services[:2]

        self.mock_client.get_service_health_summary.return_value = health_summary
        self.mock_client.list_problem_services.return_value = problem_services
        self.mock_client.get_acknowledged_services.return_value = ack_services
        self.mock_client.get_services_in_downtime.return_value = downtime_services

        # Test complete dashboard generation
        dashboard = self.status_manager.get_service_health_dashboard()

        # Verify all sections are present
        assert "overall_health" in dashboard
        assert "problem_analysis" in dashboard
        assert "host_distribution" in dashboard
        assert "urgent_problems" in dashboard
        assert "acknowledged_count" in dashboard
        assert "downtime_count" in dashboard
        assert "needs_attention" in dashboard
        assert "summary_message" in dashboard

        # Verify counts
        assert dashboard["acknowledged_count"] == 8
        assert dashboard["downtime_count"] == 2
        assert dashboard["needs_attention"] == 15  # 23 - 8 handled

        # Verify problem analysis structure
        problem_analysis = dashboard["problem_analysis"]
        assert len(problem_analysis["critical"]) == 5
        assert len(problem_analysis["warning"]) == 18

        # Verify host distribution
        host_distribution = dashboard["host_distribution"]
        assert len(host_distribution) == 23  # One host per problem

        # Verify urgent problems (critical + unhandled)
        urgent_problems = dashboard["urgent_problems"]
        assert len(urgent_problems) <= 10  # Limited to top 10

        # All API methods should have been called
        self.mock_client.get_service_health_summary.assert_called_once()
        self.mock_client.list_problem_services.assert_called_once()
        self.mock_client.get_acknowledged_services.assert_called_once()
        self.mock_client.get_services_in_downtime.assert_called_once()


@pytest.fixture
def mock_service_data():
    """Fixture providing mock service data."""
    return {
        "critical_service": {
            "extensions": {
                "host_name": "production-web01",
                "description": "Database Connection",
                "state": 2,
                "acknowledged": 0,
                "scheduled_downtime_depth": 0,
                "plugin_output": "Connection timeout after 30 seconds",
                "last_check": 1642680000,
                "current_attempt": 3,
                "max_check_attempts": 3,
            }
        },
        "warning_service": {
            "extensions": {
                "host_name": "production-app02",
                "description": "Memory Usage",
                "state": 1,
                "acknowledged": 1,
                "scheduled_downtime_depth": 0,
                "plugin_output": "Memory usage at 85% - close to threshold",
                "last_check": 1642679940,
                "current_attempt": 1,
                "max_check_attempts": 3,
            }
        },
        "ok_service": {
            "extensions": {
                "host_name": "production-db01",
                "description": "CPU Load",
                "state": 0,
                "acknowledged": 0,
                "scheduled_downtime_depth": 0,
                "plugin_output": "CPU load: 15% - all normal",
                "last_check": 1642679970,
                "current_attempt": 1,
                "max_check_attempts": 3,
            }
        },
    }
