#!/usr/bin/env python3
"""
Bulk Parameter Operations Example

This script demonstrates how to use the bulk parameter management capabilities
to efficiently configure monitoring parameters across large environments.

Usage:
    python bulk_operations.py --config config.yaml --operation generate-defaults --services-file services.yaml
    python bulk_operations.py --config config.yaml --operation validate-all --environment production
    python bulk_operations.py --config config.yaml --operation migrate-parameters --source-env dev --target-env prod
"""

import asyncio
import argparse
import json
import yaml
import csv
from typing import Dict, List, Any, Optional
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import time

from checkmk_mcp_server.services.parameter_service import ParameterService
from checkmk_mcp_server.api_client import CheckmkClient
from checkmk_mcp_server.config import Config


class BulkParameterOperations:
    """Handles bulk parameter operations across large environments."""
    
    def __init__(self, parameter_service: ParameterService):
        self.parameter_service = parameter_service
        self.max_concurrent = 10
        self.batch_size = 50
    
    async def bulk_generate_defaults(self, services: List[Dict[str, Any]], 
                                   context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generate default parameters for a large list of services."""
        print(f"🚀 Generating defaults for {len(services)} services...")
        
        start_time = time.time()
        results = {
            "total_services": len(services),
            "successful": 0,
            "failed": 0,
            "results": [],
            "processing_time": 0,
            "throughput": 0
        }
        
        # Process services in batches
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def process_service(service_info: Dict[str, Any]) -> Dict[str, Any]:
            async with semaphore:
                service_name = service_info["service_name"]
                service_context = {**(context or {}), **service_info.get("context", {})}
                
                try:
                    defaults_result = await self.parameter_service.get_specialized_defaults(
                        service_name, service_context
                    )
                    
                    if defaults_result.success:
                        return {
                            "service_name": service_name,
                            "host_name": service_info.get("host_name"),
                            "success": True,
                            "handler_used": defaults_result.data["handler_used"],
                            "parameters": defaults_result.data["parameters"],
                            "metadata": defaults_result.data.get("metadata", {})
                        }
                    else:
                        return {
                            "service_name": service_name,
                            "host_name": service_info.get("host_name"),
                            "success": False,
                            "error": defaults_result.error
                        }
                
                except Exception as e:
                    return {
                        "service_name": service_name,
                        "host_name": service_info.get("host_name"),
                        "success": False,
                        "error": str(e)
                    }
        
        # Execute all tasks concurrently
        tasks = [process_service(service) for service in services]
        
        # Process in batches to avoid overwhelming the system
        for i in range(0, len(tasks), self.batch_size):
            batch = tasks[i:i + self.batch_size]
            batch_results = await asyncio.gather(*batch, return_exceptions=True)
            
            for result in batch_results:
                if isinstance(result, Exception):
                    results["results"].append({
                        "success": False,
                        "error": str(result)
                    })
                    results["failed"] += 1
                else:
                    results["results"].append(result)
                    if result["success"]:
                        results["successful"] += 1
                    else:
                        results["failed"] += 1
            
            # Progress indicator
            processed = min(i + self.batch_size, len(services))
            print(f"  📊 Processed {processed}/{len(services)} services ({processed/len(services)*100:.1f}%)")
        
        end_time = time.time()
        results["processing_time"] = end_time - start_time
        results["throughput"] = len(services) / results["processing_time"]
        
        print(f"✅ Bulk generation complete!")
        print(f"   - Successful: {results['successful']}")
        print(f"   - Failed: {results['failed']}")
        print(f"   - Processing time: {results['processing_time']:.2f}s")
        print(f"   - Throughput: {results['throughput']:.1f} services/sec")
        
        return results
    
    async def bulk_validate_parameters(self, 
                                     services_with_params: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate parameters for multiple services in bulk."""
        print(f"🔍 Validating parameters for {len(services_with_params)} services...")
        
        start_time = time.time()
        results = {
            "total_services": len(services_with_params),
            "valid": 0,
            "invalid": 0,
            "errors": 0,
            "results": [],
            "processing_time": 0,
            "validation_issues": []
        }
        
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def validate_service(service_info: Dict[str, Any]) -> Dict[str, Any]:
            async with semaphore:
                service_name = service_info["service_name"]
                parameters = service_info["parameters"]
                
                try:
                    validation_result = await self.parameter_service.validate_specialized_parameters(
                        parameters, service_name
                    )
                    
                    if validation_result.success:
                        is_valid = validation_result.data["is_valid"]
                        return {
                            "service_name": service_name,
                            "host_name": service_info.get("host_name"),
                            "success": True,
                            "is_valid": is_valid,
                            "handler_used": validation_result.data["handler_used"],
                            "errors": validation_result.data.get("errors", []),
                            "warnings": validation_result.data.get("warnings", [])
                        }
                    else:
                        return {
                            "service_name": service_name,
                            "host_name": service_info.get("host_name"),
                            "success": False,
                            "error": validation_result.error
                        }
                
                except Exception as e:
                    return {
                        "service_name": service_name,
                        "host_name": service_info.get("host_name"),
                        "success": False,
                        "error": str(e)
                    }
        
        # Execute validation tasks
        tasks = [validate_service(service) for service in services_with_params]
        
        for i in range(0, len(tasks), self.batch_size):
            batch = tasks[i:i + self.batch_size]
            batch_results = await asyncio.gather(*batch, return_exceptions=True)
            
            for result in batch_results:
                if isinstance(result, Exception):
                    results["results"].append({
                        "success": False,
                        "error": str(result)
                    })
                    results["errors"] += 1
                else:
                    results["results"].append(result)
                    if result["success"]:
                        if result["is_valid"]:
                            results["valid"] += 1
                        else:
                            results["invalid"] += 1
                            # Collect validation issues
                            for error in result.get("errors", []):
                                results["validation_issues"].append({
                                    "service": result["service_name"],
                                    "host": result.get("host_name"),
                                    "type": "error",
                                    "message": error
                                })
                    else:
                        results["errors"] += 1
            
            # Progress indicator
            processed = min(i + self.batch_size, len(services_with_params))
            print(f"  🔍 Validated {processed}/{len(services_with_params)} services ({processed/len(services_with_params)*100:.1f}%)")
        
        end_time = time.time()
        results["processing_time"] = end_time - start_time
        
        print(f"✅ Bulk validation complete!")
        print(f"   - Valid: {results['valid']}")
        print(f"   - Invalid: {results['invalid']}")
        print(f"   - Errors: {results['errors']}")
        print(f"   - Validation issues: {len(results['validation_issues'])}")
        print(f"   - Processing time: {results['processing_time']:.2f}s")
        
        return results
    
    async def bulk_create_rules(self, services_with_params: List[Dict[str, Any]], 
                              base_folder: str = "/bulk_configured") -> Dict[str, Any]:
        """Create rules for multiple services in bulk."""
        print(f"📝 Creating rules for {len(services_with_params)} services...")
        
        start_time = time.time()
        results = {
            "total_services": len(services_with_params),
            "successful": 0,
            "failed": 0,
            "results": [],
            "processing_time": 0
        }
        
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def create_rule(service_info: Dict[str, Any]) -> Dict[str, Any]:
            async with semaphore:
                service_name = service_info["service_name"]
                parameters = service_info["parameters"]
                
                try:
                    # Determine appropriate ruleset based on service type
                    handler_used = service_info.get("handler_used", "generic")
                    ruleset_mapping = {
                        "temperature": "checkgroup_parameters:temperature",
                        "database": "checkgroup_parameters:mysql",  # Default to mysql, could be more specific
                        "network_services": "checkgroup_parameters:http",
                        "custom_checks": "checkgroup_parameters:custom_checks"
                    }
                    
                    ruleset = ruleset_mapping.get(handler_used, "checkgroup_parameters:generic")
                    
                    # Create rule data
                    rule_data = {
                        "ruleset": ruleset,
                        "folder": f"{base_folder}/{handler_used}",
                        "conditions": {
                            "host_name": [service_info.get("host_name", "*")],
                            "service_description": [service_name]
                        },
                        "properties": {
                            "comment": f"Bulk configured {service_name}",
                            "description": f"Automated parameter configuration via bulk operations"
                        },
                        "value": parameters
                    }
                    
                    rule_result = await self.parameter_service.create_specialized_rule(
                        service_name, rule_data
                    )
                    
                    if rule_result.success:
                        return {
                            "service_name": service_name,
                            "host_name": service_info.get("host_name"),
                            "success": True,
                            "rule_id": rule_result.data["rule_id"],
                            "ruleset": ruleset,
                            "folder": rule_data["folder"]
                        }
                    else:
                        return {
                            "service_name": service_name,
                            "host_name": service_info.get("host_name"),
                            "success": False,
                            "error": rule_result.error
                        }
                
                except Exception as e:
                    return {
                        "service_name": service_name,
                        "host_name": service_info.get("host_name"),
                        "success": False,
                        "error": str(e)
                    }
        
        # Execute rule creation tasks
        tasks = [create_rule(service) for service in services_with_params]
        
        for i in range(0, len(tasks), self.batch_size):
            batch = tasks[i:i + self.batch_size]
            batch_results = await asyncio.gather(*batch, return_exceptions=True)
            
            for result in batch_results:
                if isinstance(result, Exception):
                    results["results"].append({
                        "success": False,
                        "error": str(result)
                    })
                    results["failed"] += 1
                else:
                    results["results"].append(result)
                    if result["success"]:
                        results["successful"] += 1
                    else:
                        results["failed"] += 1
            
            # Progress indicator
            processed = min(i + self.batch_size, len(services_with_params))
            print(f"  📝 Created {processed}/{len(services_with_params)} rules ({processed/len(services_with_params)*100:.1f}%)")
        
        end_time = time.time()
        results["processing_time"] = end_time - start_time
        
        print(f"✅ Bulk rule creation complete!")
        print(f"   - Successful: {results['successful']}")
        print(f"   - Failed: {results['failed']}")
        print(f"   - Processing time: {results['processing_time']:.2f}s")
        
        return results
    
    async def parameter_migration(self, source_services: List[Dict[str, Any]], 
                                target_context: Dict[str, Any]) -> Dict[str, Any]:
        """Migrate parameters from one environment to another with context adaptation."""
        print(f"🔄 Migrating parameters for {len(source_services)} services...")
        
        results = {
            "total_services": len(source_services),
            "migrated": 0,
            "failed": 0,
            "adaptations": [],
            "results": []
        }
        
        for service_info in source_services:
            service_name = service_info["service_name"]
            source_params = service_info["parameters"]
            
            try:
                # Get new defaults for target environment
                target_defaults = await self.parameter_service.get_specialized_defaults(
                    service_name, target_context
                )
                
                if target_defaults.success:
                    target_params = target_defaults.data["parameters"]
                    
                    # Compare and adapt parameters
                    adaptations = []
                    final_params = source_params.copy()
                    
                    # Check for parameter differences
                    for param_name, target_value in target_params.items():
                        source_value = source_params.get(param_name)
                        
                        if source_value != target_value:
                            # Adapt critical parameters based on environment
                            if param_name == "levels" and target_context.get("environment") == "production":
                                # Use stricter thresholds in production
                                if isinstance(target_value, (list, tuple)) and len(target_value) == 2:
                                    final_params[param_name] = target_value
                                    adaptations.append({
                                        "parameter": param_name,
                                        "source_value": source_value,
                                        "target_value": target_value,
                                        "reason": "Production environment requires stricter thresholds"
                                    })
                            elif param_name in ["timeout", "connection_timeout"]:
                                # Adapt timeouts based on environment
                                final_params[param_name] = target_value
                                adaptations.append({
                                    "parameter": param_name,
                                    "source_value": source_value,
                                    "target_value": target_value,
                                    "reason": "Timeout adapted for target environment"
                                })
                    
                    # Validate migrated parameters
                    validation_result = await self.parameter_service.validate_specialized_parameters(
                        final_params, service_name
                    )
                    
                    if validation_result.success and validation_result.data["is_valid"]:
                        results["results"].append({
                            "service_name": service_name,
                            "host_name": service_info.get("host_name"),
                            "success": True,
                            "source_parameters": source_params,
                            "migrated_parameters": final_params,
                            "adaptations": adaptations
                        })
                        results["migrated"] += 1
                        results["adaptations"].extend(adaptations)
                        
                        print(f"  ✅ {service_name}: {len(adaptations)} adaptations")
                    else:
                        results["results"].append({
                            "service_name": service_name,
                            "host_name": service_info.get("host_name"),
                            "success": False,
                            "error": "Parameter validation failed",
                            "validation_errors": validation_result.data.get("errors", [])
                        })
                        results["failed"] += 1
                        print(f"  ❌ {service_name}: Validation failed")
                else:
                    results["results"].append({
                        "service_name": service_name,
                        "host_name": service_info.get("host_name"),
                        "success": False,
                        "error": f"Failed to get target defaults: {target_defaults.error}"
                    })
                    results["failed"] += 1
                    print(f"  ❌ {service_name}: Failed to get defaults")
            
            except Exception as e:
                results["results"].append({
                    "service_name": service_name,
                    "host_name": service_info.get("host_name"),
                    "success": False,
                    "error": str(e)
                })
                results["failed"] += 1
                print(f"  ❌ {service_name}: Exception - {e}")
        
        print(f"✅ Parameter migration complete!")
        print(f"   - Migrated: {results['migrated']}")
        print(f"   - Failed: {results['failed']}")
        print(f"   - Total adaptations: {len(results['adaptations'])}")
        
        return results
    
    def load_services_from_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """Load service list from various file formats."""
        print(f"📂 Loading services from {file_path}")
        
        if file_path.suffix.lower() in ['.yaml', '.yml']:
            with open(file_path, 'r') as f:
                data = yaml.safe_load(f)
                return data.get('services', [])
        
        elif file_path.suffix.lower() == '.json':
            with open(file_path, 'r') as f:
                data = json.load(f)
                return data.get('services', [])
        
        elif file_path.suffix.lower() == '.csv':
            services = []
            with open(file_path, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    services.append(dict(row))
            return services
        
        else:
            raise ValueError(f"Unsupported file format: {file_path.suffix}")
    
    def export_results(self, results: Dict[str, Any], output_path: Path, format: str = "json"):
        """Export results to various formats."""
        print(f"💾 Exporting results to {output_path}")
        
        if format.lower() == "json":
            with open(output_path, 'w') as f:
                json.dump(results, f, indent=2)
        
        elif format.lower() in ["yaml", "yml"]:
            with open(output_path, 'w') as f:
                yaml.dump(results, f, default_flow_style=False)
        
        elif format.lower() == "csv":
            # Export flattened results to CSV
            if "results" in results and results["results"]:
                with open(output_path, 'w', newline='') as f:
                    if results["results"]:
                        fieldnames = results["results"][0].keys()
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        writer.writeheader()
                        for result in results["results"]:
                            # Flatten complex fields
                            flattened = {}
                            for key, value in result.items():
                                if isinstance(value, (dict, list)):
                                    flattened[key] = json.dumps(value)
                                else:
                                    flattened[key] = value
                            writer.writerow(flattened)
        
        else:
            raise ValueError(f"Unsupported export format: {format}")


async def main():
    """Main function for bulk parameter operations."""
    parser = argparse.ArgumentParser(description="Bulk Parameter Operations")
    parser.add_argument("--config", required=True, help="Configuration file path")
    parser.add_argument("--operation", required=True,
                       choices=["generate-defaults", "validate-all", "create-rules", "migrate-parameters"],
                       help="Bulk operation to perform")
    parser.add_argument("--services-file", help="File containing service definitions")
    parser.add_argument("--environment", help="Target environment context")
    parser.add_argument("--source-env", help="Source environment for migration")
    parser.add_argument("--target-env", help="Target environment for migration")
    parser.add_argument("--folder", default="/bulk_configured", help="Base folder for rule creation")
    parser.add_argument("--max-concurrent", type=int, default=10, help="Maximum concurrent operations")
    parser.add_argument("--batch-size", type=int, default=50, help="Batch size for processing")
    parser.add_argument("--output", help="Output file for results")
    parser.add_argument("--output-format", default="json", choices=["json", "yaml", "csv"],
                       help="Output format")
    
    args = parser.parse_args()
    
    # Load configuration
    config = Config.from_file(args.config)
    
    # Initialize services
    client = CheckmkClient(config.checkmk)
    parameter_service = ParameterService(client, config)
    
    # Initialize bulk operations
    bulk_ops = BulkParameterOperations(parameter_service)
    bulk_ops.max_concurrent = args.max_concurrent
    bulk_ops.batch_size = args.batch_size
    
    try:
        if args.operation == "generate-defaults":
            if not args.services_file:
                print("❌ --services-file is required for generate-defaults operation")
                return 1
            
            services = bulk_ops.load_services_from_file(Path(args.services_file))
            context = {"environment": args.environment} if args.environment else {}
            
            results = await bulk_ops.bulk_generate_defaults(services, context)
        
        elif args.operation == "validate-all":
            if not args.services_file:
                print("❌ --services-file is required for validate-all operation")
                return 1
            
            services_with_params = bulk_ops.load_services_from_file(Path(args.services_file))
            results = await bulk_ops.bulk_validate_parameters(services_with_params)
        
        elif args.operation == "create-rules":
            if not args.services_file:
                print("❌ --services-file is required for create-rules operation")
                return 1
            
            services_with_params = bulk_ops.load_services_from_file(Path(args.services_file))
            results = await bulk_ops.bulk_create_rules(services_with_params, args.folder)
        
        elif args.operation == "migrate-parameters":
            if not args.services_file or not args.target_env:
                print("❌ --services-file and --target-env are required for migrate-parameters operation")
                return 1
            
            source_services = bulk_ops.load_services_from_file(Path(args.services_file))
            target_context = {"environment": args.target_env}
            
            results = await bulk_ops.parameter_migration(source_services, target_context)
        
        # Export results
        if args.output:
            bulk_ops.export_results(results, Path(args.output), args.output_format)
            print(f"📁 Results exported to {args.output}")
        
        # Print summary
        print(f"\n📊 Summary:")
        print(f"   - Operation: {args.operation}")
        print(f"   - Total services: {results.get('total_services', 0)}")
        print(f"   - Processing time: {results.get('processing_time', 0):.2f}s")
        if 'throughput' in results:
            print(f"   - Throughput: {results['throughput']:.1f} services/sec")
    
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))