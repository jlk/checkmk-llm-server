"""
AJAX Data Extractor

This module handles AJAX endpoint data extraction for real-time
monitoring data retrieval from Checkmk interfaces.
"""

from typing import Dict, Any, List, Optional, Tuple, Union
import requests
import logging
import json
import time
import datetime
import re
from urllib.parse import quote
from bs4 import BeautifulSoup


class AjaxExtractor:
    """Handle AJAX endpoint data extraction.
    
    This class manages communication with AJAX endpoints to extract
    real-time monitoring data and historical time-series information.
    """
    
    def __init__(self, session: Optional[requests.Session] = None):
        """Initialize AJAX extractor.
        
        Args:
            session: Optional authenticated requests session
        """
        self.session = session
        self.logger = logging.getLogger(__name__)
        # Will be set during AJAX request for timestamp calculation
        self._ajax_calculated_start = None
        self._ajax_calculated_end = None
    
    def extract_ajax_data(
        self,
        host: str,
        service: str,
        period: str = "4h",
        server_url: Optional[str] = None,
        site: Optional[str] = None
    ) -> List[Tuple[str, Union[float, str]]]:
        """Main AJAX extraction method.
        
        Args:
            host: Host name to extract data for
            service: Service name to extract data for  
            period: Time period for data extraction (4h, 25h, 8d, etc.)
            server_url: Base URL of Checkmk server
            site: Checkmk site name
            
        Returns:
            List of (timestamp, value) tuples extracted from AJAX endpoints
            
        Raises:
            ScrapingError: If AJAX extraction fails
        """
        if not self.session:
            from .. import ScrapingError
            raise ScrapingError("No authenticated session available for AJAX extraction")
            
        self.logger.debug(f"Starting AJAX data extraction for {host}/{service}, period: {period}")
        
        try:
            # Try multiple AJAX strategies
            extracted_data = []
            
            # Strategy 1: ajax_render_graph_content.py endpoint
            try:
                graph_params = self._extract_graph_parameters_from_page(host, service, server_url, site)
                if graph_params:
                    ajax_response = self.make_ajax_request(graph_params, period, server_url, site)
                    if ajax_response:
                        data = self.parse_ajax_response(ajax_response)
                        if data:
                            extracted_data.extend(data)
                            self.logger.debug(f"Successfully extracted {len(data)} points via ajax_render_graph_content")
            except Exception as e:
                self.logger.debug(f"ajax_render_graph_content strategy failed: {e}")
            
            # Strategy 2: Direct ajax_graph.py endpoint (if available)
            if not extracted_data:
                try:
                    ajax_params = self._prepare_ajax_params_for_direct_endpoint(host, service, period, site)
                    direct_response = self._make_direct_ajax_request(ajax_params, server_url, site)
                    if direct_response:
                        data = self._parse_direct_ajax_response(direct_response)
                        if data:
                            extracted_data.extend(data)
                            self.logger.debug(f"Successfully extracted {len(data)} points via direct AJAX")
                except Exception as e:
                    self.logger.debug(f"Direct AJAX strategy failed: {e}")
            
            return extracted_data
            
        except Exception as e:
            from .. import ScrapingError
            error_msg = f"AJAX extraction failed for {host}/{service}: {e}"
            self.logger.error(error_msg)
            raise ScrapingError(
                error_msg,
                response_data={"host": host, "service": service, "period": period, "error": str(e)}
            )
    
    def make_ajax_request(
        self, 
        parameters: Dict[str, Any], 
        period: str = "4h",
        server_url: Optional[str] = None,
        site: Optional[str] = None
    ) -> Optional[str]:
        """Make AJAX POST request to ajax_render_graph_content.py endpoint.
        
        This method replicates the browser's AJAX flow by sending a POST request 
        with proper request parameter to the ajax_render_graph_content.py endpoint.
        
        Args:
            parameters: Dictionary containing graph_recipe, graph_data_range, 
                       graph_render_config, and graph_display_id
            period: Time period for the data request (e.g., '4h', '25h', '8d')
            server_url: Base URL of Checkmk server
            site: Checkmk site name
                       
        Returns:
            Raw HTML response from the AJAX endpoint, or None if request fails
            
        Raises:
            ScrapingError: If AJAX request fails with authentication or network issues
        """
        from .. import ScrapingError
        
        self.logger.debug("Making AJAX request to ajax_render_graph_content.py")
        
        try:
            # Ensure we have an authenticated session
            if not self.session:
                raise ScrapingError("Session not authenticated")
            
            # Construct the correct AJAX endpoint URL 
            ajax_url = f"{server_url}/{site}/check_mk/ajax_render_graph_content.py"
            
            # Update graph_data_range with correct time_range based on period parameter
            updated_graph_data_range = parameters['graph_data_range'].copy()
            
            # Calculate time range based on requested period
            period_seconds = self._convert_period_to_seconds(period)
            current_time = int(time.time())
            start_time = current_time - period_seconds
            
            # Store calculated time range for use in timestamp calculation
            self._ajax_calculated_start = start_time
            self._ajax_calculated_end = current_time
            
            # Update time_range to match the requested period
            if 'time_range' in updated_graph_data_range:
                self.logger.debug(f"Original time_range: {updated_graph_data_range['time_range']}")
                updated_graph_data_range['time_range'] = [start_time, current_time]
                self.logger.debug(f"Updated time_range for period {period}: [{start_time}, {current_time}] ({period_seconds} seconds)")
            else:
                self.logger.warning("No time_range found in graph_data_range, adding new one")
                updated_graph_data_range['time_range'] = [start_time, current_time]
            
            # Ensure render_config has required fields for Pydantic validation
            render_config = parameters['graph_render_config'].copy()
            
            # Add required fields if missing
            if 'foreground_color' not in render_config:
                render_config['foreground_color'] = '#000000'
            if 'background_color' not in render_config:
                render_config['background_color'] = '#ffffff'
            if 'canvas_color' not in render_config:
                render_config['canvas_color'] = '#ffffff'
            
            # Construct request data in the exact format the browser uses
            request_data = {
                "graph_recipe": parameters['graph_recipe'],
                "graph_data_range": updated_graph_data_range,
                "graph_render_config": render_config,
                "graph_display_id": parameters['graph_display_id']
            }
            
            # Encode request as JSON string for the 'request' parameter
            request_json = json.dumps(request_data, separators=(',', ':'))
            post_data = "request=" + quote(request_json)
            
            self.logger.debug(f"AJAX URL: {ajax_url}")
            self.logger.debug(f"POST data length: {len(post_data)} characters")
            
            # Set headers to match browser AJAX requests
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'X-Requested-With': 'XMLHttpRequest',
                'Accept': 'text/html, */*; q=0.01',
                'Referer': f"{server_url}/{site}/check_mk/index.py"
            }
            
            # Make the POST request
            response = self.session.post(
                ajax_url,
                data=post_data,
                headers=headers,
                timeout=30,
                allow_redirects=True
            )
            
            self.logger.debug(f"AJAX response status: {response.status_code}")
            self.logger.debug(f"AJAX response length: {len(response.text)} characters")
            
            if response.status_code == 200:
                # Check if response is JSON with result_code (common Checkmk AJAX pattern)
                try:
                    if response.headers.get('content-type', '').startswith('application/json'):
                        json_response = response.json()
                        self.logger.debug(f"AJAX JSON response keys: {json_response.keys()}")
                        
                        # Check for different response formats
                        if json_response.get('result_code') == 0:
                            # Standard Checkmk AJAX success response
                            result_content = json_response.get('result', '')
                            self.logger.debug("AJAX request successful with result_code=0")
                            return result_content
                        elif 'graph' in json_response and 'html' in json_response:
                            # Graph endpoint success response (different format)
                            self.logger.debug("AJAX request successful - received graph data response")
                            return response.text  # Return the full JSON response for parsing
                        elif json_response.get('result_code') is not None:
                            # Error response with result_code
                            error_code = json_response.get('result_code', 'unknown')
                            error_result = json_response.get('result', '')
                            error_severity = json_response.get('severity', 'error')
                            error_msg = f"AJAX request failed with result_code={error_code}, result='{error_result}', severity={error_severity}"
                            self.logger.error(error_msg)
                            raise ScrapingError(error_msg, url=ajax_url, response_data=json_response)
                        else:
                            # Unknown response format, try to use it anyway
                            self.logger.debug("AJAX request received unknown format, returning response")
                            return response.text
                    else:
                        # Non-JSON response, return as is
                        self.logger.debug("AJAX request successful, returning response content")
                        return response.text
                except json.JSONDecodeError:
                    # Not valid JSON, treat as regular text response
                    self.logger.debug("AJAX request successful, returning response content (non-JSON)")
                    return response.text
            elif response.status_code == 401:
                error_msg = "Authentication failed for AJAX request - session may have expired"
                self.logger.error(error_msg)
                raise ScrapingError(error_msg, url=ajax_url, status_code=response.status_code)
            elif response.status_code == 403:
                error_msg = "Access forbidden for AJAX request - insufficient permissions"
                self.logger.error(error_msg)
                raise ScrapingError(error_msg, url=ajax_url, status_code=response.status_code)
            elif response.status_code == 404:
                error_msg = "AJAX endpoint not found - URL may be incorrect"
                self.logger.error(error_msg)
                raise ScrapingError(error_msg, url=ajax_url, status_code=response.status_code)
            else:
                error_msg = f"AJAX request failed with status {response.status_code}: {response.text[:200]}"
                self.logger.error(error_msg)
                raise ScrapingError(error_msg, url=ajax_url, status_code=response.status_code)
                
        except requests.exceptions.RequestException as e:
            error_msg = f"Network error during AJAX request: {e}"
            self.logger.error(error_msg)
            raise ScrapingError(error_msg, url=ajax_url, response_data={"error": str(e)})
        except Exception as e:
            if isinstance(e, ScrapingError):
                raise
            error_msg = f"Unexpected error during AJAX request: {e}"
            self.logger.error(error_msg)
            raise ScrapingError(error_msg, url=ajax_url, response_data={"error": str(e)})

    def parse_ajax_response(self, ajax_html: str) -> List[Tuple[str, float]]:
        """Parse time-series data from AJAX response HTML.
        
        Extracts rich time-series data from embedded JavaScript parameters 
        in cmk.graphs.create_graph() calls. The response contains complete 
        graph data with data points and summary statistics.
        
        Args:
            ajax_html: Raw JSON response from ajax_render_graph_content.py
            
        Returns:
            List of (timestamp, value) tuples with timestamps in ISO format
            
        Raises:
            ScrapingError: If parsing the AJAX response fails completely
        """
        from bs4 import Tag
        
        self.logger.debug("Parsing time-series data from AJAX response")
        self.logger.debug(f"AJAX response length: {len(ajax_html)} characters")
        
        # Validate input parameters
        if not ajax_html:
            self.logger.warning("Empty AJAX response received")
            return []
            
        if not isinstance(ajax_html, str):
            self.logger.warning(f"Invalid AJAX response type: {type(ajax_html)}")
            return []
            
        if len(ajax_html.strip()) < 10:
            self.logger.warning("AJAX response too short to contain valid data")
            return []
        
        extracted_data = []
        
        try:
            # Parse response and extract embedded graph data efficiently
            # Handle both JSON and direct HTML responses
            if ajax_html.strip().startswith('{'):
                try:
                    json_data = json.loads(ajax_html)
                    self.logger.debug("Detected JSON data in AJAX response")
                    
                    # Validate JSON response structure
                    if not isinstance(json_data, dict):
                        self.logger.warning("JSON response is not a dictionary")
                        return []
                    
                    # Check for successful response
                    result_code = json_data.get('result_code')
                    if result_code == 0:
                        self.logger.debug("AJAX request successful with result_code=0")
                        
                        # Extract HTML content containing JavaScript graph calls
                        result_html = json_data.get('result', '')
                        
                        # Validate result content
                        if not result_html:
                            self.logger.warning("Empty result content in JSON response")
                            return []
                            
                        if not isinstance(result_html, str):
                            self.logger.warning(f"Invalid result content type: {type(result_html)}")
                            return []
                        
                        # Extract graph data directly from cmk.graphs.create_graph() calls
                        graph_data = self._extract_graph_data_from_javascript(result_html)
                        
                        # Process the extracted graph data if found
                        if graph_data:
                            extracted_data = self._process_graph_data(graph_data)
                            if extracted_data:
                                self.logger.debug(f"Successfully extracted {len(extracted_data)} data points from graph data")
                                return self._clean_and_sort_data(extracted_data)
                        else:
                            self.logger.debug("No graph data found in JSON wrapped AJAX response")
                    else:
                        # Handle error responses gracefully
                        error_result = json_data.get('result', 'Unknown error')
                        error_severity = json_data.get('severity', 'error')
                        self.logger.warning(f"AJAX request failed with result_code={result_code}, result='{error_result}', severity={error_severity}")
                        return []
                        
                except json.JSONDecodeError as e:
                    self.logger.debug(f"Failed to parse as JSON ({e}), treating as HTML")
            else:
                # Handle direct HTML response (newer ajax_render_graph_content.py format)
                self.logger.debug("Detected direct HTML response from AJAX endpoint")
                
                # Extract graph data directly from cmk.graphs.create_graph() calls in HTML
                graph_data = self._extract_graph_data_from_javascript(ajax_html)
                
                # Process the extracted graph data if found
                if graph_data:
                    extracted_data = self._process_graph_data(graph_data)
                    if extracted_data:
                        self.logger.debug(f"Successfully extracted {len(extracted_data)} data points from HTML response")
                        return self._clean_and_sort_data(extracted_data)
                else:
                    self.logger.debug("No graph data found in direct HTML AJAX response")
            
            # Fallback: Try to extract from the HTML content using table parsing
            self.logger.debug("Trying HTML table parsing as fallback")
            
            # Parse the HTML content for table data  
            # Use ajax_html directly for HTML responses, or result_html for JSON responses
            html_to_parse = ajax_html
            if ajax_html.strip().startswith('{'):
                try:
                    json_data = json.loads(ajax_html)
                    if json_data.get('result_code') == 0:
                        html_to_parse = json_data.get('result', ajax_html)
                except json.JSONDecodeError:
                    pass
            
            soup = self._parse_html_with_fallback(html_to_parse)
            
            # Look for table data in the HTML legend
            tables = soup.find_all('table')
            for table in tables:
                if isinstance(table, Tag):
                    table_class = table.get('class')
                    if table_class and 'legend' in table_class:
                        rows = table.find_all('tr')
                        for row in rows:
                            if isinstance(row, Tag):
                                cells = row.find_all(['td', 'th'])
                                for cell in cells:
                                    if isinstance(cell, Tag):
                                        cell_text = cell.get_text(strip=True)
                                        # Look for temperature values with units
                                        temp_match = re.search(r'([\d.]+)\s*°C', cell_text)
                                        if temp_match:
                                            temp_value = float(temp_match.group(1))
                                            # Use current time as timestamp for summary data
                                            timestamp = datetime.datetime.now().isoformat()
                                            extracted_data.append((timestamp, temp_value))
            
            if extracted_data:
                self.logger.debug(f"Extracted {len(extracted_data)} data points from HTML fallback")
                return self._clean_and_sort_data(extracted_data)
            
            # If we still have no data, try the original HTML parsing approach
            if not extracted_data and not ajax_html.strip().startswith('{'):
                self.logger.debug("Processing direct HTML content")
                soup = self._parse_html_with_fallback(ajax_html)
                
                # Use existing HTML parsing strategies as fallback
                script_tags = soup.find_all('script', type='text/javascript')
                for script in script_tags:
                    script_content = script.get_text()
                    if not script_content.strip():
                        continue
                    
                    # Look for various data patterns
                    data_patterns = [
                        r'data\s*:\s*\[\s*\[([d\.,\s\[\]]+)\]\s*\]',
                        r'points\s*:\s*\[([d\.,\s\[\]]+)\]',
                        r'\[\s*(\d{10}),\s*([\d\.]+)\s*\]',
                    ]
                    
                    for pattern in data_patterns:
                        matches = re.finditer(pattern, script_content, re.MULTILINE | re.DOTALL)
                        for match in matches:
                            try:
                                if len(match.groups()) == 2:
                                    timestamp_raw = match.group(1)
                                    value_raw = match.group(2)
                                    timestamp = self._convert_timestamp_to_iso(timestamp_raw)
                                    if timestamp:
                                        value = float(value_raw)
                                        extracted_data.append((timestamp, value))
                            except (ValueError, TypeError) as e:
                                continue
            
            # Clean and return the extracted data
            return self._clean_and_sort_data(extracted_data)
                
        except Exception as e:
            from .. import ScrapingError
            error_msg = f"Failed to parse AJAX response: {e}"
            self.logger.error(error_msg)
            raise ScrapingError(
                error_msg,
                html_snippet=ajax_html[:500] if ajax_html else None,
                response_data={"error": str(e)}
            )
    
    def _prepare_ajax_params_for_direct_endpoint(
        self, 
        host: str, 
        service: str, 
        period: str = "4h", 
        site: Optional[str] = None
    ) -> Dict[str, Any]:
        """Prepare parameters for direct AJAX endpoint request.
        
        Args:
            host: Host name
            service: Service name
            period: Time period for data extraction (4h, 25h, 8d, etc.)
            site: Checkmk site name
            
        Returns:
            Dictionary of parameters formatted for the direct AJAX endpoint
        """
        
        try:
            # For ajax_graph.py, construct the context parameter structure
            current_time = int(time.time())
            period_seconds = self._convert_period_to_seconds(period)
            start_time = current_time - period_seconds
            
            minimal_context = {
                "data_range": {
                    "time_range": [start_time, current_time],
                    "step": 30
                },
                "render_config": {
                    "foreground_color": "#ffffff",
                    "background_color": "#ffffff",
                    "show_legend": True
                },
                "definition": {
                    "specification": {
                        "site": site,
                        "host_name": host,
                        "service_description": service,
                        "graph_index": 0,
                        "graph_id": "temp",
                        "graph_type": "template"
                    },
                    "title": service,
                    "unit_spec": {
                        "type": "convertible",
                        "notation": {
                            "type": "decimal",
                            "symbol": "°C"
                        },
                        "precision": {
                            "type": "auto",
                            "digits": 2
                        }
                    },
                    "explicit_vertical_range": None,
                    "omit_zero_metrics": False,
                    "consolidation_function": "max",
                    "metrics": [
                        {
                            "title": "Temperature",
                            "line_type": "stack",
                            "operation": {
                                "site_id": site,
                                "host_name": host,
                                "service_name": service,
                                "metric_name": "temp",
                                "consolidation_func_name": "max",
                                "scale": 1.0,
                                "ident": "rrd"
                            },
                            "unit": {
                                "type": "convertible",
                                "notation": {
                                    "type": "decimal",
                                    "symbol": "°C"
                                },
                                "precision": {
                                    "type": "auto",
                                    "digits": 2
                                }
                            },
                            "color": "#ff6e21"
                        }
                    ],
                    "horizontal_rules": []
                }
            }
            
            context_json = json.dumps(minimal_context)
            self.logger.debug("Created context for direct AJAX endpoint")
            return {
                'context': context_json
            }
                
        except Exception as e:
            self.logger.debug(f"Failed to prepare AJAX parameters: {e}")
            return {}

    def _make_direct_ajax_request(
        self, 
        _params: Dict[str, Any], 
        _server_url: Optional[str], 
        _site: Optional[str]
    ) -> Optional[str]:
        """Make direct AJAX request to ajax_graph.py or similar endpoint."""
        # Implementation for direct AJAX requests
        # This would be similar to make_ajax_request but for different endpoint
        return None  # Placeholder
    
    def _parse_direct_ajax_response(self, _response: str) -> List[Tuple[str, Union[float, str]]]:
        """Parse direct AJAX response data."""
        # Implementation for parsing direct AJAX responses
        return []  # Placeholder
    
    def _extract_graph_parameters_from_page(
        self, 
        _host: str, 
        _service: str, 
        _server_url: Optional[str], 
        _site: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """Extract graph parameters from monitoring page for AJAX request."""
        # Implementation for extracting graph parameters from HTML page
        return None  # Placeholder
    
    def _extract_graph_data_from_javascript(self, html_content: str) -> Optional[dict]:
        """Extract graph data from cmk.graphs.create_graph() JavaScript calls."""
        self.logger.debug("Extracting graph data from JavaScript calls")
        self.logger.debug(f"HTML content length: {len(html_content)}")
        
        # The data is embedded as the second parameter in cmk.graphs.create_graph calls
        # Format: cmk.graphs.create_graph("complex_html_string", {graph_data_object}, ...)
        
        create_graph_pos = html_content.find('cmk.graphs.create_graph')
        if create_graph_pos == -1:
            self.logger.debug("No 'cmk.graphs.create_graph' found in HTML content")
            # Look for alternative patterns that might contain the data
            patterns_to_check = [
                'cmk.graphs',
                'create_graph', 
                'graph_data',
                'curves',
                'points',
                'temperature',
                'data',
                'time_axis'
            ]
            
            found_patterns = {}
            for pattern in patterns_to_check:
                if pattern in html_content.lower():
                    count = html_content.lower().count(pattern)
                    found_patterns[pattern] = count
            
            self.logger.debug(f"Patterns found in AJAX response: {found_patterns}")
            
            # Log a sample of the beginning and end of content
            if len(html_content) > 200:
                self.logger.debug(f"AJAX response start: {html_content[:200]}...")
                self.logger.debug(f"AJAX response end: ...{html_content[-200:]}")
            
            return None
        
        try:
            # Find the opening parenthesis
            paren_pos = html_content.find('(', create_graph_pos)
            if paren_pos == -1:
                return None
            
            # Find the second parameter (after the first comma)
            # This is complex because the first parameter is a large HTML string
            # We need to find the matching closing quote and comma
            
            # Start after the opening parenthesis
            pos = paren_pos + 1
            
            # Skip whitespace
            while pos < len(html_content) and html_content[pos].isspace():
                pos += 1
            
            # The first parameter should start with a quote
            if pos >= len(html_content) or html_content[pos] not in ['"', "'"]:
                return None
            
            quote_char = html_content[pos]
            pos += 1
            
            # Find the matching closing quote (accounting for escapes)
            while pos < len(html_content):
                if html_content[pos] == quote_char and html_content[pos-1] != '\\':
                    break
                pos += 1
            else:
                return None
            
            # Move past the closing quote
            pos += 1
            
            # Skip whitespace and find the comma
            while pos < len(html_content) and html_content[pos].isspace():
                pos += 1
            
            if pos >= len(html_content) or html_content[pos] != ',':
                return None
            
            # Move past the comma
            pos += 1
            
            # Skip whitespace
            while pos < len(html_content) and html_content[pos].isspace():
                pos += 1
            
            # Now we should be at the start of the graph data object
            if pos >= len(html_content) or html_content[pos] != '{':
                return None
            
            # Extract the JSON object by counting braces
            brace_count = 0
            start_pos = pos
            
            while pos < len(html_content):
                if html_content[pos] == '{':
                    brace_count += 1
                elif html_content[pos] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        # Found the end of the object
                        json_str = html_content[start_pos:pos+1]
                        self.logger.debug(f"Extracted JSON object length: {len(json_str)} characters")
                        self.logger.debug(f"JSON sample: {json_str[:200]}...")
                        try:
                            parsed_data = json.loads(json_str)
                            self.logger.debug(f"Successfully parsed JSON with keys: {list(parsed_data.keys()) if isinstance(parsed_data, dict) else 'not_dict'}")
                            return parsed_data
                        except json.JSONDecodeError as e:
                            self.logger.debug(f"JSON parsing failed: {e}")
                            return None
                pos += 1
            
            self.logger.debug("Reached end of content without finding closing brace")
            return None
            
        except Exception as e:
            self.logger.debug(f"Failed to extract graph data from JavaScript: {e}")
            return None
    
    def _process_graph_data(self, graph_data: dict) -> List[Tuple[str, float]]:
        """Process extracted graph data into time-series format.
        
        The Checkmk graph data structure contains:
        - curves[0].points: Array of [timestamp, value] pairs for time-series data
        - time_axis.labels: Array of time labels for timestamp conversion
        - curves[0].scalars: Summary statistics (min, max, average, etc.)
        """
        processed_data = []
        
        try:
            self.logger.debug(f"Processing graph data with keys: {list(graph_data.keys())}")
            
            # Extract time-series data from curves[0].points
            if 'curves' in graph_data and isinstance(graph_data['curves'], list) and len(graph_data['curves']) > 0:
                curve = graph_data['curves'][0]  # First curve contains the temperature data
                self.logger.debug(f"First curve keys: {list(curve.keys()) if isinstance(curve, dict) else 'not_dict'}")
                
                if isinstance(curve, dict) and 'points' in curve:
                    points = curve['points']
                    self.logger.debug(f"Found {len(points)} data points in curve")
                    
                    # Get time axis information for proper timestamp calculation
                    time_axis = graph_data.get('time_axis', {})
                    start_time = graph_data.get('start_time')
                    step = graph_data.get('step', 60)  # Default 1 minute intervals
                    
                    self.logger.debug(f"Time axis info - start_time: {start_time}, step: {step}")
                    
                    # Process each data point
                    for i, point in enumerate(points):
                        if isinstance(point, (list, tuple)) and len(point) >= 2:
                            time_offset = point[0]  # Time offset from start
                            value = point[1]       # Temperature value
                            
                            # Skip points with invalid time_offset or value
                            if time_offset is None or value is None:
                                continue
                                
                            # Calculate actual timestamp
                            if start_time is not None and isinstance(time_offset, (int, float)):
                                actual_timestamp = start_time + (time_offset * step)
                                # Convert to ISO format
                                iso_timestamp = datetime.datetime.fromtimestamp(actual_timestamp).isoformat()
                            else:
                                # Fallback to current time with offset
                                current_time = time.time()
                                actual_timestamp = current_time - (len(points) - i) * step
                                iso_timestamp = datetime.datetime.fromtimestamp(actual_timestamp).isoformat()
                            
                            if isinstance(value, (int, float)):
                                processed_data.append((iso_timestamp, float(value)))
                    
                    self.logger.debug(f"Successfully processed {len(processed_data)} time-series data points")
                else:
                    self.logger.debug("No 'points' found in first curve")
            else:
                self.logger.debug("No 'curves' found in graph data or curves array is empty")
            
            # ALSO extract summary statistics from curves[0].scalars for completeness
            if 'curves' in graph_data and len(graph_data['curves']) > 0:
                curve = graph_data['curves'][0]
                if isinstance(curve, dict) and 'scalars' in curve:
                    scalars = curve['scalars']
                    self.logger.debug(f"Found scalars: {list(scalars.keys()) if isinstance(scalars, dict) else 'not_dict'}")
                    
                    # Add summary statistics as special entries
                    for stat_name, stat_value in scalars.items():
                        if isinstance(stat_value, (list, tuple)) and len(stat_value) >= 1:
                            # Scalars format: [value, "formatted_string"]
                            value = stat_value[0]
                            if isinstance(value, (int, float)) and value is not None:
                                # Use stat name as timestamp for summary stats
                                processed_data.append((stat_name, float(value)))
                                self.logger.debug(f"Added summary stat: {stat_name} = {value}")
            
        except Exception as e:
            self.logger.debug(f"Error processing graph data: {e}")
            import traceback
            self.logger.debug(f"Traceback: {traceback.format_exc()}")
        
        return processed_data
    
    def _clean_and_sort_data(self, data: List[Tuple[str, float]]) -> List[Tuple[str, float]]:
        """Clean and sort extracted data."""
        if not data:
            return []
        
        # Remove duplicates and sort by timestamp
        unique_data = list(dict.fromkeys(data))  # Remove duplicates while preserving order
        
        try:
            # Sort by timestamp if possible
            unique_data.sort(key=lambda x: x[0])
        except (TypeError, ValueError):
            # If sorting fails, just return the unique data
            pass
        
        return unique_data
    
    def _convert_timestamp_to_iso(self, timestamp_str: str) -> Optional[str]:
        """Convert various timestamp formats to ISO format."""
        
        try:
            # If it's already in ISO format, return as-is
            if re.match(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}', timestamp_str):
                return timestamp_str
            
            # If it's a Unix timestamp
            if re.match(r'^\d{10}$', timestamp_str):
                unix_timestamp = int(timestamp_str)
                dt = datetime.datetime.fromtimestamp(unix_timestamp)
                return dt.isoformat()
            
            # Add other timestamp format conversions as needed
            
        except (ValueError, TypeError):
            pass
        
        return None
    
    def _parse_html_with_fallback(self, html_content: str) -> BeautifulSoup:
        """Parse HTML with parser fallback."""
        from bs4 import BeautifulSoup
        
        try:
            # Try lxml first
            return BeautifulSoup(html_content, 'lxml')
        except:
            try:
                # Fall back to html.parser
                return BeautifulSoup(html_content, 'html.parser')
            except:
                # Last resort: default parser
                return BeautifulSoup(html_content)
    
    def _convert_period_to_seconds(self, period: str) -> int:
        """Convert time period string to seconds.
        
        Args:
            period: Time period string (e.g., '4h', '25h', '8d', '1w')
            
        Returns:
            Number of seconds in the period
        """
        
        try:
            match = re.match(r'^(\d+)([hdw])$', period.lower())
            if match:
                value = int(match.group(1))
                unit = match.group(2)
                
                if unit == 'h':
                    return value * 3600  # hours to seconds
                elif unit == 'd':
                    return value * 24 * 3600  # days to seconds
                elif unit == 'w':
                    return value * 7 * 24 * 3600  # weeks to seconds
            
            # Default fallback
            return 4 * 3600  # 4 hours
            
        except (ValueError, TypeError):
            return 4 * 3600  # 4 hours fallback