"""
Web Scraping Service Package

This package provides modular web scraping capabilities for extracting historical
data from Checkmk monitoring interfaces using a modular, maintainable service-oriented architecture.

Components:
- ScrapingError: Custom exception for web scraping errors with context
- ScraperService: Main coordination service for orchestrating scraping operations
- AuthHandler: Authentication and session management
- Factory: Factory pattern for creating specialized scrapers
- Parsers: HTML parsing with fallback detection
- Extractors: Specialized data extraction (graph, table, AJAX)
"""

from typing import Optional, Dict, Any


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


# Package exports - will be populated as components are implemented
__all__ = [
    'ScrapingError',
    'ScraperService',      # Phase 1 placeholder created
    'AuthHandler',         # Phase 1 placeholder created
    'ScraperFactory',      # Phase 1 placeholder created
]

# Import Phase 1 placeholder classes for validation
from .scraper_service import ScraperService
from .auth_handler import AuthHandler
from .factory import ScraperFactory