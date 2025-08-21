"""
Scraper Factory

This module implements the factory pattern for creating specialized scrapers
based on requirements and extraction strategies.
"""

from typing import Dict, Any, Optional, TYPE_CHECKING
import requests

from ...config import CheckmkConfig
from .extractors.graph_extractor import GraphExtractor
from .extractors.table_extractor import TableExtractor
from .extractors.ajax_extractor import AjaxExtractor

if TYPE_CHECKING:
    from .scraper_service import ScraperService


class ScraperFactory:
    """Factory pattern for creating specialized extractors and scrapers.
    
    This factory creates appropriately configured extractor instances
    based on extraction requirements and available capabilities.
    """
    
    @staticmethod
    def create_scraper(
        config: CheckmkConfig,
        extraction_method: str = "auto",
        **kwargs
    ) -> 'ScraperService':
        """Main factory method for creating scraper instances.
        
        Args:
            config: CheckmkConfig object for scraper configuration
            extraction_method: Preferred extraction strategy
            **kwargs: Additional configuration options
            
            Returns:
            Configured ScraperService instance
            
        Raises:
            ValueError: If configuration is invalid
        """
        # Avoid circular import by importing here
        from .scraper_service import ScraperService
        
        if not ScraperFactory._validate_requirements(config):
            raise ValueError("Configuration validation failed")
        
        scraper = ScraperService(config)
        return scraper
    
    @staticmethod
    def create_extractors(
        extraction_method: str = "auto",
        session: Optional[requests.Session] = None,
        config: Optional[CheckmkConfig] = None
    ) -> Dict[str, Any]:
        """Create extractor instances based on extraction method.
        
        Args:
            extraction_method: Preferred extraction strategy
            session: Optional authenticated session for extractors
            config: Optional configuration for extractors
            
        Returns:
            Dictionary of configured extractor instances
        """
        extractors = {}
        
        if extraction_method == "auto":
            # Auto mode includes all extractors in priority order
            # Graph extractor has the most sophisticated implementation for time-series data
            extractors["graph"] = GraphExtractor(session, config)
            extractors["ajax"] = AjaxExtractor(session)
            extractors["table"] = TableExtractor()
        elif extraction_method == "graph":
            extractors["graph"] = GraphExtractor(session, config)
        elif extraction_method == "table":
            extractors["table"] = TableExtractor()
        elif extraction_method == "ajax":
            extractors["ajax"] = AjaxExtractor(session)
        else:
            # Unknown method, default to all with proper priority order
            extractors["graph"] = GraphExtractor(session, config)
            extractors["ajax"] = AjaxExtractor(session)
            extractors["table"] = TableExtractor()
        
        return extractors
    
    @staticmethod
    def _determine_extraction_strategy(
        method: str,
        capabilities: Optional[Dict[str, Any]] = None
    ) -> str:
        """Choose extraction approach based on method and capabilities.
        
        Args:
            method: Requested extraction method
            capabilities: Available extraction capabilities
            
        Returns:
            Selected extraction strategy
        """
        if method == "auto":
            # Determine best strategy based on capabilities
            if capabilities and capabilities.get("ajax_available", True):
                return "ajax"  # Prefer AJAX for reliability
            elif capabilities and capabilities.get("graph_data_available", True):
                return "graph"
            else:
                return "table"  # Fallback to table extraction
        
        # Validate requested method
        valid_methods = ["graph", "table", "ajax", "auto"]
        if method not in valid_methods:
            return "auto"  # Fallback for invalid methods
        
        return method
    
    @staticmethod
    def _configure_extractors(strategy: str) -> Dict[str, Any]:
        """Configure extractor instances based on strategy.
        
        Args:
            strategy: Selected extraction strategy
            
        Returns:
            Configuration dictionary for extractors
        """
        config = {
            "timeout": 30,
            "retry_attempts": 3,
            "fallback_enabled": True
        }
        
        # Strategy-specific configuration
        if strategy == "ajax":
            config.update({
                "ajax_timeout": 15,
                "max_data_points": 1000
            })
        elif strategy == "graph":
            config.update({
                "javascript_timeout": 10,
                "regex_fallback": True
            })
        elif strategy == "table":
            config.update({
                "table_validation": True,
                "statistics_only": False
            })
        
        return config
    
    @staticmethod
    def _validate_requirements(config: CheckmkConfig) -> bool:
        """Validate dependencies and requirements.
        
        Args:
            config: Configuration to validate
            
        Returns:
            True if requirements are met, False otherwise
        """
        # Validate essential configuration fields
        if not config.server_url or not config.server_url.strip():
            return False
        
        if not config.site or not config.site.strip():
            return False
        
        # Validate authentication credentials
        if not (config.username and config.password):
            return False
        
        # Validate URL format
        try:
            from urllib.parse import urlparse
            parsed = urlparse(config.server_url)
            if not parsed.scheme or not parsed.netloc:
                return False
        except Exception:
            return False
        
        return True