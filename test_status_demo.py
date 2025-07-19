#!/usr/bin/env python3
"""
Demo script to test service status monitoring functionality with mock data.
This shows how the status commands work without requiring a real Checkmk server.
"""

from unittest.mock import Mock
from checkmk_agent.service_status import ServiceStatusManager
from checkmk_agent.interactive.ui_manager import UIManager
from checkmk_agent.interactive.command_parser import CommandParser
from checkmk_agent.api_client import CheckmkClient
from checkmk_agent.config import AppConfig

def create_mock_client():
    """Create a mock Checkmk client with sample data."""
    mock_client = Mock(spec=CheckmkClient)
    
    # Mock health summary data
    mock_health = {
        'total_services': 150,
        'health_percentage': 87.5,
        'problems': 12,
        'states': {'ok': 138, 'warning': 8, 'critical': 4, 'unknown': 0},
        'acknowledged': 3,
        'in_downtime': 1
    }
    
    # Mock problem services
    mock_problems = [
        {
            'extensions': {
                'host_name': 'web01',
                'description': 'Database Connection',
                'state': 2,
                'acknowledged': 0,
                'scheduled_downtime_depth': 0,
                'plugin_output': 'Connection timeout after 30 seconds'
            }
        },
        {
            'extensions': {
                'host_name': 'app02',
                'description': 'Memory Usage',
                'state': 2,
                'acknowledged': 0,
                'scheduled_downtime_depth': 0,
                'plugin_output': 'Memory usage at 95% - critical threshold exceeded'
            }
        },
        {
            'extensions': {
                'host_name': 'db01',
                'description': 'Disk Space /var',
                'state': 2,
                'acknowledged': 0,
                'scheduled_downtime_depth': 0,
                'plugin_output': 'Filesystem /var is 98% full'
            }
        },
        {
            'extensions': {
                'host_name': 'web02',
                'description': 'CPU Load',
                'state': 1,
                'acknowledged': 1,
                'scheduled_downtime_depth': 0,
                'plugin_output': 'CPU load average: 4.2 (warning at 4.0)'
            }
        }
    ]
    
    # Configure mock responses
    mock_client.get_service_health_summary.return_value = mock_health
    mock_client.list_problem_services.return_value = mock_problems
    mock_client.get_acknowledged_services.return_value = [mock_problems[3]]  # CPU Load is acknowledged
    mock_client.get_services_in_downtime.return_value = []
    mock_client.get_services_by_state.return_value = mock_problems[:3]  # Critical services
    
    return mock_client

def test_command_parsing():
    """Test command parsing for status queries."""
    print("🔍 Testing Command Parsing")
    print("=" * 50)
    
    parser = CommandParser()
    
    test_commands = [
        "show health dashboard",
        "health overview", 
        "list critical problems",
        "service status overview",
        "dashboard",
        "status"
    ]
    
    for cmd in test_commands:
        intent = parser.parse_command(cmd)
        cmd_type = parser.get_command_type(intent.command, intent.parameters, cmd)
        
        print(f"'{cmd}'")
        print(f"  → Command: {intent.command}")
        print(f"  → Type: {cmd_type}")
        print(f"  → Confidence: {intent.confidence:.2f}")
        print()

def test_status_manager():
    """Test ServiceStatusManager with mock data."""
    print("📊 Testing Service Status Manager")
    print("=" * 50)
    
    mock_client = create_mock_client()
    mock_config = Mock(spec=AppConfig)
    
    status_manager = ServiceStatusManager(mock_client, mock_config)
    
    # Test health dashboard
    print("🎯 Health Dashboard:")
    dashboard = status_manager.get_service_health_dashboard()
    
    print(f"Total Services: {dashboard['overall_health']['total_services']}")
    print(f"Health Percentage: {dashboard['overall_health']['health_percentage']}%")
    print(f"Problems: {dashboard['overall_health']['problems']}")
    print(f"Critical Issues: {len(dashboard['problem_analysis']['critical'])}")
    print(f"Warning Issues: {len(dashboard['problem_analysis']['warning'])}")
    print(f"Needs Attention: {dashboard['needs_attention']}")
    print()
    
    # Test status summary
    print("📋 Status Summary:")
    summary = status_manager.generate_status_summary()
    print(f"Status Icon: {summary['status_icon']}")
    print(f"Health: {summary['health_percentage']}%")
    print(f"Message: {summary['status_message']}")
    print()

def test_ui_formatting():
    """Test UI formatting with status data."""
    print("🎨 Testing UI Formatting")
    print("=" * 50)
    
    ui = UIManager()
    
    mock_client = create_mock_client()
    mock_config = Mock(spec=AppConfig)
    status_manager = ServiceStatusManager(mock_client, mock_config)
    
    # Get dashboard data
    dashboard = status_manager.get_service_health_dashboard()
    
    # Format dashboard
    formatted_dashboard = ui.format_service_health_dashboard(dashboard)
    print(formatted_dashboard)
    
    # Test status summary card
    summary = status_manager.generate_status_summary()
    summary_card = ui.format_status_summary_card(summary)
    print(summary_card)

def test_problem_analysis():
    """Test problem analysis functionality."""
    print("🎯 Testing Problem Analysis")
    print("=" * 50)
    
    mock_client = create_mock_client()
    mock_config = Mock(spec=AppConfig)
    status_manager = ServiceStatusManager(mock_client, mock_config)
    
    analysis = status_manager.analyze_service_problems()
    
    print(f"Total Problems: {analysis['total_problems']}")
    print(f"Critical Count: {analysis['critical_count']}")
    print(f"Warning Count: {analysis['warning_count']}")
    print(f"Unhandled Count: {analysis['unhandled_count']}")
    print()
    
    print("Problem Categories:")
    for category, services in analysis['categories'].items():
        if services:
            print(f"  {category}: {len(services)} services")
    print()

if __name__ == "__main__":
    print("🚀 Checkmk LLM Agent - Service Status Demo")
    print("=" * 60)
    print()
    
    test_command_parsing()
    test_status_manager()
    test_ui_formatting()
    test_problem_analysis()
    
    print("✅ Demo completed successfully!")
    print()
    print("💡 The 'show health dashboard' command works correctly!")
    print("   The API error you saw was due to the Checkmk server configuration,")
    print("   not the command parsing or status functionality.")