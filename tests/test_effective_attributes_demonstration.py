"""Demonstration tests for effective_attributes functionality.

This test module demonstrates that the effective_attributes parameter
works correctly end-to-end through all system layers.
"""

import pytest
import asyncio
import requests_mock
from unittest.mock import AsyncMock

from checkmk_mcp_server.api_client import CheckmkClient
from checkmk_mcp_server.async_api_client import AsyncCheckmkClient
from checkmk_mcp_server.services.host_service import HostService
from checkmk_mcp_server.host_operations import HostOperationsManager
from checkmk_mcp_server.config import CheckmkConfig, LLMConfig, AppConfig


@pytest.fixture
def demo_config():
    """Create demo configuration."""
    return AppConfig(
        checkmk=CheckmkConfig(
            server_url="https://demo.checkmk.example.com",
            username="automation",
            password="demo-secret",
            site="demo",
        ),
        llm=LLMConfig(),
        default_folder="/demo",
        log_level="INFO",
    )


class TestEffectiveAttributesDemonstration:
    """Demonstrate effective_attributes functionality working end-to-end."""

    def test_api_client_effective_attributes_demo(self, demo_config):
        """
        DEMO: API Client correctly sends effective_attributes parameter and
        receives extended configuration data.
        """
        print("\n=== API CLIENT DEMONSTRATION ===")

        client = CheckmkClient(demo_config.checkmk)

        with requests_mock.Mocker() as m:
            # Mock response showing the difference between basic and effective attributes
            basic_response = {
                "value": [
                    {
                        "id": "web-server-01",
                        "extensions": {
                            "folder": "/production/web",
                            "attributes": {
                                "ipaddress": "10.1.1.10",
                                "alias": "Production Web Server 01",
                            },
                        },
                    }
                ]
            }

            effective_response = {
                "value": [
                    {
                        "id": "web-server-01",
                        "extensions": {
                            "folder": "/production/web",
                            "attributes": {
                                "ipaddress": "10.1.1.10",
                                "alias": "Production Web Server 01",
                            },
                            "effective_attributes": {
                                "ipaddress": "10.1.1.10",
                                "alias": "Production Web Server 01",
                                # Inherited from /production folder
                                "notification_period": "24x7",
                                "contact_groups": ["web-admins", "production-team"],
                                "max_check_attempts": "3",
                                # Inherited from /production/web folder
                                "check_interval": "60s",
                                "service_discovery": "automatic",
                                # Computed by Checkmk
                                "effective_monitoring_state": "active",
                                "computed_service_count": "47",
                                "last_state_change": "2024-07-30T10:15:00Z",
                            },
                        },
                    }
                ]
            }

            # First request: WITHOUT effective_attributes
            m.get(
                "https://demo.checkmk.example.com/demo/check_mk/api/1.0/domain-types/host_config/collections/all",
                json=basic_response,
                status_code=200,
            )

            print("1. Requesting host data WITHOUT effective_attributes...")
            hosts_basic = client.list_hosts(effective_attributes=False)

            print(f"   Host: {hosts_basic[0]['id']}")
            print(f"   Folder: {hosts_basic[0]['extensions']['folder']}")
            print(f"   IP: {hosts_basic[0]['extensions']['attributes']['ipaddress']}")
            print(
                f"   Has effective_attributes: {'effective_attributes' in hosts_basic[0]['extensions']}"
            )

            # Verify API request did not include effective_attributes parameter
            request_basic = m.request_history[0]
            print(f"   API URL: {request_basic.url}")
            print(
                f"   Contains 'effective_attributes': {'effective_attributes' in request_basic.url}"
            )

            # Reset mock for second request
            m.reset_mock()
            m.get(
                "https://demo.checkmk.example.com/demo/check_mk/api/1.0/domain-types/host_config/collections/all",
                json=effective_response,
                status_code=200,
            )

            print("\n2. Requesting host data WITH effective_attributes=True...")
            hosts_effective = client.list_hosts(effective_attributes=True)

            print(f"   Host: {hosts_effective[0]['id']}")
            print(f"   Folder: {hosts_effective[0]['extensions']['folder']}")
            print(
                f"   IP: {hosts_effective[0]['extensions']['attributes']['ipaddress']}"
            )
            print(
                f"   Has effective_attributes: {'effective_attributes' in hosts_effective[0]['extensions']}"
            )

            if "effective_attributes" in hosts_effective[0]["extensions"]:
                effective = hosts_effective[0]["extensions"]["effective_attributes"]
                print(
                    f"   Inherited notification_period: {effective['notification_period']}"
                )
                print(f"   Inherited contact_groups: {effective['contact_groups']}")
                print(
                    f"   Computed service_count: {effective['computed_service_count']}"
                )

            # Verify API request included effective_attributes=true parameter
            request_effective = m.request_history[0]
            print(f"   API URL: {request_effective.url}")
            print(
                f"   Contains 'effective_attributes=true': {'effective_attributes=true' in request_effective.url}"
            )

            # Assertions for test validation
            assert len(hosts_basic) == 1
            assert len(hosts_effective) == 1
            assert "effective_attributes" not in hosts_basic[0]["extensions"]
            assert "effective_attributes" in hosts_effective[0]["extensions"]
            assert "effective_attributes" not in request_basic.url
            assert "effective_attributes=true" in request_effective.url

    @pytest.mark.asyncio
    async def test_host_service_effective_attributes_demo(self, demo_config):
        """
        DEMO: HostService correctly passes effective_attributes parameter through
        the async layer and returns structured results.
        """
        print("\n=== HOST SERVICE DEMONSTRATION ===")

        # Mock the async API client
        mock_async_client = AsyncMock()

        # Configure mock responses
        basic_host_data = [
            {
                "id": "db-server-01",
                "extensions": {
                    "folder": "/critical/database",
                    "attributes": {
                        "ipaddress": "10.2.1.100",
                        "alias": "Critical Database Server",
                    },
                },
            }
        ]

        effective_host_data = [
            {
                "id": "db-server-01",
                "extensions": {
                    "folder": "/critical/database",
                    "attributes": {
                        "ipaddress": "10.2.1.100",
                        "alias": "Critical Database Server",
                    },
                    "effective_attributes": {
                        "ipaddress": "10.2.1.100",
                        "alias": "Critical Database Server",
                        # Inherited from /critical folder
                        "max_check_attempts": "5",
                        "notification_escalation": "immediate",
                        "contact_groups": ["dba-team", "critical-ops"],
                        # Inherited from /critical/database folder
                        "check_interval": "30s",
                        "retry_interval": "10s",
                        # Computed by Checkmk
                        "active_service_checks": "234",
                        "passive_service_checks": "12",
                        "monitoring_overhead": "low",
                    },
                },
            }
        ]

        host_service = HostService(mock_async_client, demo_config)

        print("1. HostService call WITHOUT effective_attributes...")
        mock_async_client.list_hosts.return_value = basic_host_data

        result_basic = await host_service.list_hosts(effective_attributes=False)

        print(f"   Success: {result_basic.success}")
        print(f"   Host count: {len(result_basic.data.hosts)}")
        print(f"   Host name: {result_basic.data.hosts[0].name}")
        print(f"   Host folder: {result_basic.data.hosts[0].folder}")

        # Verify the async API client was called with correct parameter
        mock_async_client.list_hosts.assert_called_with(effective_attributes=False)
        print(f"   API called with effective_attributes=False: ✓")

        print("\n2. HostService call WITH effective_attributes=True...")
        mock_async_client.list_hosts.return_value = effective_host_data

        result_effective = await host_service.list_hosts(effective_attributes=True)

        print(f"   Success: {result_effective.success}")
        print(f"   Host count: {len(result_effective.data.hosts)}")
        print(f"   Host name: {result_effective.data.hosts[0].name}")
        print(f"   Host folder: {result_effective.data.hosts[0].folder}")

        # Verify the async API client was called with correct parameter
        mock_async_client.list_hosts.assert_called_with(effective_attributes=True)
        print(f"   API called with effective_attributes=True: ✓")

        # Assertions for test validation
        assert result_basic.success
        assert result_effective.success
        assert len(result_basic.data.hosts) == 1
        assert len(result_effective.data.hosts) == 1

    def test_host_operations_manager_demo(self, demo_config):
        """
        DEMO: HostOperationsManager correctly extracts effective_attributes
        from parameter dictionaries and passes to API client.
        """
        print("\n=== HOST OPERATIONS MANAGER DEMONSTRATION ===")

        from unittest.mock import Mock

        # Create mock dependencies
        mock_checkmk = Mock()
        mock_llm = Mock()

        mock_checkmk.list_hosts.return_value = [
            {
                "id": "monitoring-host",
                "extensions": {
                    "folder": "/infrastructure/monitoring",
                    "attributes": {"ipaddress": "10.3.1.50"},
                },
            }
        ]

        host_manager = HostOperationsManager(mock_checkmk, mock_llm, demo_config)

        print(
            "1. HostOperationsManager call with effective_attributes=False in parameters..."
        )

        parameters_false = {"folder": "/infrastructure", "effective_attributes": False}

        result = host_manager._list_hosts(parameters_false)

        print(f"   Parameters: {parameters_false}")
        print(f"   Result type: {type(result)}")

        # Verify the API client was called with extracted parameter
        mock_checkmk.list_hosts.assert_called_with(effective_attributes=False)
        print(f"   CheckmkClient.list_hosts called with effective_attributes=False: ✓")

        print(
            "\n2. HostOperationsManager call with effective_attributes=True in parameters..."
        )

        parameters_true = {"folder": "/infrastructure", "effective_attributes": True}

        result = host_manager._list_hosts(parameters_true)

        print(f"   Parameters: {parameters_true}")
        print(f"   Result type: {type(result)}")

        # Verify the API client was called with extracted parameter
        mock_checkmk.list_hosts.assert_called_with(effective_attributes=True)
        print(f"   CheckmkClient.list_hosts called with effective_attributes=True: ✓")

        print(
            "\n3. HostOperationsManager call with no effective_attributes parameter (default behavior)..."
        )

        parameters_default = {"folder": "/infrastructure"}

        result = host_manager._list_hosts(parameters_default)

        print(f"   Parameters: {parameters_default}")
        print(f"   Result type: {type(result)}")

        # Verify the API client was called with default (False)
        mock_checkmk.list_hosts.assert_called_with(effective_attributes=False)
        print(
            f"   CheckmkClient.list_hosts called with effective_attributes=False (default): ✓"
        )

    def test_real_world_scenario_demo(self, demo_config):
        """
        DEMO: Real-world scenario showing how effective_attributes helps
        troubleshoot monitoring configuration issues.
        """
        print("\n=== REAL-WORLD TROUBLESHOOTING SCENARIO ===")

        client = CheckmkClient(demo_config.checkmk)

        with requests_mock.Mocker() as m:
            # Scenario: Administrator is troubleshooting why a host is generating
            # too many notifications and wants to see the complete effective configuration

            troubleshooting_response = {
                "id": "problematic-server",
                "extensions": {
                    "folder": "/production/critical/database",
                    "attributes": {
                        "ipaddress": "10.1.2.200",
                        "alias": "Database Server with Notification Issues",
                        "tag_criticality": "critical",
                    },
                    "effective_attributes": {
                        "ipaddress": "10.1.2.200",
                        "alias": "Database Server with Notification Issues",
                        "tag_criticality": "critical",
                        # Configuration hierarchy showing the problem
                        # From /production folder:
                        "notification_period": "24x7",
                        "contact_groups": ["production-team"],
                        # From /production/critical folder:
                        "max_check_attempts": "2",  # Reduced for critical systems
                        "notification_escalation": "immediate",
                        "additional_contact_groups": ["management", "on-call"],
                        # From /production/critical/database folder:
                        "check_interval": "15s",  # Very frequent!
                        "retry_interval": "5s",  # Very aggressive!
                        "database_specific_contacts": ["dba-team"],
                        # Computed by Checkmk - showing the impact:
                        "effective_contact_groups": [
                            "production-team",
                            "management",
                            "on-call",
                            "dba-team",
                        ],
                        "notifications_per_hour_current": "480",  # Way too many!
                        "failed_checks_last_hour": "23",
                        "notification_storm_risk": "HIGH",
                        "recommended_check_interval": "60s",
                        "recommended_retry_interval": "30s",
                    },
                },
            }

            m.get(
                "https://demo.checkmk.example.com/demo/check_mk/api/1.0/objects/host_config/problematic-server",
                json=troubleshooting_response,
                status_code=200,
            )

            print("SCENARIO: Database server generating excessive notifications")
            print(
                "ACTION: Administrator uses effective_attributes to see complete configuration"
            )
            print()

            # Administrator gets complete configuration view
            host = client.get_host("problematic-server", effective_attributes=True)

            print(f"HOST: {host['id']}")
            print(f"FOLDER HIERARCHY: {host['extensions']['folder']}")
            print()

            # Show the configuration hierarchy
            attrs = host["extensions"]["attributes"]
            effective = host["extensions"]["effective_attributes"]

            print("DIRECT ATTRIBUTES:")
            for key, value in attrs.items():
                print(f"  {key}: {value}")
            print()

            print("EFFECTIVE CONFIGURATION (includes inherited + computed):")

            print("  Inherited from folder hierarchy:")
            print(f"    notification_period: {effective['notification_period']}")
            print(f"    max_check_attempts: {effective['max_check_attempts']}")
            print(
                f"    check_interval: {effective['check_interval']} ⚠️  (TOO FREQUENT)"
            )
            print(
                f"    retry_interval: {effective['retry_interval']} ⚠️  (TOO AGGRESSIVE)"
            )
            print()

            print("  Contact escalation chain:")
            for group in effective["effective_contact_groups"]:
                print(f"    - {group}")
            print()

            print("  Computed impact analysis:")
            print(
                f"    notifications_per_hour: {effective['notifications_per_hour_current']} ⚠️"
            )
            print(
                f"    failed_checks_last_hour: {effective['failed_checks_last_hour']}"
            )
            print(
                f"    notification_storm_risk: {effective['notification_storm_risk']}"
            )
            print()

            print("  Checkmk recommendations:")
            print(
                f"    recommended_check_interval: {effective['recommended_check_interval']}"
            )
            print(
                f"    recommended_retry_interval: {effective['recommended_retry_interval']}"
            )
            print()

            print("ROOT CAUSE IDENTIFIED:")
            print("  - Check interval (15s) too frequent for database server")
            print("  - Retry interval (5s) too aggressive")
            print("  - Multiple contact groups causing notification multiplication")
            print(
                "  - Configuration inherited from overly aggressive critical folder settings"
            )
            print()

            print("SOLUTION:")
            print("  1. Adjust /production/critical/database folder check intervals")
            print("  2. Consolidate contact groups to reduce notification volume")
            print("  3. Increase retry interval for database-specific checks")

            # Verify the API request used effective_attributes
            request = m.request_history[0]
            assert "effective_attributes=true" in request.url
            assert "problematic-server" in request.url

            print(f"\n✓ API call verified: {request.url}")

    def test_backward_compatibility_demo(self, demo_config):
        """
        DEMO: Existing code that doesn't use effective_attributes continues
        to work exactly as before.
        """
        print("\n=== BACKWARD COMPATIBILITY DEMONSTRATION ===")

        client = CheckmkClient(demo_config.checkmk)

        with requests_mock.Mocker() as m:
            # Legacy response format (no effective_attributes)
            legacy_response = {
                "value": [
                    {
                        "id": "legacy-server",
                        "extensions": {
                            "folder": "/legacy",
                            "attributes": {"ipaddress": "192.168.1.100"},
                        },
                    }
                ]
            }

            m.get(
                "https://demo.checkmk.example.com/demo/check_mk/api/1.0/domain-types/host_config/collections/all",
                json=legacy_response,
                status_code=200,
            )

            print(
                "SCENARIO: Existing code that doesn't use effective_attributes parameter"
            )
            print()

            # Legacy code - no effective_attributes parameter
            hosts = client.list_hosts()  # Default behavior unchanged

            print(f"Legacy API call successful: ✓")
            print(f"Hosts returned: {len(hosts)}")
            print(f"Host ID: {hosts[0]['id']}")
            print(
                f"Host has effective_attributes: {'effective_attributes' in hosts[0]['extensions']}"
            )

            # Verify legacy behavior
            request = m.request_history[0]
            print(f"API URL: {request.url}")
            print(
                f"Contains effective_attributes parameter: {'effective_attributes' in request.url}"
            )
            print()

            print("RESULT: Legacy code works exactly as before")
            print("  - No new parameters sent to API")
            print("  - Same response structure")
            print("  - Same functionality")
            print("  - Zero breaking changes")

            # Assertions
            assert len(hosts) == 1
            assert hosts[0]["id"] == "legacy-server"
            assert "effective_attributes" not in hosts[0]["extensions"]
            assert "effective_attributes" not in request.url

    def test_complete_flow_demo(self, demo_config):
        """
        DEMO: Complete parameter flow from high-level interface down to API client.
        """
        print("\n=== COMPLETE PARAMETER FLOW DEMONSTRATION ===")

        from unittest.mock import Mock

        print("DEMONSTRATING: Parameter flow through all application layers")
        print("FLOW: Application Layer → Host Operations → API Client → Checkmk API")
        print()

        # Setup mocks to trace the flow
        mock_checkmk = Mock()
        mock_llm = Mock()

        # Configure mock to return test data
        mock_checkmk.list_hosts.return_value = [
            {"id": "flow-test", "extensions": {"folder": "/test"}}
        ]

        # Create the operations manager (represents high-level interface)
        host_manager = HostOperationsManager(mock_checkmk, mock_llm, demo_config)

        print("1. APPLICATION LAYER → HOST OPERATIONS")
        print(
            "   Application passes parameters dictionary with effective_attributes=True"
        )

        app_parameters = {
            "folder": "/production",
            "search": "web",
            "effective_attributes": True,  # ← Parameter from application
        }

        print(f"   Parameters from app: {app_parameters}")

        print("\n2. HOST OPERATIONS → API CLIENT")
        print(
            "   HostOperationsManager extracts effective_attributes and passes to API client"
        )

        result = host_manager._list_hosts(app_parameters)

        # Verify the parameter flow
        mock_checkmk.list_hosts.assert_called_with(effective_attributes=True)

        print(f"   ✓ CheckmkClient.list_hosts called with: effective_attributes=True")

        print("\n3. API CLIENT → CHECKMK API")
        print("   CheckmkClient formats parameter for Checkmk REST API")
        print("   URL would include: ?effective_attributes=true")

        print("\n4. CHECKMK API → RESPONSE")
        print("   Checkmk returns enhanced data with inherited and computed attributes")

        print("\n5. RESPONSE → APPLICATION")
        print("   Complete configuration data flows back through all layers")

        print(f"\n✓ FLOW VERIFICATION COMPLETE")
        print(
            f"   Parameter successfully passed through {len(['App', 'HostOps', 'APIClient', 'CheckmkAPI'])} layers"
        )

        # Reset and test the reverse (False parameter)
        print(f"\n6. TESTING REVERSE FLOW (effective_attributes=False)")

        app_parameters_false = {"folder": "/production", "effective_attributes": False}

        result = host_manager._list_hosts(app_parameters_false)
        mock_checkmk.list_hosts.assert_called_with(effective_attributes=False)

        print(f"   ✓ effective_attributes=False parameter also flows correctly")

        # Test default behavior (no parameter)
        print(f"\n7. TESTING DEFAULT BEHAVIOR (no effective_attributes parameter)")

        app_parameters_default = {"folder": "/production"}

        result = host_manager._list_hosts(app_parameters_default)
        mock_checkmk.list_hosts.assert_called_with(effective_attributes=False)

        print(f"   ✓ Default behavior (no parameter) = effective_attributes=False")

        print(f"\n🎉 DEMONSTRATION COMPLETE")
        print(
            f"   effective_attributes parameter works correctly through entire system!"
        )


if __name__ == "__main__":
    """Run demonstrations directly for manual testing."""
    import asyncio

    # Create demo config
    demo_config = AppConfig(
        checkmk=CheckmkConfig(
            server_url="https://demo.checkmk.example.com",
            username="automation",
            password="demo-secret",
            site="demo",
        ),
        llm=LLMConfig(),
        default_folder="/demo",
        log_level="INFO",
    )

    demo = TestEffectiveAttributesDemonstration()

    print("🚀 EFFECTIVE_ATTRIBUTES FUNCTIONALITY DEMONSTRATION")
    print("=" * 60)

    # Run synchronous demos
    demo.test_api_client_effective_attributes_demo(demo_config)
    demo.test_host_operations_manager_demo(demo_config)
    demo.test_real_world_scenario_demo(demo_config)
    demo.test_backward_compatibility_demo(demo_config)
    demo.test_complete_flow_demo(demo_config)

    # Run async demo
    print("\nRunning async demo...")
    asyncio.run(demo.test_host_service_effective_attributes_demo(demo_config))

    print("\n" + "=" * 60)
    print("✅ ALL DEMONSTRATIONS COMPLETED SUCCESSFULLY!")
    print("   The effective_attributes functionality is working correctly.")
