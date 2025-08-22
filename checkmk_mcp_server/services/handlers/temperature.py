"""
Specialized parameter handler for temperature monitoring services.

Handles different sensor types, temperature units, hardware-specific profiles,
and provides appropriate default thresholds based on sensor type.
"""

import re
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from .base import BaseParameterHandler, HandlerResult, ValidationSeverity


@dataclass
class TemperatureProfile:
    """Temperature profile for different sensor types."""

    sensor_type: str
    description: str
    default_upper_c: tuple  # (warning, critical) in Celsius
    default_lower_c: tuple  # (warning, critical) in Celsius
    max_reasonable_c: float  # Maximum reasonable temperature
    min_reasonable_c: float  # Minimum reasonable temperature


class TemperatureParameterHandler(BaseParameterHandler):
    """
    Specialized handler for temperature monitoring parameters.

    Supports:
    - Different sensor types (CPU, ambient, disk, PSU, etc.)
    - Multiple temperature units (Celsius, Fahrenheit, Kelvin)
    - Hardware-specific temperature profiles
    - Trend monitoring and device aggregation
    - Validation of temperature ranges and thresholds
    """

    # Temperature profiles for different sensor types
    TEMPERATURE_PROFILES = {
        "cpu": TemperatureProfile(
            sensor_type="cpu",
            description="CPU/Processor temperature",
            default_upper_c=(75.0, 85.0),
            default_lower_c=(5.0, 0.0),
            max_reasonable_c=100.0,
            min_reasonable_c=-10.0,
        ),
        "ambient": TemperatureProfile(
            sensor_type="ambient",
            description="Ambient/Room temperature",
            default_upper_c=(35.0, 40.0),
            default_lower_c=(15.0, 10.0),
            max_reasonable_c=60.0,
            min_reasonable_c=-20.0,
        ),
        "disk": TemperatureProfile(
            sensor_type="disk",
            description="Hard disk temperature",
            default_upper_c=(50.0, 60.0),
            default_lower_c=(5.0, 0.0),
            max_reasonable_c=80.0,
            min_reasonable_c=-10.0,
        ),
        "psu": TemperatureProfile(
            sensor_type="psu",
            description="Power supply temperature",
            default_upper_c=(70.0, 80.0),
            default_lower_c=(10.0, 5.0),
            max_reasonable_c=100.0,
            min_reasonable_c=-10.0,
        ),
        "motherboard": TemperatureProfile(
            sensor_type="motherboard",
            description="Motherboard/System temperature",
            default_upper_c=(60.0, 70.0),
            default_lower_c=(10.0, 5.0),
            max_reasonable_c=90.0,
            min_reasonable_c=-10.0,
        ),
        "case": TemperatureProfile(
            sensor_type="case",
            description="Case/Chassis temperature",
            default_upper_c=(45.0, 55.0),
            default_lower_c=(10.0, 5.0),
            max_reasonable_c=70.0,
            min_reasonable_c=-10.0,
        ),
        "memory": TemperatureProfile(
            sensor_type="memory",
            description="Memory/RAM temperature",
            default_upper_c=(70.0, 80.0),
            default_lower_c=(5.0, 0.0),
            max_reasonable_c=95.0,
            min_reasonable_c=-10.0,
        ),
        "gpu": TemperatureProfile(
            sensor_type="gpu",
            description="Graphics card temperature",
            default_upper_c=(80.0, 90.0),
            default_lower_c=(5.0, 0.0),
            max_reasonable_c=105.0,
            min_reasonable_c=-10.0,
        ),
        "generic": TemperatureProfile(
            sensor_type="generic",
            description="Generic temperature sensor",
            default_upper_c=(70.0, 80.0),
            default_lower_c=(5.0, 0.0),
            max_reasonable_c=100.0,
            min_reasonable_c=-20.0,
        ),
    }

    @property
    def name(self) -> str:
        """Unique name for this handler."""
        return "temperature"

    @property
    def service_patterns(self) -> List[str]:
        """Regex patterns that match temperature-related services."""
        return [
            r".*temp.*",
            r".*temperature.*",
            r".*thermal.*",
            r".*cpu.*temp.*",
            r".*ambient.*",
            r".*sensor.*temp.*",
            r".*hw.*temp.*",
            r".*ipmi.*temp.*",
            r".*lm.*sensors.*",
            r".*core.*temp.*",
        ]

    @property
    def supported_rulesets(self) -> List[str]:
        """Rulesets this handler supports."""
        return [
            "checkgroup_parameters:temperature",
            "checkgroup_parameters:hw_temperature",
            "checkgroup_parameters:ipmi_sensors",
            "checkgroup_parameters:lm_sensors",
        ]

    def get_default_parameters(
        self, service_name: str, context: Optional[Dict[str, Any]] = None
    ) -> HandlerResult:
        """
        Get specialized default parameters for temperature monitoring.

        Args:
            service_name: Name of the temperature service
            context: Optional context (host info, hardware details, etc.)

        Returns:
            HandlerResult with temperature-specific defaults
        """
        # Determine sensor type from service name
        sensor_type = self._detect_sensor_type(service_name)
        profile = self.TEMPERATURE_PROFILES.get(
            sensor_type, self.TEMPERATURE_PROFILES["generic"]
        )

        # Build raw parameters (including trending - will be filtered by policies)
        raw_parameters = {
            "levels": profile.default_upper_c,
            "levels_lower": profile.default_lower_c,
            "output_unit": "c",  # Celsius by default
            "device_levels_handling": "worst",  # Use worst case for multiple sensors
            "trend_compute": {
                "period": 30,  # 30 minute trend period
                "trend_levels": (5.0, 10.0),  # Temperature rise per period
                "trend_levels_lower": (5.0, 10.0),  # Temperature drop per period
            },
        }

        # Add sensor-specific adjustments
        if sensor_type == "cpu":
            # CPU temperatures can vary more rapidly
            raw_parameters["trend_compute"]["period"] = 15
            raw_parameters["device_levels_handling"] = (
                "average"  # Average for multi-core CPUs
            )
        elif sensor_type == "ambient":
            # Ambient temperature changes slowly
            raw_parameters["trend_compute"]["period"] = 60
            raw_parameters["trend_compute"]["trend_levels"] = (
                3.0,
                5.0,
            )  # Slower changes
        elif sensor_type == "disk":
            # Disk temperature monitoring is less critical for trends
            raw_parameters["trend_compute"]["period"] = 60

        # Add context-based adjustments
        if context:
            # Adjust for data center environments
            if context.get("environment") == "datacenter":
                # Data centers typically have tighter temperature control
                warn, crit = raw_parameters["levels"]
                raw_parameters["levels"] = (warn - 5, crit - 5)

            # Adjust for server hardware
            if context.get("hardware_type") == "server":
                # Server hardware typically runs hotter
                warn, crit = raw_parameters["levels"]
                raw_parameters["levels"] = (warn + 5, crit + 5)

        # Apply parameter policies (this will filter trending if not requested)
        filtered_parameters, filter_messages = self.apply_parameter_policies(
            raw_parameters, context or {}
        )

        messages = [
            self._create_validation_message(
                ValidationSeverity.INFO,
                f"Using {profile.description} profile for temperature monitoring",
            ),
            self._create_validation_message(
                ValidationSeverity.INFO,
                f"Default thresholds: Warning {filtered_parameters['levels'][0]}°C, Critical {filtered_parameters['levels'][1]}°C",
            ),
        ]

        # Add filter messages as info messages
        for filter_msg in filter_messages:
            messages.append(
                self._create_validation_message(
                    ValidationSeverity.INFO,
                    filter_msg,
                )
            )

        return HandlerResult(
            success=True, parameters=filtered_parameters, validation_messages=messages
        )

    def validate_parameters(
        self,
        parameters: Dict[str, Any],
        service_name: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> HandlerResult:
        """
        Validate temperature monitoring parameters.

        Args:
            parameters: Parameters to validate
            service_name: Name of the temperature service
            context: Optional context information

        Returns:
            HandlerResult with validation results
        """
        messages = []
        normalized_params = parameters.copy()

        # Detect sensor type for context-aware validation
        sensor_type = self._detect_sensor_type(service_name)
        profile = self.TEMPERATURE_PROFILES.get(
            sensor_type, self.TEMPERATURE_PROFILES["generic"]
        )

        # Check for required parameters
        if not parameters:
            messages.append(
                self._create_validation_message(
                    ValidationSeverity.ERROR,
                    "Temperature monitoring requires at least 'levels' parameter to be configured",
                    None,
                    "Add levels parameter like: {'levels': (70.0, 80.0)}",
                )
            )
        elif "levels" not in parameters:
            messages.append(
                self._create_validation_message(
                    ValidationSeverity.ERROR,
                    "Temperature thresholds ('levels') are required for monitoring",
                    "levels",
                    f"Add levels appropriate for {profile.description}: {profile.default_upper_c}",
                )
            )

        # Validate temperature unit
        output_unit = parameters.get("output_unit", "c")
        unit_messages = self._validate_choice(
            output_unit, "output_unit", ["c", "f", "k"]
        )
        messages.extend(unit_messages)

        # Validate upper temperature thresholds
        if "levels" in parameters:
            threshold_messages = self._validate_threshold_tuple(
                parameters["levels"],
                "levels",
                min_values=2,
                max_values=2,
                numeric_type=float,
            )
            messages.extend(threshold_messages)

            # Additional temperature-specific validation
            if not threshold_messages:  # Only if basic validation passed
                warn_temp, crit_temp = parameters["levels"]

                # Convert to Celsius for validation
                warn_c, crit_c = self._convert_to_celsius(
                    warn_temp, crit_temp, output_unit
                )

                # Check against sensor profile limits
                if crit_c > profile.max_reasonable_c:
                    messages.append(
                        self._create_validation_message(
                            ValidationSeverity.WARNING,
                            f"Critical temperature {crit_c}°C exceeds reasonable maximum for {profile.description} ({profile.max_reasonable_c}°C)",
                            "levels",
                            f"Consider using a threshold below {profile.max_reasonable_c}°C",
                        )
                    )

                if warn_c < profile.min_reasonable_c:
                    messages.append(
                        self._create_validation_message(
                            ValidationSeverity.WARNING,
                            f"Warning temperature {warn_c}°C is below reasonable minimum for {profile.description} ({profile.min_reasonable_c}°C)",
                            "levels",
                        )
                    )

                # Normalize to consistent precision
                normalized_params["levels"] = (
                    round(float(warn_temp), 1),
                    round(float(crit_temp), 1),
                )

        # Validate lower temperature thresholds
        if "levels_lower" in parameters:
            lower_messages = self._validate_threshold_tuple(
                parameters["levels_lower"],
                "levels_lower",
                min_values=2,
                max_values=2,
                numeric_type=float,
            )
            messages.extend(lower_messages)

            if not lower_messages:
                warn_temp, crit_temp = parameters["levels_lower"]
                warn_c, crit_c = self._convert_to_celsius(
                    warn_temp, crit_temp, output_unit
                )

                if crit_c < profile.min_reasonable_c:
                    messages.append(
                        self._create_validation_message(
                            ValidationSeverity.WARNING,
                            f"Lower critical temperature {crit_c}°C is below reasonable minimum for {profile.description}",
                            "levels_lower",
                        )
                    )

                # Normalize to consistent precision
                normalized_params["levels_lower"] = (
                    round(float(warn_temp), 1),
                    round(float(crit_temp), 1),
                )

        # Validate device handling method
        if "device_levels_handling" in parameters:
            handling_messages = self._validate_choice(
                parameters["device_levels_handling"],
                "device_levels_handling",
                ["worst", "best", "average", "individual"],
            )
            messages.extend(handling_messages)

        # Validate trend monitoring parameters
        if "trend_compute" in parameters:
            trend_messages = self._validate_trend_parameters(
                parameters["trend_compute"]
            )
            messages.extend(trend_messages)

        # Validate consistency between upper and lower thresholds
        if "levels" in parameters and "levels_lower" in parameters:
            consistency_messages = self._validate_threshold_consistency(
                parameters["levels"], parameters["levels_lower"], output_unit
            )
            messages.extend(consistency_messages)

        # Add recommendations based on sensor type
        if sensor_type != "generic":
            messages.append(
                self._create_validation_message(
                    ValidationSeverity.INFO,
                    f"Detected {profile.description} - consider profile-specific thresholds if needed",
                )
            )

        return HandlerResult(
            success=True,  # Validation function executed successfully
            parameters=parameters,
            normalized_parameters=normalized_params,
            validation_messages=messages,
        )

    def get_parameter_info(self, parameter_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about temperature parameters."""
        parameter_info = {
            "levels": {
                "description": "Upper temperature thresholds (warning, critical)",
                "type": "tuple",
                "elements": ["float", "float"],
                "unit_dependent": True,
                "example": "(70.0, 80.0)",
            },
            "levels_lower": {
                "description": "Lower temperature thresholds (warning, critical)",
                "type": "tuple",
                "elements": ["float", "float"],
                "unit_dependent": True,
                "example": "(5.0, 0.0)",
            },
            "output_unit": {
                "description": "Temperature unit for display",
                "type": "choice",
                "choices": ["c", "f", "k"],
                "default": "c",
                "help": "c=Celsius, f=Fahrenheit, k=Kelvin",
            },
            "device_levels_handling": {
                "description": "How to handle multiple temperature sensors",
                "type": "choice",
                "choices": ["worst", "best", "average", "individual"],
                "default": "worst",
                "help": "worst=use highest temperature, best=use lowest, average=use average, individual=check each sensor separately",
            },
            "trend_compute": {
                "description": "Temperature trend monitoring configuration",
                "type": "dict",
                "elements": {
                    "period": "Period in minutes for trend calculation",
                    "trend_levels": "Temperature rise thresholds per period",
                    "trend_levels_lower": "Temperature drop thresholds per period",
                },
            },
        }

        return parameter_info.get(parameter_name)

    def suggest_parameters(
        self,
        service_name: str,
        current_parameters: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Suggest temperature parameter optimizations."""
        suggestions = []

        # Detect sensor type
        sensor_type = self._detect_sensor_type(service_name)
        profile = self.TEMPERATURE_PROFILES.get(
            sensor_type, self.TEMPERATURE_PROFILES["generic"]
        )

        current = current_parameters or {}

        # Suggest sensor-type specific thresholds
        if sensor_type != "generic":
            current_levels = current.get("levels")
            if not current_levels or current_levels != profile.default_upper_c:
                suggestions.append(
                    {
                        "parameter": "levels",
                        "current_value": current_levels,
                        "suggested_value": profile.default_upper_c,
                        "reason": f"Optimized thresholds for {profile.description}",
                        "impact": "Better monitoring accuracy for this sensor type",
                    }
                )

        # Always suggest trend monitoring (policy will filter if not appropriate)
        raw_trend_suggestion = {
            "parameter": "trend_compute",
            "current_value": current.get("trend_compute"),
            "suggested_value": {
                "period": 30,
                "trend_levels": (5.0, 10.0),
                "trend_levels_lower": (5.0, 10.0),
            },
            "reason": "Enable temperature trend monitoring",
            "impact": "Detect gradual temperature increases that might indicate hardware issues",
        }

        # Apply policies to see if trending should be suggested
        test_parameters = {"trend_compute": raw_trend_suggestion["suggested_value"]}
        filtered_test, _ = self.apply_parameter_policies(test_parameters, context or {})

        # Only suggest if policies allow it
        if "trend_compute" in filtered_test and "trend_compute" not in current:
            suggestions.append(raw_trend_suggestion)

        # Suggest device handling for multi-sensor systems
        if "device_levels_handling" not in current and "multi" in service_name.lower():
            suggested_handling = "average" if sensor_type == "cpu" else "worst"
            suggestions.append(
                {
                    "parameter": "device_levels_handling",
                    "current_value": None,
                    "suggested_value": suggested_handling,
                    "reason": f"Optimal handling for multiple {sensor_type} sensors",
                    "impact": "More appropriate alerting for multi-sensor configurations",
                }
            )

        return suggestions

    def _detect_sensor_type(self, service_name: str) -> str:
        """Detect the sensor type from service name."""
        service_lower = service_name.lower()

        # Check for specific sensor types
        if any(keyword in service_lower for keyword in ["cpu", "processor", "core"]):
            return "cpu"
        elif any(keyword in service_lower for keyword in ["ambient", "room", "air"]):
            return "ambient"
        elif any(
            keyword in service_lower for keyword in ["disk", "hdd", "ssd", "drive"]
        ):
            return "disk"
        elif any(keyword in service_lower for keyword in ["psu", "power", "supply"]):
            return "psu"
        elif any(
            keyword in service_lower
            for keyword in ["motherboard", "mainboard", "system"]
        ):
            return "motherboard"
        elif any(
            keyword in service_lower for keyword in ["case", "chassis", "enclosure"]
        ):
            return "case"
        elif any(keyword in service_lower for keyword in ["memory", "ram", "dimm"]):
            return "memory"
        elif any(keyword in service_lower for keyword in ["gpu", "graphics", "video"]):
            return "gpu"
        else:
            return "generic"

    def _convert_to_celsius(self, temp1: float, temp2: float, unit: str) -> tuple:
        """Convert temperatures to Celsius for validation."""
        if unit == "f":  # Fahrenheit
            return ((temp1 - 32) * 5 / 9, (temp2 - 32) * 5 / 9)
        elif unit == "k":  # Kelvin
            return (temp1 - 273.15, temp2 - 273.15)
        else:  # Celsius
            return (temp1, temp2)

    def _validate_trend_parameters(self, trend_config: Any) -> List:
        """Validate temperature trend monitoring parameters."""
        messages = []

        if not isinstance(trend_config, dict):
            messages.append(
                self._create_validation_message(
                    ValidationSeverity.ERROR,
                    "trend_compute must be a dictionary",
                    "trend_compute",
                )
            )
            return messages

        # Validate period
        if "period" in trend_config:
            period_messages = self._validate_positive_number(
                trend_config["period"], "trend_compute.period", int
            )
            messages.extend(period_messages)

            # Check for reasonable period values
            try:
                period = int(trend_config["period"])
                if period < 5:
                    messages.append(
                        self._create_validation_message(
                            ValidationSeverity.WARNING,
                            "Trend period less than 5 minutes may be too short for meaningful trend detection",
                            "trend_compute.period",
                        )
                    )
                elif period > 240:  # 4 hours
                    messages.append(
                        self._create_validation_message(
                            ValidationSeverity.WARNING,
                            "Trend period longer than 4 hours may be too long for timely alerting",
                            "trend_compute.period",
                        )
                    )
            except (TypeError, ValueError):
                pass  # Already caught by positive number validation

        # Validate trend levels
        if "trend_levels" in trend_config:
            trend_messages = self._validate_threshold_tuple(
                trend_config["trend_levels"], "trend_compute.trend_levels"
            )
            messages.extend(trend_messages)

        if "trend_levels_lower" in trend_config:
            lower_trend_messages = self._validate_threshold_tuple(
                trend_config["trend_levels_lower"], "trend_compute.trend_levels_lower"
            )
            messages.extend(lower_trend_messages)

        return messages

    def _validate_threshold_consistency(
        self, upper_levels: tuple, lower_levels: tuple, unit: str
    ) -> List:
        """Validate consistency between upper and lower temperature thresholds."""
        messages = []

        try:
            upper_warn, upper_crit = upper_levels
            lower_warn, lower_crit = lower_levels

            # Convert to consistent unit for comparison
            upper_warn_c, upper_crit_c = self._convert_to_celsius(
                upper_warn, upper_crit, unit
            )
            lower_warn_c, lower_crit_c = self._convert_to_celsius(
                lower_warn, lower_crit, unit
            )

            # Check for overlapping thresholds
            if lower_warn_c >= upper_warn_c:
                messages.append(
                    self._create_validation_message(
                        ValidationSeverity.ERROR,
                        f"Lower warning threshold ({lower_warn_c:.1f}°C) must be less than upper warning threshold ({upper_warn_c:.1f}°C)",
                        "levels_lower",
                    )
                )

            if lower_crit_c >= upper_crit_c:
                messages.append(
                    self._create_validation_message(
                        ValidationSeverity.ERROR,
                        f"Lower critical threshold ({lower_crit_c:.1f}°C) must be less than upper critical threshold ({upper_crit_c:.1f}°C)",
                        "levels_lower",
                    )
                )

            # Check for reasonable gap between thresholds
            gap = upper_warn_c - lower_warn_c
            if gap < 10:  # Less than 10°C gap
                messages.append(
                    self._create_validation_message(
                        ValidationSeverity.WARNING,
                        f"Small gap ({gap:.1f}°C) between upper and lower warning thresholds may cause frequent state changes",
                        "levels",
                    )
                )

        except (TypeError, ValueError, IndexError):
            # Skip consistency check if threshold values are invalid
            pass

        return messages
