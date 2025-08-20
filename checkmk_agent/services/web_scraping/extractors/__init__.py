"""
Data Extractors Package

This package contains specialized data extraction classes for different
types of content from Checkmk monitoring interfaces.

Components:
- GraphExtractor: Extract time-series data from graphs and JavaScript
- TableExtractor: Extract statistical data from HTML tables  
- AjaxExtractor: Handle AJAX endpoint data extraction
"""

# Package exports - will be populated as components are implemented
__all__ = [
    'GraphExtractor',  # Phase 1 placeholder created
    'TableExtractor',  # Phase 1 placeholder created
    'AjaxExtractor',   # Phase 1 placeholder created
]

# Import placeholder classes for basic validation
from .graph_extractor import GraphExtractor
from .table_extractor import TableExtractor  
from .ajax_extractor import AjaxExtractor