#!/usr/bin/env python3
"""
Database Monitoring Parameter Management Example

This script demonstrates how to use the specialized database parameter handler
to set up comprehensive database monitoring across different database systems.

Usage:
    python database_monitoring.py --config config.yaml --database-type mysql
    python database_monitoring.py --config config.yaml --database-type oracle --setup-tablespaces
    python database_monitoring.py --config config.yaml --database-type postgresql --connection-monitoring
"""

import asyncio
import argparse
import json
import yaml
from typing import Dict, List, Any, Optional
from pathlib import Path

from checkmk_agent.services.parameter_service import ParameterService
from checkmk_agent.api_client import CheckmkClient
from checkmk_agent.config import Config


class DatabaseMonitoringSetup:
    """Handles database monitoring parameter setup."""
    
    def __init__(self, parameter_service: ParameterService):
        self.parameter_service = parameter_service
        
        # Database service patterns by type
        self.database_services = {
            "mysql": [
                "MySQL Connections",
                "MySQL InnoDB Buffer Pool",
                "MySQL Slow Queries",
                "MySQL Replication Lag",
                "MySQL Query Cache Hit Rate",
                "MySQL Table Locks"
            ],
            "oracle": [
                "Oracle Tablespace USERS",
                "Oracle Tablespace TEMP",
                "Oracle Tablespace SYSTEM",
                "Oracle Session Count",
                "Oracle Archive Log",
                "Oracle Redo Log Switch",
                "Oracle SGA Memory",
                "Oracle PGA Memory"
            ],
            "postgresql": [
                "PostgreSQL Connections",
                "PostgreSQL Database Size",
                "PostgreSQL Locks",
                "PostgreSQL Vacuum Performance",
                "PostgreSQL WAL Files",
                "PostgreSQL Replication Lag"
            ],
            "mongodb": [
                "MongoDB Connections",
                "MongoDB Memory Usage",
                "MongoDB Replica Set Status",
                "MongoDB Locks",
                "MongoDB Operations"
            ],
            "redis": [
                "Redis Memory Usage",
                "Redis Connections",
                "Redis Keyspace",
                "Redis Replication Status"
            ]
        }
    
    async def setup_mysql_monitoring(self, connection_info: Dict[str, Any]) -> Dict[str, Any]:
        """Set up comprehensive MySQL monitoring."""
        print("🐬 Setting up MySQL monitoring...")
        
        mysql_context = {
            "database_type": "mysql",
            "environment": "production",
            "high_availability": True,
            "connection_info": connection_info
        }
        
        results = {
            "database_type": "mysql",
            "connection_info": connection_info,
            "services_configured": [],
            "rules_created": []
        }
        
        mysql_services = self.database_services["mysql"]
        
        for service_name in mysql_services:
            print(f"  📊 Configuring {service_name}...")
            
            try:
                # Get specialized defaults
                defaults_result = await self.parameter_service.get_specialized_defaults(
                    service_name, mysql_context
                )
                
                if not defaults_result.success:
                    print(f"    ❌ Failed to get defaults: {defaults_result.error}")
                    continue
                
                parameters = defaults_result.data["parameters"]
                handler_used = defaults_result.data["handler_used"]
                
                # Add MySQL-specific connection parameters
                if "connection" in service_name.lower():
                    parameters.update({
                        "hostname": connection_info.get("hostname"),
                        "port": connection_info.get("port", 3306),
                        "database": connection_info.get("database"),
                        "username": connection_info.get("username"),
                        "connection_timeout": 30,
                        "ssl_verify": connection_info.get("ssl_verify", True)
                    })
                elif "innodb" in service_name.lower():
                    # InnoDB specific parameters
                    parameters.update({
                        "buffer_pool_hit_rate": (90.0, 95.0),
                        "buffer_pool_size_threshold": (80.0, 90.0)
                    })
                elif "replication" in service_name.lower():
                    # Replication specific parameters
                    parameters.update({
                        "lag_threshold": (60, 300),  # seconds
                        "slave_sql_running": True,
                        "slave_io_running": True
                    })
                
                # Validate parameters
                validation_result = await self.parameter_service.validate_specialized_parameters(
                    parameters, service_name
                )
                
                if validation_result.success and validation_result.data["is_valid"]:
                    # Create rule
                    rule_data = {
                        "ruleset": "checkgroup_parameters:mysql",
                        "folder": "/databases/mysql",
                        "conditions": {
                            "host_name": [connection_info.get("hostname", "*mysql*")],
                            "service_description": [service_name]
                        },
                        "properties": {
                            "comment": f"MySQL {service_name} monitoring",
                            "description": f"Automated MySQL monitoring for {service_name}"
                        },
                        "value": parameters
                    }
                    
                    rule_result = await self.parameter_service.create_specialized_rule(
                        service_name, rule_data
                    )
                    
                    if rule_result.success:
                        rule_id = rule_result.data["rule_id"]
                        print(f"    ✅ Rule created: {rule_id}")
                        
                        results["rules_created"].append({
                            "service_name": service_name,
                            "rule_id": rule_id,
                            "parameters": parameters
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
    
    async def setup_oracle_monitoring(self, 
                                    connection_info: Dict[str, Any],
                                    tablespaces: Optional[List[str]] = None) -> Dict[str, Any]:
        """Set up comprehensive Oracle monitoring."""
        print("🏛️  Setting up Oracle monitoring...")
        
        if not tablespaces:
            tablespaces = ["USERS", "TEMP", "SYSTEM", "SYSAUX", "UNDOTBS1"]
        
        oracle_context = {
            "database_type": "oracle",
            "environment": "production",
            "high_availability": True,
            "connection_info": connection_info,
            "tablespaces": tablespaces
        }
        
        results = {
            "database_type": "oracle",
            "connection_info": connection_info,
            "tablespaces": tablespaces,
            "services_configured": [],
            "rules_created": []
        }
        
        # Create specific tablespace services
        oracle_services = []
        for tablespace in tablespaces:
            oracle_services.append(f"Oracle Tablespace {tablespace}")
        
        # Add other Oracle services
        oracle_services.extend([
            "Oracle Session Count",
            "Oracle Archive Log",
            "Oracle Redo Log Switch",
            "Oracle SGA Memory", 
            "Oracle PGA Memory"
        ])
        
        for service_name in oracle_services:
            print(f"  📊 Configuring {service_name}...")
            
            try:
                # Get specialized defaults
                defaults_result = await self.parameter_service.get_specialized_defaults(
                    service_name, oracle_context
                )
                
                if not defaults_result.success:
                    print(f"    ❌ Failed to get defaults: {defaults_result.error}")
                    continue
                
                parameters = defaults_result.data["parameters"]
                handler_used = defaults_result.data["handler_used"]
                
                # Add Oracle-specific parameters
                parameters.update({
                    "hostname": connection_info.get("hostname"),
                    "port": connection_info.get("port", 1521),
                    "sid": connection_info.get("sid"),
                    "username": connection_info.get("username"),
                    "connection_timeout": 30
                })
                
                if "tablespace" in service_name.lower():
                    # Tablespace specific parameters
                    tablespace_name = service_name.split()[-1]  # Extract tablespace name
                    parameters.update({
                        "autoextend": True,
                        "magic_normsize": 1000,
                        "show_tablespaces": [tablespace_name],
                        "levels": (80.0, 90.0) if tablespace_name != "TEMP" else (90.0, 95.0)
                    })
                elif "session" in service_name.lower():
                    # Session count parameters
                    parameters.update({
                        "levels": (80.0, 90.0),  # Percentage of max sessions
                        "max_sessions_percent": True
                    })
                elif "archive" in service_name.lower():
                    # Archive log parameters
                    parameters.update({
                        "levels": (50, 100),  # Number of archive logs
                        "archive_lag_threshold": 300  # seconds
                    })
                
                # Validate and create rule
                validation_result = await self.parameter_service.validate_specialized_parameters(
                    parameters, service_name
                )
                
                if validation_result.success and validation_result.data["is_valid"]:
                    rule_data = {
                        "ruleset": "checkgroup_parameters:oracle_tablespaces" if "tablespace" in service_name.lower() else "checkgroup_parameters:oracle",
                        "folder": "/databases/oracle",
                        "conditions": {
                            "host_name": [connection_info.get("hostname", "*oracle*")],
                            "service_description": [service_name]
                        },
                        "properties": {
                            "comment": f"Oracle {service_name} monitoring",
                            "description": f"Automated Oracle monitoring for {service_name}"
                        },
                        "value": parameters
                    }
                    
                    rule_result = await self.parameter_service.create_specialized_rule(
                        service_name, rule_data
                    )
                    
                    if rule_result.success:
                        rule_id = rule_result.data["rule_id"]
                        print(f"    ✅ Rule created: {rule_id}")
                        
                        results["rules_created"].append({
                            "service_name": service_name,
                            "rule_id": rule_id,
                            "parameters": parameters
                        })
                    else:
                        print(f"    ❌ Failed to create rule: {rule_result.error}")
                
                results["services_configured"].append({
                    "service_name": service_name,
                    "success": defaults_result.success,
                    "handler_used": handler_used,
                    "parameters": parameters
                })
            
            except Exception as e:
                print(f"    ❌ Error configuring {service_name}: {e}")
        
        return results
    
    async def setup_postgresql_monitoring(self, connection_info: Dict[str, Any]) -> Dict[str, Any]:
        """Set up comprehensive PostgreSQL monitoring."""
        print("🐘 Setting up PostgreSQL monitoring...")
        
        postgres_context = {
            "database_type": "postgresql",
            "environment": "production",
            "connection_info": connection_info
        }
        
        results = {
            "database_type": "postgresql",
            "connection_info": connection_info,
            "services_configured": [],
            "rules_created": []
        }
        
        postgres_services = self.database_services["postgresql"]
        
        for service_name in postgres_services:
            print(f"  📊 Configuring {service_name}...")
            
            try:
                # Get specialized defaults
                defaults_result = await self.parameter_service.get_specialized_defaults(
                    service_name, postgres_context
                )
                
                if not defaults_result.success:
                    print(f"    ❌ Failed to get defaults: {defaults_result.error}")
                    continue
                
                parameters = defaults_result.data["parameters"]
                handler_used = defaults_result.data["handler_used"]
                
                # Add PostgreSQL-specific parameters
                parameters.update({
                    "hostname": connection_info.get("hostname"),
                    "port": connection_info.get("port", 5432),
                    "database": connection_info.get("database", "postgres"),
                    "username": connection_info.get("username"),
                    "connection_timeout": 30
                })
                
                if "connections" in service_name.lower():
                    # Connection specific parameters
                    parameters.update({
                        "levels": (80.0, 90.0),  # Percentage of max_connections
                        "max_connections_percent": True
                    })
                elif "locks" in service_name.lower():
                    # Lock specific parameters
                    parameters.update({
                        "levels": (100, 200),  # Number of locks
                        "lock_timeout_threshold": 30  # seconds
                    })
                elif "vacuum" in service_name.lower():
                    # Vacuum specific parameters
                    parameters.update({
                        "vacuum_age_threshold": 86400,  # 24 hours
                        "analyze_age_threshold": 86400
                    })
                elif "wal" in service_name.lower():
                    # WAL specific parameters
                    parameters.update({
                        "wal_files_threshold": (50, 100),
                        "wal_archive_lag": 300  # seconds
                    })
                
                # Validate and create rule
                validation_result = await self.parameter_service.validate_specialized_parameters(
                    parameters, service_name
                )
                
                if validation_result.success and validation_result.data["is_valid"]:
                    rule_data = {
                        "ruleset": "checkgroup_parameters:postgres",
                        "folder": "/databases/postgresql",
                        "conditions": {
                            "host_name": [connection_info.get("hostname", "*postgres*")],
                            "service_description": [service_name]
                        },
                        "properties": {
                            "comment": f"PostgreSQL {service_name} monitoring",
                            "description": f"Automated PostgreSQL monitoring for {service_name}"
                        },
                        "value": parameters
                    }
                    
                    rule_result = await self.parameter_service.create_specialized_rule(
                        service_name, rule_data
                    )
                    
                    if rule_result.success:
                        rule_id = rule_result.data["rule_id"]
                        print(f"    ✅ Rule created: {rule_id}")
                        
                        results["rules_created"].append({
                            "service_name": service_name,
                            "rule_id": rule_id,
                            "parameters": parameters
                        })
                    else:
                        print(f"    ❌ Failed to create rule: {rule_result.error}")
                
                results["services_configured"].append({
                    "service_name": service_name,
                    "success": defaults_result.success,
                    "handler_used": handler_used,
                    "parameters": parameters
                })
            
            except Exception as e:
                print(f"    ❌ Error configuring {service_name}: {e}")
        
        return results
    
    async def setup_mongodb_monitoring(self, connection_info: Dict[str, Any]) -> Dict[str, Any]:
        """Set up MongoDB monitoring."""
        print("🍃 Setting up MongoDB monitoring...")
        
        mongo_context = {
            "database_type": "mongodb",
            "environment": "production",
            "replica_set": connection_info.get("replica_set"),
            "connection_info": connection_info
        }
        
        results = {
            "database_type": "mongodb",
            "connection_info": connection_info,
            "services_configured": [],
            "rules_created": []
        }
        
        mongo_services = self.database_services["mongodb"]
        
        for service_name in mongo_services:
            print(f"  📊 Configuring {service_name}...")
            
            try:
                defaults_result = await self.parameter_service.get_specialized_defaults(
                    service_name, mongo_context
                )
                
                if defaults_result.success:
                    parameters = defaults_result.data["parameters"]
                    
                    # Add MongoDB-specific parameters
                    parameters.update({
                        "hostname": connection_info.get("hostname"),
                        "port": connection_info.get("port", 27017),
                        "username": connection_info.get("username"),
                        "authentication_database": connection_info.get("auth_db", "admin")
                    })
                    
                    if "memory" in service_name.lower():
                        parameters.update({
                            "resident_levels": (1024, 2048),  # MB
                            "virtual_levels": (2048, 4096)    # MB
                        })
                    elif "replica" in service_name.lower():
                        parameters.update({
                            "replica_set_name": connection_info.get("replica_set"),
                            "member_health_check": True
                        })
                    
                    # Create rule
                    rule_data = {
                        "ruleset": "checkgroup_parameters:mongodb",
                        "folder": "/databases/mongodb",
                        "conditions": {
                            "host_name": [connection_info.get("hostname", "*mongo*")],
                            "service_description": [service_name]
                        },
                        "value": parameters
                    }
                    
                    rule_result = await self.parameter_service.create_specialized_rule(
                        service_name, rule_data
                    )
                    
                    if rule_result.success:
                        print(f"    ✅ Rule created: {rule_result.data['rule_id']}")
                        results["rules_created"].append({
                            "service_name": service_name,
                            "rule_id": rule_result.data["rule_id"],
                            "parameters": parameters
                        })
                
                results["services_configured"].append({
                    "service_name": service_name,
                    "success": defaults_result.success,
                    "parameters": parameters
                })
            
            except Exception as e:
                print(f"    ❌ Error configuring {service_name}: {e}")
        
        return results
    
    async def validate_database_configuration(self, database_type: str, connection_info: Dict[str, Any]) -> Dict[str, Any]:
        """Validate database monitoring configuration."""
        print(f"🔍 Validating {database_type} configuration...")
        
        services = self.database_services.get(database_type, [])
        validation_results = {
            "database_type": database_type,
            "total_services": len(services),
            "validated_services": [],
            "overall_status": "pass"
        }
        
        for service_name in services:
            print(f"  🧪 Validating {service_name}...")
            
            service_result = {
                "service_name": service_name,
                "status": "pass",
                "issues": [],
                "parameters": None
            }
            
            try:
                # Get defaults
                defaults_result = await self.parameter_service.get_specialized_defaults(
                    service_name, {"database_type": database_type}
                )
                
                if defaults_result.success:
                    parameters = defaults_result.data["parameters"]
                    service_result["parameters"] = parameters
                    
                    # Validate connection parameters
                    if any(param in service_name.lower() for param in ["connection", "session"]):
                        required_params = ["hostname", "port", "username"]
                        for param in required_params:
                            if param not in parameters or not parameters[param]:
                                service_result["issues"].append(f"Missing required parameter: {param}")
                                service_result["status"] = "fail"
                    
                    # Validate thresholds
                    if "levels" in parameters:
                        levels = parameters["levels"]
                        if isinstance(levels, (list, tuple)) and len(levels) == 2:
                            if levels[0] >= levels[1]:
                                service_result["issues"].append("Warning threshold should be less than critical threshold")
                                service_result["status"] = "fail"
                        else:
                            service_result["issues"].append("Invalid levels format")
                            service_result["status"] = "fail"
                    
                    if service_result["status"] == "pass":
                        print(f"    ✅ Configuration valid")
                    else:
                        print(f"    ❌ Validation issues found")
                        for issue in service_result["issues"]:
                            print(f"      - {issue}")
                        validation_results["overall_status"] = "fail"
                
                else:
                    service_result["status"] = "error"
                    service_result["issues"].append(f"Failed to get defaults: {defaults_result.error}")
                    print(f"    ❌ Error getting defaults")
                    validation_results["overall_status"] = "fail"
            
            except Exception as e:
                service_result["status"] = "error"
                service_result["issues"].append(f"Exception: {str(e)}")
                print(f"    ❌ Exception: {e}")
                validation_results["overall_status"] = "fail"
            
            validation_results["validated_services"].append(service_result)
        
        return validation_results
    
    async def generate_database_report(self, database_type: str, connection_info: Dict[str, Any]) -> str:
        """Generate a comprehensive database monitoring report."""
        print(f"📋 Generating {database_type} monitoring report...")
        
        services = self.database_services.get(database_type, [])
        configurations = {}
        
        for service_name in services:
            defaults_result = await self.parameter_service.get_specialized_defaults(
                service_name, {"database_type": database_type}
            )
            
            if defaults_result.success:
                configurations[service_name] = {
                    "handler_used": defaults_result.data["handler_used"],
                    "parameters": defaults_result.data["parameters"],
                    "metadata": defaults_result.data.get("metadata", {})
                }
        
        # Generate report
        report = f"""
# {database_type.upper()} Monitoring Configuration Report
## Database: {database_type.upper()}
## Host: {connection_info.get('hostname', 'N/A')}
## Port: {connection_info.get('port', 'N/A')}

### Summary
- **Total Services**: {len(services)}
- **Configured Services**: {len(configurations)}
- **Handler Used**: database (specialized)

### Service Configurations

"""
        
        for service_name, config in configurations.items():
            parameters = config["parameters"]
            levels = parameters.get("levels")
            
            report += f"""
#### {service_name}
- **Thresholds**: {levels if levels else "N/A"}
- **Timeout**: {parameters.get("connection_timeout", parameters.get("timeout", "N/A"))}s
- **Parameters**: {len(parameters)} configured
"""
            
            # Add service-specific details
            if "connection" in service_name.lower():
                report += f"- **Host**: {parameters.get('hostname', 'N/A')}\n"
                report += f"- **Port**: {parameters.get('port', 'N/A')}\n"
            elif "tablespace" in service_name.lower():
                report += f"- **Autoextend**: {parameters.get('autoextend', 'N/A')}\n"
            elif "memory" in service_name.lower():
                if "resident_levels" in parameters:
                    report += f"- **Resident Memory**: {parameters['resident_levels']} MB\n"
                if "virtual_levels" in parameters:
                    report += f"- **Virtual Memory**: {parameters['virtual_levels']} MB\n"
            
            report += "\n"
        
        report += f"""
### Connection Information
- **Hostname**: {connection_info.get('hostname', 'N/A')}
- **Port**: {connection_info.get('port', 'N/A')}
- **Database**: {connection_info.get('database', connection_info.get('sid', 'N/A'))}
- **Username**: {connection_info.get('username', 'N/A')}

### Recommended Actions
1. **Test Connections**: Verify all database connections are working
2. **Baseline Monitoring**: Collect metrics for 1-2 weeks to establish baselines
3. **Tune Thresholds**: Adjust thresholds based on observed performance patterns
4. **Set Up Alerts**: Configure notifications for threshold breaches
5. **Regular Maintenance**: Schedule regular database health checks

### Configuration Commands

To recreate this configuration:

```bash
# Set up {database_type} monitoring
python database_monitoring.py --config config.yaml --database-type {database_type}

# Validate configuration
python database_monitoring.py --config config.yaml --database-type {database_type} --validate
```
"""
        
        return report


async def main():
    """Main function to run database monitoring setup."""
    parser = argparse.ArgumentParser(description="Database Monitoring Parameter Management")
    parser.add_argument("--config", required=True, help="Configuration file path")
    parser.add_argument("--database-type", required=True,
                       choices=["mysql", "oracle", "postgresql", "mongodb", "redis"],
                       help="Database type to configure")
    parser.add_argument("--hostname", help="Database hostname")
    parser.add_argument("--port", type=int, help="Database port")
    parser.add_argument("--database", help="Database name")
    parser.add_argument("--username", help="Database username")
    parser.add_argument("--sid", help="Oracle SID")
    parser.add_argument("--replica-set", help="MongoDB replica set name")
    parser.add_argument("--tablespaces", help="Comma-separated list of Oracle tablespaces")
    parser.add_argument("--validate", action="store_true", help="Validate configuration")
    parser.add_argument("--generate-report", action="store_true", help="Generate monitoring report")
    parser.add_argument("--output", help="Output file for results/reports")
    
    args = parser.parse_args()
    
    # Build connection info
    connection_info = {
        "hostname": args.hostname or f"{args.database_type}-server.example.com",
        "port": args.port,
        "database": args.database,
        "username": args.username or "monitor_user",
        "sid": args.sid,
        "replica_set": args.replica_set
    }
    
    # Set default ports
    if not args.port:
        default_ports = {
            "mysql": 3306,
            "oracle": 1521,
            "postgresql": 5432,
            "mongodb": 27017,
            "redis": 6379
        }
        connection_info["port"] = default_ports.get(args.database_type)
    
    # Load configuration
    config = Config.from_file(args.config)
    
    # Initialize services
    client = CheckmkClient(config.checkmk)
    parameter_service = ParameterService(client, config)
    
    # Initialize database monitoring setup
    db_setup = DatabaseMonitoringSetup(parameter_service)
    
    try:
        if args.validate:
            # Validate configuration
            validation_results = await db_setup.validate_database_configuration(
                args.database_type, connection_info
            )
            
            print(f"\n📊 Validation Results: {validation_results['overall_status'].upper()}")
            
            if args.output:
                with open(args.output, 'w') as f:
                    json.dump(validation_results, f, indent=2)
                print(f"📁 Validation results saved to {args.output}")
        
        elif args.generate_report:
            # Generate report
            report = await db_setup.generate_database_report(args.database_type, connection_info)
            
            if args.output:
                with open(args.output, 'w') as f:
                    f.write(report)
                print(f"📁 Report saved to {args.output}")
            else:
                print(report)
        
        else:
            # Set up monitoring based on database type
            if args.database_type == "mysql":
                results = await db_setup.setup_mysql_monitoring(connection_info)
            elif args.database_type == "oracle":
                tablespaces = args.tablespaces.split(",") if args.tablespaces else None
                results = await db_setup.setup_oracle_monitoring(connection_info, tablespaces)
            elif args.database_type == "postgresql":
                results = await db_setup.setup_postgresql_monitoring(connection_info)
            elif args.database_type == "mongodb":
                results = await db_setup.setup_mongodb_monitoring(connection_info)
            else:
                print(f"❌ Database type {args.database_type} not yet implemented")
                return 1
            
            print(f"\n✅ {args.database_type.upper()} monitoring setup complete!")
            print(f"   - Services configured: {len(results['services_configured'])}")
            print(f"   - Rules created: {len(results['rules_created'])}")
            
            if args.output:
                with open(args.output, 'w') as f:
                    json.dump(results, f, indent=2)
                print(f"📁 Setup results saved to {args.output}")
    
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))