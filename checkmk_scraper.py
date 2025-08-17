#!/usr/bin/env python3
"""
Checkmk Historical Data Scraper

A standalone Python script to scrape historical temperature data from Checkmk monitoring pages.
Extracts time-series data from graphs and summary statistics from tables without using Selenium.

PHASE 4C: CORRECTED AJAX ENDPOINT IMPLEMENTATION (2025-08-16):
✅ Corrected endpoint: /cmk/check_mk/ajax_render_graph_content.py (browser-accurate)
✅ Fixed parameter format: request= instead of context= (matches JavaScript source)
✅ Updated parameter structure: graph_recipe, graph_data_range, graph_render_config, graph_display_id
✅ Removed hardcoded graph_id dependency for flexible graph support
✅ Optimized response parsing for direct HTML content (not JSON wrapper)
✅ Enhanced time-series extraction with Unix timestamp to ISO conversion
✅ Comprehensive error handling with validation error logging
✅ Graceful fallback to static JavaScript parsing when AJAX fails

Phase 4C Achievements:
- Switched from incorrect ajax_graph.py to correct ajax_render_graph_content.py endpoint
- Changed parameter format from 'context=' to 'request=' matching browser behavior
- Updated parameter structure to exact browser format with graph_display_id
- Eliminated hardcoded graph_id="temperature" dependency for universal graph support
- Optimized parsing for direct HTML content returned by ajax_render_graph_content.py
- Maintained backward compatibility and comprehensive error handling
- Expected output: ~480 data points (4 hours × 60 minutes ÷ 0.5 minutes per sample)

Author: Checkmk LLM Agent Development Team
Date: 2025-08-12
"""

import sys
import urllib.parse
import re
import json
import click
import requests
from datetime import datetime
from typing import Optional, List, Tuple, Dict, Union, Any
from urllib.parse import quote

# HTML parsing dependencies
try:
    from bs4 import BeautifulSoup, Tag
except ImportError:
    print("Error: BeautifulSoup4 not installed. Please run: pip install beautifulsoup4")
    sys.exit(1)

# Check for lxml availability at import time for parser selection
try:
    import lxml  # noqa: F401 - Only used for parser detection
    print("Info: lxml parser available for fast HTML parsing")
except ImportError:
    print("Warning: lxml not installed. HTML parsing will be slower. Install with: pip install lxml")

# Import from existing codebase
try:
    from checkmk_agent.config import load_config, CheckmkConfig
    from checkmk_agent.api_client import CheckmkClient
    from checkmk_agent.logging_utils import setup_logging, get_logger_with_request_id
    from checkmk_agent.utils.request_context import generate_request_id, set_request_id
except ImportError as e:
    print(f"Error importing from checkmk_agent module: {e}")
    print("Make sure you're running this script from the project root directory.")
    sys.exit(1)


class ScrapingError(Exception):
    """Custom exception for web scraping errors with context.
    
    This exception provides detailed context about scraping failures,
    including HTTP status codes, URLs, and HTML snippets for debugging.
    """

    def __init__(
        self,
        message: str,
        url: Optional[str] = None,
        status_code: Optional[int] = None,
        html_snippet: Optional[str] = None,
        response_data: Optional[Dict] = None,
    ):
        """Initialize ScrapingError with context information.
        
        Args:
            message: Human-readable error description
            url: The URL that was being scraped when the error occurred
            status_code: HTTP status code if applicable
            html_snippet: Snippet of HTML content for debugging (first 500 chars)
            response_data: Any additional response data for context
        """
        super().__init__(message)
        self.url = url
        self.status_code = status_code
        self.html_snippet = html_snippet[:500] if html_snippet else None
        self.response_data = response_data

    def __str__(self) -> str:
        """Provide detailed error message for debugging."""
        parts = [str(self.args[0])]

        if self.url:
            parts.append(f"URL: {self.url}")

        if self.status_code:
            parts.append(f"Status: {self.status_code}")

        # Add helpful context based on status code
        if self.status_code == 401:
            parts.append("Authentication failed - check credentials")
        elif self.status_code == 403:
            parts.append("Access forbidden - check permissions")
        elif self.status_code == 404:
            parts.append("Page not found - check URL and parameters")
        elif self.status_code == 500:
            parts.append("Server error - Checkmk may be unavailable")

        if self.html_snippet:
            parts.append(f"HTML snippet: {self.html_snippet}")

        return " | ".join(parts)


class CheckmkHistoricalScraper:
    """Main scraper class for extracting historical data from Checkmk web interface.
    
    This class handles authentication, page fetching, and data extraction
    from Checkmk monitoring pages to provide historical temperature data.
    """

    def __init__(self, config: CheckmkConfig):
        """Initialize the scraper with Checkmk configuration.
        
        Args:
            config: CheckmkConfig object containing server details and authentication
        """
        self.config = config
        self.logger = get_logger_with_request_id(__name__)
        self.session: Optional[requests.Session] = None
        self.checkmk_client: Optional[CheckmkClient] = None
        
        # Target URL template for service graphs - use direct view URL
        self.base_graph_url = (
            f"{config.server_url}/{config.site}/check_mk/view.py"
            "?host={host}&service={service}&siteopt={site}&view_name=service_graphs"
        )
        
        self.logger.debug(f"Initialized scraper for server: {config.server_url}")
        
        # Track available HTML parsers
        self.available_parsers = self._detect_available_parsers()
        self.logger.debug(f"Available HTML parsers: {self.available_parsers}")

    def _detect_available_parsers(self) -> List[str]:
        """Detect which HTML parsers are available on the system.
        
        Returns:
            List of available parser names in order of preference
        """
        parsers = []
        
        # Test lxml parser
        try:
            BeautifulSoup("<html></html>", "lxml")
            parsers.append("lxml")
        except Exception:
            pass
            
        # Test html.parser (built-in)
        try:
            BeautifulSoup("<html></html>", "html.parser")
            parsers.append("html.parser")
        except Exception:
            pass
            
        # Test html5lib parser
        try:
            BeautifulSoup("<html></html>", "html5lib")
            parsers.append("html5lib")
        except Exception:
            pass
            
        if not parsers:
            parsers = ["html.parser"]  # Fallback to built-in
            
        return parsers
    
    def _parse_html_with_fallback(self, html_content: str) -> BeautifulSoup:
        """Parse HTML content using best available parser with fallbacks.
        
        Args:
            html_content: Raw HTML content to parse
            
        Returns:
            BeautifulSoup object for HTML navigation
            
        Raises:
            ScrapingError: If all parsers fail
        """
        last_error = None
        
        for parser in self.available_parsers:
            try:
                self.logger.debug(f"Attempting to parse HTML with {parser} parser")
                soup = BeautifulSoup(html_content, parser)
                
                # Basic validation - check if we got a valid parse
                if soup and soup.find():
                    self.logger.debug(f"Successfully parsed HTML with {parser} parser")
                    return soup
                else:
                    self.logger.debug(f"Parser {parser} returned empty or invalid result")
                    continue
                    
            except Exception as e:
                self.logger.debug(f"Parser {parser} failed: {e}")
                last_error = e
                continue
        
        # All parsers failed
        error_msg = f"All HTML parsers failed. Last error: {last_error}"
        self.logger.error(error_msg)
        raise ScrapingError(
            error_msg,
            html_snippet=html_content[:500] if html_content else None,
            response_data={"available_parsers": self.available_parsers, "last_error": str(last_error)}
        )
    
    def _validate_response_content(self, html_content: str, host: str, service: str) -> bool:
        """Validate that the response contains expected monitoring page content.
        
        Args:
            html_content: Raw HTML content to validate
            host: Expected host name
            service: Expected service name
            
        Returns:
            True if content appears to be a valid monitoring page
        """
        if not html_content or len(html_content) < 100:
            self.logger.debug("Response content too short to be valid")
            return False
            
        # Basic checks for Checkmk page structure
        checkmk_indicators = [
            "check_mk",
            "Checkmk",
            host.lower(),
            "graph",
            "monitoring"
        ]
        
        content_lower = html_content.lower()
        found_indicators = sum(1 for indicator in checkmk_indicators if indicator in content_lower)
        
        self.logger.debug(f"Found {found_indicators}/{len(checkmk_indicators)} content indicators")
        
        # Require at least 2 indicators to consider content valid
        return found_indicators >= 2
    
    def _validate_page_structure(self, soup: BeautifulSoup, host: str, service: str) -> bool:
        """Enhanced validation that page contains expected Checkmk monitoring content.
        
        Args:
            soup: Parsed HTML content
            host: Expected host name
            service: Expected service name
            
        Returns:
            True if page structure appears to be a valid Checkmk monitoring page
        """
        validation_checks = {
            "has_title": bool(soup.find("title")),
            "has_graphs": self._has_potential_graphs(soup),
            "has_tables": self._has_potential_tables(soup),
            "has_scripts": bool(soup.find_all("script")),
            "has_host_reference": self._contains_host_reference(soup, host),
            "has_service_reference": self._contains_service_reference(soup, service),
            "has_checkmk_elements": self._has_checkmk_elements(soup)
        }
        
        passed_checks = sum(validation_checks.values())
        total_checks = len(validation_checks)
        
        self.logger.debug(f"Page structure validation: {passed_checks}/{total_checks} checks passed")
        for check_name, result in validation_checks.items():
            self.logger.debug(f"  {check_name}: {result}")
        
        # Require at least 4 out of 7 checks to pass
        return passed_checks >= 4
    
    def _has_potential_graphs(self, soup: BeautifulSoup) -> bool:
        """Check if page contains elements that could be graphs."""
        graph_indicators = [
            soup.find_all("canvas"),
            soup.find_all("svg"),
            soup.find_all(attrs={"class": re.compile(r"graph", re.I)}),
            soup.find_all(attrs={"id": re.compile(r"graph", re.I)}),
            soup.find_all(attrs={"class": re.compile(r"chart", re.I)}),
            soup.find_all("div", attrs={"style": re.compile(r"chart|graph", re.I)})
        ]
        return any(len(indicator) > 0 for indicator in graph_indicators)
    
    def _has_potential_tables(self, soup: BeautifulSoup) -> bool:
        """Check if page contains data tables."""
        tables = soup.find_all("table")
        if not tables:
            return False
            
        # Look for tables that might contain temperature data
        for table in tables:
            table_text = table.get_text().lower()
            if any(keyword in table_text for keyword in ["temperature", "min", "max", "average", "last"]):
                return True
        return len(tables) > 0  # At least some tables exist
    
    def _contains_host_reference(self, soup: BeautifulSoup, host: str) -> bool:
        """Check if page contains reference to the expected host."""
        page_text = soup.get_text().lower()
        return host.lower() in page_text
    
    def _contains_service_reference(self, soup: BeautifulSoup, service: str) -> bool:
        """Check if page contains reference to the expected service."""
        page_text = soup.get_text().lower()
        service_keywords = service.lower().split()
        return any(keyword in page_text for keyword in service_keywords)
    
    def _has_checkmk_elements(self, soup: BeautifulSoup) -> bool:
        """Check for Checkmk-specific HTML elements and patterns."""
        checkmk_patterns = [
            soup.find_all(attrs={"class": re.compile(r"checkmk|cmk", re.I)}),
            soup.find_all(attrs={"id": re.compile(r"checkmk|cmk", re.I)}),
            soup.find_all("a", href=re.compile(r"check_mk|checkmk", re.I)),
            soup.find_all(string=re.compile(r"checkmk|check_mk", re.I))
        ]
        return any(len(pattern) > 0 for pattern in checkmk_patterns)

    def authenticate_session(self) -> requests.Session:
        """Set up authenticated session using existing CheckmkClient patterns.
        
        This method creates an authenticated session that can access both the REST API
        and the web interface pages. It reuses the CheckmkClient authentication but
        adapts it for web scraping by ensuring cookies are properly handled.
        
        Returns:
            Authenticated requests Session object
            
        Raises:
            ScrapingError: If authentication fails
        """
        self.logger.debug(f"Setting up authenticated session with Checkmk server: {self.config.server_url}")
        
        try:
            # Use existing CheckmkClient for authentication
            self.logger.debug("Initializing CheckmkClient for authentication")
            self.checkmk_client = CheckmkClient(self.config)
            
            # Extract the authenticated session and enhance it for web scraping
            self.session = self.checkmk_client.session
            
            # The CheckmkClient session already has Bearer token authentication
            # but for web interface access, we may need to establish a web session
            self.logger.debug("Enhancing session for web interface access")
            
            # Set additional headers for web interface compatibility
            self.session.headers.update({
                'User-Agent': 'Checkmk-Historical-Scraper/1.0',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            })
            
            # Enable cookie jar for session persistence
            if not self.session.cookies:
                from requests.cookies import RequestsCookieJar
                self.session.cookies = RequestsCookieJar()
            
            # Test the session with a simple API call first
            self.logger.debug("Testing authentication with version info request")
            version_info = self.checkmk_client.get_version_info()
            
            # Extract version information more safely
            checkmk_version = "unknown"
            if isinstance(version_info, dict):
                if 'versions' in version_info and isinstance(version_info['versions'], dict):
                    checkmk_version = version_info['versions'].get('checkmk', 'unknown')
                elif 'checkmk_version' in version_info:
                    checkmk_version = version_info.get('checkmk_version', 'unknown')
                    
            self.logger.debug(f"Authentication successful, Checkmk version: {checkmk_version}")
            
            # Test web interface access by trying to access the main page
            self.logger.debug("Testing web interface access")
            web_test_url = f"{self.config.server_url}/{self.config.site}/check_mk/"
            
            try:
                response = self.session.get(web_test_url, timeout=10, allow_redirects=True)
                self.logger.debug(f"Web interface test response: {response.status_code}")
                
                if response.status_code == 200:
                    self.logger.debug("Web interface access confirmed")
                elif response.status_code in [401, 403]:
                    self.logger.warning(f"Web interface returned {response.status_code} - may need additional authentication")
                else:
                    self.logger.warning(f"Web interface test returned unexpected status: {response.status_code}")
                    
            except Exception as e:
                self.logger.warning(f"Web interface test failed: {e} - continuing with API-only session")
            
            self.logger.debug("Session authentication completed successfully")
            return self.session
            
        except Exception as e:
            error_msg = f"Failed to authenticate with Checkmk server: {e}"
            self.logger.error(error_msg)
            raise ScrapingError(
                error_msg,
                url=self.config.server_url,
                response_data={"error": str(e)}
            )

    def fetch_page(self, period: str = "4h", host: str = "piaware", service: str = "Temperature Zone 0") -> str:
        """Fetch the monitoring page for specified time period.
        
        This method constructs the appropriate URL for accessing historical data
        and handles different time periods by mapping them to Checkmk's expected format.
        
        Args:
            period: Time period (4h, 25h, 8d, etc.)
            host: Target host name
            service: Service name (will be URL encoded)
            
        Returns:
            Raw HTML content of the page
            
        Raises:
            ScrapingError: If page fetch fails
        """
        if not self.session:
            self.logger.debug("No existing session, authenticating...")
            self.authenticate_session()
        
        # URL encode the service name properly
        encoded_service = urllib.parse.quote_plus(service)
        
        # Map time periods to Checkmk's expected format
        time_range_mapping = {
            "4h": "4h",      # Last 4 hours
            "25h": "25h",    # Last 25 hours 
            "8d": "8d",      # Last 8 days
            "35d": "35d",    # Last 35 days
            "1h": "1h",      # Last hour
            "1d": "1d",      # Last day
            "1w": "1w",      # Last week
            "1m": "1m",      # Last month
            "1y": "1y"       # Last year
        }
        
        # Validate and map the period
        if period not in time_range_mapping:
            self.logger.warning(f"Unknown time period '{period}', using default '4h'")
            period = "4h"
        
        mapped_period = time_range_mapping[period]
        self.logger.debug(f"Using time period: {period} (mapped to: {mapped_period})")
        
        # Construct the URL for the service graphs page
        full_url = self.base_graph_url.format(
            host=host,
            service=encoded_service,
            site=self.config.site
        )
        
        # Add time range parameter to URL - Checkmk supports timerange parameter
        if '?' in full_url:
            full_url += f"&timerange={mapped_period}"
        else:
            full_url += f"?timerange={mapped_period}"
        
        self.logger.debug(f"Fetching page with URL: {full_url} (timerange: {mapped_period})")
        
        try:
            if self.session is None:
                raise ScrapingError("Session not authenticated. Call authenticate_session() first.")
            
            response = self.session.get(
                full_url, 
                timeout=30, 
                allow_redirects=True,
                headers={'Referer': f"{self.config.server_url}/{self.config.site}/check_mk/"}
            )
            
            self.logger.debug(f"Response status: {response.status_code}, content-length: {len(response.content)}")
            
            # Check for successful response
            if response.status_code == 200:
                self.logger.debug("Successfully fetched monitoring page")
                
                # Basic validation: check if response contains expected content
                if self._validate_response_content(response.text, host, service):
                    return response.text
                else:
                    self.logger.warning("Response content validation failed")
                    
            elif response.status_code == 401:
                self.logger.warning("Authentication failed, attempting to re-authenticate")
                self.authenticate_session()
                # Retry with fresh authentication
                response = self.session.get(
                    full_url, 
                    timeout=30, 
                    allow_redirects=True,
                    headers={'Referer': f"{self.config.server_url}/{self.config.site}/check_mk/"}
                )
                if response.status_code == 200 and self._validate_response_content(response.text, host, service):
                    return response.text
                    
            # Handle other status codes
            raise ScrapingError(
                f"HTTP {response.status_code} error fetching page",
                url=full_url,
                status_code=response.status_code,
                html_snippet=response.text
            )
                
        except requests.RequestException as e:
            error_msg = f"Network error: {e}"
            self.logger.error(error_msg)
            raise ScrapingError(
                error_msg,
                url=full_url,
                response_data={"error": str(e)}
            )

    def _log_html_structure(self, soup: BeautifulSoup) -> None:
        """Log comprehensive information about HTML page structure for debugging.
        
        Args:
            soup: Parsed HTML content
        """
        self.logger.debug("=== HTML Structure Analysis ===")
        
        # Basic page info
        title = soup.find("title")
        self.logger.debug(f"Page title: {title.get_text().strip() if title else 'None'}")
        
        # Count key element types
        element_counts = {
            "divs": len(soup.find_all("div")),
            "tables": len(soup.find_all("table")),
            "scripts": len(soup.find_all("script")),
            "forms": len(soup.find_all("form")),
            "links": len(soup.find_all("a")),
            "images": len(soup.find_all("img")),
            "canvas": len(soup.find_all("canvas")),
            "svg": len(soup.find_all("svg"))
        }
        
        for element_type, count in element_counts.items():
            self.logger.debug(f"Found {count} {element_type} elements")
        
        # Log important CSS classes and IDs
        self._log_css_selectors(soup)
        
        # Log script tag information
        self._log_script_information(soup)
        
        # Log table structure
        self._log_table_structure(soup)
        
        # Log first 500 chars of body content
        body = soup.find("body")
        if body:
            body_text = body.get_text()[:500].strip()
            self.logger.debug(f"Body content preview: {body_text}...")
        
        self.logger.debug("=== End HTML Structure Analysis ===")
    
    def _log_css_selectors(self, soup: BeautifulSoup) -> None:
        """Log important CSS classes and IDs found in the page."""
        # Collect unique class names
        classes = set()
        for element in soup.find_all(attrs={"class": True}):
            if isinstance(element, Tag):
                class_attr = element.get("class")
                if isinstance(class_attr, list):
                    classes.update(class_attr)
                elif class_attr:
                    classes.add(class_attr)
        
        # Collect unique IDs
        ids = set()
        for element in soup.find_all(attrs={"id": True}):
            if isinstance(element, Tag):
                id_attr = element.get("id")
                if id_attr:
                    ids.add(id_attr)
        
        # Log interesting classes (graph/chart/table related)
        interesting_classes = [cls for cls in classes if any(keyword in cls.lower() 
                              for keyword in ["graph", "chart", "table", "data", "temperature", "sensor"])]
        
        if interesting_classes:
            self.logger.debug(f"Interesting CSS classes: {interesting_classes[:10]}")
        
        # Log interesting IDs
        interesting_ids = [id_name for id_name in ids if any(keyword in id_name.lower() 
                          for keyword in ["graph", "chart", "table", "data", "temperature", "sensor"])]
        
        if interesting_ids:
            self.logger.debug(f"Interesting IDs: {interesting_ids[:10]}")
    
    def _log_script_information(self, soup: BeautifulSoup) -> None:
        """Log information about script tags that might contain data."""
        scripts = soup.find_all("script")
        self.logger.debug(f"Found {len(scripts)} script tags")
        
        for i, script in enumerate(scripts[:5]):  # Log first 5 scripts
            script_content = script.get_text()
            if script_content.strip():
                # Look for JSON data or variables
                has_json = "json" in script_content.lower() or "{" in script_content
                has_data = any(keyword in script_content.lower() 
                              for keyword in ["data", "temperature", "series", "values"])
                
                self.logger.debug(f"Script {i+1}: {len(script_content)} chars, has_json={has_json}, has_data={has_data}")
                
                if has_json or has_data:
                    # Log first 200 chars of potentially interesting scripts
                    preview = script_content[:200].strip().replace("\n", " ")
                    self.logger.debug(f"Script {i+1} preview: {preview}...")
    
    def _log_table_structure(self, soup: BeautifulSoup) -> None:
        """Log information about tables that might contain summary data."""
        tables = soup.find_all("table")
        self.logger.debug(f"Found {len(tables)} table elements")
        
        for i, table in enumerate(tables[:3]):  # Log first 3 tables
            if isinstance(table, Tag):
                rows = table.find_all("tr")
                cells = table.find_all(["td", "th"])
                
                # Check if table contains temperature-related data
                table_text = table.get_text().lower()
                has_temp_data = any(keyword in table_text 
                                   for keyword in ["temperature", "min", "max", "average", "last", "°c", "°f"])
                
                self.logger.debug(f"Table {i+1}: {len(rows)} rows, {len(cells)} cells, has_temp_data={has_temp_data}")
                
                if has_temp_data and rows:
                    # Log first row as sample
                    first_row_text = rows[0].get_text().strip().replace("\n", " ")
                    self.logger.debug(f"Table {i+1} first row: {first_row_text}")
    
    def parse_graph_data(self, html_content: str, period: str = "4h") -> List[Tuple[str, Union[float, str]]]:
        """Extract time-series data using Phase 4B AJAX-based approach.
        
        Phase 4B Implementation: Based on source code analysis, this method replicates
        the browser's AJAX flow by:
        1. Extracting parameters from cmk.graphs.load_graph_content() JavaScript calls
        2. Making POST requests to ajax_render_graph_content.py with proper JSON data
        3. Parsing the AJAX response to extract actual time-series data
        4. Falling back to static JavaScript parsing if AJAX fails
        
        Args:
            html_content: Raw HTML content from the monitoring page
            
        Returns:
            List of (timestamp, temperature) tuples with timestamps in ISO format
            
        Raises:
            ScrapingError: If parsing fails
        """
        self.logger.debug("Starting Phase 4B graph data extraction with AJAX-based approach")
        self.logger.debug(f"HTML content length: {len(html_content)} characters")
        
        extracted_data = []
        
        try:
            # Parse HTML with fallback parsers
            soup = self._parse_html_with_fallback(html_content)
            
            # Log HTML structure for debugging
            self._log_html_structure(soup)
            
            # PHASE 4B: Try new AJAX approach - extract parameters and make ajax_render_graph_content.py requests
            self.logger.debug("Phase 4B: Attempting new AJAX-based data extraction")
            
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
                            ajax_response = self.make_ajax_request(parameters, period)
                            
                            if ajax_response:
                                # Parse the AJAX response to extract time-series data
                                graph_data = self.parse_ajax_response(ajax_response)
                                
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
                self.logger.debug(f"Phase 4B AJAX extraction failed: {e}")
            
            if extracted_data:
                self.logger.info(f"Phase 4B successfully extracted {len(extracted_data)} data points via AJAX")
            else:
                self.logger.debug("Phase 4B found no data via AJAX, falling back to static JavaScript parsing")
            
            # FALLBACK: Static JavaScript parsing if AJAX failed
            if not extracted_data:
                self.logger.debug("Fallback: Using static JavaScript extraction as last resort")
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
            
            self.logger.debug(f"Enhanced Phase 4 extraction complete: {len(processed_data)} validated data points")
            
            if processed_data:
                # Log sample of extracted data
                sample_size = min(3, len(processed_data))
                sample_data = processed_data[:sample_size]
                self.logger.debug(f"Sample extracted data: {sample_data}")
                return processed_data  # type: ignore
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

    def parse_table_data(self, html_content: str) -> List[Tuple[str, Union[float, str]]]:
        """Extract summary statistics from HTML tables.
        
        Phase 5 Implementation: Complete table data extraction with multiple parsing strategies.
        Extracts Min, Max, Average, Last values from temperature monitoring tables.
        
        Args:
            html_content: Raw HTML content from the monitoring page
            
        Returns:
            List of (statistic_name, value) tuples (min, max, average, last)
            
        Raises:
            ScrapingError: If parsing fails
        """
        self.logger.debug("Starting Phase 5 table data extraction")
        self.logger.debug(f"HTML content length: {len(html_content)} characters")
        
        try:
            # Parse HTML with fallback parsers
            soup = self._parse_html_with_fallback(html_content)
            
            # Use helper functions to find temperature-related tables
            data_tables = self.find_data_tables(soup)
            
            self.logger.debug(f"Found {len(data_tables)} potential data tables")
            
            # Extract statistics from tables using multiple strategies
            extracted_stats = []
            
            for i, table in enumerate(data_tables):
                self.logger.debug(f"Processing table {i+1}/{len(data_tables)}")
                
                # Try multiple parsing strategies for each table
                table_stats = self._extract_statistics_from_table(table, i+1)
                extracted_stats.extend(table_stats)
            
            # Remove duplicates and prioritize most reliable values
            final_stats = self._consolidate_statistics(extracted_stats)
            
            self.logger.info(f"Phase 5 complete: Extracted {len(final_stats)} temperature statistics")
            for stat_name, value in final_stats:
                self.logger.info(f"  {stat_name}: {value}°C")
            
            return final_stats  # type: ignore
            
        except Exception as e:
            error_msg = f"Failed to parse table data: {e}"
            self.logger.error(error_msg)
            raise ScrapingError(
                error_msg,
                html_snippet=html_content[:500] if html_content else None,
                response_data={"error": str(e)}
            )
    
    def _extract_statistics_from_table(self, table, table_num: int) -> List[Tuple[str, float]]:
        """Extract temperature statistics from a single table using multiple strategies.
        
        Args:
            table: BeautifulSoup table element
            table_num: Table number for logging
            
        Returns:
            List of (statistic_name, value) tuples found in this table
        """
        self.logger.debug(f"Extracting statistics from table {table_num}")
        
        stats = []
        
        # Strategy 1: Header-based parsing (look for column/row headers)
        header_stats = self._parse_table_with_headers(table, table_num)
        stats.extend(header_stats)
        
        # Strategy 2: Cell content analysis (look for patterns like "Min: 66.8°C")
        content_stats = self._parse_table_cell_content(table, table_num)
        stats.extend(content_stats)
        
        # Strategy 3: Position-based parsing (common table layouts)
        position_stats = self._parse_table_by_position(table, table_num)
        stats.extend(position_stats)
        
        # Strategy 4: Keyword proximity (find numbers near statistic keywords)
        proximity_stats = self._parse_table_keyword_proximity(table, table_num)
        stats.extend(proximity_stats)
        
        self.logger.debug(f"Table {table_num} yielded {len(stats)} potential statistics")
        
        return stats
    
    def _parse_table_with_headers(self, table, table_num: int) -> List[Tuple[str, float]]:
        """Parse table using column/row headers to identify statistics.
        
        Args:
            table: BeautifulSoup table element
            table_num: Table number for logging
            
        Returns:
            List of (statistic_name, value) tuples
        """
        stats = []
        
        try:
            # Look for header cells (th elements)
            headers = table.find_all(['th', 'td'])
            rows = table.find_all('tr')
            
            self.logger.debug(f"Table {table_num} has {len(headers)} headers and {len(rows)} rows")
            
            # Check for horizontal layout (statistics as column headers)
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 2:
                    # Try to match header-value pairs
                    for i in range(len(cells) - 1):
                        header_text = cells[i].get_text().strip().lower()
                        value_text = cells[i + 1].get_text().strip()
                        
                        stat_name = self._identify_statistic_name(header_text)
                        if stat_name:
                            value = self._extract_numeric_value(value_text)
                            if value is not None:
                                stats.append((stat_name, value))
                                self.logger.debug(f"Table {table_num} header parsing: {stat_name} = {value}")
            
            # Check for vertical layout (statistics as row headers)
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 2:
                    header_text = cells[0].get_text().strip().lower()
                    stat_name = self._identify_statistic_name(header_text)
                    if stat_name:
                        # Look for numeric value in subsequent cells
                        for cell in cells[1:]:
                            value = self._extract_numeric_value(cell.get_text().strip())
                            if value is not None:
                                stats.append((stat_name, value))
                                self.logger.debug(f"Table {table_num} row parsing: {stat_name} = {value}")
                                break
                                
        except Exception as e:
            self.logger.debug(f"Table {table_num} header parsing failed: {e}")
            
        return stats
    
    def _parse_table_cell_content(self, table, table_num: int) -> List[Tuple[str, float]]:
        """Parse table by analyzing cell content for patterns like 'Min: 66.8°C'.
        
        Args:
            table: BeautifulSoup table element
            table_num: Table number for logging
            
        Returns:
            List of (statistic_name, value) tuples
        """
        stats = []
        
        try:
            all_cells = table.find_all(['td', 'th'])
            
            for cell in all_cells:
                cell_text = cell.get_text().strip()
                
                # Look for patterns like "Min: 66.8°C", "Maximum: 70.1", "Avg 68.4"
                patterns = [
                    r'(min|minimum)\s*:?\s*(\d+\.?\d*)\s*°?[cf]?',
                    r'(max|maximum)\s*:?\s*(\d+\.?\d*)\s*°?[cf]?',
                    r'(avg|average|mean)\s*:?\s*(\d+\.?\d*)\s*°?[cf]?',
                    r'(last|current|latest)\s*:?\s*(\d+\.?\d*)\s*°?[cf]?',
                ]
                
                for pattern in patterns:
                    matches = re.finditer(pattern, cell_text.lower(), re.IGNORECASE)
                    for match in matches:
                        stat_type = match.group(1).lower()
                        value_str = match.group(2)
                        
                        stat_name = self._normalize_statistic_name(stat_type)
                        value = self._extract_numeric_value(value_str)
                        
                        # Enhanced validation: ensure values are reasonable temperatures
                        if stat_name and value is not None and self._is_reasonable_temperature(value):
                            # Additional check: avoid time range control values
                            if not self._is_time_range_value(cell_text, value):
                                stats.append((stat_name, value))
                                self.logger.debug(f"Table {table_num} content parsing: {stat_name} = {value} (from '{cell_text.strip()}')")
                            else:
                                self.logger.debug(f"Table {table_num} skipped potential time range value: {value} (from '{cell_text.strip()}')")
                            
        except Exception as e:
            self.logger.debug(f"Table {table_num} content parsing failed: {e}")
            
        return stats
    
    def _parse_table_by_position(self, table, table_num: int) -> List[Tuple[str, float]]:
        """Parse table using common positional layouts.
        
        Args:
            table: BeautifulSoup table element
            table_num: Table number for logging
            
        Returns:
            List of (statistic_name, value) tuples
        """
        stats = []
        
        try:
            rows = table.find_all('tr')
            
            # Common layout: 4-column table with Min, Max, Avg, Last
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) == 4:
                    # Check if this looks like a statistics row
                    values = []
                    for cell in cells:
                        value = self._extract_numeric_value(cell.get_text().strip())
                        values.append(value)
                    
                    # If we found 4 numeric values, assume it's min, max, avg, last
                    if all(v is not None for v in values):
                        stat_names = ['min', 'max', 'average', 'last']
                        for stat_name, value in zip(stat_names, values):
                            stats.append((stat_name, value))
                            self.logger.debug(f"Table {table_num} position parsing: {stat_name} = {value}")
                        break  # Only take the first matching row
                        
        except Exception as e:
            self.logger.debug(f"Table {table_num} position parsing failed: {e}")
            
        return stats
    
    def _parse_table_keyword_proximity(self, table, table_num: int) -> List[Tuple[str, float]]:
        """Parse table by finding numeric values near statistic keywords.
        
        Args:
            table: BeautifulSoup table element
            table_num: Table number for logging
            
        Returns:
            List of (statistic_name, value) tuples
        """
        stats = []
        
        try:
            # Get all text from the table
            table_text = table.get_text()
            
            # Keywords and their normalized names
            keyword_map = {
                'min': ['min', 'minimum', 'lowest'],
                'max': ['max', 'maximum', 'highest', 'peak'],
                'average': ['avg', 'average', 'mean'],
                'last': ['last', 'current', 'latest', 'now']
            }
            
            # Look for keywords followed by numeric values
            for stat_name, keywords in keyword_map.items():
                for keyword in keywords:
                    # Pattern: keyword followed by optional colon/separator and number
                    pattern = rf'\b{re.escape(keyword)}\b\s*:?\s*(\d+\.?\d*)\s*°?[cf]?'
                    matches = re.finditer(pattern, table_text, re.IGNORECASE)
                    
                    for match in matches:
                        value_str = match.group(1)
                        value = self._extract_numeric_value(value_str)
                        
                        if value is not None:
                            stats.append((stat_name, value))
                            self.logger.debug(f"Table {table_num} proximity parsing: {stat_name} = {value} (keyword: {keyword})")
                            
        except Exception as e:
            self.logger.debug(f"Table {table_num} proximity parsing failed: {e}")
            
        return stats
    
    def _identify_statistic_name(self, text: str) -> Optional[str]:
        """Identify which statistic a text header represents.
        
        Args:
            text: Header text to analyze
            
        Returns:
            Normalized statistic name or None
        """
        text_lower = text.lower().strip()
        
        if any(keyword in text_lower for keyword in ['min', 'minimum', 'lowest']):
            return 'min'
        elif any(keyword in text_lower for keyword in ['max', 'maximum', 'highest', 'peak']):
            return 'max'
        elif any(keyword in text_lower for keyword in ['avg', 'average', 'mean']):
            return 'average'
        elif any(keyword in text_lower for keyword in ['last', 'current', 'latest', 'now']):
            return 'last'
        
        return None
    
    def _normalize_statistic_name(self, stat_type: str) -> Optional[str]:
        """Normalize statistic type names to standard format.
        
        Args:
            stat_type: Raw statistic type string
            
        Returns:
            Normalized statistic name
        """
        stat_lower = stat_type.lower().strip()
        
        if stat_lower in ['min', 'minimum']:
            return 'min'
        elif stat_lower in ['max', 'maximum']:
            return 'max'
        elif stat_lower in ['avg', 'average', 'mean']:
            return 'average'
        elif stat_lower in ['last', 'current', 'latest']:
            return 'last'
        
        return None
    
    def _extract_numeric_value(self, text: str) -> Optional[float]:
        """Extract numeric value from text, handling temperature units.
        
        Args:
            text: Text that may contain a numeric value
            
        Returns:
            Numeric value as float or None if not found/invalid
        """
        if not text:
            return None
            
        try:
            # Remove common non-numeric characters but keep decimal points
            cleaned = re.sub(r'[^\d\.\-\+]', '', text.strip())
            
            if not cleaned:
                return None
                
            value = float(cleaned)
            
            # Validate using existing method
            if self._is_numeric_value(value):
                return value
            else:
                self.logger.debug(f"Value {value} outside reasonable temperature range")
                return None
                
        except (ValueError, TypeError):
            return None
    
    def _consolidate_statistics(self, extracted_stats: List[Tuple[str, float]]) -> List[Tuple[str, float]]:
        """Consolidate duplicate statistics, keeping the most reliable values.
        
        Args:
            extracted_stats: List of all extracted (statistic_name, value) tuples
            
        Returns:
            List of consolidated (statistic_name, value) tuples
        """
        if not extracted_stats:
            return []
        
        # Group by statistic name
        stat_groups = {}
        for stat_name, value in extracted_stats:
            if stat_name not in stat_groups:
                stat_groups[stat_name] = []
            stat_groups[stat_name].append(value)
        
        # For each statistic, choose the most representative value
        final_stats = []
        for stat_name, values in stat_groups.items():
            if len(values) == 1:
                final_stats.append((stat_name, values[0]))
                self.logger.debug(f"Consolidation: {stat_name} = {values[0]} (single value)")
            else:
                # Multiple values found - choose based on frequency and reasonableness
                from collections import Counter
                value_counts = Counter(values)
                most_common_value = value_counts.most_common(1)[0][0]
                
                final_stats.append((stat_name, most_common_value))
                self.logger.debug(f"Consolidation: {stat_name} = {most_common_value} (most frequent from {values})")
        
        # Sort in standard order: min, max, average, last
        order = {'min': 0, 'max': 1, 'average': 2, 'last': 3}
        final_stats.sort(key=lambda x: order.get(x[0], 999))
        
        return final_stats
    
    # Helper Functions for Element Finding (Phase 3)
    
    
    def find_data_tables(self, soup: BeautifulSoup) -> List:
        """Find tables that might contain temperature summary statistics.
        
        Args:
            soup: Parsed HTML content
            
        Returns:
            List of potential data tables
        """
        self.logger.debug("Searching for data tables")
        
        all_tables = soup.find_all("table")
        self.logger.debug(f"Found {len(all_tables)} total table elements")
        
        data_tables = []
        
        # Filter tables that might contain temperature data (enhanced filtering)
        for i, table in enumerate(all_tables):
            table_text = table.get_text().lower()
            
            # Log all table content for first few tables to see what we're missing
            if i < 5:  # Show first 5 tables
                self.logger.debug(f"Table {i+1} content sample: {table_text[:150]}...")
            
            # Skip tables that are clearly time range controls
            time_control_indicators = [
                "timerange", "time range", "period", "4h", "25h", "8d", "35d",
                "range selector", "time selector", "dropdown", "select period"
            ]
            if any(indicator in table_text for indicator in time_control_indicators):
                self.logger.debug(f"Table {i+1} skipped - appears to be time range controls")
                continue
            
            # Check for temperature-related keywords AND numeric values
            temp_keywords = ["temperature", "min", "max", "average", "last", "°c", "°f", "celsius", "fahrenheit"]
            has_temp_keywords = any(keyword in table_text for keyword in temp_keywords)
            
            # Look for numeric values that could be temperatures (reasonable range)
            # Fixed regex to match complete decimal numbers, not fragments
            temp_pattern = r'\b(\d+(?:\.\d+)?)\s*°?[cf]?\b'
            temp_matches = re.findall(temp_pattern, table_text)
            has_temp_values = any(20 <= float(match) <= 100 for match in temp_matches if match.replace('.', '').isdigit())
            
            if has_temp_keywords:
                self.logger.debug(f"Table {i+1} has temp keywords: {[kw for kw in temp_keywords if kw in table_text]}")
                if temp_matches:
                    self.logger.debug(f"Table {i+1} temp matches: {temp_matches[:5]}")  # Show first 5 matches
                # Show first 200 characters of table text to debug why values aren't found
                self.logger.debug(f"Table {i+1} text sample: {table_text[:200]}")
                if not has_temp_values:
                    self.logger.debug(f"Table {i+1} has temp keywords but no valid temp values - skipping")
            
            # Only include tables that have both keywords AND reasonable temperature values
            if has_temp_keywords and has_temp_values:
                data_tables.append(table)
                self.logger.debug(f"Table {i+1} contains temperature-related data with numeric values")
                
                # Log table structure for debugging
                if isinstance(table, Tag):
                    rows = table.find_all("tr")
                    headers = table.find_all("th")
                    cells = table.find_all("td")
                    
                    self.logger.debug(f"  Table {i+1} structure: {len(rows)} rows, {len(headers)} headers, {len(cells)} cells")
                    
                    # Log first row content as sample
                    if rows:
                        first_row_text = rows[0].get_text().strip().replace("\n", " ")[:100]
                        self.logger.debug(f"  Table {i+1} first row sample: {first_row_text}...")
            elif has_temp_keywords:
                self.logger.debug(f"Table {i+1} has temp keywords but no valid temp values - skipping")
        
        self.logger.debug(f"Found {len(data_tables)} tables with potential temperature data")
        return data_tables
    
    def find_script_tags(self, soup: BeautifulSoup) -> List:
        """Find script tags that might contain time-series data.
        
        Args:
            soup: Parsed HTML content
            
        Returns:
            List of script elements with potential data
        """
        self.logger.debug("Searching for script tags with potential data")
        
        all_scripts = soup.find_all("script")
        self.logger.debug(f"Found {len(all_scripts)} total script tags")
        
        data_scripts = []
        
        for i, script in enumerate(all_scripts):
            script_content = script.get_text()
            
            if not script_content.strip():
                continue  # Skip empty scripts
            
            # Check for data-related content
            content_lower = script_content.lower()
            data_indicators = [
                "json" in content_lower,
                "data" in content_lower,
                "temperature" in content_lower,
                "series" in content_lower,
                "values" in content_lower,
                "timestamp" in content_lower,
                "[" in script_content and "]" in script_content,  # Array-like structures
                "{" in script_content and "}" in script_content,  # Object-like structures
            ]
            
            indicators_found = sum(data_indicators)
            
            if indicators_found >= 2:  # Require at least 2 indicators
                data_scripts.append(script)
                self.logger.debug(f"Script {i+1} has {indicators_found} data indicators")
                
                # Log script preview for debugging
                preview = script_content[:200].strip().replace("\n", " ")
                self.logger.debug(f"  Script {i+1} preview: {preview}...")
        
        self.logger.debug(f"Found {len(data_scripts)} scripts with potential data")
        return data_scripts
    

    def _extract_data_from_script(self, script_content: str, script_num: int) -> List[Tuple]:
        """Extract time-series data from JavaScript content using multiple patterns.
        
        Args:
            script_content: JavaScript source code to analyze
            script_num: Script number for logging purposes
            
        Returns:
            List of raw (timestamp, value) tuples found in the script
        """
        self.logger.debug(f"Analyzing script {script_num} content ({len(script_content)} chars)")
        
        extracted_data = []
        
        # Phase 4 Implementation: Multiple JavaScript data extraction patterns
        search_patterns = [
            # Pattern 1: Checkmk specific graph data loading (most likely to contain real data)
            (r'cmk\.graphs\.load_graph_content\((\{.*?\})\);', "checkmk_graph_data"),
            
            # Pattern 2: Variable assignments with array data
            (r'var\s+(\w*(?:data|series|graph|chart|temp|temperature)\w*)\s*=\s*(\[.*?\]);', "variable_array"),
            
            # Pattern 3: Object property assignments
            (r'(\w+)\s*:\s*(\[.*?\])', "object_property"),
            
            # Pattern 4: JSON data assignments
            (r'var\s+(\w+)\s*=\s*(\{.*?\});', "json_object"),
            
            # Pattern 5: Function parameters or return values
            (r'(?:return|=)\s*(\[.*?\])', "function_data"),
            
            # Pattern 6: Chart.js or similar library data
            (r'"data"\s*:\s*(\[.*?\])', "chart_data"),
            
            # Pattern 7: Direct array literals in variable context
            (r'=\s*(\[\s*\[.*?\]\s*\])', "nested_array"),
        ]
        
        for pattern, pattern_name in search_patterns:
            try:
                matches = re.finditer(pattern, script_content, re.DOTALL | re.IGNORECASE)
                
                for match in matches:
                    self.logger.debug(f"Script {script_num}: Found {pattern_name} pattern")
                    
                    # Extract the data portion (usually the last group)
                    data_text = match.groups()[-1]
                    self.logger.debug(f"Script {script_num}: {pattern_name} matched data_text: {data_text[:100]}...")
                    
                    # Attempt to parse the data
                    parsed_data = self._parse_javascript_data(data_text, pattern_name, script_num)
                    
                    if parsed_data:
                        self.logger.debug(f"Script {script_num}: Extracted {len(parsed_data)} points from {pattern_name}")
                        self.logger.debug(f"Script {script_num}: Sample data from {pattern_name}: {parsed_data[:3]}")
                        extracted_data.extend(parsed_data)
                        
            except Exception as e:
                self.logger.debug(f"Script {script_num}: Pattern {pattern_name} failed: {e}")
                continue
        
        # Also try to find time-series data in specific formats
        extracted_data.extend(self._extract_timestamp_value_pairs(script_content, script_num))
        
        # Remove duplicates based on timestamp
        unique_data = self._remove_duplicate_data_points(extracted_data)
        
        self.logger.debug(f"Script {script_num}: Total unique data points: {len(unique_data)}")
        
        return unique_data

    def _parse_javascript_data(self, data_text: str, pattern_name: str, script_num: int) -> List[Tuple]:
        """Parse JavaScript data structures into timestamp-value pairs.
        
        Args:
            data_text: JavaScript data structure as string
            pattern_name: Name of the pattern that matched
            script_num: Script number for logging
            
        Returns:
            List of (timestamp, value) tuples
        """
        parsed_data = []
        
        try:
            # Clean up the data text for JSON parsing
            cleaned_data = self._clean_javascript_for_json(data_text)
            
            # Attempt JSON parsing
            try:
                parsed_json = json.loads(cleaned_data)
                self.logger.debug(f"Script {script_num}: Successfully parsed JSON from {pattern_name}")
                
                # Extract time-series data from parsed JSON
                parsed_data = self._extract_timeseries_from_ajax_json(parsed_json, script_num)
                
            except json.JSONDecodeError as e:
                self.logger.debug(f"Script {script_num}: JSON parsing failed for {pattern_name}: {e}")
                
                # Fallback: Try to extract data using regex
                parsed_data = self._extract_data_with_regex_fallback(data_text, script_num)
                
        except Exception as e:
            self.logger.debug(f"Script {script_num}: Data parsing failed for {pattern_name}: {e}")
        
        return parsed_data

    def _clean_javascript_for_json(self, js_data: str) -> str:
        """Clean JavaScript data to make it valid JSON.
        
        Args:
            js_data: JavaScript data structure as string
            
        Returns:
            Cleaned string suitable for JSON parsing
        """
        # Remove JavaScript-specific syntax that breaks JSON
        cleaned = js_data.strip()
        
        # Remove trailing semicolons
        cleaned = re.sub(r';\s*$', '', cleaned)
        
        # Replace JavaScript undefined with null
        cleaned = re.sub(r'\bundefined\b', 'null', cleaned)
        
        # Replace JavaScript single quotes with double quotes (carefully)
        # Only replace quotes around strings, not inside strings
        cleaned = re.sub(r"'([^']*)'", r'"\1"', cleaned)
        
        # Remove JavaScript comments
        cleaned = re.sub(r'//.*$', '', cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r'/\*.*?\*/', '', cleaned, flags=re.DOTALL)
        
        # Remove trailing commas before closing brackets/braces
        cleaned = re.sub(r',(\s*[}\]])', r'\1', cleaned)
        
        return cleaned

    def _extract_timeseries_from_ajax_json(self, json_data, script_num: int) -> List[Tuple]:
        """Extract time-series data from parsed JSON structure.
        
        Args:
            json_data: Parsed JSON data structure
            script_num: Script number for logging
            
        Returns:
            List of (timestamp, value) tuples
        """
        extracted = []
        
        try:
            # Handle different JSON structures
            if isinstance(json_data, list):
                # Direct array of data points
                extracted = self._process_array_data(json_data, script_num)
                
            elif isinstance(json_data, dict):
                # Check if this is Checkmk graph data structure
                if self._is_checkmk_graph_data(json_data):
                    extracted = self._process_checkmk_graph_data(json_data, script_num)
                else:
                    # Generic object with nested data
                    extracted = self._process_object_data(json_data, script_num)
                
        except Exception as e:
            self.logger.debug(f"Script {script_num}: JSON structure processing failed: {e}")
        
        return extracted

    def _is_checkmk_graph_data(self, data: dict) -> bool:
        """Check if data structure is Checkmk graph data.
        
        Args:
            data: Dictionary to check
            
        Returns:
            True if this appears to be Checkmk graph data
        """
        # Look for Checkmk graph data indicators
        checkmk_indicators = ['metrics', 'unit_spec', 'title', 'time_range']
        found_indicators = sum(1 for key in checkmk_indicators if key in data)
        return found_indicators >= 2

    def _process_checkmk_graph_data(self, graph_data: dict, script_num: int) -> List[Tuple]:
        """Process Checkmk-specific graph data structure.
        
        Args:
            graph_data: Checkmk graph data dictionary
            script_num: Script number for logging
            
        Returns:
            List of (timestamp, value) tuples
        """
        self.logger.debug(f"Script {script_num}: Processing Checkmk graph data structure")
        extracted = []
        
        try:
            # Look for metrics data
            if 'metrics' in graph_data and isinstance(graph_data['metrics'], list):
                for metric in graph_data['metrics']:
                    if isinstance(metric, dict) and 'time_series' in metric:
                        time_series = metric['time_series']
                        self.logger.debug(f"Script {script_num}: Found time_series in metric")
                        
                        # Process time series data points
                        if isinstance(time_series, list):
                            for data_point in time_series:
                                if isinstance(data_point, list) and len(data_point) >= 2:
                                    timestamp_raw = data_point[0]
                                    value_raw = data_point[1]
                                    
                                    if self._is_likely_timestamp(timestamp_raw) and self._is_numeric_value(value_raw):
                                        extracted.append((timestamp_raw, value_raw))
                        
                        # Also check for 'data' field in metrics
                        elif 'data' in metric and isinstance(metric['data'], list):
                            data_points = metric['data']
                            self.logger.debug(f"Script {script_num}: Found data field with {len(data_points)} points")
                            
                            for data_point in data_points:
                                if isinstance(data_point, list) and len(data_point) >= 2:
                                    timestamp_raw = data_point[0]
                                    value_raw = data_point[1]
                                    
                                    if self._is_likely_timestamp(timestamp_raw) and self._is_numeric_value(value_raw):
                                        extracted.append((timestamp_raw, value_raw))
            
            # Also check for direct data arrays
            if 'data' in graph_data:
                data_array = graph_data['data']
                if isinstance(data_array, list):
                    extracted.extend(self._process_array_data(data_array, script_num))
                    
            self.logger.debug(f"Script {script_num}: Extracted {len(extracted)} points from Checkmk graph data")
            
        except Exception as e:
            self.logger.debug(f"Script {script_num}: Failed to process Checkmk graph data: {e}")
        
        return extracted

    def _process_array_data(self, array_data: list, script_num: int) -> List[Tuple]:
        """Process array data to extract timestamp-value pairs.
        
        Args:
            array_data: List of data items
            script_num: Script number for logging
            
        Returns:
            List of (timestamp, value) tuples
        """
        extracted = []
        
        for item in array_data:
            try:
                if isinstance(item, list) and len(item) >= 2:
                    # Array of [timestamp, value] pairs
                    timestamp_raw = item[0]
                    value_raw = item[1]
                    
                    # Validate that this looks like timestamp-value data
                    if self._is_likely_timestamp(timestamp_raw) and self._is_numeric_value(value_raw):
                        extracted.append((timestamp_raw, value_raw))
                        
                elif isinstance(item, dict):
                    # Object with timestamp and value properties
                    timestamp_raw = self._extract_timestamp_from_object(item)
                    value_raw = self._extract_value_from_object(item)
                    
                    if timestamp_raw is not None and value_raw is not None:
                        extracted.append((timestamp_raw, value_raw))
                        
            except Exception as e:
                self.logger.debug(f"Script {script_num}: Failed to process array item {item}: {e}")
                continue
        
        self.logger.debug(f"Script {script_num}: Processed {len(extracted)} items from array data")
        return extracted

    def _process_object_data(self, object_data: dict, script_num: int) -> List[Tuple]:
        """Process object data to find time-series data.
        
        Args:
            object_data: Dictionary data structure
            script_num: Script number for logging
            
        Returns:
            List of (timestamp, value) tuples
        """
        extracted = []
        
        # Look for common data keys
        data_keys = ['data', 'series', 'values', 'points', 'temperature', 'temperatures']
        
        for key in data_keys:
            if key in object_data:
                value = object_data[key]
                if isinstance(value, list):
                    extracted.extend(self._process_array_data(value, script_num))
                    
        # Also check nested structures
        for key, value in object_data.items():
            if isinstance(value, dict):
                extracted.extend(self._process_object_data(value, script_num))
                
        return extracted

    def _extract_timestamp_value_pairs(self, script_content: str, script_num: int) -> List[Tuple]:
        """Extract timestamp-value pairs using specific regex patterns.
        
        Args:
            script_content: JavaScript content to search
            script_num: Script number for logging
            
        Returns:
            List of (timestamp, value) tuples
        """
        extracted = []
        
        # Pattern for arrays of [timestamp, value] pairs
        timestamp_patterns = [
            # Unix timestamp patterns (10 or 13 digits)
            r'\[\s*(\d{10,13})\s*,\s*([+-]?\d*\.?\d+)\s*\]',
            
            # ISO timestamp patterns
            r'\[\s*["\'](\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}(?:\.\d{3})?(?:Z|[+-]\d{2}:?\d{2})?)["\']?\s*,\s*([+-]?\d*\.?\d+)\s*\]',
            
            # Relative timestamp patterns (seconds since start)
            r'\[\s*([+-]?\d+)\s*,\s*([+-]?\d*\.?\d+)\s*\]',
        ]
        
        for pattern in timestamp_patterns:
            try:
                matches = re.finditer(pattern, script_content, re.IGNORECASE)
                
                for match in matches:
                    timestamp_raw = match.group(1)
                    value_raw = match.group(2)
                    
                    try:
                        # Convert value to float
                        value = float(value_raw)
                        
                        # Validate temperature range (reasonable sensor values)
                        if -100 <= value <= 200:  # Extended range for various sensors
                            extracted.append((timestamp_raw, value))
                            
                    except (ValueError, TypeError):
                        continue
                        
            except Exception as e:
                self.logger.debug(f"Script {script_num}: Timestamp pattern failed: {e}")
                continue
        
        self.logger.debug(f"Script {script_num}: Found {len(extracted)} timestamp-value pairs")
        return extracted

    def _extract_data_with_regex_fallback(self, data_text: str, script_num: int) -> List[Tuple]:
        """Fallback data extraction using regex when JSON parsing fails.
        
        Args:
            data_text: JavaScript data text that couldn't be parsed as JSON
            script_num: Script number for logging
            
        Returns:
            List of (timestamp, value) tuples
        """
        extracted = []
        
        try:
            # Try to find array-like patterns even in malformed JSON
            array_patterns = [
                # Simple [number, number] patterns
                r'\[\s*([+-]?\d+(?:\.\d+)?)\s*,\s*([+-]?\d+(?:\.\d+)?)\s*\]',
                
                # Timestamp, value patterns with quotes
                r'\[\s*["\']?([^"\']+?)["\']?\s*,\s*([+-]?\d+(?:\.\d+)?)\s*\]',
                
                # Object-like patterns
                r'\{\s*["\']?(?:time|timestamp|x)["\']?\s*:\s*([^,}]+)\s*,\s*["\']?(?:value|temp|temperature|y)["\']?\s*:\s*([+-]?\d+(?:\.\d+)?)\s*\}',
            ]
            
            for pattern in array_patterns:
                matches = re.finditer(pattern, data_text, re.IGNORECASE)
                
                for match in matches:
                    timestamp_raw = match.group(1).strip().strip('"\'')
                    value_raw = match.group(2)
                    
                    try:
                        value = float(value_raw)
                        if -100 <= value <= 200:  # Reasonable temperature range
                            extracted.append((timestamp_raw, value))
                    except (ValueError, TypeError):
                        continue
                        
        except Exception as e:
            self.logger.debug(f"Script {script_num}: Regex fallback failed: {e}")
        
        self.logger.debug(f"Script {script_num}: Regex fallback found {len(extracted)} data points")
        return extracted

    def _is_likely_timestamp(self, value) -> bool:
        """Check if a value looks like a timestamp.
        
        Args:
            value: Value to check
            
        Returns:
            True if value appears to be a timestamp
        """
        if isinstance(value, (int, float)):
            # Unix timestamp (10 or 13 digits)
            timestamp = int(value)
            return (1000000000 <= timestamp <= 9999999999) or (1000000000000 <= timestamp <= 9999999999999)
            
        elif isinstance(value, str):
            # ISO timestamp pattern
            iso_pattern = r'^\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}'
            return re.match(iso_pattern, value) is not None
            
        return False

    def _is_numeric_value(self, value) -> bool:
        """Check if a value is numeric and in reasonable temperature range.
        
        Args:
            value: Value to check
            
        Returns:
            True if value is numeric and reasonable
        """
        try:
            num_value = float(value)
            # Extended temperature range for various sensors
            return -100 <= num_value <= 200
        except (ValueError, TypeError):
            return False

    def _extract_timestamp_from_object(self, obj: dict):
        """Extract timestamp from object with various property names.
        
        Args:
            obj: Dictionary object
            
        Returns:
            Timestamp value or None
        """
        timestamp_keys = ['timestamp', 'time', 'x', 'date', 'datetime']
        
        for key in timestamp_keys:
            if key in obj:
                return obj[key]
                
        return None

    def _extract_value_from_object(self, obj: dict):
        """Extract numeric value from object with various property names.
        
        Args:
            obj: Dictionary object
            
        Returns:
            Numeric value or None
        """
        value_keys = ['value', 'y', 'temperature', 'temp', 'val']
        
        for key in value_keys:
            if key in obj and self._is_numeric_value(obj[key]):
                return obj[key]
                
        return None

    def _remove_duplicate_data_points(self, data_points: List[Tuple]) -> List[Tuple]:
        """Remove duplicate data points based on timestamp.
        
        Args:
            data_points: List of (timestamp, value) tuples
            
        Returns:
            List with duplicates removed
        """
        seen_timestamps = set()
        unique_points = []
        
        for timestamp, value in data_points:
            # Convert timestamp to string for comparison
            timestamp_str = str(timestamp)
            
            if timestamp_str not in seen_timestamps:
                seen_timestamps.add(timestamp_str)
                unique_points.append((timestamp, value))
        
        return unique_points

    def _process_and_validate_data(self, raw_data: List[Tuple]) -> List[Tuple[str, float]]:
        """Process and validate extracted data, converting timestamps to ISO format.
        
        Args:
            raw_data: List of raw (timestamp, value) tuples
            
        Returns:
            List of validated (iso_timestamp, temperature) tuples
        """
        self.logger.debug(f"Processing and validating {len(raw_data)} raw data points")
        
        processed_data = []
        
        for timestamp_raw, value_raw in raw_data:
            try:
                # Convert value to float
                temperature = float(value_raw)
                
                # Validate temperature range
                if not (-100 <= temperature <= 200):
                    self.logger.debug(f"Temperature {temperature} outside valid range, skipping")
                    continue
                
                # Convert timestamp to ISO format
                iso_timestamp = self._convert_timestamp_to_iso(timestamp_raw)
                
                if iso_timestamp:
                    processed_data.append((iso_timestamp, temperature))
                else:
                    self.logger.debug(f"Could not convert timestamp {timestamp_raw}, skipping")
                    
            except (ValueError, TypeError) as e:
                self.logger.debug(f"Failed to process data point ({timestamp_raw}, {value_raw}): {e}")
                continue
        
        # Sort by timestamp
        processed_data.sort(key=lambda x: x[0])
        
        self.logger.debug(f"Processed {len(processed_data)} valid data points")
        return processed_data

    def _convert_timestamp_to_iso(self, timestamp_raw) -> Optional[str]:
        """Convert various timestamp formats to ISO format.
        
        Args:
            timestamp_raw: Raw timestamp value
            
        Returns:
            ISO formatted timestamp string or None if conversion fails
        """
        from datetime import datetime, timezone
        
        try:
            if isinstance(timestamp_raw, (int, float)):
                # Unix timestamp
                timestamp = int(timestamp_raw)
                
                # Handle both seconds and milliseconds
                if timestamp > 1000000000000:  # Milliseconds
                    timestamp = timestamp / 1000
                
                # Convert to datetime
                dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
                return dt.strftime('%Y-%m-%dT%H:%M:%S')
                
            elif isinstance(timestamp_raw, str):
                # Try to parse as ISO string first
                iso_pattern = r'^\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}'
                if re.match(iso_pattern, timestamp_raw):
                    # Clean up the timestamp
                    cleaned = timestamp_raw.replace(' ', 'T')
                    # Remove timezone info and milliseconds for consistency
                    cleaned = re.sub(r'(\.\d{3})?(?:Z|[+-]\d{2}:?\d{2})?$', '', cleaned)
                    return cleaned
                
                # Try to parse as unix timestamp string
                try:
                    timestamp = int(float(timestamp_raw))
                    if timestamp > 1000000000000:  # Milliseconds
                        timestamp = timestamp / 1000
                    dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
                    return dt.strftime('%Y-%m-%dT%H:%M:%S')
                except (ValueError, TypeError):
                    pass
                    
        except Exception as e:
            self.logger.debug(f"Timestamp conversion failed for {timestamp_raw}: {e}")
        
        return None

    def _parse_js_object_params(self, params_str: str) -> Dict:
        """Parse JavaScript object parameters from string.
        
        Args:
            params_str: JavaScript object parameter string
            
        Returns:
            Dictionary of parsed parameters
        """
        params = {}
        
        try:
            # Simple regex patterns for key-value pairs
            patterns = [
                r'(["\']?\w+["\']?)\s*:\s*(["\']?)([^,}]+)\2',
                r'(\w+)\s*:\s*["\']([^"\']+)["\']',
                r'(\w+)\s*:\s*(\d+)',
                r'(\w+)\s*:\s*(true|false|null)'
            ]
            
            for pattern in patterns:
                matches = re.finditer(pattern, params_str)
                for match in matches:
                    key = match.group(1).strip('"\'')
                    value = match.group(3) if len(match.groups()) >= 3 else match.group(2)
                    params[key] = value.strip('"\'')
            
            self.logger.debug(f"Parsed JS params: {params}")
            return params
            
        except Exception as e:
            self.logger.debug(f"Failed to parse JS object params: {e}")
            return {}

    def _parse_javascript_object(self, js_str: str) -> Dict:
        """Parse a JavaScript object string into a Python dictionary.
        
        Enhanced to handle complex nested JSON structures found in Checkmk AJAX parameters.
        
        Args:
            js_str: JavaScript object as string
            
        Returns:
            Parsed dictionary or empty dict if parsing fails
        """
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

    def _extract_complex_js_object(self, js_str: str) -> Dict:
        """Extract complex JavaScript object with proper nested structure handling.
        
        This method handles the complex structures found in Checkmk's cmk.graphs.load_graph_content
        calls, which contain deeply nested objects with arrays and complex validation requirements.
        
        Args:
            js_str: JavaScript object string with complex nested structures
            
        Returns:
            Dictionary with properly parsed nested structures
        """
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
    
    def _manual_js_extraction(self, js_content: str) -> Dict:
        """Manual extraction for JavaScript objects that resist JSON parsing.
        
        Handles cases where automatic JSON cleaning doesn't work due to complex
        nested structures or JavaScript-specific syntax.
        
        Args:
            js_content: JavaScript object content to extract
            
        Returns:
            Dictionary with extracted key-value pairs
        """
        result = {}
        
        try:
            # Extract title - this should always work
            title_match = re.search(r'"title"\s*:\s*"([^"]*)"', js_content)
            if title_match:
                result["title"] = title_match.group(1)
            
            # Extract unit_spec with complex structure
            unit_spec = self._extract_unit_spec(js_content)
            if unit_spec:
                result["unit_spec"] = unit_spec
            
            # Extract explicit_vertical_range
            if "explicit_vertical_range" in js_content:
                if "null" in js_content:
                    result["explicit_vertical_range"] = None
                else:
                    # Try to extract numeric value
                    evr_match = re.search(r'"explicit_vertical_range"\s*:\s*([^,}]+)', js_content)
                    if evr_match:
                        try:
                            result["explicit_vertical_range"] = float(evr_match.group(1))
                        except ValueError:
                            result["explicit_vertical_range"] = None
            
            # Extract horizontal_rules array
            horizontal_rules = self._extract_horizontal_rules(js_content)
            if horizontal_rules is not None:
                result["horizontal_rules"] = horizontal_rules
            
            # Extract omit_zero_metrics
            ozm_match = re.search(r'"omit_zero_metrics"\s*:\s*(true|false)', js_content)
            if ozm_match:
                result["omit_zero_metrics"] = ozm_match.group(1) == "true"
            
            # Extract consolidation_function
            cf_match = re.search(r'"consolidation_function"\s*:\s*"([^"]*)"', js_content)
            if cf_match:
                result["consolidation_function"] = cf_match.group(1)
            
            # Extract metrics array
            metrics = self._extract_metrics_array(js_content)
            if metrics is not None:
                result["metrics"] = metrics
            
            self.logger.debug(f"Manual extraction result keys: {list(result.keys())}")
            return result
            
        except Exception as e:
            self.logger.debug(f"Manual JS extraction failed: {e}")
            return {}
    
    def _extract_unit_spec(self, js_content: str) -> Optional[Dict]:
        """Extract unit_spec with proper discriminator type.
        
        The unit_spec structure requires a 'type' field for discriminator validation.
        
        Args:
            js_content: JavaScript content containing unit_spec
            
        Returns:
            Dictionary with unit_spec structure or None if not found
        """
        try:
            # Look for unit_spec pattern
            unit_spec_match = re.search(r'"unit_spec"\s*:\s*\{([^}]+(?:\{[^}]*\}[^}]*)*)\}', js_content)
            if not unit_spec_match:
                return None
            
            unit_spec_content = "{" + unit_spec_match.group(1) + "}"
            
            # Clean and try JSON parsing
            cleaned = self._clean_javascript_for_json(unit_spec_content)
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError:
                # Manual extraction for unit_spec
                result = {}
                
                # Extract type (required discriminator)
                type_match = re.search(r'"type"\s*:\s*"([^"]*)"', unit_spec_content)
                if type_match:
                    result["type"] = type_match.group(1)
                
                # Extract notation if present
                notation_match = re.search(r'"notation"\s*:\s*\{([^}]+)\}', unit_spec_content)
                if notation_match:
                    notation_content = "{" + notation_match.group(1) + "}"
                    try:
                        notation_cleaned = self._clean_javascript_for_json(notation_content)
                        result["notation"] = json.loads(notation_cleaned)
                    except:
                        pass
                
                # Extract precision if present
                precision_match = re.search(r'"precision"\s*:\s*\{([^}]+)\}', unit_spec_content)
                if precision_match:
                    precision_content = "{" + precision_match.group(1) + "}"
                    try:
                        precision_cleaned = self._clean_javascript_for_json(precision_content)
                        result["precision"] = json.loads(precision_cleaned)
                    except:
                        pass
                
                return result if result else None
                
        except Exception as e:
            self.logger.debug(f"Unit spec extraction failed: {e}")
            return None
    
    def _extract_horizontal_rules(self, js_content: str) -> Optional[List[Dict]]:
        """Extract horizontal_rules array from JavaScript content.
        
        Args:
            js_content: JavaScript content containing horizontal_rules
            
        Returns:
            List of horizontal rule dictionaries or None if not found
        """
        try:
            # Look for horizontal_rules array
            hr_match = re.search(r'"horizontal_rules"\s*:\s*\[([^\]]*(?:\[[^\]]*\][^\]]*)*)\]', js_content)
            if not hr_match:
                return []
            
            hr_content = "[" + hr_match.group(1) + "]"
            
            # Clean and try JSON parsing
            cleaned = self._clean_javascript_for_json(hr_content)
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError:
                # Manual extraction for individual rules
                rules = []
                
                # Find individual rule objects within the array
                rule_pattern = r'\{([^}]+(?:\{[^}]*\}[^}]*)*)\}'
                for rule_match in re.finditer(rule_pattern, hr_content):
                    rule_content = "{" + rule_match.group(1) + "}"
                    try:
                        rule_cleaned = self._clean_javascript_for_json(rule_content)
                        rule = json.loads(rule_cleaned)
                        rules.append(rule)
                    except:
                        # Manual rule extraction
                        rule = {}
                        
                        # Extract common fields
                        value_match = re.search(r'"value"\s*:\s*([0-9.]+)', rule_content)
                        if value_match:
                            rule["value"] = float(value_match.group(1))
                        
                        rendered_value_match = re.search(r'"rendered_value"\s*:\s*"([^"]*)"', rule_content)
                        if rendered_value_match:
                            rule["rendered_value"] = rendered_value_match.group(1)
                        
                        color_match = re.search(r'"color"\s*:\s*"([^"]*)"', rule_content)
                        if color_match:
                            rule["color"] = color_match.group(1)
                        
                        title_match = re.search(r'"title"\s*:\s*"([^"]*)"', rule_content)
                        if title_match:
                            rule["title"] = title_match.group(1)
                        
                        if rule:
                            rules.append(rule)
                
                return rules
                
        except Exception as e:
            self.logger.debug(f"Horizontal rules extraction failed: {e}")
            return []
    
    def _extract_metrics_array(self, js_content: str) -> Optional[List[Dict]]:
        """Extract metrics array from JavaScript content.
        
        Args:
            js_content: JavaScript content containing metrics array
            
        Returns:
            List of metric dictionaries or None if not found
        """
        try:
            # Look for metrics array - this is complex due to nested structures
            metrics_match = re.search(r'"metrics"\s*:\s*\[([^\]]*(?:\[[^\]]*\][^\]]*)*)\]', js_content)
            if not metrics_match:
                return []
            
            metrics_content = "[" + metrics_match.group(1) + "]"
            
            # Clean and try JSON parsing
            cleaned = self._clean_javascript_for_json(metrics_content)
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError:
                # Manual extraction for metrics
                metrics = []
                
                # Find individual metric objects
                metric_pattern = r'\{([^}]+(?:\{[^}]*\}[^}]*)*)\}'
                for metric_match in re.finditer(metric_pattern, metrics_content):
                    metric_content = "{" + metric_match.group(1) + "}"
                    try:
                        metric_cleaned = self._clean_javascript_for_json(metric_content)
                        metric = json.loads(metric_cleaned)
                        metrics.append(metric)
                    except:
                        # Basic metric extraction
                        metric = {}
                        
                        title_match = re.search(r'"title"\s*:\s*"([^"]*)"', metric_content)
                        if title_match:
                            metric["title"] = title_match.group(1)
                        
                        line_type_match = re.search(r'"line_type"\s*:\s*"([^"]*)"', metric_content)
                        if line_type_match:
                            metric["line_type"] = line_type_match.group(1)
                        
                        # Extract operation object
                        operation = self._extract_operation_object(metric_content)
                        if operation:
                            metric["operation"] = operation
                        
                        # Extract unit object
                        unit = self._extract_unit_object(metric_content)
                        if unit:
                            metric["unit"] = unit
                        
                        if metric:
                            metrics.append(metric)
                
                return metrics
                
        except Exception as e:
            self.logger.debug(f"Metrics extraction failed: {e}")
            return []
    
    def _extract_operation_object(self, content: str) -> Optional[Dict]:
        """Extract operation object from metric content."""
        try:
            op_match = re.search(r'"operation"\s*:\s*\{([^}]+)\}', content)
            if not op_match:
                return None
            
            op_content = "{" + op_match.group(1) + "}"
            cleaned = self._clean_javascript_for_json(op_content)
            return json.loads(cleaned)
        except:
            return None
    
    def _extract_unit_object(self, content: str) -> Optional[Dict]:
        """Extract unit object from metric content."""
        try:
            unit_match = re.search(r'"unit"\s*:\s*\{([^}]+(?:\{[^}]*\}[^}]*)*)\}', content)
            if not unit_match:
                return None
            
            unit_content = "{" + unit_match.group(1) + "}"
            cleaned = self._clean_javascript_for_json(unit_content)
            return json.loads(cleaned)
        except:
            return None

    def _parse_function_arguments(self, args_str: str) -> List[str]:
        """Parse function arguments with proper handling of nested objects and arrays.
        
        This method correctly splits JavaScript function arguments even when they contain
        nested objects with commas, brackets, and complex structures.
        
        Args:
            args_str: String containing all function arguments
            
        Returns:
            List of individual argument strings
        """
        arguments = []
        current_arg = ""
        brace_depth = 0
        bracket_depth = 0
        paren_depth = 0
        in_string = False
        string_char = None
        i = 0
        
        while i < len(args_str):
            char = args_str[i]
            
            # Handle string literals
            if char in ['"', "'"]:
                if not in_string:
                    in_string = True
                    string_char = char
                elif char == string_char and (i == 0 or args_str[i-1] != '\\'):
                    in_string = False
                    string_char = None
            
            # Skip processing if we're inside a string
            if in_string:
                current_arg += char
                i += 1
                continue
            
            # Handle nested structures
            if char == '{':
                brace_depth += 1
            elif char == '}':
                brace_depth -= 1
            elif char == '[':
                bracket_depth += 1
            elif char == ']':
                bracket_depth -= 1
            elif char == '(':
                paren_depth += 1
            elif char == ')':
                paren_depth -= 1
            elif char == ',' and brace_depth == 0 and bracket_depth == 0 and paren_depth == 0:
                # This is a top-level comma separating arguments
                arguments.append(current_arg.strip())
                current_arg = ""
                i += 1
                continue
            
            current_arg += char
            i += 1
        
        # Add the last argument
        if current_arg.strip():
            arguments.append(current_arg.strip())
        
        self.logger.debug(f"Parsed {len(arguments)} function arguments")
        for idx, arg in enumerate(arguments):
            self.logger.debug(f"  Arg {idx + 1}: {arg[:50]}{'...' if len(arg) > 50 else ''}")
        
        return arguments

    def _extract_current_page_params(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract parameters from current page for AJAX requests.
        
        Args:
            soup: Parsed HTML content
            
        Returns:
            URL parameter string or None
        """
        try:
            # Look for hidden form inputs or data attributes
            params = {}
            
            # Extract from hidden inputs
            for input_elem in soup.find_all("input", attrs={"type": "hidden"}):
                if isinstance(input_elem, Tag):
                    name = input_elem.get("name")
                    value = input_elem.get("value")
                    if name and value:
                        params[name] = value
            
            # Extract from data attributes
            for elem in soup.find_all(attrs={"data-host": True}):
                if isinstance(elem, Tag):
                    if elem.get("data-host"):
                        params["host"] = elem.get("data-host")
                    if elem.get("data-service"):
                        params["service"] = elem.get("data-service")
                    if elem.get("data-site"):
                        params["site"] = elem.get("data-site")
            
            # Fallback: extract from page title or meta
            if not params.get("site"):
                params["site"] = self.config.site
            
            if params:
                param_string = "&".join([f"{k}={urllib.parse.quote_plus(str(v))}" for k, v in params.items()])
                self.logger.debug(f"Extracted page params: {param_string}")
                return param_string
            
            return None
            
        except Exception as e:
            self.logger.debug(f"Failed to extract page params: {e}")
            return None

    def _fetch_ajax_data(self, endpoint_info: Dict, period: str = "4h") -> List[Tuple]:
        """Fetch data from an AJAX endpoint with authentication.
        
        Enhanced to use the exact parameter structure discovered for ajax_graph.py
        with complex nested JSON context parameter.
        
        Args:
            endpoint_info: Dictionary containing URL and request parameters
            period: Time period for data extraction (4h, 25h, 8d, etc.)
            
        Returns:
            List of (timestamp, value) tuples from the AJAX response
        """
        try:
            url = endpoint_info['url']
            method = endpoint_info.get('method', 'GET')
            endpoint_type = endpoint_info.get('type', 'unknown')
            
            self.logger.debug(f"Fetching AJAX data from: {url} (type: {endpoint_type})")
            
            # Ensure we have an authenticated session
            if not self.session:
                self.authenticate_session()
            
            # Set appropriate headers for AJAX requests
            ajax_headers = {
                'X-Requested-With': 'XMLHttpRequest',
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'Referer': f"{self.config.server_url}/{self.config.site}/check_mk/"
            }
            
            # Prepare request parameters based on endpoint type
            request_params = self._prepare_ajax_params(endpoint_info, period)
            
            if not request_params:
                self.logger.debug("No valid parameters constructed for AJAX request")
                return []
            
            self.logger.debug(f"AJAX request parameters: {list(request_params.keys())}")
            if 'context' in request_params:
                self.logger.debug(f"Context structure: {json.dumps(request_params['context'], indent=2)[:500]}...")
            
            # Make the AJAX request
            if self.session is None:
                raise ScrapingError("Session not authenticated. Call authenticate_session() first.")
                
            if method.upper() == 'GET':
                response = self.session.get(
                    url,
                    params=request_params,
                    headers=ajax_headers,
                    timeout=30,
                    allow_redirects=True
                )
            else:
                response = self.session.post(
                    url,
                    headers=ajax_headers,
                    data=request_params,
                    timeout=30,
                    allow_redirects=True
                )
            
            self.logger.debug(f"AJAX response status: {response.status_code}, content-type: {response.headers.get('content-type', 'unknown')}")
            
            if response.status_code == 200:
                # Parse the AJAX response
                return self._parse_ajax_response(response, endpoint_info)
            elif response.status_code in [400, 422]:
                # Log validation errors for debugging
                self.logger.debug(f"AJAX validation error (status {response.status_code}): {response.text[:500]}")
                return []
            else:
                self.logger.debug(f"AJAX request failed with status {response.status_code}: {response.text[:200]}")
                return []
                
        except Exception as e:
            self.logger.debug(f"AJAX request failed: {e}")
            return []

    def _prepare_ajax_params(self, endpoint_info: Dict[str, Any], period: str = "4h") -> Dict[str, Any]:
        """Prepare parameters for AJAX request based on endpoint type.
        
        Args:
            endpoint_info: Endpoint information dictionary
            period: Time period for data extraction (4h, 25h, 8d, etc.)
            
        Returns:
            Dictionary of parameters formatted for the specific endpoint
        """
        try:
            endpoint_type = endpoint_info.get('type', 'unknown')
            
            # Handle the discovered ajax_graph.py endpoint with context parameter
            if endpoint_type == 'checkmk_ajax_graph' and 'context' in endpoint_info:
                # Use the exact parameter structure discovered
                context_data = endpoint_info['context']
                
                # Serialize context as JSON string for the 'context' parameter
                context_json = json.dumps(context_data['context'])
                
                return {
                    'context': context_json
                }
            
            # Handle inferred ajax_graph.py endpoint - need to construct context parameter
            elif endpoint_type == 'inferred_ajax_graph':
                # For ajax_graph.py, try to use minimal required context structure
                # This is a simplified version based on what the working endpoint uses
                import time
                current_time = int(time.time())
                period_seconds = self._convert_period_to_seconds(period)
                start_time = current_time - period_seconds
                minimal_context = {
                    "data_range": {
                        "time_range": [start_time, current_time],  # Use requested period
                        "step": 30
                    },
                    "render_config": {
                        "foreground_color": "#ffffff",
                        "background_color": "#ffffff",
                        "show_legend": True
                    },
                    "definition": {
                        "specification": {
                            "site": self.config.site,
                            "host_name": "piaware",
                            "service_description": "Temperature Zone 0",
                            "graph_index": 0,
                            "graph_id": "temp",
                            "graph_type": "template"
                        },
                        "title": "Temperature Zone 0",
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
                                    "site_id": self.config.site,
                                    "host_name": "piaware",
                                    "service_name": "Temperature Zone 0",
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
                self.logger.debug(f"Created minimal context for inferred endpoint")
                return {
                    'context': context_json
                }
            
            # Handle fallback patterns with traditional URL parameters
            elif 'params' in endpoint_info:
                params = endpoint_info['params']
                
                # Convert params to appropriate format
                if isinstance(params, str):
                    # Parse URL parameter string
                    parsed_params = {}
                    for param_pair in params.split('&'):
                        if '=' in param_pair:
                            key, value = param_pair.split('=', 1)
                            parsed_params[key] = urllib.parse.unquote_plus(value)
                    return parsed_params
                elif isinstance(params, dict):
                    return params
                else:
                    # params is neither string nor dict, use fallback
                    return {
                        'host': 'piaware',
                        'service': 'Temperature Zone 0', 
                        'site': self.config.site,
                        'timerange': period,
                        'format': 'json'
                    }
            
            # Fallback: construct basic parameters from current context
            else:
                return {
                    'host': 'piaware',
                    'service': 'Temperature Zone 0',
                    'site': self.config.site,
                    'timerange': period,
                    'format': 'json'
                }
                
        except Exception as e:
            self.logger.debug(f"Failed to prepare AJAX parameters: {e}")
            return {}

    def _convert_period_to_seconds(self, period: str) -> int:
        """Convert time period string to seconds.
        
        Args:
            period: Time period string (e.g., '4h', '25h', '8d', '1w')
            
        Returns:
            Number of seconds corresponding to the period
        """
        import re
        
        # Parse the period string
        match = re.match(r'^(\d+)([hdwmy])$', period.lower())
        if not match:
            self.logger.warning(f"Invalid period format: {period}, defaulting to 4h")
            return 4 * 60 * 60  # Default to 4 hours
        
        value = int(match.group(1))
        unit = match.group(2)
        
        # Convert to seconds
        if unit == 'h':  # hours
            return value * 60 * 60
        elif unit == 'd':  # days
            return value * 24 * 60 * 60
        elif unit == 'w':  # weeks
            return value * 7 * 24 * 60 * 60
        elif unit == 'm':  # months (approximate as 30 days)
            return value * 30 * 24 * 60 * 60
        elif unit == 'y':  # years (approximate as 365 days)
            return value * 365 * 24 * 60 * 60
        else:
            self.logger.warning(f"Unknown time unit: {unit}, defaulting to 4h")
            return 4 * 60 * 60

    def _parse_ajax_response(self, response, endpoint_info: Dict) -> List[Tuple]:
        """Parse AJAX response to extract time-series data.
        
        Enhanced to handle time-series data arrays from ajax_graph.py and convert
        Unix timestamps to ISO format as expected by the scraper.
        
        Args:
            response: HTTP response object from AJAX request
            endpoint_info: Information about the endpoint that was called
            
        Returns:
            List of (timestamp, value) tuples with ISO formatted timestamps
        """
        extracted_data = []
        
        try:
            content_type = response.headers.get('content-type', '').lower()
            response_text = response.text
            endpoint_type = endpoint_info.get('type', 'unknown')
            
            self.logger.debug(f"Parsing AJAX response: {len(response_text)} chars, content-type: {content_type}, endpoint-type: {endpoint_type}")
            
            # Log first 500 chars of response for debugging
            if response_text:
                self.logger.debug(f"Response preview: {response_text[:500]}...")
            
            # Try JSON parsing first (most likely for ajax_graph.py)
            if 'json' in content_type or response_text.strip().startswith(('{', '[')):
                try:
                    json_data = response.json()
                    self.logger.debug("Successfully parsed AJAX response as JSON")
                    self.logger.debug(f"JSON structure: {type(json_data)}, keys: {list(json_data.keys()) if isinstance(json_data, dict) else 'N/A'}")
                    
                    # Extract time-series data from JSON with enhanced handling
                    extracted_data = self._extract_timeseries_from_ajax_response(json_data, endpoint_type)
                    
                except json.JSONDecodeError as e:
                    self.logger.debug(f"JSON parsing failed: {e}")
                    # Fallback to text parsing
                    extracted_data = self._extract_data_from_ajax_text(response_text)
            
            # Try text/HTML parsing
            elif 'text' in content_type or 'html' in content_type:
                self.logger.debug("Parsing AJAX response as text/HTML")
                extracted_data = self._extract_data_from_ajax_text(response_text)
            
            # Unknown content type - try both approaches
            else:
                self.logger.debug("Unknown content type, trying multiple parsing approaches")
                # Try JSON first
                try:
                    json_data = response.json()
                    extracted_data = self._extract_timeseries_from_ajax_response(json_data, endpoint_type)
                except:
                    # Fallback to text parsing
                    extracted_data = self._extract_data_from_ajax_text(response_text)
            
            # Convert raw data to the expected format (ISO timestamps, floats)
            processed_data = self._process_ajax_data_points(extracted_data)
            
            self.logger.debug(f"Extracted {len(extracted_data)} raw data points, processed {len(processed_data)} valid points")
            
            if processed_data:
                # Log sample for debugging
                sample = processed_data[:3]
                self.logger.debug(f"Sample processed AJAX data: {sample}")
            
            return processed_data
            
        except Exception as e:
            self.logger.debug(f"Failed to parse AJAX response: {e}")
            return []

    def _process_ajax_data_points(self, raw_data: List[Tuple]) -> List[Tuple[str, float]]:
        """Process raw AJAX data points into the expected format.
        
        Converts Unix timestamps to ISO format and ensures temperature values are floats.
        
        Args:
            raw_data: List of raw (timestamp, value) tuples from AJAX
            
        Returns:
            List of (iso_timestamp, temperature) tuples
        """
        processed_data = []
        
        try:
            for timestamp_raw, value_raw in raw_data:
                # Convert timestamp to ISO format
                iso_timestamp = self._convert_timestamp_to_iso(timestamp_raw)
                
                if iso_timestamp is None:
                    self.logger.debug(f"Skipping data point with invalid timestamp: {timestamp_raw}")
                    continue
                
                # Convert value to float
                try:
                    temperature = float(value_raw)
                    
                    # Validate temperature range (reasonable sensor values)
                    if -100 <= temperature <= 200:
                        processed_data.append((iso_timestamp, temperature))
                    else:
                        self.logger.debug(f"Skipping data point with out-of-range temperature: {temperature}")
                        
                except (ValueError, TypeError):
                    self.logger.debug(f"Skipping data point with invalid temperature value: {value_raw}")
                    continue
            
            # Sort by timestamp for consistency
            processed_data.sort(key=lambda x: x[0])
            
            return processed_data
            
        except Exception as e:
            self.logger.debug(f"Failed to process AJAX data points: {e}")
            return []

    def _extract_timeseries_from_ajax_response(self, json_data, endpoint_type: str = 'unknown') -> List[Tuple]:
        """Extract time-series data from AJAX JSON response.
        
        Enhanced to handle specific response formats from ajax_graph.py endpoint
        and other Checkmk AJAX endpoints.
        
        Args:
            json_data: Parsed JSON data from AJAX response
            endpoint_type: Type of endpoint that returned this data
            
        Returns:
            List of (timestamp, value) tuples
        """
        extracted_data = []
        
        try:
            self.logger.debug(f"Analyzing AJAX JSON structure: {type(json_data)}, endpoint_type: {endpoint_type}")
            
            # Handle specific ajax_graph.py response format
            if endpoint_type == 'checkmk_ajax_graph' and isinstance(json_data, dict):
                self.logger.debug("Processing ajax_graph.py specific response format")
                
                # Look for common ajax_graph.py response structures
                ajax_graph_fields = ['curves', 'graph_data', 'plot_data', 'time_series', 'data']
                
                for field in ajax_graph_fields:
                    if field in json_data:
                        field_data = json_data[field]
                        self.logger.debug(f"Found '{field}' in ajax_graph.py response")
                        
                        if isinstance(field_data, list):
                            # Direct array of data points or curves
                            for item in field_data:
                                if isinstance(item, dict) and 'data' in item:
                                    # Curve with data points
                                    curve_data = item['data']
                                    if isinstance(curve_data, list):
                                        extracted_data.extend(self._process_array_data(curve_data, 1))
                                elif isinstance(item, list) and len(item) >= 2:
                                    # Direct [timestamp, value] pairs
                                    if self._is_likely_timestamp(item[0]) and self._is_numeric_value(item[1]):
                                        extracted_data.append((item[0], item[1]))
                        
                        elif isinstance(field_data, dict):
                            # Nested structure - recurse
                            nested_data = self._extract_timeseries_from_ajax_response(field_data, endpoint_type)
                            extracted_data.extend(nested_data)
                
                # Also check for error/status information
                if 'error' in json_data:
                    self.logger.debug(f"ajax_graph.py returned error: {json_data['error']}")
                elif 'status' in json_data:
                    self.logger.debug(f"ajax_graph.py status: {json_data['status']}")
            
            # Generic Checkmk response handling
            elif isinstance(json_data, dict):
                # Check for common Checkmk graph data structures
                data_fields = ['data', 'series', 'graph_data', 'metrics', 'curves', 'timeseries']
                
                for field in data_fields:
                    if field in json_data:
                        field_data = json_data[field]
                        self.logger.debug(f"Found '{field}' in AJAX JSON response")
                        
                        if isinstance(field_data, list):
                            # Direct array of data points
                            for item in field_data:
                                if isinstance(item, list) and len(item) >= 2:
                                    timestamp_raw = item[0]
                                    value_raw = item[1]
                                    
                                    if self._is_likely_timestamp(timestamp_raw) and self._is_numeric_value(value_raw):
                                        extracted_data.append((timestamp_raw, value_raw))
                                        
                                elif isinstance(item, dict):
                                    # Object with timestamp/value properties
                                    timestamp_raw = self._extract_timestamp_from_object(item)
                                    value_raw = self._extract_value_from_object(item)
                                    
                                    if timestamp_raw is not None and value_raw is not None:
                                        extracted_data.append((timestamp_raw, value_raw))
                        
                        elif isinstance(field_data, dict):
                            # Nested structure - recurse
                            nested_data = self._extract_timeseries_from_ajax_json(field_data, 1)
                            extracted_data.extend(nested_data)
                
                # Also check for Checkmk-specific response formats
                if 'result' in json_data:
                    result_data = self._extract_timeseries_from_ajax_json(json_data['result'], 1)
                    extracted_data.extend(result_data)
                    
            elif isinstance(json_data, list):
                # Direct array of data points
                extracted_data.extend(self._process_array_data(json_data, 1))
            
            self.logger.debug(f"Extracted {len(extracted_data)} points from AJAX JSON")
            return extracted_data
            
        except Exception as e:
            self.logger.debug(f"Failed to extract data from AJAX JSON: {e}")
            return []

    def _extract_data_from_ajax_text(self, response_text: str) -> List[Tuple]:
        """Extract data from non-JSON AJAX response text.
        
        Args:
            response_text: Raw text response from AJAX
            
        Returns:
            List of (timestamp, value) tuples
        """
        extracted_data = []
        
        try:
            # Try to find JSON embedded in text response
            json_patterns = [
                r'\{.*"data".*\[.*\].*\}',
                r'\[\s*\[.*\]\s*\]',  # Array of arrays
                r'"(?:data|series|points)"\s*:\s*(\[.*?\])',
            ]
            
            for pattern in json_patterns:
                matches = re.finditer(pattern, response_text, re.DOTALL)
                for match in matches:
                    json_str = match.group(0)
                    try:
                        json_data = json.loads(json_str)
                        nested_data = self._extract_timeseries_from_ajax_json(json_data, 1)
                        extracted_data.extend(nested_data)
                    except json.JSONDecodeError:
                        continue
            
            # If no JSON found, try regex patterns for data
            if not extracted_data:
                extracted_data = self._extract_timestamp_value_pairs(response_text, 1)
            
            self.logger.debug(f"Extracted {len(extracted_data)} points from AJAX text")
            return extracted_data
            
        except Exception as e:
            self.logger.debug(f"Failed to extract data from AJAX text: {e}")
            return []

    def scrape_historical_data(
        self,
        period: str = "4h",
        host: str = "piaware",
        service: str = "Temperature Zone 0"
    ) -> List[Tuple[str, Union[float, str]]]:
        """Main scraping method that combines graph and table data.
        
        Args:
            period: Time period for historical data
            host: Target host name
            service: Service name
            
        Returns:
            Combined list of time-series data and summary statistics as tuples
            Format: [("timestamp", temperature), ("min", value), ("max", value), ...]
            
        Raises:
            ScrapingError: If any step of the scraping process fails
        """
        self.logger.debug(f"Starting historical data scrape for {host}/{service}, period: {period}")
        
        try:
            # Step 1: Authenticate if needed
            if not self.session:
                self.authenticate_session()
            
            # Step 2: Fetch the monitoring page
            html_content = self.fetch_page(period, host, service)
            
            # Step 2.5: Parse and validate HTML structure (Phase 3)
            self.logger.debug("Parsing and validating HTML structure")
            soup = self._parse_html_with_fallback(html_content)
            
            # Validate that we have a proper monitoring page
            if not self._validate_page_structure(soup, host, service):
                self.logger.warning("Page structure validation failed - may not be the expected monitoring page")
                # Log HTML structure for troubleshooting
                self._log_html_structure(soup)
            else:
                self.logger.debug("Page structure validation passed")
            
            # Step 3: Try primary AJAX approach for graph data (Phase 4)
            graph_data = self.parse_graph_data(html_content, period)
            self.logger.debug(f"Primary AJAX approach extracted {len(graph_data)} data points from graph")
            
            # Step 4: Parse table data (Phase 5)
            table_data = self.parse_table_data(html_content)
            self.logger.debug(f"Extracted {len(table_data)} summary statistics from table")
            
            # Step 5: Combine primary data
            combined_data = graph_data + table_data
            
            # Step 6: If primary approaches failed or returned minimal data, try alternatives
            if len(combined_data) <= 1:  # Only got minimal data (like one incorrect point)
                self.logger.warning(f"Primary approaches returned minimal data ({len(combined_data)} points). Trying alternative approaches...")
                try:
                    alternative_data = self.try_alternative_approaches(host, service, period)
                    if alternative_data:
                        self.logger.info(f"Alternative approaches succeeded with {len(alternative_data)} data points")
                        # Replace or supplement primary data with alternative data
                        combined_data = alternative_data
                    else:
                        self.logger.warning("Alternative approaches also returned no data")
                except Exception as e:
                    self.logger.error(f"Alternative approaches failed: {e}")
                    # Continue with whatever data we have
            
            self.logger.debug(f"Final output contains {len(combined_data)} total data points")
            
            if combined_data:
                self.logger.debug(f"Sample data: {combined_data[:3]}")
                
                # Log success details
                if len(combined_data) > 1:
                    self.logger.info(f"✅ Successfully extracted {len(combined_data)} temperature data points")
                else:
                    self.logger.warning(f"⚠️ Only extracted {len(combined_data)} data point (minimal success)")
            else:
                self.logger.error("❌ No temperature data extracted")
            
            return combined_data
            
        except ScrapingError:
            # Re-raise ScrapingError without modification
            raise
        except Exception as e:
            # Convert unexpected errors to ScrapingError
            error_msg = f"Unexpected error during scraping: {e}"
            self.logger.error(error_msg)
            raise ScrapingError(error_msg, response_data={"error": str(e)})

    # Phase 4B: AJAX-Based Graph Data Extraction Methods
    
    def extract_graph_parameters(self, html_content: str) -> List[Dict]:
        """Extract JavaScript parameters from cmk.graphs.load_graph_content() calls.
        
        Phase 4B implementation: Parses the HTML to find JavaScript calls to
        cmk.graphs.load_graph_content(graph_recipe, graph_data_range, graph_render_config, graph_display_id)
        and extracts the four parameters needed for AJAX requests to ajax_render_graph_content.py.
        
        Args:
            html_content: Raw HTML content from the monitoring page
            
        Returns:
            List of parameter dictionaries containing graph_recipe, graph_data_range, 
            graph_render_config, and graph_display_id for each graph found
            
        Raises:
            ScrapingError: If parameter extraction fails
        """
        self.logger.debug("Phase 4B: Extracting JavaScript parameters from cmk.graphs.load_graph_content() calls")
        
        parameters_list = []
        
        try:
            # Pattern to match cmk.graphs.load_graph_content() calls with 4 arguments
            # This pattern captures all function calls with proper argument parsing
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

    def make_ajax_request(self, parameters: Dict, period: str = "4h") -> Optional[str]:
        """Make AJAX POST request to ajax_render_graph_content.py endpoint.
        
        Phase 4C implementation: Replicates the browser's AJAX flow by sending
        a POST request with proper request parameter to the ajax_render_graph_content.py
        endpoint, matching the exact format used by Checkmk's JavaScript.
        
        Args:
            parameters: Dictionary containing graph_recipe, graph_data_range, 
                       graph_render_config, and graph_display_id
            period: Time period for the data request (e.g., '4h', '25h', '8d')
                   Used to update the time_range in graph_data_range
                       
        Returns:
            Raw HTML response from the AJAX endpoint, or None if request fails
            
        Raises:
            ScrapingError: If AJAX request fails with authentication or network issues
        """
        self.logger.debug("Phase 4C: Making AJAX request to ajax_render_graph_content.py")
        
        try:
            # Ensure we have an authenticated session
            if not self.session:
                self.authenticate_session()
            
            # Construct the correct AJAX endpoint URL 
            ajax_url = f"{self.config.server_url}/{self.config.site}/check_mk/ajax_render_graph_content.py"
            
            # Update graph_data_range with correct time_range based on period parameter
            # This fixes the issue where different periods return identical time ranges
            import time
            updated_graph_data_range = parameters['graph_data_range'].copy()
            
            # Calculate time range based on requested period
            period_seconds = self._convert_period_to_seconds(period)
            current_time = int(time.time())
            start_time = current_time - period_seconds
            
            # Store calculated time range for use in timestamp calculation
            self._ajax_calculated_start = start_time
            self._ajax_calculated_end = current_time
            
            # Update time_range to match the requested period
            # Keep other parameters like 'step' unchanged for compatibility
            if 'time_range' in updated_graph_data_range:
                self.logger.debug(f"Original time_range: {updated_graph_data_range['time_range']}")
                updated_graph_data_range['time_range'] = [start_time, current_time]
                self.logger.debug(f"Updated time_range for period {period}: [{start_time}, {current_time}] ({period_seconds} seconds)")
            else:
                self.logger.warning("No time_range found in graph_data_range, adding new one")
                updated_graph_data_range['time_range'] = [start_time, current_time]
            
            # Phase 4C: Create the request parameter that ajax_render_graph_content.py requires
            # This matches the browser's exact format from the JavaScript source
            
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
            self.logger.debug(f"Request JSON preview: {request_json[:200]}...")
            self.logger.debug(f"Graph display ID: {parameters['graph_display_id']}")
            
            # Set headers to match browser AJAX requests
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'X-Requested-With': 'XMLHttpRequest',
                'Accept': 'text/html, */*; q=0.01',
                'Referer': f"{self.config.server_url}/{self.config.site}/check_mk/index.py"
            }
            
            # Make the POST request
            if self.session is None:
                raise ScrapingError("Session not authenticated. Call authenticate_session() first.")
                
            response = self.session.post(
                ajax_url,
                data=post_data,
                headers=headers,
                timeout=30,
                allow_redirects=True
            )
            
            self.logger.debug(f"AJAX response status: {response.status_code}")
            self.logger.debug(f"AJAX response content-type: {response.headers.get('content-type', 'unknown')}")
            self.logger.debug(f"AJAX response length: {len(response.text)} characters")
            self.logger.debug(f"AJAX response first 200 chars: {repr(response.text[:200])}")
            
            if response.status_code == 200:
                # Check if response is JSON with result_code (common Checkmk AJAX pattern)
                try:
                    if response.headers.get('content-type', '').startswith('application/json'):
                        json_response = response.json()
                        self.logger.debug(f"AJAX JSON response: {json_response}")
                        
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
            error_msg = f"Unexpected error during AJAX request: {e}"
            self.logger.error(error_msg)
            raise ScrapingError(error_msg, url=ajax_url, response_data={"error": str(e)})

    def parse_ajax_response(self, ajax_html: str) -> List[Tuple[str, float]]:
        """Parse time-series data from AJAX response HTML.
        
        Phase 4D implementation: Extracts rich time-series data from embedded
        JavaScript parameters in cmk.graphs.create_graph() calls. The response
        contains complete graph data with 480+ data points and summary statistics.
        
        Phase 6 Edge Case Handling: Comprehensive validation for null/missing data,
        empty responses, malformed JSON, and partial data scenarios with graceful fallbacks.
        
        Args:
            ajax_html: Raw JSON response from ajax_render_graph_content.py
            
        Returns:
            List of (timestamp, temperature) tuples with timestamps in ISO format
            
        Raises:
            ScrapingError: If parsing the AJAX response fails completely
        """
        self.logger.debug("Phase 4D: Enhanced parsing of time-series data from AJAX response")
        self.logger.debug(f"AJAX response length: {len(ajax_html)} characters")
        
        # Phase 6: Validate input parameters
        if not ajax_html:
            self.logger.warning("Phase 6: Empty AJAX response received")
            return []
            
        if not isinstance(ajax_html, str):
            self.logger.warning(f"Phase 6: Invalid AJAX response type: {type(ajax_html)}")
            return []
            
        if len(ajax_html.strip()) < 10:
            self.logger.warning("Phase 6: AJAX response too short to contain valid data")
            return []
        
        extracted_data = []
        
        try:
            # Phase 4D: Parse response and extract embedded graph data efficiently
            # Handle both JSON and direct HTML responses
            if ajax_html.strip().startswith('{'):
                try:
                    json_data = json.loads(ajax_html)
                    self.logger.debug("Detected JSON data in AJAX response")
                    
                    # Phase 6: Validate JSON response structure
                    if not isinstance(json_data, dict):
                        self.logger.warning("Phase 6: JSON response is not a dictionary")
                        return []
                    
                    # Check for successful response
                    result_code = json_data.get('result_code')
                    if result_code == 0:
                        self.logger.debug("AJAX request successful with result_code=0")
                        
                        # Extract HTML content containing JavaScript graph calls
                        result_html = json_data.get('result', '')
                        
                        # Phase 6: Validate result content
                        if not result_html:
                            self.logger.warning("Phase 6: Empty result content in JSON response")
                            return []
                            
                        if not isinstance(result_html, str):
                            self.logger.warning(f"Phase 6: Invalid result content type: {type(result_html)}")
                            return []
                        
                        # Phase 4D: Extract graph data directly from cmk.graphs.create_graph() calls
                        # The data is embedded as the second parameter in JavaScript function calls
                        graph_data = self._extract_graph_data_from_javascript(result_html)
                        
                        # Process the extracted graph data if found
                        if graph_data:
                            extracted_data = self._process_graph_data(graph_data)
                            if extracted_data:
                                self.logger.debug(f"Phase 4D: Successfully extracted {len(extracted_data)} data points from graph data")
                                return self._clean_and_sort_data(extracted_data)
                        else:
                            self.logger.debug("No graph data found in JSON wrapped AJAX response")
                    else:
                        # Phase 6: Handle error responses gracefully
                        error_result = json_data.get('result', 'Unknown error')
                        error_severity = json_data.get('severity', 'error')
                        self.logger.warning(f"Phase 6: AJAX request failed with result_code={result_code}, result='{error_result}', severity={error_severity}")
                        return []
                        
                except json.JSONDecodeError as e:
                    self.logger.debug(f"Phase 6: Failed to parse as JSON ({e}), treating as HTML")
            else:
                # Handle direct HTML response (newer ajax_render_graph_content.py format)
                self.logger.debug("Detected direct HTML response from AJAX endpoint")
                
                # Phase 4D: Extract graph data directly from cmk.graphs.create_graph() calls in HTML
                graph_data = self._extract_graph_data_from_javascript(ajax_html)
                
                # Process the extracted graph data if found
                if graph_data:
                    extracted_data = self._process_graph_data(graph_data)
                    if extracted_data:
                        self.logger.debug(f"Phase 4D: Successfully extracted {len(extracted_data)} data points from HTML response")
                        return self._clean_and_sort_data(extracted_data)
                else:
                    self.logger.debug("No graph data found in direct HTML AJAX response")
            
            # Fallback: Try to extract from the HTML content using original parsing methods
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
            from bs4 import Tag
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
                                            import datetime
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
            error_msg = f"Failed to parse AJAX response: {e}"
            self.logger.error(error_msg)
            raise ScrapingError(
                error_msg,
                html_snippet=ajax_html[:500] if ajax_html else None,
                response_data={"error": str(e)}
            )
    
    def _extract_graph_data_from_javascript(self, html_content: str) -> Optional[dict]:
        """Extract graph data from cmk.graphs.create_graph() JavaScript calls.
        
        Phase 4D implementation: Efficiently extracts the embedded JSON data
        from JavaScript function parameters using a targeted approach.
        
        Args:
            html_content: HTML content containing JavaScript graph calls
            
        Returns:
            Dictionary containing graph data structure, or None if not found
        """
        self.logger.debug("Phase 4D: Extracting graph data from JavaScript calls")
        
        # The data is embedded as the second parameter in cmk.graphs.create_graph calls
        # Format: cmk.graphs.create_graph("complex_html_string", {graph_data_object}, ...)
        # We need to skip over the complex first parameter and extract the second one
        
        # Use a simpler approach: look for the pattern "), {" which marks the transition
        # from the first parameter (HTML string) to the second parameter (graph data)
        pattern = r'cmk\.graphs\.create_graph\s*\([^,]+,\s*(\{[^}]+\}|\{.*?\})'
        
        # Since the JSON can be very large and nested, use a more robust approach
        # Look for cmk.graphs.create_graph and then find the second parameter manually
        
        create_graph_pos = html_content.find('cmk.graphs.create_graph')
        while create_graph_pos != -1:
            try:
                # Find the opening parenthesis
                paren_pos = html_content.find('(', create_graph_pos)
                if paren_pos == -1:
                    break
                    
                # Skip over the first parameter (the HTML string)
                # Look for "), {" pattern which indicates start of second parameter
                search_start = paren_pos + 1
                remaining = html_content[search_start:]
                
                # Find the pattern that indicates the start of the data object
                # Look for "), {" - end of first param, start of second param
                transition_pattern = r'\"\s*,\s*\{'
                match = re.search(transition_pattern, remaining)
                
                if match:
                    # Found the start of the data object
                    json_start = search_start + match.end() - 1  # -1 to include the opening brace
                    
                    # Extract the complete JSON object
                    json_data = self._extract_json_object(html_content, json_start)
                    if json_data:
                        self.logger.debug(f"Phase 4D: Extracted JSON data: {len(json_data)} characters")
                        try:
                            graph_data = json.loads(json_data)
                            if 'curves' in graph_data and isinstance(graph_data['curves'], list):
                                self.logger.debug("Phase 4D: Successfully parsed graph data with curves")
                                return graph_data
                            elif 'title' in graph_data:
                                self.logger.debug("Phase 4D: Found graph data but no curves")
                                # Continue searching for one with curves
                        except json.JSONDecodeError as e:
                            self.logger.debug(f"Phase 4D: JSON parsing failed: {e}")
                            # Continue searching
                
                # Look for the next cmk.graphs.create_graph call
                create_graph_pos = html_content.find('cmk.graphs.create_graph', create_graph_pos + 1)
                
            except Exception as e:
                self.logger.debug(f"Phase 4D: Error processing create_graph call: {e}")
                # Continue to next occurrence
                create_graph_pos = html_content.find('cmk.graphs.create_graph', create_graph_pos + 1)
        
        self.logger.debug("Phase 4D: No valid graph data with curves found in JavaScript calls")
        return None
    
    def _extract_json_object(self, content: str, start_pos: int) -> Optional[str]:
        """Extract a complete JSON object from JavaScript code using brace counting.
        
        Args:
            content: JavaScript content
            start_pos: Position of the opening brace
            
        Returns:
            Complete JSON object as string, or None if extraction fails
        """
        if start_pos >= len(content) or content[start_pos] != '{':
            return None
            
        brace_level = 0
        in_string = False
        escape_next = False
        
        for i in range(start_pos, len(content)):
            char = content[i]
            
            if escape_next:
                escape_next = False
                continue
                
            if char == '\\' and in_string:
                escape_next = True
                continue
                
            if char == '"':
                in_string = not in_string
                continue
                
            if not in_string:
                if char == '{':
                    brace_level += 1
                elif char == '}':
                    brace_level -= 1
                    if brace_level == 0:
                        # Found the complete object
                        return content[start_pos:i+1]
                        
        return None
    
    def _process_graph_data(self, graph_data: dict) -> List[Tuple[str, float]]:
        """Process extracted graph data to create time-series and summary data.
        
        Phase 4D implementation: Processes curves data to extract all 480+ data points
        and summary statistics with proper timestamp calculation.
        
        Phase 6 Edge Case Handling: Comprehensive validation for null/missing graph data,
        empty curves, invalid timestamps, and malformed scalar data with graceful fallbacks.
        
        Args:
            graph_data: Dictionary containing graph data structure
            
        Returns:
            List of (timestamp/name, value) tuples
        """
        self.logger.debug("Phase 4D: Processing graph data to extract time-series and statistics")
        extracted_data = []
        
        # Phase 6: Comprehensive input validation
        if not graph_data:
            self.logger.warning("Phase 6: Empty graph_data provided")
            return extracted_data
            
        if not isinstance(graph_data, dict):
            self.logger.warning(f"Phase 6: Invalid graph_data type: {type(graph_data)}")
            return extracted_data
            
        if 'curves' not in graph_data:
            self.logger.warning("Phase 6: Graph data does not contain 'curves' field")
            return extracted_data
            
        curves = graph_data['curves']
        if not curves:
            self.logger.warning("Phase 6: Empty curves array in graph data")
            return extracted_data
            
        if not isinstance(curves, list):
            self.logger.warning(f"Phase 6: Invalid curves type: {type(curves)}")
            return extracted_data
            
        # Extract time axis information for accurate timestamps with validation
        time_range_start = graph_data.get('start_time')
        time_range_step = graph_data.get('step')
        
        # Phase 6: Validate time range values
        if time_range_start is not None:
            if not isinstance(time_range_start, (int, float)):
                self.logger.warning(f"Phase 6: Invalid start_time type: {type(time_range_start)}")
                time_range_start = None
            elif time_range_start <= 0 or time_range_start > 9999999999:  # Invalid timestamp range
                self.logger.warning(f"Phase 6: Invalid start_time value: {time_range_start}")
                time_range_start = None
                
        if time_range_step is not None:
            if not isinstance(time_range_step, (int, float)):
                self.logger.warning(f"Phase 6: Invalid step type: {type(time_range_step)}")
                time_range_step = None
            elif time_range_step <= 0 or time_range_step > 86400:  # More than 1 day per step is unreasonable
                self.logger.warning(f"Phase 6: Invalid step value: {time_range_step}")
                time_range_step = None
        
        # Fallback to time_axis labels if direct time info not available
        if not time_range_start and 'time_axis' in graph_data:
            time_axis = graph_data['time_axis']
            if isinstance(time_axis, dict) and 'labels' in time_axis and time_axis['labels']:
                try:
                    first_label = time_axis['labels'][0]
                    if isinstance(first_label, dict) and 'position' in first_label:
                        time_range_start = first_label['position']
                        time_range = time_axis.get('range', [])
                        if isinstance(time_range, list) and len(time_range) >= 2:
                            total_time = time_range[1] - time_range[0]
                            # Step will be calculated per curve based on number of points
                except (KeyError, IndexError, TypeError) as e:
                    self.logger.debug(f"Phase 6: Failed to extract time_axis fallback data: {e}")
        
        self.logger.debug(f"Time range info: start={time_range_start}, step={time_range_step}")
        
        # Process each curve with comprehensive validation
        valid_curves_processed = 0
        for curve_idx, curve in enumerate(curves):
            # Phase 6: Validate curve structure
            if not curve:
                self.logger.debug(f"Phase 6: Empty curve {curve_idx}, skipping")
                continue
                
            if not isinstance(curve, dict):
                self.logger.debug(f"Phase 6: Invalid curve {curve_idx} type: {type(curve)}, skipping")
                continue
                
            if 'points' not in curve:
                self.logger.debug(f"Phase 6: Curve {curve_idx} missing 'points' field, skipping")
                continue
                
            points = curve['points']
            if not points:
                self.logger.debug(f"Phase 6: Curve {curve_idx} has empty points array, skipping")
                continue
                
            if not isinstance(points, list):
                self.logger.debug(f"Phase 6: Curve {curve_idx} points is not a list: {type(points)}, skipping")
                continue
                
            curve_title = curve.get('title', f'Curve {curve_idx}')
            self.logger.debug(f"Processing curve '{curve_title}' with {len(points)} data points")
            valid_curves_processed += 1
            
            # Calculate step size based on actual data points if not provided
            if not time_range_step and time_range_start:
                if 'time_axis' in graph_data and 'range' in graph_data['time_axis']:
                    time_range = graph_data['time_axis']['range']
                    if len(time_range) >= 2 and len(points) > 1:
                        total_time = time_range[1] - time_range[0]
                        time_range_step = total_time / len(points)
                        self.logger.debug(f"Calculated step size: {time_range_step} seconds")
            
            # Process each data point with comprehensive validation
            valid_points_in_curve = 0
            null_points_skipped = 0
            invalid_points_skipped = 0
            
            for point_idx, point in enumerate(points):
                # Phase 6: Comprehensive point validation
                if not point:
                    invalid_points_skipped += 1
                    continue
                    
                if not isinstance(point, list):
                    invalid_points_skipped += 1
                    continue
                    
                if len(point) < 2:
                    invalid_points_skipped += 1
                    continue
                    
                # Point format: [time_offset, temperature_value]
                time_offset = point[0]
                temp_value = point[1]
                
                # Phase 6: Enhanced null value handling
                if temp_value is None:
                    null_points_skipped += 1
                    continue
                    
                # Phase 6: Validate temperature value type and range
                if not isinstance(temp_value, (int, float)):
                    try:
                        temp_value = float(temp_value)
                    except (ValueError, TypeError):
                        invalid_points_skipped += 1
                        continue
                
                # Phase 6: Reasonable temperature range validation (handle both Celsius and Fahrenheit)
                import math
                if math.isnan(temp_value) or math.isinf(temp_value):
                    self.logger.debug(f"Phase 6: Temperature value {temp_value} is NaN or infinite, skipping")
                    invalid_points_skipped += 1
                    continue
                    
                if temp_value < -100 or temp_value > 200:  # Extended range for various systems
                    self.logger.debug(f"Phase 6: Temperature value {temp_value} outside reasonable range, skipping")
                    invalid_points_skipped += 1
                    continue
                
                # Phase 6: Handle null time offset
                if time_offset is None:
                    time_offset = 0
                elif not isinstance(time_offset, (int, float)):
                    try:
                        time_offset = float(time_offset)
                    except (ValueError, TypeError):
                        time_offset = 0
                    
                # Calculate absolute timestamp with validation
                try:
                    if time_range_start and time_range_step:
                        # For long periods like 1y, use our calculated time range instead of
                        # potentially incorrect values from the AJAX response
                        if hasattr(self, '_ajax_calculated_start') and hasattr(self, '_ajax_calculated_end'):
                            # Use our time range from the AJAX request
                            calculated_duration = self._ajax_calculated_end - self._ajax_calculated_start
                            calculated_step = calculated_duration / len(points) if len(points) > 1 else time_range_step
                            absolute_time = self._ajax_calculated_start + (point_idx * calculated_step)
                        else:
                            # Fallback to response values for shorter periods
                            absolute_time = time_range_start + (point_idx * time_range_step)
                    else:
                        # Phase 6: Enhanced fallback to current time distribution
                        import datetime
                        current_time = datetime.datetime.now().timestamp()
                        fallback_start = current_time - (4 * 3600)  # Default 4 hours ago
                        fallback_step = (4 * 3600) / len(points) if len(points) > 0 else 1
                        absolute_time = fallback_start + (point_idx * fallback_step)
                    
                    # Phase 6: Validate calculated timestamp
                    if absolute_time <= 0 or absolute_time > 9999999999:  # Invalid timestamp
                        self.logger.debug(f"Phase 6: Invalid calculated timestamp {absolute_time} for point {point_idx}, using fallback")
                        import datetime
                        absolute_time = datetime.datetime.now().timestamp()
                    
                    # Convert to ISO format with error handling
                    import datetime
                    timestamp = datetime.datetime.fromtimestamp(absolute_time).isoformat()
                    extracted_data.append((timestamp, float(temp_value)))
                    valid_points_in_curve += 1
                    
                except (ValueError, OSError, OverflowError) as e:
                    self.logger.debug(f"Phase 6: Failed to process timestamp for point {point_idx}: {e}")
                    invalid_points_skipped += 1
                    continue
            
            # Phase 6: Log curve processing statistics
            total_points = len(points)
            self.logger.debug(f"Phase 6: Curve '{curve_title}' processed: {valid_points_in_curve}/{total_points} valid points, {null_points_skipped} null values, {invalid_points_skipped} invalid points")
            
            # Extract summary statistics from scalars with enhanced validation
            scalars_extracted = 0
            scalars_skipped = 0
            
            if 'scalars' in curve and isinstance(curve['scalars'], dict):
                scalars = curve['scalars']
                self.logger.debug(f"Phase 6: Processing {len(scalars)} scalar values for curve '{curve_title}'")
                
                for scalar_name, scalar_data in scalars.items():
                    if scalar_name in ['min', 'max', 'average', 'last', 'first']:
                        try:
                            scalar_value = None
                            
                            # Phase 6: Handle different scalar data formats
                            if isinstance(scalar_data, list):
                                if len(scalar_data) >= 1 and scalar_data[0] is not None:
                                    scalar_value = scalar_data[0]
                                else:
                                    self.logger.debug(f"Phase 6: Empty or null scalar list for {scalar_name}")
                                    scalars_skipped += 1
                                    continue
                            elif isinstance(scalar_data, (int, float)):
                                scalar_value = scalar_data
                            elif scalar_data is None:
                                self.logger.debug(f"Phase 6: Null scalar value for {scalar_name}")
                                scalars_skipped += 1
                                continue
                            else:
                                # Try to convert to float
                                try:
                                    scalar_value = float(scalar_data)
                                except (ValueError, TypeError):
                                    self.logger.debug(f"Phase 6: Invalid scalar data type for {scalar_name}: {type(scalar_data)}")
                                    scalars_skipped += 1
                                    continue
                            
                            # Phase 6: Validate scalar value range
                            if scalar_value is not None:
                                if not isinstance(scalar_value, (int, float)):
                                    scalar_value = float(scalar_value)
                                
                                # Reasonable range check for temperature statistics (including NaN/inf)
                                import math
                                if math.isnan(scalar_value) or math.isinf(scalar_value):
                                    self.logger.debug(f"Phase 6: Scalar {scalar_name} value {scalar_value} is NaN or infinite")
                                    scalars_skipped += 1
                                    continue
                                    
                                if scalar_value < -100 or scalar_value > 200:
                                    self.logger.debug(f"Phase 6: Scalar {scalar_name} value {scalar_value} outside reasonable range")
                                    scalars_skipped += 1
                                    continue
                                
                                extracted_data.append((scalar_name, float(scalar_value)))
                                scalars_extracted += 1
                                self.logger.debug(f"Extracted scalar {scalar_name}: {scalar_value}")
                            
                        except (ValueError, TypeError) as e:
                            self.logger.debug(f"Phase 6: Failed to process scalar {scalar_name}: {e}")
                            scalars_skipped += 1
                            continue
                            
                self.logger.debug(f"Phase 6: Scalar processing for curve '{curve_title}': {scalars_extracted} extracted, {scalars_skipped} skipped")
            else:
                self.logger.debug(f"Phase 6: No scalars found in curve '{curve_title}'")
        
        # Phase 6: Summary logging for overall processing
        self.logger.debug(f"Phase 4D: Processed graph data, extracted {len(extracted_data)} total data points")
        self.logger.debug(f"Phase 6: Processing summary: {valid_curves_processed}/{len(curves)} valid curves processed")
        
        if not extracted_data:
            self.logger.warning("Phase 6: No valid data points extracted from any curves")
        
        return extracted_data

    
    def _clean_and_sort_data(self, extracted_data: List[Tuple[str, float]]) -> List[Tuple[str, float]]:
        """Clean, deduplicate, and sort time-series data.
        
        Phase 6 Edge Case Handling: Enhanced validation for null tuples, invalid data types,
        malformed timestamps, and comprehensive data quality checking with detailed logging.
        
        Args:
            extracted_data: Raw list of (timestamp, value) tuples
            
        Returns:
            Cleaned and sorted list of (timestamp, value) tuples
        """
        # Phase 6: Input validation
        if not extracted_data:
            self.logger.debug("Phase 4D: No time-series data found in response")
            return []
            
        if not isinstance(extracted_data, list):
            self.logger.warning(f"Phase 6: Invalid extracted_data type: {type(extracted_data)}")
            return []
        
        self.logger.debug(f"Phase 6: Starting data cleaning with {len(extracted_data)} raw data points")
        
        # Phase 6: Validate and clean each data point
        valid_data = []
        invalid_tuples = 0
        invalid_timestamps = 0
        invalid_values = 0
        duplicate_count = 0
        
        for i, item in enumerate(extracted_data):
            # Validate tuple structure
            if not isinstance(item, tuple) or len(item) != 2:
                invalid_tuples += 1
                continue
                
            timestamp, value = item
            
            # Validate timestamp
            if not timestamp:
                invalid_timestamps += 1
                continue
                
            if not isinstance(timestamp, str):
                try:
                    timestamp = str(timestamp)
                except (ValueError, TypeError):
                    invalid_timestamps += 1
                    continue
            
            # Validate value
            if value is None:
                invalid_values += 1
                continue
                
            try:
                # Ensure value is numeric
                if not isinstance(value, (int, float)):
                    value = float(value)
                    
                # Range validation for temperature values (including NaN/inf check)
                import math
                if math.isnan(value) or math.isinf(value):
                    self.logger.debug(f"Phase 6: Value {value} is NaN or infinite, skipping")
                    invalid_values += 1
                    continue
                    
                if value < -100 or value > 200:
                    self.logger.debug(f"Phase 6: Value {value} outside reasonable range, skipping")
                    invalid_values += 1
                    continue
                    
            except (ValueError, TypeError):
                invalid_values += 1
                continue
            
            valid_data.append((timestamp, value))
        
        self.logger.debug(f"Phase 6: Data validation: {len(valid_data)}/{len(extracted_data)} valid points, {invalid_tuples} invalid tuples, {invalid_timestamps} invalid timestamps, {invalid_values} invalid values")
        
        if not valid_data:
            self.logger.warning("Phase 6: No valid data points remain after validation")
            return []
        
        # Remove duplicates while preserving order
        seen = set()
        unique_data = []
        for timestamp, value in valid_data:
            key = (timestamp, value)
            if key not in seen:
                seen.add(key)
                unique_data.append((timestamp, value))
            else:
                duplicate_count += 1
        
        # Sort by timestamp with error handling
        try:
            unique_data.sort(key=lambda x: x[0])
        except Exception as e:
            self.logger.warning(f"Phase 6: Failed to sort data by timestamp: {e}")
            # Continue with unsorted data rather than failing completely
        
        self.logger.debug(f"Phase 4D: Successfully cleaned and sorted {len(unique_data)} unique data points ({duplicate_count} duplicates removed)")
        
        if unique_data:
            # Separate time-series data from summary statistics for logging
            time_series_data = [point for point in unique_data if not point[0] in ['min', 'max', 'average', 'last', 'first']]
            summary_data = [point for point in unique_data if point[0] in ['min', 'max', 'average', 'last', 'first']]
            
            self.logger.debug(f"Time-series points: {len(time_series_data)}, Summary statistics: {len(summary_data)}")
            if time_series_data:
                self.logger.debug(f"Time range: {time_series_data[0][0]} to {time_series_data[-1][0]}")
                self.logger.debug(f"Value range: {min(point[1] for point in time_series_data):.2f} to {max(point[1] for point in time_series_data):.2f}")
        
        return unique_data
    
    def _is_reasonable_temperature(self, value: float) -> bool:
        """Check if a value is a reasonable temperature.
        
        Args:
            value: Numeric value to check
            
        Returns:
            True if value is in reasonable temperature range
        """
        # Reasonable temperature range for most systems (20°C to 100°C)
        return 20.0 <= value <= 100.0
    
    def _is_time_range_value(self, cell_text: str, value: float) -> bool:
        """Check if a value appears to be from time range controls.
        
        Args:
            cell_text: Original cell text containing the value
            value: Numeric value extracted
            
        Returns:
            True if value appears to be a time range control value
        """
        # Common time range values that should be filtered out
        time_range_values = {4, 25, 8, 35}  # Common values: 4h, 25h, 8d, 35d
        
        # Check if value matches common time range indicators
        if value in time_range_values:
            # Additional context check - look for time-related words nearby
            time_indicators = ["hour", "day", "h", "d", "time", "range", "period"]
            cell_lower = cell_text.lower()
            if any(indicator in cell_lower for indicator in time_indicators):
                return True
        
        return False

    # ========================================
    # ALTERNATIVE APPROACHES FOR DATA EXTRACTION
    # ========================================
    
    def try_alternative_approaches(
        self,
        host: str,
        service: str,
        period: str = "4h"
    ) -> List[Tuple[str, Union[float, str]]]:
        """Try multiple alternative approaches to extract temperature data.
        
        This method implements a systematic fallback strategy when the primary
        AJAX approach fails. It tries multiple methods in order of reliability:
        
        1. Service Status Current Values (REST API)
        2. REST API Metrics Endpoints  
        3. Alternative URL Strategies
        4. Enhanced HTML Parsing
        
        Args:
            host: Target host name
            service: Service name
            period: Time period for historical data
            
        Returns:
            List of tuples with timestamp/label and temperature values
            At minimum returns current temperature value if available
            
        Raises:
            ScrapingError: If all approaches fail
        """
        self.logger.info("AJAX approach failed, trying alternative data extraction methods...")
        
        approaches = [
            ("Service Status Current Values", self._approach_service_status),
            ("REST API Metrics", self._approach_rest_api_metrics), 
            ("Alternative URLs", self._approach_alternative_urls),
            ("Enhanced HTML Parsing", self._approach_enhanced_html_parsing)
        ]
        
        all_results = []
        
        for approach_name, approach_method in approaches:
            self.logger.info(f"Trying approach: {approach_name}")
            try:
                results = approach_method(host, service, period)
                if results:
                    self.logger.info(f"✅ {approach_name} succeeded with {len(results)} data points")
                    all_results.extend(results)
                    # If we get good results from an approach, we can stop here
                    # or continue to gather more data from other approaches
                    if len(results) > 1:  # More than just current value
                        break
                else:
                    self.logger.warning(f"❌ {approach_name} returned no data")
                    
            except Exception as e:
                self.logger.error(f"❌ {approach_name} failed: {e}")
                continue
        
        if all_results:
            # Remove duplicates and sort by timestamp
            unique_results = self._deduplicate_results(all_results)
            self.logger.info(f"Combined alternative approaches: {len(unique_results)} total data points")
            return unique_results
        else:
            raise ScrapingError("All alternative approaches failed to extract temperature data")
    
    def _approach_service_status(
        self,
        host: str,
        service: str,
        period: str
    ) -> List[Tuple[str, Union[float, str]]]:
        """Approach 1: Extract current temperature from service status API.
        
        This uses the existing Checkmk REST API to get current service status
        including performance data and plugin output.
        
        Args:
            host: Target host name
            service: Service name  
            period: Time period (not used for current status)
            
        Returns:
            List with current temperature value, e.g. [("current", 67.2)]
        """
        self.logger.debug("Attempting to extract current temperature from service status")
        
        try:
            # Initialize API client using the same config as scraper
            from checkmk_agent.api_client import CheckmkClient
            api_client = CheckmkClient(self.config)
            
            # Get service monitoring data with performance data
            services = api_client.get_service_monitoring_data(host, service)
            
            if not services:
                self.logger.warning(f"No services found for {host}/{service}")
                return []
            
            for svc in services:
                extensions = svc.get("extensions", {})
                svc_description = extensions.get("description", "")
                
                # Match service name (case insensitive)
                if svc_description.lower() != service.lower():
                    continue
                
                self.logger.debug(f"Found matching service: {svc_description}")
                
                # Try to extract temperature from performance data
                perf_data = extensions.get("perf_data", "")
                if perf_data:
                    temp_value = self._extract_temperature_from_perf_data(perf_data)
                    if temp_value is not None:
                        self.logger.info(f"Extracted temperature from perf_data: {temp_value}°C")
                        return [("current", temp_value)]
                
                # Try to extract from plugin output
                plugin_output = extensions.get("plugin_output", "")
                if plugin_output:
                    temp_value = self._extract_temperature_from_output(plugin_output)
                    if temp_value is not None:
                        self.logger.info(f"Extracted temperature from plugin_output: {temp_value}°C")
                        return [("current", temp_value)]
                
                # Log what we found for debugging
                self.logger.debug(f"Service state: {extensions.get('state', 'unknown')}")
                self.logger.debug(f"Plugin output: {plugin_output[:100]}...")
                self.logger.debug(f"Performance data: {perf_data[:100]}...")
            
            self.logger.warning("Could not extract temperature from service status data")
            return []
            
        except Exception as e:
            self.logger.error(f"Service status approach failed: {e}")
            return []
    
    def _extract_temperature_from_perf_data(self, perf_data: str) -> Optional[float]:
        """Extract temperature value from Checkmk performance data string.
        
        Performance data format is typically:
        'temp=67.2;70;80;0;100'
        
        Args:
            perf_data: Performance data string from service
            
        Returns:
            Temperature value if found, None otherwise
        """
        if not perf_data:
            return None
        
        # Look for temperature-related performance metrics
        import re
        
        # Common temperature metric patterns
        temp_patterns = [
            r'temp=([0-9.]+)',           # temp=67.2
            r'temperature=([0-9.]+)',    # temperature=67.2  
            r'celsius=([0-9.]+)',        # celsius=67.2
            r'°C=([0-9.]+)',            # °C=67.2
            r'degc=([0-9.]+)',          # degc=67.2
        ]
        
        for pattern in temp_patterns:
            match = re.search(pattern, perf_data, re.IGNORECASE)
            if match:
                try:
                    temp_value = float(match.group(1))
                    if self._is_reasonable_temperature(temp_value):
                        return temp_value
                except ValueError:
                    continue
        
        # If no specific temp metric, look for any numeric value that could be temperature
        # This is more aggressive parsing for cases where metric name is unclear
        all_numbers = re.findall(r'([0-9.]+)', perf_data)
        for num_str in all_numbers:
            try:
                value = float(num_str)
                if self._is_reasonable_temperature(value):
                    self.logger.debug(f"Found potential temperature value in perf_data: {value}")
                    return value
            except ValueError:
                continue
        
        return None
    
    def _extract_temperature_from_output(self, plugin_output: str) -> Optional[float]:
        """Extract temperature value from plugin output text.
        
        Plugin output often contains human-readable temperature information like:
        "Temperature: 67.2°C (warn/crit at 70°C/80°C)"
        
        Args:
            plugin_output: Plugin output string from service
            
        Returns:
            Temperature value if found, None otherwise
        """
        if not plugin_output:
            return None
        
        import re
        
        # Common temperature output patterns
        temp_patterns = [
            r'Temperature:\s*([0-9.]+)\s*°?C',        # Temperature: 67.2°C
            r'Temp:\s*([0-9.]+)\s*°?C',               # Temp: 67.2°C
            r'([0-9.]+)\s*°C',                        # 67.2°C
            r'([0-9.]+)\s*degrees?',                  # 67.2 degrees
            r'([0-9.]+)\s*celsius',                   # 67.2 celsius
            r'Zone\s*\d+:\s*([0-9.]+)',              # Zone 0: 67.2
            r'Sensor\s*\d*:\s*([0-9.]+)',            # Sensor: 67.2
        ]
        
        for pattern in temp_patterns:
            match = re.search(pattern, plugin_output, re.IGNORECASE)
            if match:
                try:
                    temp_value = float(match.group(1))
                    if self._is_reasonable_temperature(temp_value):
                        return temp_value
                except ValueError:
                    continue
        
        return None
    
    def _approach_rest_api_metrics(
        self,
        host: str,
        service: str,
        period: str
    ) -> List[Tuple[str, Union[float, str]]]:
        """Approach 2: Try REST API endpoints for historical metrics.
        
        This explores less common REST API endpoints that might provide
        historical metric data.
        
        Args:
            host: Target host name
            service: Service name
            period: Time period for historical data
            
        Returns:
            List with historical data points if available
        """
        self.logger.debug("Attempting to extract historical data from REST API metrics endpoints")
        
        try:
            from checkmk_agent.api_client import CheckmkClient
            api_client = CheckmkClient(self.config)
            
            # Try different metric-related endpoints
            endpoints_to_try = [
                f"/objects/host/{host}/services/{quote(service)}/metrics",
                f"/domain-types/metric/collections/all",
                f"/objects/host/{host}/collections/services",
                f"/domain-types/service/collections/all"
            ]
            
            results = []
            
            for endpoint in endpoints_to_try:
                try:
                    self.logger.debug(f"Trying REST API endpoint: {endpoint}")
                    response = api_client._make_request("GET", endpoint)
                    
                    # Look for metric data in response
                    if isinstance(response, dict):
                        metric_data = self._extract_metrics_from_response(response, service)
                        results.extend(metric_data)
                        
                except Exception as e:
                    self.logger.debug(f"Endpoint {endpoint} failed: {e}")
                    continue
            
            if results:
                self.logger.info(f"REST API metrics approach found {len(results)} data points")
            
            return results
            
        except Exception as e:
            self.logger.error(f"REST API metrics approach failed: {e}")
            return []
    
    def _extract_metrics_from_response(
        self,
        response: Dict,
        service: str
    ) -> List[Tuple[str, Union[float, str]]]:
        """Extract metric data from REST API response.
        
        Args:
            response: API response dictionary
            service: Service name to match
            
        Returns:
            List of extracted metric data points
        """
        results = []
        
        # Look for metric data in various response structures
        if "value" in response and isinstance(response["value"], list):
            for item in response["value"]:
                if isinstance(item, dict):
                    # Check if this item relates to our service
                    extensions = item.get("extensions", {})
                    description = extensions.get("description", "")
                    
                    if description.lower() == service.lower():
                        # Try to extract temperature from this service data
                        temp_value = self._extract_temperature_from_service_data(extensions)
                        if temp_value is not None:
                            results.append(("api_current", temp_value))
        
        return results
    
    def _extract_temperature_from_service_data(self, service_data: Dict) -> Optional[float]:
        """Extract temperature from service data dictionary.
        
        Args:
            service_data: Service data from API response
            
        Returns:
            Temperature value if found
        """
        # Check performance data
        perf_data = service_data.get("perf_data", "")
        if perf_data:
            temp_value = self._extract_temperature_from_perf_data(perf_data)
            if temp_value is not None:
                return temp_value
        
        # Check plugin output
        plugin_output = service_data.get("plugin_output", "")
        if plugin_output:
            temp_value = self._extract_temperature_from_output(plugin_output)
            if temp_value is not None:
                return temp_value
        
        return None
    
    def _approach_alternative_urls(
        self,
        host: str,
        service: str,
        period: str
    ) -> List[Tuple[str, Union[float, str]]]:
        """Approach 3: Try alternative URL patterns for data access.
        
        This tries different URL patterns that might bypass the AJAX issues
        and provide direct access to historical data.
        
        Args:
            host: Target host name
            service: Service name
            period: Time period for historical data
            
        Returns:
            List with data points if found via alternative URLs
        """
        self.logger.debug("Attempting alternative URL strategies")
        
        try:
            # Try different URL patterns
            alternative_urls = [
                # Direct RRD access patterns
                f"/cmk/check_mk/rrd.py?host={host}&service={quote(service)}&from=-{period}",
                
                # Different graph endpoints
                f"/cmk/check_mk/graph.py?host={host}&service={quote(service)}&timerange={period}",
                
                # Metrics endpoints
                f"/cmk/check_mk/metrics.py?host={host}&service={quote(service)}&range={period}",
                
                # Alternative service graph URLs
                f"/cmk/check_mk/view.py?view_name=service_graphs&host={host}&service={quote(service)}",
                
                # Raw data endpoints
                f"/cmk/check_mk/raw_data.py?host={host}&service={quote(service)}&period={period}",
            ]
            
            results = []
            
            for url in alternative_urls:
                try:
                    self.logger.debug(f"Trying alternative URL: {url}")
                    full_url = f"{self.config.server_url}{url}"
                    
                    if not self.session:
                        self.logger.error("Session not initialized for alternative URL approach")
                        continue
                    
                    response = self.session.get(full_url, timeout=30)
                    if response.status_code == 200:
                        # Try to extract data from response
                        data = self._extract_data_from_alternative_response(
                            response.text, response.headers.get('content-type', '')
                        )
                        results.extend(data)
                        
                        if data:
                            self.logger.info(f"Alternative URL {url} found {len(data)} data points")
                    else:
                        self.logger.debug(f"Alternative URL {url} returned status {response.status_code}")
                        
                except Exception as e:
                    self.logger.debug(f"Alternative URL {url} failed: {e}")
                    continue
            
            return results
            
        except Exception as e:
            self.logger.error(f"Alternative URLs approach failed: {e}")
            return []
    
    def _extract_data_from_alternative_response(
        self,
        content: str,
        content_type: str
    ) -> List[Tuple[str, Union[float, str]]]:
        """Extract data from alternative URL responses.
        
        Args:
            content: Response content
            content_type: Content type header
            
        Returns:
            List of extracted data points
        """
        results = []
        
        # Handle JSON responses
        if 'json' in content_type.lower():
            try:
                import json
                data = json.loads(content)
                # Look for time series data in JSON
                results.extend(self._extract_timeseries_from_json(data))
            except json.JSONDecodeError:
                pass
        
        # Handle CSV or plain text responses
        elif 'text' in content_type.lower() or 'csv' in content_type.lower():
            results.extend(self._extract_timeseries_from_text(content))
        
        # Handle HTML responses (like from view.py)
        elif 'html' in content_type.lower():
            soup = self._parse_html_with_fallback(content)
            # Try enhanced HTML parsing
            results.extend(self._enhanced_html_temperature_extraction(soup))
        
        return results
    
    def _extract_timeseries_from_json(self, data: Dict) -> List[Tuple[str, Union[float, str]]]:
        """Extract time series data from JSON response."""
        results = []
        
        # Look for common JSON structures containing time series
        if isinstance(data, dict):
            # Look for arrays of data points
            for key, value in data.items():
                if isinstance(value, list) and len(value) > 0:
                    for item in value:
                        if isinstance(item, (list, tuple)) and len(item) >= 2:
                            # Looks like [timestamp, value] pairs
                            try:
                                timestamp = item[0]
                                temp_value = float(item[1])
                                if self._is_reasonable_temperature(temp_value):
                                    # Convert timestamp if needed
                                    formatted_time = self._format_timestamp(timestamp)
                                    results.append((formatted_time, temp_value))
                            except (ValueError, IndexError):
                                continue
        
        return results
    
    def _extract_timeseries_from_text(self, content: str) -> List[Tuple[str, Union[float, str]]]:
        """Extract time series data from text/CSV response."""
        results = []
        
        lines = content.strip().split('\n')
        for line in lines:
            # Try CSV format: timestamp,value
            if ',' in line:
                parts = line.split(',')
                if len(parts) >= 2:
                    try:
                        timestamp = parts[0].strip()
                        temp_value = float(parts[1].strip())
                        if self._is_reasonable_temperature(temp_value):
                            results.append((timestamp, temp_value))
                    except ValueError:
                        continue
            
            # Try space-separated format: timestamp value
            elif ' ' in line:
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        timestamp = parts[0].strip()
                        temp_value = float(parts[1].strip())
                        if self._is_reasonable_temperature(temp_value):
                            results.append((timestamp, temp_value))
                    except ValueError:
                        continue
        
        return results
    
    def _approach_enhanced_html_parsing(
        self,
        host: str,
        service: str,
        period: str
    ) -> List[Tuple[str, Union[float, str]]]:
        """Approach 4: Enhanced HTML parsing with aggressive data extraction.
        
        This tries more aggressive HTML parsing techniques to find temperature
        data that might be embedded in various ways in the HTML.
        
        Args:
            host: Target host name
            service: Service name
            period: Time period for historical data
            
        Returns:
            List with data points found via enhanced HTML parsing
        """
        self.logger.debug("Attempting enhanced HTML parsing")
        
        try:
            # Get the original page content
            html_content = self.fetch_page(period, host, service)
            soup = self._parse_html_with_fallback(html_content)
            
            # Try various enhanced parsing techniques
            results = []
            
            # 1. Look for hidden form fields with data
            results.extend(self._extract_from_hidden_fields(soup))
            
            # 2. Look for CSS/style attributes with data
            results.extend(self._extract_from_css_data(soup))
            
            # 3. Look for JavaScript variables we might have missed
            results.extend(self._extract_from_js_variables(html_content))
            
            # 4. Look for canvas/SVG data attributes
            results.extend(self._extract_from_canvas_svg(soup))
            
            # 5. Look for any numeric values that could be temperatures
            results.extend(self._enhanced_html_temperature_extraction(soup))
            
            if results:
                self.logger.info(f"Enhanced HTML parsing found {len(results)} data points")
            
            return results
            
        except Exception as e:
            self.logger.error(f"Enhanced HTML parsing approach failed: {e}")
            return []
    
    def _extract_from_hidden_fields(self, soup) -> List[Tuple[str, Union[float, str]]]:
        """Extract data from hidden form fields."""
        results = []
        
        hidden_fields = soup.find_all('input', {'type': 'hidden'})
        for field in hidden_fields:
            value = field.get('value', '')
            if value and self._looks_like_temperature_data(value):
                try:
                    temp_value = float(value)
                    if self._is_reasonable_temperature(temp_value):
                        results.append(("hidden_field", temp_value))
                except ValueError:
                    pass
        
        return results
    
    def _extract_from_css_data(self, soup) -> List[Tuple[str, Union[float, str]]]:
        """Extract data from CSS styles and data attributes."""
        results = []
        
        # Look for elements with data-* attributes
        elements_with_data = soup.find_all(attrs=lambda x: x and any(key.startswith('data-') for key in x.keys()))
        
        for element in elements_with_data:
            for attr_name, attr_value in element.attrs.items():
                if attr_name.startswith('data-') and self._looks_like_temperature_data(str(attr_value)):
                    try:
                        temp_value = float(attr_value)
                        if self._is_reasonable_temperature(temp_value):
                            results.append((f"data_attr_{attr_name}", temp_value))
                    except ValueError:
                        pass
        
        return results
    
    def _extract_from_js_variables(self, html_content: str) -> List[Tuple[str, Union[float, str]]]:
        """Extract data from JavaScript variables with more aggressive parsing."""
        results = []
        
        import re
        
        # Look for variable declarations that might contain temperature data
        js_patterns = [
            r'var\s+(\w*temp\w*)\s*=\s*([0-9.]+)',
            r'let\s+(\w*temp\w*)\s*=\s*([0-9.]+)',
            r'const\s+(\w*temp\w*)\s*=\s*([0-9.]+)',
            r'(\w*temperature\w*)\s*:\s*([0-9.]+)',
            r'(\w*celsius\w*)\s*:\s*([0-9.]+)',
        ]
        
        for pattern in js_patterns:
            matches = re.finditer(pattern, html_content, re.IGNORECASE)
            for match in matches:
                try:
                    var_name = match.group(1)
                    temp_value = float(match.group(2))
                    if self._is_reasonable_temperature(temp_value):
                        results.append((f"js_var_{var_name}", temp_value))
                except (ValueError, IndexError):
                    continue
        
        return results
    
    def _extract_from_canvas_svg(self, soup) -> List[Tuple[str, Union[float, str]]]:
        """Extract data from canvas and SVG elements."""
        results = []
        
        # Look for canvas elements with data attributes
        canvas_elements = soup.find_all('canvas')
        for canvas in canvas_elements:
            for attr_name, attr_value in canvas.attrs.items():
                if self._looks_like_temperature_data(str(attr_value)):
                    try:
                        temp_value = float(attr_value)
                        if self._is_reasonable_temperature(temp_value):
                            results.append((f"canvas_{attr_name}", temp_value))
                    except ValueError:
                        pass
        
        # Look for SVG elements with numeric content
        svg_elements = soup.find_all('svg')
        for svg in svg_elements:
            text_elements = svg.find_all('text')
            for text_elem in text_elements:
                text_content = text_elem.get_text(strip=True)
                if self._looks_like_temperature_data(text_content):
                    try:
                        temp_value = float(text_content)
                        if self._is_reasonable_temperature(temp_value):
                            results.append(("svg_text", temp_value))
                    except ValueError:
                        pass
        
        return results
    
    def _enhanced_html_temperature_extraction(self, soup) -> List[Tuple[str, Union[float, str]]]:
        """Enhanced temperature extraction from HTML content."""
        results = []
        
        # Look for any text content that contains temperature-like patterns
        import re
        
        all_text = soup.get_text()
        
        # Temperature patterns in text
        temp_text_patterns = [
            r'(\d+\.?\d*)\s*°C',
            r'(\d+\.?\d*)\s*degrees',
            r'Temperature:\s*(\d+\.?\d*)',
            r'Temp:\s*(\d+\.?\d*)',
            r'Zone\s*\d*:\s*(\d+\.?\d*)',
        ]
        
        for pattern in temp_text_patterns:
            matches = re.finditer(pattern, all_text, re.IGNORECASE)
            for match in matches:
                try:
                    temp_value = float(match.group(1))
                    if self._is_reasonable_temperature(temp_value):
                        results.append(("html_text", temp_value))
                except (ValueError, IndexError):
                    continue
        
        return results
    
    def _looks_like_temperature_data(self, value_str: str) -> bool:
        """Check if a string value looks like it could contain temperature data."""
        if not value_str:
            return False
        
        # Check if it's a reasonable numeric value
        try:
            value = float(value_str)
            return self._is_reasonable_temperature(value)
        except ValueError:
            # Check if it contains temperature-related keywords
            temp_keywords = ['temp', 'temperature', 'celsius', 'degree', '°c']
            value_lower = value_str.lower()
            return any(keyword in value_lower for keyword in temp_keywords)
    
    def _deduplicate_results(
        self,
        results: List[Tuple[str, Union[float, str]]]
    ) -> List[Tuple[str, Union[float, str]]]:
        """Remove duplicate results while preserving order."""
        seen = set()
        unique_results = []
        
        for timestamp, value in results:
            # Create a key for deduplication
            key = (timestamp, value)
            if key not in seen:
                seen.add(key)
                unique_results.append((timestamp, value))
        
        return unique_results
    
    def _format_timestamp(self, timestamp: Union[str, int, float]) -> str:
        """Format various timestamp formats to a standard string."""
        if isinstance(timestamp, str):
            return timestamp
        
        try:
            # Try to convert Unix timestamp to ISO format
            if isinstance(timestamp, (int, float)):
                from datetime import datetime
                dt = datetime.fromtimestamp(timestamp)
                return dt.isoformat()
        except (ValueError, OSError):
            pass
        
        return str(timestamp)


# CLI Interface
@click.command()
@click.option(
    "--period",
    default="4h",
    help="Time period for historical data (4h, 25h, 8d, etc.)",
    show_default=True
)
@click.option(
    "--host",
    default="piaware",
    help="Target host name",
    show_default=True
)
@click.option(
    "--service",
    default="Temperature Zone 0",
    help="Service name",
    show_default=True
)
@click.option(
    "--config",
    "--config-file",
    help="Path to configuration file (YAML, TOML, or JSON)"
)
@click.option(
    "--debug",
    is_flag=True,
    help="Enable debug logging"
)
@click.option(
    "--log-level",
    default="INFO",
    help="Logging level (DEBUG, INFO, WARNING, ERROR)",
    show_default=True
)
def main(
    period: str,
    host: str,
    service: str,
    config: Optional[str],
    debug: bool,
    log_level: str
):
    """Checkmk Historical Data Scraper
    
    Scrapes historical temperature data from Checkmk monitoring pages.
    Extracts both time-series data from graphs and summary statistics from tables.
    
    Examples:
    
        # Basic usage with default 4 hours
        python checkmk_scraper.py
        
        # Specific time period
        python checkmk_scraper.py --period 25h
        
        # Different host and service
        python checkmk_scraper.py --host server01 --service "CPU Temperature"
        
        # With debug logging
        python checkmk_scraper.py --debug
        
        # Custom config file
        python checkmk_scraper.py --config /path/to/config.yaml
    """
    # Generate request ID for tracing
    request_id = generate_request_id()
    set_request_id(request_id)
    
    # Determine effective log level
    if debug:
        effective_log_level = "DEBUG"
    else:
        effective_log_level = log_level.upper()
    
    # Setup logging with request ID support
    setup_logging(effective_log_level, include_request_id=True)
    logger = get_logger_with_request_id(__name__)
    
    logger.info(f"Starting Checkmk Historical Data Scraper (Request: {request_id})")
    logger.debug(f"Parameters: period={period}, host={host}, service={service}")
    
    try:
        # Load configuration
        logger.debug("Loading configuration...")
        app_config = load_config(config_file=config)
        logger.debug(f"Configuration loaded successfully from: {config or 'auto-discovered'}")
        
        # Validate Checkmk configuration
        if not app_config.checkmk.server_url:
            raise ScrapingError("Checkmk server URL not configured")
        if not app_config.checkmk.username:
            raise ScrapingError("Checkmk username not configured")
        if not app_config.checkmk.password:
            raise ScrapingError("Checkmk password not configured")
        if not app_config.checkmk.site:
            raise ScrapingError("Checkmk site not configured")
        
        logger.debug(f"Using Checkmk server: {app_config.checkmk.server_url}")
        logger.debug(f"Using site: {app_config.checkmk.site}")
        
        # Initialize scraper
        scraper = CheckmkHistoricalScraper(app_config.checkmk)
        
        # Perform scraping
        logger.info(f"Scraping historical data for {host}/{service} (period: {period})")
        data = scraper.scrape_historical_data(period, host, service)
        
        # Output results
        if data:
            logger.info(f"Successfully extracted {len(data)} data points")
            click.echo("\n=== Historical Data ===")
            for timestamp, value in data:
                click.echo(f"{timestamp}: {value}")
        else:
            logger.warning("No data extracted - this is expected in Phase 3")
            click.echo("No data extracted (Phase 3 - parsing infrastructure complete, data extraction in Phase 4-5)")
        
        logger.info("Scraping completed successfully")
        
    except ScrapingError as e:
        logger.error(f"Scraping error: {e}")
        click.echo(f"❌ Scraping Error: {e}", err=True)
        sys.exit(1)
        
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        click.echo(f"❌ Unexpected Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()