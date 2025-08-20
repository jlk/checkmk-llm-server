"""
Authentication Handler

This module handles Checkmk authentication and session management for web scraping operations.
"""

from typing import Optional, Dict, Any
import requests
import logging
from requests.cookies import RequestsCookieJar

from ...config import CheckmkConfig
from ...api_client import CheckmkClient
from . import ScrapingError


class AuthHandler:
    """Handle Checkmk authentication and session management.
    
    This class manages the authentication flow and maintains sessions
    for scraping operations on Checkmk web interfaces.
    """
    
    def __init__(self, config: CheckmkConfig):
        """Initialize the authentication handler with configuration.
        
        Args:
            config: CheckmkConfig object containing server details and authentication
        """
        self.config = config
        self.session: Optional[requests.Session] = None
        self.checkmk_client: Optional[CheckmkClient] = None
        self.logger = logging.getLogger(__name__)
    
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
            self._test_web_interface_access()
            
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
    
    def validate_session(self) -> bool:
        """Check if current session is valid.
        
        Returns:
            True if session is valid, False otherwise
        """
        if not self.session or not self.checkmk_client:
            return False
            
        try:
            # Test session validity with a lightweight API call
            version_info = self.checkmk_client.get_version_info()
            return isinstance(version_info, dict) and len(version_info) > 0
        except Exception as e:
            self.logger.debug(f"Session validation failed: {e}")
            return False
    
    def refresh_session(self) -> requests.Session:
        """Refresh expired session.
        
        Returns:
            Refreshed authenticated session
            
        Raises:
            ScrapingError: If session refresh fails
        """
        self.logger.debug("Refreshing expired session")
        
        # Clean up old session
        self.session = None
        self.checkmk_client = None
        
        # Create new authenticated session
        return self.authenticate_session()
    
    def _test_web_interface_access(self) -> None:
        """Test web interface access to ensure session works for scraping.
        
        Raises:
            ScrapingError: If web interface is not accessible
        """
        if not self.session:
            raise ScrapingError("No session available for web interface test")
            
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
    
    def _handle_login_flow(self) -> None:
        """Process login forms and authentication.
        
        Note: Currently using CheckmkClient which handles authentication via API tokens.
        This method is reserved for future form-based authentication if needed.
        
        Raises:
            ScrapingError: If login process fails
        """
        # Current implementation uses API token authentication via CheckmkClient
        # Form-based login can be implemented here if needed in the future
        pass