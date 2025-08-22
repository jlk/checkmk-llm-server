"""Prompt validation for MCP server.

This module contains argument validation for each prompt type,
including type checking and constraint validation.
"""

from typing import Dict, Any, Optional, Union
import logging

logger = logging.getLogger(__name__)


class PromptValidators:
    """Handles prompt argument validation and constraint checking."""

    @staticmethod
    def validate_analyze_host_health(args: Dict[str, str]) -> Dict[str, Any]:
        """Validate analyze_host_health prompt arguments.
        
        Args:
            args: Raw string arguments from prompt
            
        Returns:
            Dict[str, Any]: Validated and converted arguments
            
        Raises:
            ValueError: If validation fails
        """
        validated = {}
        
        # Validate host_name (required)
        host_name = args.get("host_name", "").strip()
        if not host_name:
            raise ValueError("host_name is required and cannot be empty")
        validated["host_name"] = host_name
        
        # Validate include_grade (optional, default True)
        include_grade_str = args.get("include_grade", "true").lower()
        if include_grade_str not in ["true", "false", "yes", "no", "1", "0"]:
            raise ValueError("include_grade must be true, false, yes, no, 1, or 0")
        validated["include_grade"] = include_grade_str in ["true", "yes", "1"]
        
        return validated

    @staticmethod
    def validate_troubleshoot_service(args: Dict[str, str]) -> Dict[str, Any]:
        """Validate troubleshoot_service prompt arguments.
        
        Args:
            args: Raw string arguments from prompt
            
        Returns:
            Dict[str, Any]: Validated and converted arguments
            
        Raises:
            ValueError: If validation fails
        """
        validated = {}
        
        # Validate host_name (required)
        host_name = args.get("host_name", "").strip()
        if not host_name:
            raise ValueError("host_name is required and cannot be empty")
        validated["host_name"] = host_name
        
        # Validate service_name (required)
        service_name = args.get("service_name", "").strip()
        if not service_name:
            raise ValueError("service_name is required and cannot be empty")
        validated["service_name"] = service_name
        
        return validated

    @staticmethod
    def validate_infrastructure_overview(args: Dict[str, str]) -> Dict[str, Any]:
        """Validate infrastructure_overview prompt arguments.
        
        Args:
            args: Raw string arguments from prompt
            
        Returns:
            Dict[str, Any]: Validated and converted arguments
            
        Raises:
            ValueError: If validation fails
        """
        validated = {}
        
        # Validate time_range_hours (optional, default 24)
        time_range_str = args.get("time_range_hours", "24")
        try:
            time_range = int(time_range_str)
            if time_range < 1 or time_range > 8760:  # Max 1 year
                raise ValueError("time_range_hours must be between 1 and 8760 (1 year)")
        except (TypeError, ValueError):
            raise ValueError("time_range_hours must be a valid integer between 1 and 8760")
        
        validated["time_range_hours"] = time_range
        
        return validated

    @staticmethod
    def validate_optimize_parameters(args: Dict[str, str]) -> Dict[str, Any]:
        """Validate optimize_parameters prompt arguments.
        
        Args:
            args: Raw string arguments from prompt
            
        Returns:
            Dict[str, Any]: Validated and converted arguments
            
        Raises:
            ValueError: If validation fails
        """
        validated = {}
        
        # Validate host_name (required)
        host_name = args.get("host_name", "").strip()
        if not host_name:
            raise ValueError("host_name is required and cannot be empty")
        validated["host_name"] = host_name
        
        # Validate service_name (required)
        service_name = args.get("service_name", "").strip()
        if not service_name:
            raise ValueError("service_name is required and cannot be empty")
        validated["service_name"] = service_name
        
        return validated

    @staticmethod
    def validate_adjust_host_check_attempts(args: Dict[str, str]) -> Dict[str, Any]:
        """Validate adjust_host_check_attempts prompt arguments.
        
        Args:
            args: Raw string arguments from prompt
            
        Returns:
            Dict[str, Any]: Validated and converted arguments
            
        Raises:
            ValueError: If validation fails
        """
        validated = {}
        
        # Validate host_name (required)
        host_name = args.get("host_name", "").strip()
        if not host_name:
            raise ValueError("host_name is required and cannot be empty")
        if host_name.lower() == "all":
            validated["host_name"] = "all"
        else:
            # Basic host name validation - could be enhanced
            if len(host_name) > 255:
                raise ValueError("host_name too long (max 255 characters)")
            validated["host_name"] = host_name
        
        # Validate max_attempts (required)
        max_attempts_str = args.get("max_attempts", "").strip()
        if not max_attempts_str:
            raise ValueError("max_attempts is required")
        
        try:
            max_attempts = int(max_attempts_str)
            if max_attempts < 1 or max_attempts > 10:
                raise ValueError("max_attempts must be between 1 and 10")
        except (TypeError, ValueError):
            raise ValueError("max_attempts must be a valid integer between 1 and 10")
        
        validated["max_attempts"] = max_attempts
        
        # Validate reason (optional)
        reason = args.get("reason", "Not specified").strip()
        if len(reason) > 500:
            raise ValueError("reason too long (max 500 characters)")
        validated["reason"] = reason or "Not specified"
        
        return validated

    @staticmethod
    def validate_adjust_host_retry_interval(args: Dict[str, str]) -> Dict[str, Any]:
        """Validate adjust_host_retry_interval prompt arguments.
        
        Args:
            args: Raw string arguments from prompt
            
        Returns:
            Dict[str, Any]: Validated and converted arguments
            
        Raises:
            ValueError: If validation fails
        """
        validated = {}
        
        # Validate host_name (required)
        host_name = args.get("host_name", "").strip()
        if not host_name:
            raise ValueError("host_name is required and cannot be empty")
        if host_name.lower() == "all":
            validated["host_name"] = "all"
        else:
            if len(host_name) > 255:
                raise ValueError("host_name too long (max 255 characters)")
            validated["host_name"] = host_name
        
        # Validate retry_interval (required)
        retry_interval_str = args.get("retry_interval", "").strip()
        if not retry_interval_str:
            raise ValueError("retry_interval is required")
        
        try:
            retry_interval = float(retry_interval_str)
            if retry_interval < 0.1 or retry_interval > 60:
                raise ValueError("retry_interval must be between 0.1 and 60 minutes")
        except (TypeError, ValueError):
            raise ValueError("retry_interval must be a valid number between 0.1 and 60")
        
        validated["retry_interval"] = retry_interval
        
        # Validate reason (optional)
        reason = args.get("reason", "Not specified").strip()
        if len(reason) > 500:
            raise ValueError("reason too long (max 500 characters)")
        validated["reason"] = reason or "Not specified"
        
        return validated

    @staticmethod
    def validate_adjust_host_check_timeout(args: Dict[str, str]) -> Dict[str, Any]:
        """Validate adjust_host_check_timeout prompt arguments.
        
        Args:
            args: Raw string arguments from prompt
            
        Returns:
            Dict[str, Any]: Validated and converted arguments
            
        Raises:
            ValueError: If validation fails
        """
        validated = {}
        
        # Validate host_name (required)
        host_name = args.get("host_name", "").strip()
        if not host_name:
            raise ValueError("host_name is required and cannot be empty")
        if host_name.lower() == "all":
            validated["host_name"] = "all"
        else:
            if len(host_name) > 255:
                raise ValueError("host_name too long (max 255 characters)")
            validated["host_name"] = host_name
        
        # Validate timeout_seconds (required)
        timeout_seconds_str = args.get("timeout_seconds", "").strip()
        if not timeout_seconds_str:
            raise ValueError("timeout_seconds is required")
        
        try:
            timeout_seconds = int(timeout_seconds_str)
            if timeout_seconds < 1 or timeout_seconds > 60:
                raise ValueError("timeout_seconds must be between 1 and 60")
        except (TypeError, ValueError):
            raise ValueError("timeout_seconds must be a valid integer between 1 and 60")
        
        validated["timeout_seconds"] = timeout_seconds
        
        # Validate check_type (optional, default 'icmp')
        check_type = args.get("check_type", "icmp").lower().strip()
        if check_type not in ["icmp", "snmp", "all"]:
            raise ValueError("check_type must be 'icmp', 'snmp', or 'all'")
        validated["check_type"] = check_type
        
        # Validate reason (optional)
        reason = args.get("reason", "Not specified").strip()
        if len(reason) > 500:
            raise ValueError("reason too long (max 500 characters)")
        validated["reason"] = reason or "Not specified"
        
        return validated

    @staticmethod
    def validate_prompt_arguments(prompt_name: str, args: Dict[str, str]) -> Dict[str, Any]:
        """Central validation dispatcher for all prompt types.
        
        Args:
            prompt_name: Name of the prompt to validate
            args: Raw string arguments from prompt
            
        Returns:
            Dict[str, Any]: Validated and converted arguments
            
        Raises:
            ValueError: If validation fails
            KeyError: If prompt_name is unknown
        """
        validators = {
            "analyze_host_health": PromptValidators.validate_analyze_host_health,
            "troubleshoot_service": PromptValidators.validate_troubleshoot_service,
            "infrastructure_overview": PromptValidators.validate_infrastructure_overview,
            "optimize_parameters": PromptValidators.validate_optimize_parameters,
            "adjust_host_check_attempts": PromptValidators.validate_adjust_host_check_attempts,
            "adjust_host_retry_interval": PromptValidators.validate_adjust_host_retry_interval,
            "adjust_host_check_timeout": PromptValidators.validate_adjust_host_check_timeout,
        }
        
        if prompt_name not in validators:
            available = ", ".join(validators.keys())
            raise KeyError(f"Unknown prompt '{prompt_name}'. Available: {available}")
        
        try:
            return validators[prompt_name](args)
        except Exception as e:
            logger.error(f"Validation failed for prompt '{prompt_name}': {str(e)}")
            raise ValueError(f"Validation failed for '{prompt_name}': {str(e)}")

    @staticmethod
    def get_validation_schema(prompt_name: str) -> Dict[str, Any]:
        """Get validation schema for a prompt.
        
        Args:
            prompt_name: Name of the prompt
            
        Returns:
            Dict[str, Any]: Schema describing validation rules
            
        Raises:
            KeyError: If prompt_name is unknown
        """
        schemas = {
            "analyze_host_health": {
                "host_name": {
                    "type": "string",
                    "required": True,
                    "min_length": 1,
                    "max_length": 255,
                    "description": "Name of the host to analyze"
                },
                "include_grade": {
                    "type": "boolean", 
                    "required": False,
                    "default": True,
                    "description": "Include health grade (A+ through F)"
                }
            },
            "troubleshoot_service": {
                "host_name": {
                    "type": "string",
                    "required": True,
                    "min_length": 1,
                    "max_length": 255,
                    "description": "Host name where the service is running"
                },
                "service_name": {
                    "type": "string",
                    "required": True,
                    "min_length": 1,
                    "max_length": 255,
                    "description": "Name of the service to troubleshoot"
                }
            },
            "infrastructure_overview": {
                "time_range_hours": {
                    "type": "integer",
                    "required": False,
                    "default": 24,
                    "minimum": 1,
                    "maximum": 8760,
                    "description": "Time range in hours for the analysis"
                }
            },
            "optimize_parameters": {
                "host_name": {
                    "type": "string",
                    "required": True,
                    "min_length": 1,
                    "max_length": 255,
                    "description": "Host name where the service is running"
                },
                "service_name": {
                    "type": "string",
                    "required": True,
                    "min_length": 1,
                    "max_length": 255,
                    "description": "Name of the service to optimize"
                }
            },
            "adjust_host_check_attempts": {
                "host_name": {
                    "type": "string",
                    "required": True,
                    "min_length": 1,
                    "max_length": 255,
                    "special_values": ["all"],
                    "description": "Name of the host to configure (or 'all' for global rule)"
                },
                "max_attempts": {
                    "type": "integer",
                    "required": True,
                    "minimum": 1,
                    "maximum": 10,
                    "description": "Maximum number of check attempts before host is considered down"
                },
                "reason": {
                    "type": "string",
                    "required": False,
                    "default": "Not specified",
                    "max_length": 500,
                    "description": "Reason for adjustment"
                }
            },
            "adjust_host_retry_interval": {
                "host_name": {
                    "type": "string",
                    "required": True,
                    "min_length": 1,
                    "max_length": 255,
                    "special_values": ["all"],
                    "description": "Name of the host to configure (or 'all' for global rule)"
                },
                "retry_interval": {
                    "type": "float",
                    "required": True,
                    "minimum": 0.1,
                    "maximum": 60,
                    "description": "Retry interval in minutes"
                },
                "reason": {
                    "type": "string",
                    "required": False,
                    "default": "Not specified",
                    "max_length": 500,
                    "description": "Reason for adjustment"
                }
            },
            "adjust_host_check_timeout": {
                "host_name": {
                    "type": "string",
                    "required": True,
                    "min_length": 1,
                    "max_length": 255,
                    "special_values": ["all"],
                    "description": "Name of the host to configure (or 'all' for global rule)"
                },
                "timeout_seconds": {
                    "type": "integer",
                    "required": True,
                    "minimum": 1,
                    "maximum": 60,
                    "description": "Timeout in seconds"
                },
                "check_type": {
                    "type": "string",
                    "required": False,
                    "default": "icmp",
                    "enum": ["icmp", "snmp", "all"],
                    "description": "Type of check: 'icmp', 'snmp', or 'all'"
                },
                "reason": {
                    "type": "string",
                    "required": False,
                    "default": "Not specified",
                    "max_length": 500,
                    "description": "Reason for adjustment"
                }
            }
        }
        
        if prompt_name not in schemas:
            available = ", ".join(schemas.keys())
            raise KeyError(f"No schema for prompt '{prompt_name}'. Available: {available}")
        
        return schemas[prompt_name]