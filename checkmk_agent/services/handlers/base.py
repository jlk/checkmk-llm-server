"""
Base parameter handler class providing common functionality for specialized handlers.
"""

import logging
import re
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass
from enum import Enum


class ValidationSeverity(Enum):
    """Validation message severity levels."""
    INFO = "info"
    WARNING = "warning" 
    ERROR = "error"


@dataclass
class ValidationMessage:
    """A validation message with severity and context."""
    severity: ValidationSeverity
    message: str
    field: Optional[str] = None
    suggestion: Optional[str] = None


@dataclass
class HandlerResult:
    """Result of handler processing."""
    success: bool
    parameters: Optional[Dict[str, Any]] = None
    normalized_parameters: Optional[Dict[str, Any]] = None
    validation_messages: List[ValidationMessage] = None
    error: Optional[str] = None
    
    def __post_init__(self):
        if self.validation_messages is None:
            self.validation_messages = []
    
    @property
    def errors(self) -> List[ValidationMessage]:
        """Get error messages only."""
        return [msg for msg in self.validation_messages if msg.severity == ValidationSeverity.ERROR]
    
    @property
    def warnings(self) -> List[ValidationMessage]:
        """Get warning messages only."""
        return [msg for msg in self.validation_messages if msg.severity == ValidationSeverity.WARNING]
    
    @property
    def is_valid(self) -> bool:
        """Check if result has no errors."""
        return self.success and len(self.errors) == 0


class BaseParameterHandler(ABC):
    """
    Base class for specialized parameter handlers.
    
    Each handler specializes in understanding the parameters for specific
    types of monitoring services (e.g., temperature, databases, network services).
    """
    
    def __init__(self):
        """Initialize the parameter handler."""
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique name for this handler."""
        pass
    
    @property
    @abstractmethod
    def service_patterns(self) -> List[str]:
        """
        List of regex patterns that match service names this handler supports.
        
        Returns:
            List of regex patterns (strings)
        """
        pass
    
    @property
    @abstractmethod
    def supported_rulesets(self) -> List[str]:
        """
        List of Checkmk rulesets this handler supports.
        
        Returns:
            List of ruleset names (e.g., 'checkgroup_parameters:temperature')
        """
        pass
    
    def matches_service(self, service_name: str) -> bool:
        """
        Check if this handler can process the given service.
        
        Args:
            service_name: Name of the service to check
            
        Returns:
            True if this handler can process the service
        """
        service_lower = service_name.lower()
        
        for pattern in self.service_patterns:
            if re.search(pattern, service_lower):
                return True
        
        return False
    
    def matches_ruleset(self, ruleset: str) -> bool:
        """
        Check if this handler supports the given ruleset.
        
        Args:
            ruleset: Ruleset name to check
            
        Returns:
            True if this handler supports the ruleset
        """
        return ruleset in self.supported_rulesets
    
    @abstractmethod
    def get_default_parameters(self, service_name: str, context: Optional[Dict[str, Any]] = None) -> HandlerResult:
        """
        Get specialized default parameters for a service.
        
        Args:
            service_name: Name of the service
            context: Optional context information (host details, etc.)
            
        Returns:
            HandlerResult containing default parameters
        """
        pass
    
    @abstractmethod
    def validate_parameters(
        self, 
        parameters: Dict[str, Any], 
        service_name: str,
        context: Optional[Dict[str, Any]] = None
    ) -> HandlerResult:
        """
        Validate and normalize parameters for a service.
        
        Args:
            parameters: Parameters to validate
            service_name: Name of the service
            context: Optional context information
            
        Returns:
            HandlerResult with validation results and normalized parameters
        """
        pass
    
    def get_parameter_info(self, parameter_name: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a specific parameter.
        
        Args:
            parameter_name: Name of the parameter
            
        Returns:
            Parameter information or None if not found
        """
        return None
    
    def suggest_parameters(
        self, 
        service_name: str, 
        current_parameters: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Suggest parameters for optimization or improvement.
        
        Args:
            service_name: Name of the service
            current_parameters: Current parameter values
            context: Optional context information
            
        Returns:
            List of parameter suggestions
        """
        return []
    
    def _create_validation_message(
        self, 
        severity: ValidationSeverity, 
        message: str, 
        field: Optional[str] = None,
        suggestion: Optional[str] = None
    ) -> ValidationMessage:
        """Helper to create validation messages."""
        return ValidationMessage(
            severity=severity,
            message=message,
            field=field,
            suggestion=suggestion
        )
    
    def _validate_threshold_tuple(
        self, 
        value: Any, 
        field_name: str,
        min_values: int = 2,
        max_values: int = 2,
        numeric_type: type = float
    ) -> List[ValidationMessage]:
        """
        Common validation for threshold tuples like (warning, critical).
        
        Args:
            value: Value to validate
            field_name: Name of the field being validated
            min_values: Minimum number of values required
            max_values: Maximum number of values allowed
            numeric_type: Expected numeric type (int or float)
            
        Returns:
            List of validation messages
        """
        messages = []
        
        if not isinstance(value, (list, tuple)):
            messages.append(self._create_validation_message(
                ValidationSeverity.ERROR,
                f"{field_name} must be a tuple/list of thresholds",
                field_name,
                f"Use format like ({numeric_type.__name__}, {numeric_type.__name__})"
            ))
            return messages
        
        if len(value) < min_values:
            messages.append(self._create_validation_message(
                ValidationSeverity.ERROR,
                f"{field_name} must have at least {min_values} values",
                field_name
            ))
            return messages
        
        if len(value) > max_values:
            messages.append(self._create_validation_message(
                ValidationSeverity.WARNING,
                f"{field_name} has more than {max_values} values, only first {max_values} will be used",
                field_name
            ))
        
        # Validate numeric values
        for i, threshold in enumerate(value[:max_values]):
            try:
                numeric_type(threshold)
            except (TypeError, ValueError):
                messages.append(self._create_validation_message(
                    ValidationSeverity.ERROR,
                    f"{field_name}[{i}] must be a {numeric_type.__name__}",
                    field_name
                ))
        
        # Validate threshold ordering (warning < critical for upper thresholds)
        if len(value) >= 2 and field_name.endswith('levels') and not field_name.endswith('levels_lower'):
            try:
                warn, crit = numeric_type(value[0]), numeric_type(value[1])
                if warn >= crit:
                    messages.append(self._create_validation_message(
                        ValidationSeverity.ERROR,
                        f"{field_name}: warning threshold must be less than critical threshold",
                        field_name,
                        f"Try ({warn}, {warn + 10}) or adjust thresholds appropriately"
                    ))
            except (TypeError, ValueError):
                pass  # Already caught above
        
        # Validate reverse threshold ordering for lower thresholds
        elif len(value) >= 2 and field_name.endswith('levels_lower'):
            try:
                warn, crit = numeric_type(value[0]), numeric_type(value[1])
                if warn <= crit:
                    messages.append(self._create_validation_message(
                        ValidationSeverity.ERROR,
                        f"{field_name}: warning threshold must be greater than critical threshold for lower limits",
                        field_name,
                        f"Try ({crit + 5}, {crit}) or adjust thresholds appropriately"
                    ))
            except (TypeError, ValueError):
                pass  # Already caught above
        
        return messages
    
    def _normalize_threshold_tuple(
        self, 
        value: Any, 
        numeric_type: type = float,
        length: int = 2
    ) -> Tuple[Union[int, float], ...]:
        """
        Normalize a threshold tuple to the specified type and length.
        
        Args:
            value: Value to normalize
            numeric_type: Target numeric type
            length: Target tuple length
            
        Returns:
            Normalized tuple
        """
        if not isinstance(value, (list, tuple)):
            raise ValueError("Value must be a list or tuple")
        
        normalized = []
        for i in range(length):
            if i < len(value):
                normalized.append(numeric_type(value[i]))
            else:
                # Pad with reasonable defaults
                normalized.append(numeric_type(0))
        
        return tuple(normalized)
    
    def _validate_percentage(self, value: Any, field_name: str, allow_over_100: bool = False) -> List[ValidationMessage]:
        """
        Validate a percentage value.
        
        Args:
            value: Value to validate
            field_name: Name of the field
            allow_over_100: Whether to allow values over 100%
            
        Returns:
            List of validation messages
        """
        messages = []
        
        try:
            num_value = float(value)
            
            if num_value < 0:
                messages.append(self._create_validation_message(
                    ValidationSeverity.ERROR,
                    f"{field_name} cannot be negative",
                    field_name
                ))
            
            if not allow_over_100 and num_value > 100:
                messages.append(self._create_validation_message(
                    ValidationSeverity.ERROR,
                    f"{field_name} cannot exceed 100%",
                    field_name
                ))
            elif allow_over_100 and num_value > 1000:
                messages.append(self._create_validation_message(
                    ValidationSeverity.WARNING,
                    f"{field_name} value {num_value}% seems unusually high",
                    field_name
                ))
                
        except (TypeError, ValueError):
            messages.append(self._create_validation_message(
                ValidationSeverity.ERROR,
                f"{field_name} must be a numeric percentage",
                field_name
            ))
        
        return messages
    
    def _validate_positive_number(self, value: Any, field_name: str, numeric_type: type = float) -> List[ValidationMessage]:
        """
        Validate a positive number.
        
        Args:
            value: Value to validate
            field_name: Name of the field
            numeric_type: Expected numeric type
            
        Returns:
            List of validation messages
        """
        messages = []
        
        try:
            num_value = numeric_type(value)
            
            if num_value <= 0:
                messages.append(self._create_validation_message(
                    ValidationSeverity.ERROR,
                    f"{field_name} must be a positive {numeric_type.__name__}",
                    field_name
                ))
                
        except (TypeError, ValueError):
            messages.append(self._create_validation_message(
                ValidationSeverity.ERROR,
                f"{field_name} must be a {numeric_type.__name__}",
                field_name
            ))
        
        return messages
    
    def _validate_choice(self, value: Any, field_name: str, choices: List[Any]) -> List[ValidationMessage]:
        """
        Validate a choice from a list of options.
        
        Args:
            value: Value to validate
            field_name: Name of the field
            choices: List of valid choices
            
        Returns:
            List of validation messages
        """
        messages = []
        
        if value not in choices:
            messages.append(self._create_validation_message(
                ValidationSeverity.ERROR,
                f"{field_name} must be one of {choices}",
                field_name,
                f"Valid options: {', '.join(map(str, choices))}"
            ))
        
        return messages