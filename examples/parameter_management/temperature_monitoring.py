#!/usr/bin/env python3
"""
Temperature Monitoring Parameter Management Example

This script demonstrates how to use the specialized temperature parameter handler
to set up comprehensive temperature monitoring across a server environment.

Usage:
    python temperature_monitoring.py --config config.yaml --environment production
"""

import asyncio
import argparse
import json
import yaml
from typing import Dict, List, Any
from pathlib import Path

from checkmk_agent.services.parameter_service import ParameterService
from checkmk_agent.api_client import CheckmkClient
from checkmk_agent.config import Config


class TemperatureMonitoringSetup:
    """Handles temperature monitoring parameter setup."""
    
    def __init__(self, parameter_service: ParameterService):
        self.parameter_service = parameter_service
        self.temperature_services = [
            "CPU Temperature",
            "CPU Core 0 Temperature", 
            "CPU Core 1 Temperature",
            "GPU Temperature",
            "System Temperature",
            "Ambient Temperature",
            "HDD Temperature",
            "SSD Temperature",
            "Chassis Temperature",
            "Power Supply Temperature",
            "Network Card Temperature"
        ]
    
    async def setup_datacenter_monitoring(self, environment: str = "production") -> Dict[str, Any]:
        """Set up temperature monitoring for a datacenter environment."""
        print(f"🌡️  Setting up temperature monitoring for {environment} environment")
        
        # Define environment-specific context
        context = {
            "environment": environment,
            "criticality": "high" if environment == "production" else "medium",
            "location": "datacenter_primary",
            "hardware_type": "server"
        }
        
        results = {
            "environment": environment,
            "context": context,
            "services_configured": [],
            "rules_created": [],
            "validation_results": []
        }
        
        for service_name in self.temperature_services:
            print(f"  📊 Configuring {service_name}...")
            
            try:
                # Get specialized defaults for this service
                defaults_result = await self.parameter_service.get_specialized_defaults(
                    service_name, context
                )
                
                if not defaults_result.success:
                    print(f"    ❌ Failed to get defaults: {defaults_result.error}")
                    continue
                
                parameters = defaults_result.data["parameters"]
                handler_used = defaults_result.data["handler_used"]
                
                print(f"    ✅ Using {handler_used} handler")
                print(f"    🔧 Parameters: {parameters}")
                
                # Validate the generated parameters
                validation_result = await self.parameter_service.validate_specialized_parameters(
                    parameters, service_name
                )
                
                if validation_result.success and validation_result.data["is_valid"]:
                    print(f"    ✅ Parameters validated successfully")
                    
                    # Create rule for production servers
                    rule_data = {
                        "ruleset": "checkgroup_parameters:temperature",
                        "folder": f"/servers/{environment}",
                        "conditions": {
                            "host_name": [f"{environment}-*"],
                            "service_description": [service_name]
                        },
                        "properties": {
                            "comment": f"Automated {environment} temperature monitoring",
                            "description": f"{service_name} monitoring for {environment} environment"
                        },
                        "value": parameters
                    }
                    
                    # Create the rule
                    rule_result = await self.parameter_service.create_specialized_rule(
                        service_name, rule_data
                    )
                    
                    if rule_result.success:
                        rule_id = rule_result.data["rule_id"]
                        print(f"    ✅ Rule created: {rule_id}")
                        
                        results["rules_created"].append({
                            "service_name": service_name,
                            "rule_id": rule_id,
                            "parameters": parameters,
                            "handler_used": handler_used
                        })
                    else:
                        print(f"    ❌ Failed to create rule: {rule_result.error}")
                else:
                    print(f"    ❌ Parameter validation failed")
                    if validation_result.data.get("errors"):
                        for error in validation_result.data["errors"]:
                            print(f"      - {error}")
                
                results["services_configured"].append({
                    "service_name": service_name,
                    "success": defaults_result.success,
                    "handler_used": handler_used,
                    "parameters": parameters
                })
                
            except Exception as e:
                print(f"    ❌ Error configuring {service_name}: {e}")
        
        return results
    
    async def setup_custom_temperature_profiles(self) -> Dict[str, Any]:
        """Set up custom temperature profiles for specific use cases."""
        print("🎯 Setting up custom temperature profiles")
        
        custom_scenarios = [
            {
                "name": "High-Performance Computing",
                "context": {
                    "environment": "hpc",
                    "hardware_type": "compute_node",
                    "cooling": "liquid",
                    "workload": "intensive"
                },
                "services": ["CPU Temperature", "GPU Temperature"],
                "folder": "/hpc/compute"
            },
            {
                "name": "Edge Computing",
                "context": {
                    "environment": "edge",
                    "hardware_type": "embedded",
                    "cooling": "passive",
                    "ambient_temp": 40.0
                },
                "services": ["System Temperature", "Ambient Temperature"],
                "folder": "/edge/devices"
            },
            {
                "name": "Storage Array",
                "context": {
                    "environment": "storage",
                    "hardware_type": "storage_array",
                    "drive_count": 24
                },
                "services": ["HDD Temperature", "SSD Temperature", "Chassis Temperature"],
                "folder": "/storage/arrays"
            }
        ]
        
        results = {"custom_profiles": []}
        
        for scenario in custom_scenarios:
            print(f"  🔧 Setting up {scenario['name']} profile...")
            
            scenario_results = {
                "name": scenario["name"],
                "context": scenario["context"],
                "services": [],
                "rules": []
            }
            
            for service_name in scenario["services"]:
                # Get specialized defaults with custom context
                defaults_result = await self.parameter_service.get_specialized_defaults(
                    service_name, scenario["context"]
                )
                
                if defaults_result.success:
                    parameters = defaults_result.data["parameters"]
                    
                    # Create rule for this scenario
                    rule_data = {
                        "ruleset": "checkgroup_parameters:temperature",
                        "folder": scenario["folder"],
                        "conditions": {
                            "host_name": [f"{scenario['context']['environment']}-*"],
                            "service_description": [service_name]
                        },
                        "properties": {
                            "comment": f"{scenario['name']} temperature profile",
                            "description": f"Optimized for {scenario['name'].lower()} use case"
                        },
                        "value": parameters
                    }
                    
                    rule_result = await self.parameter_service.create_specialized_rule(
                        service_name, rule_data
                    )
                    
                    if rule_result.success:
                        scenario_results["rules"].append({
                            "service_name": service_name,
                            "rule_id": rule_result.data["rule_id"],
                            "parameters": parameters
                        })
                        print(f"    ✅ {service_name} configured")
                    else:
                        print(f"    ❌ Failed to create rule for {service_name}")
                
                scenario_results["services"].append({
                    "service_name": service_name,
                    "success": defaults_result.success,
                    "parameters": defaults_result.data.get("parameters") if defaults_result.success else None
                })
            
            results["custom_profiles"].append(scenario_results)
        
        return results
    
    async def validate_temperature_setup(self, environment: str) -> Dict[str, Any]:
        """Validate the temperature monitoring setup."""
        print(f"🔍 Validating temperature monitoring setup for {environment}")
        
        validation_tests = [
            {
                "name": "CPU Temperature Thresholds",
                "service": "CPU Temperature",
                "expected_ranges": {
                    "warning_min": 70.0,
                    "warning_max": 80.0,
                    "critical_min": 80.0,
                    "critical_max": 90.0
                }
            },
            {
                "name": "GPU Temperature Thresholds", 
                "service": "GPU Temperature",
                "expected_ranges": {
                    "warning_min": 75.0,
                    "warning_max": 85.0,
                    "critical_min": 85.0,
                    "critical_max": 95.0
                }
            },
            {
                "name": "Ambient Temperature Thresholds",
                "service": "Ambient Temperature",
                "expected_ranges": {
                    "warning_min": 30.0,
                    "warning_max": 40.0,
                    "critical_min": 35.0,
                    "critical_max": 45.0
                }
            }
        ]
        
        results = {"validation_tests": [], "overall_status": "pass"}
        
        for test in validation_tests:
            print(f"  🧪 Testing {test['name']}...")
            
            # Get current parameters
            defaults_result = await self.parameter_service.get_specialized_defaults(
                test["service"], 
                {"environment": environment, "criticality": "high"}
            )
            
            test_result = {
                "name": test["name"],
                "service": test["service"],
                "status": "pass",
                "issues": []
            }
            
            if defaults_result.success:
                parameters = defaults_result.data["parameters"]
                levels = parameters.get("levels")
                
                if levels and len(levels) == 2:
                    warning_threshold, critical_threshold = levels
                    expected = test["expected_ranges"]
                    
                    # Validate warning threshold
                    if not (expected["warning_min"] <= warning_threshold <= expected["warning_max"]):
                        test_result["issues"].append(
                            f"Warning threshold {warning_threshold}°C outside expected range "
                            f"{expected['warning_min']}-{expected['warning_max']}°C"
                        )
                        test_result["status"] = "fail"
                    
                    # Validate critical threshold
                    if not (expected["critical_min"] <= critical_threshold <= expected["critical_max"]):
                        test_result["issues"].append(
                            f"Critical threshold {critical_threshold}°C outside expected range "
                            f"{expected['critical_min']}-{expected['critical_max']}°C"
                        )
                        test_result["status"] = "fail"
                    
                    # Validate threshold ordering
                    if warning_threshold >= critical_threshold:
                        test_result["issues"].append(
                            f"Warning threshold ({warning_threshold}°C) should be less than "
                            f"critical threshold ({critical_threshold}°C)"
                        )
                        test_result["status"] = "fail"
                    
                    if test_result["status"] == "pass":
                        print(f"    ✅ Thresholds valid: {warning_threshold}°C/{critical_threshold}°C")
                    else:
                        print(f"    ❌ Validation failed")
                        for issue in test_result["issues"]:
                            print(f"      - {issue}")
                        results["overall_status"] = "fail"
            else:
                test_result["status"] = "error"
                test_result["issues"].append(f"Failed to get defaults: {defaults_result.error}")
                print(f"    ❌ Error getting defaults")
                results["overall_status"] = "fail"
            
            results["validation_tests"].append(test_result)
        
        return results
    
    async def generate_temperature_report(self, environment: str) -> str:
        """Generate a comprehensive temperature monitoring report."""
        print(f"📋 Generating temperature monitoring report for {environment}")
        
        # Get configuration for all temperature services
        configurations = {}
        
        for service_name in self.temperature_services:
            defaults_result = await self.parameter_service.get_specialized_defaults(
                service_name, 
                {"environment": environment, "criticality": "high"}
            )
            
            if defaults_result.success:
                configurations[service_name] = {
                    "handler_used": defaults_result.data["handler_used"],
                    "parameters": defaults_result.data["parameters"],
                    "metadata": defaults_result.data.get("metadata", {})
                }
        
        # Generate report
        report = f"""
# Temperature Monitoring Configuration Report
## Environment: {environment.upper()}
## Generated: {asyncio.get_event_loop().time()}

### Summary
- **Total Services**: {len(self.temperature_services)}
- **Configured Services**: {len(configurations)}
- **Handler Used**: temperature (specialized)

### Service Configurations

"""
        
        for service_name, config in configurations.items():
            parameters = config["parameters"]
            levels = parameters.get("levels", (0, 0))
            unit = parameters.get("output_unit", "c")
            
            report += f"""
#### {service_name}
- **Warning Threshold**: {levels[0]}°{unit.upper()}
- **Critical Threshold**: {levels[1]}°{unit.upper()}
- **Output Unit**: {unit.upper()}
- **Profile**: {config.get("metadata", {}).get("profile", "generic")}

"""
        
        report += f"""
### Recommended Actions

1. **Monitor Baseline Performance**: Collect temperature data for 1-2 weeks to establish baselines
2. **Adjust Thresholds**: Fine-tune thresholds based on observed temperature patterns
3. **Set Up Alerts**: Configure notifications for temperature threshold breaches
4. **Regular Review**: Review and adjust thresholds quarterly or after hardware changes

### Configuration Commands

To recreate this configuration:

```bash
# Set up temperature monitoring
python temperature_monitoring.py --config config.yaml --environment {environment}

# Validate configuration
python temperature_monitoring.py --config config.yaml --validate --environment {environment}
```

### Notes
- All thresholds are optimized for {environment} environment
- Consider local ambient temperature when adjusting thresholds
- GPU thresholds may need adjustment based on workload intensity
- Storage device thresholds are conservative to prevent data loss
"""
        
        return report


async def main():
    """Main function to run temperature monitoring setup."""
    parser = argparse.ArgumentParser(description="Temperature Monitoring Parameter Management")
    parser.add_argument("--config", required=True, help="Configuration file path")
    parser.add_argument("--environment", default="production", 
                       choices=["development", "testing", "production", "hpc", "edge"],
                       help="Environment to configure")
    parser.add_argument("--validate", action="store_true", 
                       help="Validate existing temperature setup")
    parser.add_argument("--custom-profiles", action="store_true",
                       help="Set up custom temperature profiles")
    parser.add_argument("--generate-report", action="store_true",
                       help="Generate temperature monitoring report")
    parser.add_argument("--output", help="Output file for results/reports")
    
    args = parser.parse_args()
    
    # Load configuration
    config = Config.from_file(args.config)
    
    # Initialize services
    client = CheckmkClient(config.checkmk)
    parameter_service = ParameterService(client, config)
    
    # Initialize temperature monitoring setup
    temp_setup = TemperatureMonitoringSetup(parameter_service)
    
    try:
        if args.validate:
            # Validate existing setup
            validation_results = await temp_setup.validate_temperature_setup(args.environment)
            
            print(f"\n📊 Validation Results: {validation_results['overall_status'].upper()}")
            
            if args.output:
                with open(args.output, 'w') as f:
                    json.dump(validation_results, f, indent=2)
                print(f"📁 Validation results saved to {args.output}")
        
        elif args.custom_profiles:
            # Set up custom profiles
            profile_results = await temp_setup.setup_custom_temperature_profiles()
            
            print(f"\n✅ Custom profiles configured: {len(profile_results['custom_profiles'])}")
            
            if args.output:
                with open(args.output, 'w') as f:
                    json.dump(profile_results, f, indent=2)
                print(f"📁 Profile results saved to {args.output}")
        
        elif args.generate_report:
            # Generate report
            report = await temp_setup.generate_temperature_report(args.environment)
            
            if args.output:
                with open(args.output, 'w') as f:
                    f.write(report)
                print(f"📁 Report saved to {args.output}")
            else:
                print(report)
        
        else:
            # Standard datacenter setup
            setup_results = await temp_setup.setup_datacenter_monitoring(args.environment)
            
            print(f"\n✅ Temperature monitoring setup complete!")
            print(f"   - Environment: {setup_results['environment']}")
            print(f"   - Services configured: {len(setup_results['services_configured'])}")
            print(f"   - Rules created: {len(setup_results['rules_created'])}")
            
            if args.output:
                with open(args.output, 'w') as f:
                    json.dump(setup_results, f, indent=2)
                print(f"📁 Setup results saved to {args.output}")
    
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))