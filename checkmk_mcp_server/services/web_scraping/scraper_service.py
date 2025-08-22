"""
Main Scraper Service

This module provides the main coordination service for orchestrating all scraping operations.
Serves as the entry point for historical data extraction with dependency injection.
"""

from typing import Dict, Any, Optional, List, Tuple, Union
import logging
import urllib.parse

from ...config import CheckmkConfig
from . import ScrapingError
from .auth_handler import AuthHandler
from .parsers.html_parser import HtmlParser
from .factory import ScraperFactory


class ScraperService:
    """Main coordination service orchestrating all scraping operations.
    
    This service handles the overall workflow of scraping historical data,
    coordinating between authentication, parsing, and extraction components.
    """
    
    def __init__(self, config: CheckmkConfig):
        """Initialize the scraper service with configuration.
        
        Args:
            config: CheckmkConfig object containing server details and authentication
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Initialize core components
        self.auth_handler = AuthHandler(config)
        self.html_parser = HtmlParser()
        self.factory = ScraperFactory()
        
        # Will be set by auth_handler
        self.session = None
    
    def scrape_historical_data(
        self,
        period: str = "4h",
        host: str = None,
        service: str = None,
        extraction_method: str = "auto"
    ) -> List[Tuple[str, Union[float, str]]]:
        """Main entry point for scraping historical data.
        
        This method coordinates the entire scraping workflow including authentication,
        HTML parsing, data extraction, and result processing.
        
        Args:
            period: Time period for data extraction (default: "4h")
            host: Host name to scrape data for
            service: Service name to scrape data for
            extraction_method: Extraction strategy ("auto", "graph", "table", "ajax")
            
        Returns:
            List of tuples containing (timestamp, value) pairs for historical data points
            
        Raises:
            ScrapingError: If scraping operation fails
        """
        self.logger.debug(f"Starting historical data scrape for {host}/{service}, period: {period}")
        
        try:
            # Step 1: Validate parameters
            if host is None or service is None:
                raise ScrapingError("Both host and service parameters are required")
            self._validate_parameters(host, service, period)
            
            # Step 2: Authenticate if needed
            if not self.session or not self.auth_handler.validate_session():
                self.logger.debug("Authenticating session")
                self.session = self.auth_handler.authenticate_session()
            
            # Step 3: Fetch the monitoring page
            html_content = self._fetch_page(period, host, service)
            
            # Step 4: Parse and validate HTML structure
            self.logger.debug("Parsing and validating HTML structure")
            soup = self.html_parser.parse_html(html_content)
            
            # Validate page structure
            if not self.html_parser._validate_content(soup, host, service):
                self.logger.warning("Page structure validation failed - may not be the expected monitoring page")
                # Log metadata for troubleshooting
                metadata = self.html_parser._extract_page_metadata(soup)
                self.logger.debug(f"Page metadata: {metadata}")
            else:
                self.logger.debug("Page structure validation passed")
            
            # Step 5: Select and execute extraction method
            method = self._select_extraction_method(extraction_method)
            extractors = self.factory.create_extractors(method, self.session, self.config)
            
            combined_data = []
            method_used = None
            
            # Try selected extraction methods in order
            for extractor_name, extractor in extractors.items():
                try:
                    self.logger.debug(f"Trying {extractor_name} extraction method")
                    if extractor_name == "graph":
                        data = self._extract_graph_data(extractor, soup, period)
                    elif extractor_name == "table":
                        data = self._extract_table_data(extractor, soup)
                    elif extractor_name == "ajax":
                        data = self._extract_ajax_data(extractor, host, service, period)
                    else:
                        continue
                    
                    if data:
                        combined_data.extend(data)
                        method_used = extractor_name
                        self.logger.debug(f"{extractor_name} extraction successful: {len(data)} data points")
                    
                except Exception as e:
                    self.logger.warning(f"{extractor_name} extraction failed: {e}")
                    continue
            
            # Step 6: Process and validate results
            if not combined_data:
                raise ScrapingError(
                    f"All extraction methods failed for {host}/{service}",
                    response_data={"extraction_method": extraction_method, "methods_tried": list(extractors.keys())}
                )
            
            processed_data = self._process_results(combined_data)
            
            self.logger.debug(f"Scraping completed successfully: {len(processed_data)} data points")
            # Return list of tuples as expected by historical service
            return [(item["timestamp"], item["value"]) for item in processed_data]
            
        except Exception as e:
            if isinstance(e, ScrapingError):
                raise
            else:
                error_msg = f"Scraping failed for {host}/{service}: {e}"
                self.logger.error(error_msg)
                raise ScrapingError(
                    error_msg,
                    response_data={"host": host, "service": service, "period": period, "error": str(e)}
                )
    
    def _validate_parameters(self, host: str, service: str, period: str) -> None:
        """Validate input parameters for scraping operation.
        
        Args:
            host: Host name to validate
            service: Service name to validate  
            period: Time period to validate
            
        Raises:
            ScrapingError: If parameters are invalid
        """
        if not host or not host.strip():
            raise ScrapingError("Host name cannot be empty")
        
        if not service or not service.strip():
            raise ScrapingError("Service name cannot be empty")
        
        # Validate period format
        valid_periods = ["4h", "25h", "8d", "35d", "400d", "1h", "6h", "12h", "24h", "48h", "7d", "30d", "365d"]
        if period not in valid_periods:
            raise ScrapingError(
                f"Invalid period '{period}'. Valid periods: {valid_periods}",
                response_data={"valid_periods": valid_periods}
            )
    
    def _select_extraction_method(self, method: str) -> str:
        """Choose appropriate extractor based on method preference.
        
        Args:
            method: Requested extraction method
            
        Returns:
            Selected extraction method with priorities
        """
        if method == "auto":
            # Auto mode tries methods in order of reliability
            return "auto"  # Factory will handle the priority order
        elif method in ["graph", "table", "ajax"]:
            return method
        else:
            self.logger.warning(f"Unknown extraction method '{method}', falling back to 'auto'")
            return "auto"
    
    def _process_results(self, raw_data: List[Tuple[str, Union[float, str]]]) -> List[Dict[str, Any]]:
        """Post-process and validate extracted results.
        
        Args:
            raw_data: Raw extracted data from extractors as tuples
            
        Returns:
            Processed and validated data as structured dictionaries
        """
        processed_data = []
        
        for item in raw_data:
            if not isinstance(item, (tuple, list)) or len(item) != 2:
                self.logger.warning(f"Skipping invalid data item: {item}")
                continue
                
            timestamp, value = item
            
            # Create structured data point
            data_point = {
                "timestamp": timestamp,
                "value": value,
                "type": "timeseries" if self._is_timestamp(timestamp) else "summary"
            }
            
            processed_data.append(data_point)
        
        # Sort time-series data by timestamp
        timeseries_data = [dp for dp in processed_data if dp["type"] == "timeseries"]
        summary_data = [dp for dp in processed_data if dp["type"] == "summary"]
        
        # Sort timeseries by timestamp if possible
        try:
            timeseries_data.sort(key=lambda x: x["timestamp"])
        except (TypeError, ValueError) as e:
            self.logger.debug(f"Could not sort timeseries data: {e}")
        
        # Combine sorted timeseries first, then summary
        return timeseries_data + summary_data
    
    def _fetch_page(self, period: str, host: str, service: str) -> str:
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
            raise ScrapingError("No authenticated session available")
        
        # URL encode the service name properly
        encoded_service = urllib.parse.quote_plus(service)
        
        # Map time periods to Checkmk's expected format
        time_range_mapping = {
            "4h": "4h",      # Last 4 hours
            "25h": "25h",    # Last 25 hours
            "8d": "8d",      # Last 8 days
            "35d": "35d",    # Last 35 days
            "400d": "400d",  # Last 400 days
            "1h": "1h",      # Last 1 hour
            "6h": "6h",      # Last 6 hours
            "12h": "12h",    # Last 12 hours
            "24h": "24h",    # Last 24 hours
            "48h": "48h",    # Last 48 hours
            "7d": "7d",      # Last 7 days
            "30d": "30d",    # Last 30 days
            "365d": "365d"   # Last 365 days
        }
        
        time_range = time_range_mapping.get(period, period)
        
        # Construct monitoring page URL
        url = (f"{self.config.server_url}/{self.config.site}/check_mk/"
               f"view.py?view_name=service&site={self.config.site}&"
               f"host={urllib.parse.quote_plus(host)}&service={encoded_service}&"
               f"graph_range={time_range}")
        
        self.logger.debug(f"Fetching monitoring page: {url}")
        
        try:
            response = self.session.get(url, timeout=30, allow_redirects=True)
            
            if response.status_code == 200:
                self.logger.debug(f"Successfully fetched page ({len(response.text)} characters)")
                return response.text
            else:
                error_msg = f"HTTP {response.status_code} when fetching monitoring page"
                self.logger.error(error_msg)
                raise ScrapingError(
                    error_msg,
                    url=url,
                    status_code=response.status_code,
                    html_snippet=response.text[:500] if response.text else None
                )
                
        except Exception as e:
            if isinstance(e, ScrapingError):
                raise
            else:
                error_msg = f"Failed to fetch monitoring page: {e}"
                self.logger.error(error_msg)
                raise ScrapingError(
                    error_msg,
                    url=url,
                    response_data={"error": str(e)}
                )
    
    def _extract_graph_data(self, extractor, soup, period: str) -> List[Tuple[str, Union[float, str]]]:
        """Extract data using graph extractor."""
        try:
            # Get the HTML content from the soup
            html_content = str(soup)
            return extractor.extract_graph_data(html_content, period)
        except Exception as e:
            self.logger.debug(f"Graph extraction failed: {e}")
            return []
    
    def _extract_table_data(self, extractor, soup) -> List[Tuple[str, Union[float, str]]]:
        """Extract data using table extractor."""
        try:
            # Get the HTML content from the soup
            html_content = str(soup)
            return extractor.extract_table_data(html_content)
        except Exception as e:
            self.logger.debug(f"Table extraction failed: {e}")
            return []
    
    def _extract_ajax_data(self, extractor, host: str, service: str, period: str) -> List[Tuple[str, Union[float, str]]]:
        """Extract data using AJAX extractor."""
        try:
            return extractor.extract_ajax_data(host, service, period, self.config.server_url, self.config.site)
        except Exception as e:
            self.logger.debug(f"AJAX extraction failed: {e}")
            return []
    
    def _is_timestamp(self, value: str) -> bool:
        """Check if a value looks like a timestamp."""
        if not isinstance(value, str):
            return False
        
        # Check for common timestamp patterns
        timestamp_patterns = [
            # ISO format: 2025-08-20T10:30:00
            r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}',
            # Unix timestamp: 1692531000
            r'^\d{10}$',
            # Date only: 2025-08-20
            r'^\d{4}-\d{2}-\d{2}$',
            # Time only: 10:30:00
            r'^\d{2}:\d{2}:\d{2}$'
        ]
        
        import re
        return any(re.match(pattern, value) for pattern in timestamp_patterns)