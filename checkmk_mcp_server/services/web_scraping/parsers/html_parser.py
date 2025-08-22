"""
HTML Parser Manager

This module provides HTML parsing with fallback detection and validation
for robust web scraping operations.
"""

from typing import Optional, List, Dict, Any
import logging
from bs4 import BeautifulSoup, Tag

from .. import ScrapingError


class HtmlParser:
    """HTML parsing manager with fallback detection and validation.
    
    This class handles robust HTML parsing with multiple parser fallbacks
    and comprehensive content validation for reliable data extraction.
    """
    
    def __init__(self):
        """Initialize HTML parser with available parsers."""
        self.available_parsers = self._detect_available_parsers()
        self.logger = logging.getLogger(__name__)
    
    def parse_html(
        self,
        content: str,
        parser: Optional[str] = None
    ) -> BeautifulSoup:
        """Main parsing method with fallback detection.
        
        Args:
            content: HTML content to parse
            parser: Specific parser to use (optional)
            
        Returns:
            BeautifulSoup parsed document
            
        Raises:
            ScrapingError: If parsing fails with all available parsers
        """
        if parser:
            # Use specific parser if requested
            try:
                self.logger.debug(f"Parsing HTML with requested parser: {parser}")
                soup = BeautifulSoup(content, parser)
                if soup and soup.find():
                    return soup
                else:
                    raise ScrapingError(f"Parser {parser} returned empty result")
            except Exception as e:
                raise ScrapingError(f"Requested parser {parser} failed: {e}")
        else:
            # Use fallback parsing
            return self._parse_html_with_fallback(content)
    
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
    
    def _validate_content(
        self, 
        soup: BeautifulSoup, 
        host: Optional[str] = None, 
        service: Optional[str] = None
    ) -> bool:
        """Validate parsed HTML content structure.
        
        Args:
            soup: Parsed BeautifulSoup document
            host: Expected host name (optional)
            service: Expected service name (optional)
            
        Returns:
            True if content appears valid, False otherwise
        """
        if not soup or not soup.find():
            return False
            
        # Basic validation - check for essential HTML structure
        validation_checks = {
            "has_title": bool(soup.find("title")),
            "has_body": bool(soup.find("body")),
            "has_scripts": bool(soup.find_all("script")),
            "has_checkmk_elements": self._has_checkmk_elements(soup)
        }
        
        # Add host/service specific validation if provided
        if host:
            validation_checks["has_host_reference"] = self._contains_host_reference(soup, host)
        if service:
            validation_checks["has_service_reference"] = self._contains_service_reference(soup, service)
            
        # Require at least 60% of checks to pass
        passed_checks = sum(validation_checks.values())
        total_checks = len(validation_checks)
        
        self.logger.debug(f"Content validation: {passed_checks}/{total_checks} checks passed")
        return passed_checks >= (total_checks * 0.6)
    
    def _extract_page_metadata(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract page structure information for debugging.
        
        Args:
            soup: Parsed BeautifulSoup document
            
        Returns:
            Dictionary containing page metadata
        """
        if not soup:
            return {"error": "No parsed content available"}
            
        metadata = {
            "title": soup.find("title").get_text(strip=True) if soup.find("title") else None,
            "script_count": len(soup.find_all("script")),
            "table_count": len(soup.find_all("table")),
            "div_count": len(soup.find_all("div")),
            "form_count": len(soup.find_all("form")),
            "has_graphs": self._has_potential_graphs(soup),
            "has_tables": self._has_potential_tables(soup),
            "has_checkmk_elements": self._has_checkmk_elements(soup)
        }
        
        return metadata
    
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
    
    def _has_potential_graphs(self, soup: BeautifulSoup) -> bool:
        """Check if the page contains potential graph elements."""
        graph_indicators = [
            soup.find_all("canvas"),
            soup.find_all("svg"),
            soup.find_all(attrs={"class": lambda x: x and "graph" in x.lower() if x else False}),
            soup.find_all(attrs={"id": lambda x: x and "graph" in x.lower() if x else False}),
            soup.find_all("script", string=lambda text: text and "graph" in text.lower() if text else False)
        ]
        return any(len(indicator) > 0 for indicator in graph_indicators)
    
    def _has_potential_tables(self, soup: BeautifulSoup) -> bool:
        """Check if the page contains potential data tables."""
        return len(soup.find_all("table")) > 0
    
    def _has_checkmk_elements(self, soup: BeautifulSoup) -> bool:
        """Check if the page contains Checkmk-specific elements."""
        checkmk_patterns = [
            soup.find_all(attrs={"class": lambda x: x and "checkmk" in x.lower() if x else False}),
            soup.find_all(attrs={"class": lambda x: x and "cmk" in x.lower() if x else False}),
            soup.find_all(attrs={"id": lambda x: x and "checkmk" in x.lower() if x else False}),
            soup.find_all(attrs={"id": lambda x: x and "cmk" in x.lower() if x else False}),
            soup.find_all("a", href=lambda x: x and "check_mk" in x if x else False),
            soup.find_all(string=lambda text: text and "checkmk" in text.lower() if text else False)
        ]
        return any(len(pattern) > 0 for pattern in checkmk_patterns)
    
    def _contains_host_reference(self, soup: BeautifulSoup, host: str) -> bool:
        """Check if the page contains references to the specified host."""
        host_lower = host.lower()
        
        # Check in various locations where host name might appear
        checks = [
            # Text content
            soup.find(string=lambda text: text and host_lower in text.lower() if text else False),
            # Links
            soup.find("a", string=lambda text: text and host_lower in text.lower() if text else False),
            # Form inputs
            soup.find("input", attrs={"value": lambda x: x and host_lower in x.lower() if x else False}),
            # URL parameters
            soup.find("a", href=lambda x: x and host_lower in x.lower() if x else False)
        ]
        
        return any(check is not None for check in checks)
    
    def _contains_service_reference(self, soup: BeautifulSoup, service: str) -> bool:
        """Check if the page contains references to the specified service."""
        service_lower = service.lower()
        
        # Check in various locations where service name might appear
        checks = [
            # Text content
            soup.find(string=lambda text: text and service_lower in text.lower() if text else False),
            # Links
            soup.find("a", string=lambda text: text and service_lower in text.lower() if text else False),
            # Form inputs  
            soup.find("input", attrs={"value": lambda x: x and service_lower in x.lower() if x else False}),
            # URL parameters
            soup.find("a", href=lambda x: x and service_lower in x.lower() if x else False)
        ]
        
        return any(check is not None for check in checks)