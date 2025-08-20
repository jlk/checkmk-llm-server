"""
Table Data Extractor

This module extracts statistical data from HTML tables
for historical monitoring information.
"""

import re
import logging
from typing import Dict, Any, List, Optional, Tuple, Union
from collections import Counter

try:
    from bs4 import BeautifulSoup, Tag
    import lxml  # noqa: F401 - Only used for parser detection
    HAS_LXML = True
except ImportError:
    from bs4 import BeautifulSoup, Tag
    HAS_LXML = False

from .. import ScrapingError


class TableExtractor:
    """Extract statistical data from HTML tables.
    
    This class handles identification and extraction of statistical data
    from various table formats in Checkmk monitoring interfaces.
    """
    
    def __init__(self, logger=None):
        """Initialize table extractor.
        
        Args:
            logger: Logger instance for debugging
        """
        self.logger = logger or logging.getLogger(__name__)
    
    def extract_table_data(
        self,
        html_content: str,
        table_type: str = "statistics"
    ) -> List[Tuple[str, Union[float, str]]]:
        """Main table extraction method.
        
        Extracts summary statistics from HTML tables using Phase 5 implementation.
        Extracts Min, Max, Average, Last values from temperature monitoring tables.
        
        Args:
            html_content: Raw HTML content from the monitoring page
            table_type: Type of table data to extract (default: "statistics")
            
        Returns:
            List of (statistic_name, value) tuples (min, max, average, last)
            
        Raises:
            ScrapingError: If parsing fails
        """
        self.logger.debug("Starting table data extraction")
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
            
            self.logger.info(f"Table extraction complete: Extracted {len(final_stats)} temperature statistics")
            for stat_name, value in final_stats:
                self.logger.info(f"  {stat_name}: {value}°C")
            
            return final_stats
            
        except Exception as e:
            error_msg = f"Failed to parse table data: {e}"
            self.logger.error(error_msg)
            raise ScrapingError(
                error_msg,
                html_snippet=html_content[:500] if html_content else None,
                response_data={"error": str(e)}
            )

    def find_data_tables(self, soup: BeautifulSoup) -> List[Tag]:
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
            if not isinstance(table, Tag):
                continue
                
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

    def _extract_statistics_from_table(self, table: Tag, table_num: int) -> List[Tuple[str, float]]:
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
        
        # Strategy 3: Position-based parsing (common layouts)
        position_stats = self._parse_table_by_position(table, table_num)
        stats.extend(position_stats)
        
        # Strategy 4: Keyword proximity parsing
        proximity_stats = self._parse_table_keyword_proximity(table, table_num)
        stats.extend(proximity_stats)
        
        self.logger.debug(f"Table {table_num} extracted {len(stats)} statistics")
        
        return stats

    def _parse_table_with_headers(self, table: Tag, table_num: int) -> List[Tuple[str, float]]:
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

    def _parse_table_cell_content(self, table: Tag, table_num: int) -> List[Tuple[str, float]]:
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

    def _parse_table_by_position(self, table: Tag, table_num: int) -> List[Tuple[str, float]]:
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

    def _parse_table_keyword_proximity(self, table: Tag, table_num: int) -> List[Tuple[str, float]]:
        """Parse table by finding numeric values near statistic keywords.
        
        Args:
            table: BeautifulSoup table element
            table_num: Table number for logging
            
        Returns:
            List of (statistic_name, value) tuples
        """
        stats = []
        
        try:
            rows = table.find_all('tr')
            
            for row in rows:
                row_text = row.get_text().lower()
                cells = row.find_all(['td', 'th'])
                
                # Look for statistic keywords in the row
                stat_keywords = {
                    'min': ['min', 'minimum'],
                    'max': ['max', 'maximum'],
                    'average': ['avg', 'average', 'mean'],
                    'last': ['last', 'current', 'latest']
                }
                
                for stat_name, keywords in stat_keywords.items():
                    if any(keyword in row_text for keyword in keywords):
                        # Found a keyword, now look for nearby numeric values
                        for cell in cells:
                            value = self._extract_numeric_value(cell.get_text().strip())
                            if value is not None and self._is_reasonable_temperature(value):
                                stats.append((stat_name, value))
                                self.logger.debug(f"Table {table_num} proximity parsing: {stat_name} = {value}")
                                break  # Only take the first valid value for this statistic
                        
        except Exception as e:
            self.logger.debug(f"Table {table_num} proximity parsing failed: {e}")
            
        return stats

    def _consolidate_statistics(self, stats_list: List[Tuple[str, float]]) -> List[Tuple[str, Union[float, str]]]:
        """Remove duplicates and prioritize most reliable values.
        
        Args:
            stats_list: Raw list of (statistic_name, value) tuples
            
        Returns:
            Consolidated list of unique statistics
        """
        if not stats_list:
            return []
        
        # Group statistics by name
        stats_by_name = {}
        for stat_name, value in stats_list:
            if stat_name not in stats_by_name:
                stats_by_name[stat_name] = []
            stats_by_name[stat_name].append(value)
        
        # For each statistic, choose the most common value (mode)
        final_stats = []
        for stat_name, values in stats_by_name.items():
            if len(values) == 1:
                final_stats.append((stat_name, values[0]))
            else:
                # Use Counter to find the most common value
                value_counts = Counter(values)
                most_common_value = value_counts.most_common(1)[0][0]
                final_stats.append((stat_name, most_common_value))
                self.logger.debug(f"Consolidated {stat_name}: chose {most_common_value} from {values}")
        
        # Sort for consistent output
        final_stats.sort(key=lambda x: x[0])
        
        return final_stats

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

    def _identify_statistic_name(self, header_text: str) -> Optional[str]:
        """Identify statistic name from header text.
        
        Args:
            header_text: Text content of table header
            
        Returns:
            Normalized statistic name or None if not recognized
        """
        header_lower = header_text.lower().strip()
        
        if any(word in header_lower for word in ['min', 'minimum']):
            return 'min'
        elif any(word in header_lower for word in ['max', 'maximum']):
            return 'max'
        elif any(word in header_lower for word in ['avg', 'average', 'mean']):
            return 'average'
        elif any(word in header_lower for word in ['last', 'current', 'latest']):
            return 'last'
        
        return None

    def _normalize_statistic_name(self, stat_type: str) -> Optional[str]:
        """Normalize statistic type to standard name.
        
        Args:
            stat_type: Raw statistic type string
            
        Returns:
            Normalized statistic name
        """
        stat_lower = stat_type.lower()
        
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
        """Extract numeric value from text string.
        
        Args:
            text: Text that may contain a numeric value
            
        Returns:
            Extracted float value or None if not found/invalid
        """
        try:
            # Remove common non-numeric characters
            cleaned_text = re.sub(r'[°CFcf\s]', '', text.strip())
            
            # Extract first number found
            number_match = re.search(r'\d+\.?\d*', cleaned_text)
            if number_match:
                value = float(number_match.group())
                return value
                
        except (ValueError, AttributeError):
            pass
        
        return None

    def _is_reasonable_temperature(self, value: float) -> bool:
        """Check if value is a reasonable temperature.
        
        Args:
            value: Numeric value to check
            
        Returns:
            True if value is in reasonable temperature range
        """
        # Reasonable temperature range: -50°C to 150°C
        return -50.0 <= value <= 150.0

    def _is_time_range_value(self, cell_text: str, value: float) -> bool:
        """Check if value appears to be from time range controls.
        
        Args:
            cell_text: Original cell text for context
            value: Numeric value to check
            
        Returns:
            True if value appears to be a time range control value
        """
        cell_lower = cell_text.lower()
        
        # Common time range indicators
        time_indicators = ['hour', 'day', 'week', 'month', 'period', 'range', 'h', 'd', 'w', 'm']
        
        # Time range values are typically small integers (1, 4, 8, 24, etc.)
        is_small_integer = value == int(value) and 1 <= value <= 400
        has_time_indicator = any(indicator in cell_lower for indicator in time_indicators)
        
        return is_small_integer and has_time_indicator