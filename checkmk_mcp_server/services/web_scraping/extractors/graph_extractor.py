"""
Graph Data Extractor

This module extracts time-series data from graphs and JavaScript
for historical monitoring data retrieval.
"""

import re
import json
import logging
import time
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional, Union

try:
    from bs4 import BeautifulSoup, Tag
    import lxml  # noqa: F401 - Only used for parser detection
    HAS_LXML = True
except ImportError:
    from bs4 import BeautifulSoup, Tag
    HAS_LXML = False

from .. import ScrapingError


class GraphExtractor:
    """Extract time-series data from graphs and JavaScript.
    
    This class handles extraction of time-series data from various graph formats
    including JavaScript-embedded data and AJAX endpoints.
    """
    
    def __init__(self, session=None, config=None, logger=None):
        """Initialize graph extractor.
        
        Args:
            session: Authenticated requests session
            config: Configuration object with server details
            logger: Logger instance for debugging
        """
        self.session = session
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        
        # Store calculated time ranges for AJAX requests
        self._ajax_calculated_start = None
        self._ajax_calculated_end = None
    
    def extract_graph_data(
        self, 
        html_content: str, 
        period: str = "4h"
    ) -> List[Tuple[str, Union[float, str]]]:
        """Extract time-series data using AJAX-based approach with fallbacks.
        
        This method replicates the browser's AJAX flow by:
        1. Extracting parameters from cmk.graphs.load_graph_content() JavaScript calls
        2. Making POST requests to ajax_render_graph_content.py with proper JSON data
        3. Parsing the AJAX response to extract actual time-series data
        4. Falling back to static JavaScript parsing if AJAX fails
        
        Args:
            html_content: Raw HTML content from the monitoring page
            period: Time period for data extraction (4h, 25h, 8d, etc.)
            
        Returns:
            List of (timestamp, value) tuples with timestamps in ISO format
            
        Raises:
            ScrapingError: If parsing fails completely
        """
        self.logger.debug("Starting graph data extraction with AJAX-based approach")
        self.logger.debug(f"HTML content length: {len(html_content)} characters")
        
        extracted_data = []
        
        try:
            # Parse HTML with fallback parsers
            soup = self._parse_html_with_fallback(html_content)
            
            # Log HTML structure for debugging
            self._log_html_structure(soup)
            
            # Try new AJAX approach - extract parameters and make AJAX requests
            self.logger.debug("Attempting AJAX-based data extraction")
            
            try:
                # Extract JavaScript parameters from cmk.graphs.load_graph_content() calls
                graph_parameters_list = self.extract_graph_parameters(html_content)
                
                if graph_parameters_list:
                    self.logger.debug(f"Found {len(graph_parameters_list)} graph parameter sets")
                    
                    # Try each set of parameters to get graph data
                    for i, parameters in enumerate(graph_parameters_list):
                        self.logger.debug(f"Processing graph {i+1}/{len(graph_parameters_list)}: {parameters.get('graph_display_id', 'unknown')}")
                        
                        try:
                            # Make AJAX request to ajax_render_graph_content.py
                            ajax_response = self._make_ajax_request(parameters, period)
                            
                            if ajax_response:
                                # Parse the AJAX response to extract time-series data
                                graph_data = self._parse_ajax_response(ajax_response)
                                
                                if graph_data:
                                    self.logger.info(f"Successfully extracted {len(graph_data)} data points from AJAX graph {i+1}")
                                    extracted_data.extend(graph_data)
                                else:
                                    self.logger.debug(f"No data found in AJAX response for graph {i+1}")
                            else:
                                self.logger.debug(f"No AJAX response received for graph {i+1}")
                                
                        except Exception as e:
                            self.logger.debug(f"Error processing graph {i+1}: {e}")
                            continue
                else:
                    self.logger.debug("No cmk.graphs.load_graph_content() calls found in HTML")
                    
            except Exception as e:
                self.logger.debug(f"AJAX extraction failed: {e}")
            
            if extracted_data:
                self.logger.info(f"Successfully extracted {len(extracted_data)} data points via AJAX")
            else:
                self.logger.debug("Found no data via AJAX, falling back to static JavaScript parsing")
            
            # FALLBACK: Static JavaScript parsing if AJAX failed
            if not extracted_data:
                self.logger.debug("Fallback: Using static JavaScript extraction")
                script_elements = self.find_script_tags(soup)
                self.logger.debug(f"Found {len(script_elements)} script tags for data extraction")
                
                # Extract actual time-series data from JavaScript
                for i, script in enumerate(script_elements):
                    script_content = script.get_text()
                    if not script_content.strip():
                        continue
                    
                    self.logger.debug(f"Processing script tag {i+1}/{len(script_elements)}")
                    
                    # Extract data using multiple search patterns
                    script_data = self._extract_data_from_script(script_content, i+1)
                    
                    if script_data:
                        self.logger.debug(f"Found {len(script_data)} data points in script {i+1}")
                        extracted_data.extend(script_data)
                    else:
                        self.logger.debug(f"No data found in script {i+1}")
            
            # Process and validate extracted data
            if extracted_data:
                self.logger.debug(f"Raw extracted data before processing: {extracted_data}")
            processed_data = self._process_and_validate_data(extracted_data)
            
            self.logger.debug(f"Graph extraction complete: {len(processed_data)} validated data points")
            
            if processed_data:
                # Log sample of extracted data
                sample_size = min(3, len(processed_data))
                sample_data = processed_data[:sample_size]
                self.logger.debug(f"Sample extracted data: {sample_data}")
                return processed_data
            else:
                self.logger.warning("No time-series data extracted - the page may use dynamic loading")
                return []
            
        except Exception as e:
            error_msg = f"Failed to parse graph data: {e}"
            self.logger.error(error_msg)
            raise ScrapingError(
                error_msg,
                html_snippet=html_content[:500] if html_content else None,
                response_data={"error": str(e)}
            )

    def extract_graph_parameters(self, html_content: str) -> List[Dict[str, Any]]:
        """Extract JavaScript parameters from cmk.graphs.load_graph_content() calls.
        
        Parses the HTML to find JavaScript calls to cmk.graphs.load_graph_content()
        and extracts the four parameters needed for AJAX requests.
        
        Args:
            html_content: Raw HTML content from the monitoring page
            
        Returns:
            List of parameter dictionaries containing graph_recipe, graph_data_range, 
            graph_render_config, and graph_display_id for each graph found
            
        Raises:
            ScrapingError: If parameter extraction fails
        """
        self.logger.debug("Extracting JavaScript parameters from cmk.graphs.load_graph_content() calls")
        
        parameters_list = []
        
        try:
            # Pattern to match cmk.graphs.load_graph_content() calls with 4 arguments
            pattern = r'cmk\.graphs\.load_graph_content\s*\(\s*(.+?)\s*\)\s*;?'
            matches = re.finditer(pattern, html_content, re.DOTALL | re.MULTILINE)
            
            for i, match in enumerate(matches):
                full_args = match.group(1).strip()
                self.logger.debug(f"Found cmk.graphs.load_graph_content call {i+1}: {full_args[:100]}...")
                
                # Parse the four arguments using balanced parentheses/braces parsing
                parsed_args = self._parse_function_arguments(full_args)
                
                if len(parsed_args) >= 4:
                    graph_recipe_str = parsed_args[0].strip()
                    graph_data_range_str = parsed_args[1].strip()
                    graph_render_config_str = parsed_args[2].strip()
                    graph_display_id_str = parsed_args[3].strip()
                    
                    self.logger.debug(f"  graph_recipe: {graph_recipe_str[:50]}...")
                    self.logger.debug(f"  graph_data_range: {graph_data_range_str[:50]}...")
                    self.logger.debug(f"  graph_render_config: {graph_render_config_str[:50]}...")
                    self.logger.debug(f"  graph_display_id: {graph_display_id_str[:50]}...")
                    
                    # Parse each JavaScript parameter into Python objects
                    try:
                        graph_recipe = self._parse_javascript_object(graph_recipe_str)
                        graph_data_range = self._parse_javascript_object(graph_data_range_str)
                        graph_render_config = self._parse_javascript_object(graph_render_config_str)
                        
                        # graph_display_id is usually a simple string/identifier
                        graph_display_id = graph_display_id_str.strip('"\'')
                        
                        if graph_recipe and graph_data_range and graph_render_config:
                            parameters = {
                                'graph_recipe': graph_recipe,
                                'graph_data_range': graph_data_range,
                                'graph_render_config': graph_render_config,
                                'graph_display_id': graph_display_id
                            }
                            parameters_list.append(parameters)
                            self.logger.debug(f"Successfully parsed parameters for graph {graph_display_id}")
                        else:
                            self.logger.debug(f"Failed to parse one or more parameters for call {i+1}")
                            
                    except Exception as e:
                        self.logger.debug(f"Error parsing JavaScript objects for call {i+1}: {e}")
                        continue
                        
                else:
                    self.logger.debug(f"Found cmk.graphs.load_graph_content call with {len(parsed_args)} arguments, expected 4")
                    continue
            
            self.logger.debug(f"Successfully extracted parameters for {len(parameters_list)} graphs")
            return parameters_list
            
        except Exception as e:
            error_msg = f"Failed to extract graph parameters: {e}"
            self.logger.error(error_msg)
            raise ScrapingError(
                error_msg,
                html_snippet=html_content[:500] if html_content else None,
                response_data={"error": str(e)}
            )

    def find_script_tags(self, soup: BeautifulSoup) -> List[Tag]:
        """Find all relevant script tags for data extraction."""
        script_tags = soup.find_all('script')
        relevant_scripts = []
        
        for script in script_tags:
            if isinstance(script, Tag):
                script_content = script.get_text()
                if script_content and any(keyword in script_content for keyword in 
                    ['graph', 'data', 'points', 'series', 'temperature', 'cmk']):
                    relevant_scripts.append(script)
        
        return relevant_scripts
    
    def _make_ajax_request(self, parameters: Dict[str, Any], period: str) -> Optional[str]:
        """Make AJAX request using extracted graph parameters."""
        if not self.session or not self.config:
            self.logger.debug("No session or config available for AJAX request")
            return None
        
        try:
            # Use the AJAX extractor for the actual request
            from .ajax_extractor import AjaxExtractor
            ajax_extractor = AjaxExtractor(self.session)
            return ajax_extractor.make_ajax_request(
                parameters, 
                period, 
                self.config.server_url, 
                self.config.site
            )
        except Exception as e:
            self.logger.debug(f"AJAX request failed: {e}")
            return None
    
    def _parse_ajax_response(self, response: str) -> List[Tuple[str, Union[float, str]]]:
        """Parse AJAX response using the AJAX extractor."""
        try:
            from .ajax_extractor import AjaxExtractor
            ajax_extractor = AjaxExtractor(self.session)
            return ajax_extractor.parse_ajax_response(response)
        except Exception as e:
            self.logger.debug(f"AJAX response parsing failed: {e}")
            return []
    
    def _parse_html_with_fallback(self, html_content: str) -> BeautifulSoup:
        """Parse HTML content with fallback parsers."""
        if HAS_LXML:
            try:
                return BeautifulSoup(html_content, 'lxml')
            except Exception:
                pass
        
        try:
            return BeautifulSoup(html_content, 'html.parser')
        except Exception:
            return BeautifulSoup(html_content)
    
    def _log_html_structure(self, soup: BeautifulSoup) -> None:
        """Log HTML structure for debugging."""
        try:
            # Log basic structure
            scripts = soup.find_all('script')
            divs = soup.find_all('div')
            tables = soup.find_all('table')
            
            self.logger.debug(f"HTML structure: {len(scripts)} scripts, {len(divs)} divs, {len(tables)} tables")
            
            # Log presence of key elements
            if soup.find(string=re.compile(r'cmk\.graphs')):
                self.logger.debug("Found cmk.graphs references in HTML")
            if soup.find(string=re.compile(r'temperature', re.IGNORECASE)):
                self.logger.debug("Found temperature references in HTML")
                
        except Exception as e:
            self.logger.debug(f"Error logging HTML structure: {e}")
    
    def _extract_data_from_script(self, script_content: str, script_num: int) -> List[Tuple[str, Union[float, str]]]:
        """Extract data from JavaScript content using multiple patterns."""
        extracted_data = []
        
        # Pattern 1: Time-series data arrays (with proper timestamps)
        patterns = [
            r'data\s*:\s*\[\s*(\[[^\]]+\](?:\s*,\s*\[[^\]]+\])*)\s*\]',
            r'points\s*:\s*\[\s*(\[[^\]]+\](?:\s*,\s*\[[^\]]+\])*)\s*\]',
            r'\[\s*(\d{10})\s*,\s*([\d\.]+)\s*\]',
            r'timestamp["\']?\s*:\s*["\']?(\d{10})["\']?\s*,\s*value["\']?\s*:\s*["\']?([\d\.]+)["\']?',
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, script_content, re.MULTILINE | re.DOTALL)
            for match in matches:
                try:
                    if len(match.groups()) == 2:
                        timestamp_raw = match.group(1)
                        value_raw = match.group(2)
                        
                        # Convert timestamp
                        timestamp = self._convert_timestamp_to_iso(timestamp_raw)
                        if timestamp:
                            value = float(value_raw)
                            # Only accept reasonable temperature values (not timestamps or other large numbers)
                            if self._is_reasonable_temperature_value(value):
                                extracted_data.append((timestamp, value))
                except (ValueError, TypeError):
                    continue
        
        # If Pattern 1 found data with proper timestamps, return it
        if extracted_data:
            self.logger.debug(f"Script {script_num}: Found {len(extracted_data)} data points with proper timestamps")
            return extracted_data
        
        # Pattern 2: Look for temperature values - generate timestamps based on context
        fallback_temperatures = []
        temp_matches = re.finditer(r'([\d\.]+)\s*°C', script_content)
        for match in temp_matches:
            try:
                temp_value = float(match.group(1))
                if self._is_reasonable_temperature_value(temp_value):
                    fallback_temperatures.append(temp_value)
            except ValueError:
                continue
        
        # Pattern 3: Look for temperature patterns in text
        # Match patterns like "Temperature: 60.37" or just "60.37°C"
        temperature_patterns = [
            r'temperature\s*:?\s*([\d\.]+)\s*°?[cf]?',
            r'temp\s*:?\s*([\d\.]+)\s*°?[cf]?',
            r'([\d\.]+)\s*°[cf]',  # Direct temperature notation
        ]
        
        for pattern in temperature_patterns:
            temp_matches = re.finditer(pattern, script_content, re.IGNORECASE)
            for match in temp_matches:
                try:
                    temp_value = float(match.group(1))
                    # Only accept reasonable temperature values (not timestamps)
                    if self._is_reasonable_temperature_value(temp_value):
                        fallback_temperatures.append(temp_value)
                except ValueError:
                    continue
        
        # Process fallback temperatures with proper timestamp generation
        if fallback_temperatures:
            # Remove duplicates while preserving order
            unique_temps = list(dict.fromkeys(fallback_temperatures))
            extracted_data = self._generate_time_series_from_values(unique_temps, script_num)
        
        return extracted_data
    
    def _process_and_validate_data(self, raw_data: List[Tuple[str, Union[float, str]]]) -> List[Tuple[str, Union[float, str]]]:
        """Process and validate extracted data."""
        if not raw_data:
            return []
        
        # Remove duplicates while preserving order
        seen = set()
        unique_data = []
        for item in raw_data:
            if item not in seen:
                seen.add(item)
                unique_data.append(item)
        
        # Sort by timestamp if possible
        try:
            unique_data.sort(key=lambda x: x[0])
        except (TypeError, ValueError):
            pass
        
        # Validate data points
        validated_data = []
        for timestamp, value in unique_data:
            try:
                if isinstance(value, (int, float)) and isinstance(timestamp, str):
                    validated_data.append((timestamp, value))
                elif isinstance(value, str) and value.replace('.', '').isdigit():
                    validated_data.append((timestamp, float(value)))
            except (ValueError, TypeError):
                continue
        
        return validated_data
    
    def _parse_function_arguments(self, args_string: str) -> List[str]:
        """Parse function arguments with proper bracket/brace balancing."""
        arguments = []
        current_arg = ""
        paren_count = 0
        brace_count = 0
        bracket_count = 0
        in_string = False
        string_char = None
        
        i = 0
        while i < len(args_string):
            char = args_string[i]
            
            # Handle string literals
            if char in ['"', "'"] and (i == 0 or args_string[i-1] != '\\'):
                if not in_string:
                    in_string = True
                    string_char = char
                elif char == string_char:
                    in_string = False
                    string_char = None
            
            if not in_string:
                if char == '(':
                    paren_count += 1
                elif char == ')':
                    paren_count -= 1
                elif char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                elif char == '[':
                    bracket_count += 1
                elif char == ']':
                    bracket_count -= 1
                elif char == ',' and paren_count == 0 and brace_count == 0 and bracket_count == 0:
                    # Found argument separator
                    arguments.append(current_arg.strip())
                    current_arg = ""
                    i += 1
                    continue
            
            current_arg += char
            i += 1
        
        # Add the last argument
        if current_arg.strip():
            arguments.append(current_arg.strip())
        
        return arguments
    
    def _parse_javascript_object(self, js_str: str) -> Dict[str, Any]:
        """Parse a JavaScript object string into a Python dictionary."""
        try:
            # First attempt: Clean and parse as JSON
            cleaned = self._clean_javascript_for_json(js_str)
            
            try:
                # Try direct JSON parsing first
                return json.loads(cleaned)
            except json.JSONDecodeError:
                pass
            
            # Second attempt: Enhanced extraction for complex structures
            try:
                return self._extract_complex_js_object(js_str)
            except Exception:
                pass
                
            # Third attempt: Fallback to regex parsing
            try:
                return self._parse_js_object_params(js_str)
            except Exception:
                pass
                
        except Exception as e:
            self.logger.debug(f"Failed to parse JavaScript object: {e}")
            
        return {}
    
    def _clean_javascript_for_json(self, js_str: str) -> str:
        """Clean JavaScript object string to make it JSON-parseable."""
        # Remove JavaScript comments
        js_str = re.sub(r'//.*?$', '', js_str, flags=re.MULTILINE)
        js_str = re.sub(r'/\*.*?\*/', '', js_str, flags=re.DOTALL)
        
        # Replace single quotes with double quotes (but not inside strings)
        # This is a simplified approach - a full parser would be more robust
        js_str = re.sub(r"'([^']*)'", r'"\1"', js_str)
        
        # Handle unquoted object keys
        js_str = re.sub(r'([{,]\s*)([a-zA-Z_$][a-zA-Z0-9_$]*)\s*:', r'\1"\2":', js_str)
        
        # Remove trailing commas
        js_str = re.sub(r',(\s*[}\]])', r'\1', js_str)
        
        return js_str.strip()
    
    def _extract_complex_js_object(self, js_str: str) -> Dict[str, Any]:
        """Extract complex JavaScript object with proper nested structure handling."""
        try:
            # Remove outer JavaScript function call if present
            js_content = js_str.strip()
            
            # Find the first { and last } to extract the object content
            start_brace = js_content.find('{')
            if start_brace == -1:
                return {}
                
            # Count braces to find the matching closing brace
            brace_count = 0
            end_brace = -1
            
            for i in range(start_brace, len(js_content)):
                if js_content[i] == '{':
                    brace_count += 1
                elif js_content[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end_brace = i
                        break
            
            if end_brace == -1:
                return {}
            
            # Extract the object content
            obj_content = js_content[start_brace:end_brace + 1]
            
            # Clean for JSON parsing
            cleaned = self._clean_javascript_for_json(obj_content)
            
            # Try JSON parsing on the cleaned content
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError as e:
                self.logger.debug(f"JSON parsing failed on cleaned content: {e}")
                # Fall back to manual extraction if JSON parsing fails
                return self._manual_js_extraction(obj_content)
                
        except Exception as e:
            self.logger.debug(f"Complex JS extraction failed: {e}")
            return {}
    
    def _manual_js_extraction(self, js_content: str) -> Dict[str, Any]:
        """Manual extraction for JavaScript objects that resist JSON parsing."""
        try:
            # This is a simplified manual parser - in practice, you might want
            # to use a proper JavaScript parser library
            result = {}
            
            # Extract simple key-value pairs using regex
            patterns = [
                r'["\']?(\w+)["\']?\s*:\s*["\']([^"\']+)["\']',  # string values
                r'["\']?(\w+)["\']?\s*:\s*(\d+\.?\d*)',          # numeric values
                r'["\']?(\w+)["\']?\s*:\s*(true|false)',         # boolean values
            ]
            
            for pattern in patterns:
                matches = re.finditer(pattern, js_content)
                for match in matches:
                    key = match.group(1)
                    value = match.group(2)
                    
                    # Try to convert value to appropriate type
                    if value.lower() == 'true':
                        result[key] = True
                    elif value.lower() == 'false':
                        result[key] = False
                    elif value.replace('.', '').isdigit():
                        result[key] = float(value) if '.' in value else int(value)
                    else:
                        result[key] = value
            
            return result
            
        except Exception as e:
            self.logger.debug(f"Manual JS extraction failed: {e}")
            return {}
    
    def _parse_js_object_params(self, js_str: str) -> Dict[str, Any]:
        """Parse JavaScript object parameters using regex."""
        # Simplified regex-based parsing as fallback
        params = {}
        
        # Look for simple key-value patterns
        simple_patterns = [
            r'["\']?time_range["\']?\s*:\s*\[([^\]]+)\]',
            r'["\']?step["\']?\s*:\s*(\d+)',
            r'["\']?title["\']?\s*:\s*["\']([^"\']+)["\']',
        ]
        
        for pattern in simple_patterns:
            match = re.search(pattern, js_str)
            if match:
                key = pattern.split('["\']?')[1].split('["\']?')[0]  # Extract key from pattern
                value = match.group(1)
                
                if 'time_range' in pattern:
                    # Parse array values
                    try:
                        time_values = [int(x.strip()) for x in value.split(',')]
                        params['time_range'] = time_values
                    except ValueError:
                        pass
                elif 'step' in pattern:
                    try:
                        params['step'] = int(value)
                    except ValueError:
                        pass
                else:
                    params[key] = value
        
        return params
    
    def _convert_timestamp_to_iso(self, timestamp_str: str) -> Optional[str]:
        """Convert various timestamp formats to ISO format."""
        try:
            # If it's already in ISO format, return as-is
            if re.match(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}', timestamp_str):
                return timestamp_str
            
            # If it's a Unix timestamp
            if re.match(r'^\d{10}$', timestamp_str):
                unix_timestamp = int(timestamp_str)
                dt = datetime.fromtimestamp(unix_timestamp)
                return dt.isoformat()
            
            # Add other timestamp format conversions as needed
            
        except (ValueError, TypeError):
            pass
        
        return None
    
    def _generate_time_series_from_values(self, values: List[float], script_num: int) -> List[Tuple[str, float]]:
        """Generate time series data from temperature values with appropriate timestamps.
        
        Args:
            values: List of temperature values
            script_num: Script number for logging
            
        Returns:
            List of (timestamp, value) tuples with distributed timestamps
        """
        if not values:
            return []
        
        self.logger.debug(f"Script {script_num}: Generating timestamps for {len(values)} temperature values")
        
        # If only one value, it's likely a current reading
        if len(values) == 1:
            current_time = datetime.now().isoformat()
            self.logger.debug(f"Script {script_num}: Single temperature value, using current timestamp")
            return [(current_time, values[0])]
        
        # For multiple values, try to determine if we have time series data
        # Check if we have AJAX-calculated time range from earlier in the process
        if hasattr(self, '_ajax_calculated_start') and hasattr(self, '_ajax_calculated_end') and \
           self._ajax_calculated_start and self._ajax_calculated_end:
            # Use the time range from AJAX calculation
            start_time = self._ajax_calculated_start
            end_time = self._ajax_calculated_end
            self.logger.debug(f"Script {script_num}: Using AJAX time range [{start_time}, {end_time}]")
        else:
            # Default to a reasonable time range (last 4 hours)
            import time
            end_time = int(time.time())
            start_time = end_time - (4 * 3600)  # 4 hours ago
            self.logger.debug(f"Script {script_num}: Using default 4h time range [{start_time}, {end_time}]")
        
        # Generate evenly distributed timestamps across the time range
        time_interval = (end_time - start_time) / (len(values) - 1) if len(values) > 1 else 0
        
        time_series_data = []
        for i, value in enumerate(values):
            timestamp_unix = start_time + (i * time_interval)
            timestamp_iso = datetime.fromtimestamp(timestamp_unix).isoformat()
            time_series_data.append((timestamp_iso, value))
        
        self.logger.debug(f"Script {script_num}: Generated time series with {len(time_series_data)} points")
        return time_series_data
    
    def _is_reasonable_temperature_value(self, value: float) -> bool:
        """Check if a value looks like a reasonable temperature (not a timestamp).
        
        Args:
            value: Numeric value to check
            
        Returns:
            True if value looks like a temperature, False if it looks like a timestamp or other data
        """
        # Temperature values should be reasonable for system monitoring
        # Usually between -50°C and 150°C for computer systems
        return -50.0 <= value <= 150.0