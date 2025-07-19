"""Parameter-related command implementations."""

import logging
from typing import Dict, Any, Optional

from .base import BaseCommand, CommandContext, CommandResult, CommandCategory
from ..service_parameters import ServiceParameterManager


class ParameterCommand(BaseCommand):
    """Base class for parameter-related commands."""
    
    def __init__(self, parameter_manager: ServiceParameterManager):
        super().__init__()
        self.parameter_manager = parameter_manager
        self.logger = logging.getLogger(__name__)
    
    @property
    def category(self) -> CommandCategory:
        return CommandCategory.PARAMETER


class ViewDefaultParametersCommand(ParameterCommand):
    """Command to view default parameters for service types."""
    
    @property
    def name(self) -> str:
        return "view_default_parameters"
    
    @property
    def description(self) -> str:
        return "View default parameters for a service type (cpu, memory, disk, etc.)"
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            'service_type': {
                'type': str,
                'required': False,
                'default': 'cpu',
                'description': 'Service type to view parameters for (cpu, memory, filesystem, disk, network)'
            }
        }
    
    def _custom_validate(self, context: CommandContext) -> Optional[CommandResult]:
        """Validate service type parameter."""
        service_type = context.get_parameter('service_type', 'cpu')
        valid_types = ['cpu', 'memory', 'filesystem', 'disk', 'network']
        
        if service_type not in valid_types:
            return CommandResult.error_result(
                f"Invalid service type '{service_type}'. Valid types: {', '.join(valid_types)}"
            )
        
        return None
    
    def execute(self, context: CommandContext) -> CommandResult:
        """Execute the view default parameters command."""
        try:
            service_type = context.get_parameter('service_type', 'cpu')
            
            # Get default parameters
            default_params = self.parameter_manager.get_default_parameters(service_type)
            
            if not default_params:
                return CommandResult.error_result(
                    f"No default parameters found for service type: {service_type}"
                )
            
            result_message = f"📊 Default Parameters for {service_type.upper()} services:\n\n"
            
            # Format parameters nicely
            if 'levels' in default_params:
                warning, critical = default_params['levels']
                result_message += f"⚠️  Warning Threshold: {warning:.1f}%\n"
                result_message += f"❌ Critical Threshold: {critical:.1f}%\n"
            
            if 'average' in default_params:
                result_message += f"📈 Averaging Period: {default_params['average']} minutes\n"
            
            if 'magic_normsize' in default_params:
                result_message += f"💾 Magic Normsize: {default_params['magic_normsize']} GB\n"
            
            if 'magic' in default_params:
                result_message += f"🎯 Magic Factor: {default_params['magic']}\n"
            
            # Show applicable ruleset
            ruleset_map = self.parameter_manager.PARAMETER_RULESETS.get(service_type, {})
            default_ruleset = ruleset_map.get('default', 'Unknown')
            result_message += f"\n📋 Default Ruleset: {default_ruleset}"
            
            return CommandResult.success_result(
                data={
                    'service_type': service_type,
                    'parameters': default_params,
                    'ruleset': default_ruleset
                },
                message=result_message
            )
            
        except Exception as e:
            self.logger.error(f"Error viewing default parameters: {e}")
            return CommandResult.error_result(f"Error viewing default parameters: {e}")


class ViewServiceParametersCommand(ParameterCommand):
    """Command to view parameters for a specific service."""
    
    @property
    def name(self) -> str:
        return "view_service_parameters"
    
    @property
    def description(self) -> str:
        return "View effective parameters for a specific service"
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            'host_name': {
                'type': str,
                'required': True,
                'description': 'Hostname where the service is running'
            },
            'service_description': {
                'type': str,
                'required': True,
                'description': 'Description/name of the service'
            }
        }
    
    def execute(self, context: CommandContext) -> CommandResult:
        """Execute the view service parameters command."""
        try:
            host_name = context.require_parameter('host_name')
            service_description = context.require_parameter('service_description')
            
            # Get service parameters
            params = self.parameter_manager.get_service_parameters(host_name, service_description)
            
            if not params:
                return CommandResult.error_result(
                    f"No parameters found for {host_name}/{service_description}"
                )
            
            result_message = f"📊 Effective Parameters for {host_name}/{service_description}:\n\n"
            
            # Format parameters
            if 'parameters' in params:
                param_data = params['parameters']
                
                if 'levels' in param_data:
                    warning, critical = param_data['levels']
                    result_message += f"⚠️  Warning: {warning:.1f}%\n"
                    result_message += f"❌ Critical: {critical:.1f}%\n"
                
                if 'average' in param_data:
                    result_message += f"📈 Average: {param_data['average']} minutes\n"
                
                if 'magic_normsize' in param_data:
                    result_message += f"💾 Magic Normsize: {param_data['magic_normsize']} GB\n"
            
            # Show source
            source = params.get('source', 'Unknown')
            result_message += f"\n📋 Source: {source}"
            
            return CommandResult.success_result(
                data={
                    'host_name': host_name,
                    'service_description': service_description,
                    'parameters': params
                },
                message=result_message
            )
            
        except Exception as e:
            self.logger.error(f"Error viewing service parameters: {e}")
            return CommandResult.error_result(f"Error viewing service parameters: {e}")


class SetServiceParametersCommand(ParameterCommand):
    """Command to set/override service parameters."""
    
    @property
    def name(self) -> str:
        return "set_service_parameters"
    
    @property
    def description(self) -> str:
        return "Set or override parameters for a specific service"
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            'host_name': {
                'type': str,
                'required': True,
                'description': 'Hostname where the service is running'
            },
            'service_description': {
                'type': str,
                'required': True,
                'description': 'Description/name of the service'
            },
            'warning_value': {
                'type': (int, float),
                'required': False,
                'description': 'Warning threshold value'
            },
            'critical_value': {
                'type': (int, float),
                'required': False,
                'description': 'Critical threshold value'
            },
            'parameter_type': {
                'type': str,
                'required': False,
                'default': 'both',
                'description': 'Type of parameter to set (warning, critical, both)'
            },
            'comment': {
                'type': str,
                'required': False,
                'description': 'Comment for the parameter override rule'
            }
        }
    
    def _custom_validate(self, context: CommandContext) -> Optional[CommandResult]:
        """Validate parameter setting parameters."""
        warning_value = context.get_parameter('warning_value')
        critical_value = context.get_parameter('critical_value')
        parameter_type = context.get_parameter('parameter_type', 'both')
        
        # Check parameter type
        valid_types = ['warning', 'critical', 'both']
        if parameter_type not in valid_types:
            return CommandResult.error_result(
                f"Invalid parameter type '{parameter_type}'. Valid types: {', '.join(valid_types)}"
            )
        
        # Check that at least one threshold is provided
        if warning_value is None and critical_value is None:
            return CommandResult.error_result(
                "At least one of warning_value or critical_value must be provided"
            )
        
        # Validate threshold values
        if warning_value is not None and (warning_value < 0 or warning_value > 100):
            return CommandResult.error_result(
                "Warning value must be between 0 and 100"
            )
        
        if critical_value is not None and (critical_value < 0 or critical_value > 100):
            return CommandResult.error_result(
                "Critical value must be between 0 and 100"
            )
        
        # Check logical order (warning < critical for most services)
        if (warning_value is not None and critical_value is not None and 
            warning_value >= critical_value):
            return CommandResult.error_result(
                "Warning threshold should typically be less than critical threshold"
            )
        
        return None
    
    def execute(self, context: CommandContext) -> CommandResult:
        """Execute the set service parameters command."""
        try:
            host_name = context.require_parameter('host_name')
            service_description = context.require_parameter('service_description')
            warning_value = context.get_parameter('warning_value')
            critical_value = context.get_parameter('critical_value')
            parameter_type = context.get_parameter('parameter_type', 'both')
            comment = context.get_parameter('comment')
            
            # Determine thresholds to set
            if parameter_type == 'warning' and warning_value is not None:
                # Only setting warning, need to get current critical
                current_params = self.parameter_manager.get_service_parameters(host_name, service_description)
                current_levels = current_params.get('parameters', {}).get('levels', (80.0, 90.0))
                critical_value = current_levels[1] if len(current_levels) > 1 else 90.0
            elif parameter_type == 'critical' and critical_value is not None:
                # Only setting critical, need to get current warning
                current_params = self.parameter_manager.get_service_parameters(host_name, service_description)
                current_levels = current_params.get('parameters', {}).get('levels', (80.0, 90.0))
                warning_value = current_levels[0] if len(current_levels) > 0 else 80.0
            
            # Create simple override
            if not comment:
                comment = f"Override thresholds for {service_description} on {host_name}"
            
            rule_id = self.parameter_manager.create_simple_override(
                host_name=host_name,
                service_name=service_description,
                warning=warning_value,
                critical=critical_value,
                comment=comment
            )
            
            result_message = f"✅ Created parameter override for {host_name}/{service_description}\n"
            if warning_value is not None:
                result_message += f"⚠️  Warning: {warning_value:.1f}%\n"
            if critical_value is not None:
                result_message += f"❌ Critical: {critical_value:.1f}%\n"
            result_message += f"🆔 Rule ID: {rule_id}\n"
            result_message += f"💬 Comment: {comment}\n"
            result_message += "⏱️  Changes will take effect after next service check cycle"
            
            return CommandResult.success_result(
                data={
                    'host_name': host_name,
                    'service_description': service_description,
                    'warning_value': warning_value,
                    'critical_value': critical_value,
                    'rule_id': rule_id,
                    'comment': comment
                },
                message=result_message
            )
            
        except Exception as e:
            self.logger.error(f"Error setting service parameters: {e}")
            return CommandResult.error_result(f"Error setting service parameters: {e}")


class CreateParameterRuleCommand(ParameterCommand):
    """Command to create a new parameter rule."""
    
    @property
    def name(self) -> str:
        return "create_parameter_rule"
    
    @property
    def description(self) -> str:
        return "Create a new parameter rule for a service type"
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            'service_type': {
                'type': str,
                'required': False,
                'default': 'cpu',
                'description': 'Service type for the rule (cpu, memory, filesystem, disk, network)'
            },
            'comment': {
                'type': str,
                'required': False,
                'description': 'Comment describing the rule purpose'
            }
        }
    
    def execute(self, context: CommandContext) -> CommandResult:
        """Execute the create parameter rule command."""
        try:
            service_type = context.get_parameter('service_type', 'cpu')
            comment = context.get_parameter('comment', f"Parameter rule for {service_type} services")
            
            # Get default parameters for the service type
            default_params = self.parameter_manager.get_default_parameters(service_type)
            if not default_params:
                return CommandResult.error_result(
                    f"No default parameters found for service type: {service_type}"
                )
            
            # Determine ruleset
            ruleset_map = self.parameter_manager.PARAMETER_RULESETS.get(service_type, {})
            ruleset = ruleset_map.get('default')
            if not ruleset:
                return CommandResult.error_result(
                    f"No ruleset found for service type: {service_type}"
                )
            
            # For now, create a general rule - in practice this would need more specific conditions
            result_message = f"📋 To create a parameter rule for {service_type} services:\n\n"
            result_message += f"🔧 Service Type: {service_type}\n"
            result_message += f"📊 Ruleset: {ruleset}\n"
            result_message += f"📝 Default Parameters: {default_params}\n\n"
            result_message += "ℹ️  Use specific host/service combinations for actual rule creation.\n"
            result_message += f"Example: 'set {service_type} warning to 85% for server01'"
            
            return CommandResult.success_result(
                data={
                    'service_type': service_type,
                    'ruleset': ruleset,
                    'default_parameters': default_params,
                    'comment': comment
                },
                message=result_message
            )
            
        except Exception as e:
            self.logger.error(f"Error creating parameter rule: {e}")
            return CommandResult.error_result(f"Error creating parameter rule: {e}")


class ListParameterRulesCommand(ParameterCommand):
    """Command to list parameter rules."""
    
    @property
    def name(self) -> str:
        return "list_parameter_rules"
    
    @property
    def description(self) -> str:
        return "List existing parameter rules, optionally for a specific ruleset"
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            'ruleset_name': {
                'type': str,
                'required': False,
                'description': 'Specific ruleset to list rules for'
            }
        }
    
    def execute(self, context: CommandContext) -> CommandResult:
        """Execute the list parameter rules command."""
        try:
            ruleset_name = context.get_parameter('ruleset_name')
            
            # List available rulesets if no specific ruleset requested
            if not ruleset_name:
                rulesets = self.parameter_manager.list_parameter_rulesets()
                
                result_message = f"📋 Available Parameter Rulesets ({len(rulesets)}):\n\n"
                
                # Group by category
                categories = {}
                for ruleset in rulesets:
                    ruleset_id = ruleset.get('id', 'Unknown')
                    # Categorize based on name
                    if 'cpu' in ruleset_id:
                        categories.setdefault('CPU', []).append(ruleset_id)
                    elif 'memory' in ruleset_id:
                        categories.setdefault('Memory', []).append(ruleset_id)
                    elif 'filesystem' in ruleset_id:
                        categories.setdefault('Filesystem', []).append(ruleset_id)
                    elif 'interface' in ruleset_id or 'network' in ruleset_id:
                        categories.setdefault('Network', []).append(ruleset_id)
                    else:
                        categories.setdefault('Other', []).append(ruleset_id)
                
                for category, rulesets_list in categories.items():
                    result_message += f"📁 {category}:\n"
                    for ruleset_id in rulesets_list:
                        result_message += f"  📊 {ruleset_id}\n"
                    result_message += "\n"
                
                result_message += "💡 Specify a ruleset to see its rules: 'show rules for cpu_utilization_linux'"
                
                return CommandResult.success_result(
                    data={'rulesets': rulesets, 'categories': categories},
                    message=result_message
                )
            else:
                # List rules for specific ruleset
                rules = self.parameter_manager.checkmk_client.list_rules(ruleset_name)
                
                if not rules:
                    return CommandResult.success_result(
                        data={'ruleset': ruleset_name, 'rules': []},
                        message=f"📋 No rules found for ruleset: {ruleset_name}"
                    )
                
                result_message = f"📋 Rules for {ruleset_name} ({len(rules)}):\n\n"
                
                for rule in rules[:10]:  # Show first 10 rules
                    rule_id = rule.get('id', 'Unknown')
                    extensions = rule.get('extensions', {})
                    conditions = extensions.get('conditions', {})
                    properties = extensions.get('properties', {})
                    
                    result_message += f"🔧 Rule {rule_id}\n"
                    
                    # Show conditions
                    if conditions.get('host_name'):
                        hosts = ', '.join(conditions['host_name'][:3])
                        if len(conditions['host_name']) > 3:
                            hosts += f" (and {len(conditions['host_name']) - 3} more)"
                        result_message += f"  🖥️  Hosts: {hosts}\n"
                    
                    if conditions.get('service_description'):
                        services = ', '.join(conditions['service_description'][:2])
                        if len(conditions['service_description']) > 2:
                            services += f" (and {len(conditions['service_description']) - 2} more)"
                        result_message += f"  🔧 Services: {services}\n"
                    
                    if properties.get('description'):
                        desc = properties['description'][:50]
                        if len(properties['description']) > 50:
                            desc += "..."
                        result_message += f"  💬 Description: {desc}\n"
                    
                    result_message += "\n"
                
                if len(rules) > 10:
                    result_message += f"... and {len(rules) - 10} more rules"
                
                return CommandResult.success_result(
                    data={'ruleset': ruleset_name, 'rules': rules},
                    message=result_message
                )
            
        except Exception as e:
            self.logger.error(f"Error listing parameter rules: {e}")
            return CommandResult.error_result(f"Error listing parameter rules: {e}")


class DeleteParameterRuleCommand(ParameterCommand):
    """Command to delete a parameter rule."""
    
    @property
    def name(self) -> str:
        return "delete_parameter_rule"
    
    @property
    def description(self) -> str:
        return "Delete a parameter rule by its ID"
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            'rule_id': {
                'type': str,
                'required': True,
                'description': 'ID of the rule to delete'
            }
        }
    
    def execute(self, context: CommandContext) -> CommandResult:
        """Execute the delete parameter rule command."""
        try:
            rule_id = context.require_parameter('rule_id')
            
            # Get rule info before deletion
            try:
                rule_info = self.parameter_manager.checkmk_client.get_rule(rule_id)
                extensions = rule_info.get('extensions', {})
                ruleset = extensions.get('ruleset', 'Unknown')
                conditions = extensions.get('conditions', {})
            except Exception:
                ruleset = 'Unknown'
                conditions = {}
            
            # Delete the rule
            self.parameter_manager.delete_parameter_rule(rule_id)
            
            result_message = f"✅ Deleted parameter rule: {rule_id}\n"
            result_message += f"📊 Ruleset: {ruleset}\n"
            
            if conditions.get('host_name'):
                hosts = ', '.join(conditions['host_name'][:3])
                result_message += f"🖥️  Affected Hosts: {hosts}\n"
            
            result_message += "⏱️  Changes will take effect after configuration activation"
            
            return CommandResult.success_result(
                data={'rule_id': rule_id, 'ruleset': ruleset, 'conditions': conditions},
                message=result_message
            )
            
        except Exception as e:
            self.logger.error(f"Error deleting parameter rule: {e}")
            return CommandResult.error_result(f"Error deleting parameter rule: {e}")


class DiscoverRulesetCommand(ParameterCommand):
    """Command to discover the appropriate ruleset for a service."""
    
    @property
    def name(self) -> str:
        return "discover_ruleset"
    
    @property
    def description(self) -> str:
        return "Find the appropriate ruleset for a service"
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            'host_name': {
                'type': str,
                'required': False,
                'description': 'Hostname (optional for context)'
            },
            'service_description': {
                'type': str,
                'required': True,
                'description': 'Description/name of the service'
            }
        }
    
    def execute(self, context: CommandContext) -> CommandResult:
        """Execute the discover ruleset command."""
        try:
            host_name = context.get_parameter('host_name')
            service_description = context.require_parameter('service_description')
            
            # Discover ruleset
            ruleset = self.parameter_manager.discover_service_ruleset(
                host_name or 'unknown', 
                service_description
            )
            
            if not ruleset:
                return CommandResult.error_result(
                    f"Could not determine appropriate ruleset for service: {service_description}"
                )
            
            result_message = f"🔍 Service: {service_description}\n"
            if host_name:
                result_message += f"🖥️  Host: {host_name}\n"
            result_message += f"📋 Recommended Ruleset: {ruleset}\n\n"
            
            # Show default parameters for this ruleset
            service_type = ('cpu' if 'cpu' in ruleset else 
                          'memory' if 'memory' in ruleset else 
                          'filesystem' if 'filesystem' in ruleset else 
                          'network')
            default_params = self.parameter_manager.get_default_parameters(service_type)
            
            if default_params:
                result_message += "📊 Default Parameters:\n"
                if 'levels' in default_params:
                    warning, critical = default_params['levels']
                    result_message += f"  ⚠️  Warning: {warning:.1f}%\n"
                    result_message += f"  ❌ Critical: {critical:.1f}%\n"
                
                if 'average' in default_params:
                    result_message += f"  📈 Average: {default_params['average']} min\n"
            
            result_message += f"\n💡 To override parameters: 'set {service_type} warning to 85% for {host_name or 'HOSTNAME'}'"
            
            return CommandResult.success_result(
                data={
                    'service_description': service_description,
                    'host_name': host_name,
                    'ruleset': ruleset,
                    'service_type': service_type,
                    'default_parameters': default_params
                },
                message=result_message
            )
            
        except Exception as e:
            self.logger.error(f"Error discovering ruleset: {e}")
            return CommandResult.error_result(f"Error discovering ruleset: {e}")