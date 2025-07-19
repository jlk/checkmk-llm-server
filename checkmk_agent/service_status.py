"""Service status monitoring and analysis for Checkmk LLM Agent."""

import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict

from .api_client import CheckmkClient, CheckmkAPIError
from .config import AppConfig


class ServiceStatusManager:
    """Manager for service status operations and analysis."""
    
    # Service state mappings
    STATE_NAMES = {
        0: 'OK',
        1: 'WARNING', 
        2: 'CRITICAL',
        3: 'UNKNOWN'
    }
    
    STATE_PRIORITIES = {
        0: 0,  # OK - lowest priority
        1: 2,  # WARNING - medium priority
        3: 1,  # UNKNOWN - low-medium priority
        2: 3   # CRITICAL - highest priority
    }
    
    def __init__(self, checkmk_client: CheckmkClient, config: AppConfig):
        self.checkmk_client = checkmk_client
        self.config = config
        self.logger = logging.getLogger(__name__)
    
    def get_service_health_dashboard(self) -> Dict[str, Any]:
        """
        Generate comprehensive service health dashboard with key metrics.
        
        Returns:
            Dashboard data with health metrics, problem summaries, and trends
        """
        try:
            # Get overall health summary
            health_summary = self.checkmk_client.get_service_health_summary()
            
            # Get problem services for detailed analysis
            problem_services = self.checkmk_client.list_problem_services()
            
            # Get acknowledged and downtime services
            acknowledged_services = self.checkmk_client.get_acknowledged_services()
            downtime_services = self.checkmk_client.get_services_in_downtime()
            
            # Analyze problems by severity
            problem_analysis = self._analyze_problems_by_severity(problem_services)
            
            # Get host-based problem distribution
            host_problems = self._group_problems_by_host(problem_services)
            
            # Calculate problem urgency scores
            urgent_problems = self._identify_urgent_problems(problem_services)
            
            dashboard = {
                'timestamp': datetime.now().isoformat(),
                'overall_health': health_summary,
                'problem_analysis': problem_analysis,
                'host_distribution': host_problems,
                'urgent_problems': urgent_problems,
                'acknowledged_count': len(acknowledged_services),
                'downtime_count': len(downtime_services),
                'needs_attention': len([p for p in problem_services 
                                     if not self._is_service_handled(p)]),
                'summary_message': self._generate_health_message(health_summary, problem_analysis)
            }
            
            self.logger.info(f"Generated service health dashboard with {health_summary['total_services']} services")
            return dashboard
            
        except CheckmkAPIError as e:
            self.logger.error(f"Error generating service health dashboard: {e}")
            raise
    
    def analyze_service_problems(self, host_filter: Optional[str] = None) -> Dict[str, Any]:
        """
        Analyze current service problems with categorization and recommendations.
        
        Args:
            host_filter: Optional hostname filter
            
        Returns:
            Detailed problem analysis with categorization and action recommendations
        """
        try:
            # Get problem services
            problem_services = self.checkmk_client.list_problem_services(host_filter)
            
            if not problem_services:
                return {
                    'total_problems': 0,
                    'message': 'No service problems detected! 🎉',
                    'categories': {},
                    'recommendations': []
                }
            
            # Categorize problems
            categories = self._categorize_problems(problem_services)
            
            # Generate recommendations
            recommendations = self._generate_problem_recommendations(problem_services, categories)
            
            # Identify recurring problems
            recurring_issues = self._identify_recurring_issues(problem_services)
            
            analysis = {
                'total_problems': len(problem_services),
                'host_filter': host_filter,
                'categories': categories,
                'recommendations': recommendations,
                'recurring_issues': recurring_issues,
                'critical_count': len([s for s in problem_services 
                                     if self._get_service_state(s) == 2]),
                'warning_count': len([s for s in problem_services 
                                    if self._get_service_state(s) == 1]),
                'unhandled_count': len([s for s in problem_services 
                                      if not self._is_service_handled(s)])
            }
            
            self.logger.info(f"Analyzed {len(problem_services)} service problems")
            return analysis
            
        except CheckmkAPIError as e:
            self.logger.error(f"Error analyzing service problems: {e}")
            raise
    
    def get_service_status_details(self, host_name: str, service_description: Optional[str] = None) -> Dict[str, Any]:
        """
        Get comprehensive status details for a specific service or all services on a host.
        
        Args:
            host_name: Target hostname
            service_description: Optional service description (if None, returns all services on host)
            
        Returns:
            Detailed service status information with analysis
        """
        try:
            # Get service status
            service_info = self.checkmk_client.get_service_status(host_name, service_description)
            
            if service_description is None:
                # Return all services on host
                services = service_info.get('services', [])
                if not services:
                    return {
                        'found': False,
                        'host_name': host_name,
                        'message': f"Host '{host_name}' not found or has no services"
                    }
                
                # Calculate summary statistics for this host
                total_services = len(services)
                state_counts = {'ok': 0, 'warning': 0, 'critical': 0, 'unknown': 0}
                problems = []
                
                for service in services:
                    extensions = service.get('extensions', {})
                    state = extensions.get('state', 0)
                    
                    if state == 0:
                        state_counts['ok'] += 1
                    elif state == 1:
                        state_counts['warning'] += 1
                        problems.append(service)
                    elif state == 2:
                        state_counts['critical'] += 1
                        problems.append(service)
                    else:
                        state_counts['unknown'] += 1
                        problems.append(service)
                
                health_pct = (state_counts['ok'] / total_services * 100) if total_services > 0 else 100.0
                
                return {
                    'found': True,
                    'host_name': host_name,
                    'total_services': total_services,
                    'health_percentage': round(health_pct, 1),
                    'state_counts': state_counts,
                    'problems': problems,
                    'services': services,
                    'is_host_summary': True
                }
            
            elif not service_info.get('found'):
                return {
                    'found': False,
                    'host_name': host_name,
                    'service_description': service_description,
                    'message': f"Service '{service_description}' not found on host '{host_name}'"
                }
            
            service_data = service_info['status']
            extensions = service_data.get('extensions', {})
            
            # Extract key information
            state = extensions.get('state', 0)
            state_name = self.STATE_NAMES.get(state, 'UNKNOWN')
            acknowledged = extensions.get('acknowledged', 0)
            downtime_depth = extensions.get('scheduled_downtime_depth', 0)
            plugin_output = extensions.get('plugin_output', '')
            last_check = extensions.get('last_check', 0)
            
            # Calculate status analysis
            status_analysis = {
                'is_problem': state != 0,
                'severity': self._get_severity_level(state),
                'is_handled': acknowledged > 0 or downtime_depth > 0,
                'urgency_score': self._calculate_urgency_score(extensions),
                'requires_action': state != 0 and acknowledged == 0 and downtime_depth == 0
            }
            
            # Format last check time
            if last_check:
                try:
                    last_check_time = datetime.fromtimestamp(last_check)
                    time_ago = datetime.now() - last_check_time
                    status_analysis['last_check_ago'] = self._format_time_ago(time_ago)
                except:
                    status_analysis['last_check_ago'] = 'Unknown'
            else:
                status_analysis['last_check_ago'] = 'Never'
            
            details = {
                'found': True,
                'host_name': host_name,
                'service_description': service_description,
                'state': state,
                'state_name': state_name,
                'acknowledged': acknowledged > 0,
                'in_downtime': downtime_depth > 0,
                'plugin_output': plugin_output,
                'raw_data': extensions,
                'analysis': status_analysis
            }
            
            self.logger.info(f"Retrieved detailed status for {host_name}/{service_description}")
            return details
            
        except CheckmkAPIError as e:
            self.logger.error(f"Error getting service status details: {e}")
            raise
    
    def generate_status_summary(self) -> Dict[str, Any]:
        """
        Generate high-level status summary for quick overview.
        
        Returns:
            Concise status summary with key metrics
        """
        try:
            health_summary = self.checkmk_client.get_service_health_summary()
            
            summary = {
                'total_services': health_summary['total_services'],
                'health_percentage': round(health_summary['health_percentage'], 1),
                'problems': health_summary['problems'],
                'critical': health_summary['states']['critical'],
                'warning': health_summary['states']['warning'],
                'acknowledged': health_summary['acknowledged'],
                'in_downtime': health_summary['in_downtime'],
                'status_icon': self._get_overall_status_icon(health_summary),
                'status_message': self._get_status_message(health_summary)
            }
            
            return summary
            
        except CheckmkAPIError as e:
            self.logger.error(f"Error generating status summary: {e}")
            raise
    
    def get_host_status_dashboard(self, host_name: str) -> Dict[str, Any]:
        """
        Generate comprehensive host status dashboard with enhanced analysis.
        
        Args:
            host_name: Target hostname
            
        Returns:
            Rich host dashboard with health metrics, analysis, and recommendations
        """
        try:
            # Get basic host status
            host_status = self.get_service_status_details(host_name, None)
            
            if not host_status.get('found', True):
                return {
                    'found': False,
                    'host_name': host_name,
                    'error': f"Host '{host_name}' not found or has no services"
                }
            
            # Get infrastructure-wide health for comparison
            infrastructure_health = self.checkmk_client.get_service_health_summary()
            
            # Enhanced analysis
            services = host_status.get('services', [])
            state_counts = host_status.get('state_counts', {})
            total_services = len(services)
            
            # Calculate health metrics
            health_percentage = host_status.get('health_percentage', 100.0)
            infrastructure_avg = infrastructure_health.get('health_percentage', 100.0)
            health_comparison = health_percentage - infrastructure_avg
            
            # Analyze problems by category
            problem_services = [s for s in services if self._get_service_state(s) != 0]
            problem_analysis = self._analyze_host_problems_by_category(problem_services)
            
            # Calculate urgency and maintenance recommendations
            urgent_issues = self._identify_host_urgent_issues(problem_services)
            maintenance_suggestions = self._generate_host_maintenance_recommendations(
                problem_services, problem_analysis
            )
            
            # Recent changes analysis (simulated - in practice would use historical data)
            recent_changes = self._analyze_recent_service_changes(services)
            
            dashboard = {
                'found': True,
                'host_name': host_name,
                'timestamp': datetime.now().isoformat(),
                'health_metrics': {
                    'health_percentage': round(health_percentage, 1),
                    'total_services': total_services,
                    'state_counts': state_counts,
                    'infrastructure_comparison': round(health_comparison, 1),
                    'health_trend': self._calculate_health_trend(health_percentage, infrastructure_avg),
                    'status_icon': self._get_host_status_icon(state_counts),
                    'health_grade': self._get_health_grade(health_percentage)
                },
                'problem_analysis': problem_analysis,
                'urgent_issues': urgent_issues,
                'maintenance_suggestions': maintenance_suggestions,
                'recent_changes': recent_changes,
                'summary_message': self._generate_host_summary_message(
                    health_percentage, len(problem_services), urgent_issues
                )
            }
            
            self.logger.info(f"Generated enhanced host status dashboard for {host_name}")
            return dashboard
            
        except CheckmkAPIError as e:
            self.logger.error(f"Error generating host status dashboard for {host_name}: {e}")
            raise
    
    def find_services_by_criteria(self, criteria: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Find services matching specific criteria.
        
        Args:
            criteria: Search criteria dictionary
            
        Returns:
            List of services matching the criteria
        """
        try:
            services = []
            
            # Handle different search criteria
            if criteria.get('state') is not None:
                services = self.checkmk_client.get_services_by_state(
                    criteria['state'], 
                    criteria.get('host_filter')
                )
            elif criteria.get('acknowledged'):
                services = self.checkmk_client.get_acknowledged_services()
            elif criteria.get('in_downtime'):
                services = self.checkmk_client.get_services_in_downtime()
            elif criteria.get('has_problems'):
                services = self.checkmk_client.list_problem_services(
                    criteria.get('host_filter')
                )
            else:
                # Default to all services with filtering
                services = self.checkmk_client.list_all_services(
                    host_name=criteria.get('host_filter'),
                    columns=self.checkmk_client.STATUS_COLUMNS
                )
            
            # Apply additional filters
            if criteria.get('service_pattern'):
                pattern = criteria['service_pattern'].lower()
                services = [s for s in services 
                          if pattern in s.get('extensions', {}).get('description', '').lower()]
            
            if criteria.get('output_contains'):
                output_filter = criteria['output_contains'].lower()
                services = [s for s in services 
                          if output_filter in s.get('extensions', {}).get('plugin_output', '').lower()]
            
            self.logger.info(f"Found {len(services)} services matching criteria")
            return services
            
        except CheckmkAPIError as e:
            self.logger.error(f"Error finding services by criteria: {e}")
            raise
    
    # Helper methods
    
    def _analyze_problems_by_severity(self, problem_services: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze problems by severity level."""
        analysis = {
            'critical': [],
            'warning': [],
            'unknown': [],
            'by_host': defaultdict(list)
        }
        
        for service in problem_services:
            state = self._get_service_state(service)
            host_name = self._get_service_host(service)
            
            service_info = {
                'host_name': host_name,
                'description': self._get_service_description(service),
                'state': state,
                'state_name': self.STATE_NAMES.get(state, 'UNKNOWN'),
                'output': self._get_service_output(service),
                'acknowledged': self._is_service_acknowledged(service),
                'in_downtime': self._is_service_in_downtime(service)
            }
            
            if state == 2:
                analysis['critical'].append(service_info)
            elif state == 1:
                analysis['warning'].append(service_info)
            elif state == 3:
                analysis['unknown'].append(service_info)
            
            analysis['by_host'][host_name].append(service_info)
        
        # Sort by priority (critical first)
        analysis['critical'].sort(key=lambda x: x['description'])
        analysis['warning'].sort(key=lambda x: x['description'])
        analysis['unknown'].sort(key=lambda x: x['description'])
        
        return analysis
    
    def _group_problems_by_host(self, problem_services: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Group problems by host for host-centric view."""
        host_problems = defaultdict(lambda: {'critical': 0, 'warning': 0, 'unknown': 0, 'total': 0})
        
        for service in problem_services:
            host_name = self._get_service_host(service)
            state = self._get_service_state(service)
            
            host_problems[host_name]['total'] += 1
            if state == 2:
                host_problems[host_name]['critical'] += 1
            elif state == 1:
                host_problems[host_name]['warning'] += 1
            elif state == 3:
                host_problems[host_name]['unknown'] += 1
        
        # Convert to regular dict and sort by problem count
        sorted_hosts = sorted(host_problems.items(), 
                            key=lambda x: (x[1]['critical'], x[1]['total']), 
                            reverse=True)
        
        return dict(sorted_hosts)
    
    def _identify_urgent_problems(self, problem_services: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Identify most urgent problems requiring immediate attention."""
        urgent_problems = []
        
        for service in problem_services:
            # Skip if already handled
            if self._is_service_handled(service):
                continue
            
            state = self._get_service_state(service)
            urgency_score = self._calculate_urgency_score(service.get('extensions', {}))
            
            if state == 2 or urgency_score > 7:  # Critical or high urgency
                urgent_problems.append({
                    'host_name': self._get_service_host(service),
                    'description': self._get_service_description(service),
                    'state': state,
                    'state_name': self.STATE_NAMES.get(state, 'UNKNOWN'),
                    'output': self._get_service_output(service),
                    'urgency_score': urgency_score
                })
        
        # Sort by urgency score (highest first)
        urgent_problems.sort(key=lambda x: (x['state'], x['urgency_score']), reverse=True)
        
        return urgent_problems[:10]  # Return top 10 most urgent
    
    def _categorize_problems(self, problem_services: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        """Categorize problems by type/pattern."""
        categories = {
            'critical_issues': [],
            'warning_issues': [],
            'disk_problems': [],
            'network_problems': [],
            'performance_issues': [],
            'connectivity_issues': [],
            'other_issues': []
        }
        
        for service in problem_services:
            host_name = self._get_service_host(service)
            description = self._get_service_description(service).lower()
            output = self._get_service_output(service).lower()
            state = self._get_service_state(service)
            
            service_key = f"{host_name}/{self._get_service_description(service)}"
            
            # Categorize by state
            if state == 2:
                categories['critical_issues'].append(service_key)
            elif state == 1:
                categories['warning_issues'].append(service_key)
            
            # Categorize by service type
            if any(keyword in description for keyword in ['disk', 'filesystem', 'storage']):
                categories['disk_problems'].append(service_key)
            elif any(keyword in description for keyword in ['network', 'interface', 'ping']):
                categories['network_problems'].append(service_key)
            elif any(keyword in description for keyword in ['cpu', 'memory', 'load', 'performance']):
                categories['performance_issues'].append(service_key)
            elif any(keyword in output for keyword in ['connection', 'timeout', 'refused']):
                categories['connectivity_issues'].append(service_key)
            else:
                categories['other_issues'].append(service_key)
        
        # Remove duplicates and limit entries
        for category in categories:
            categories[category] = list(set(categories[category]))[:10]
        
        return categories
    
    def _generate_problem_recommendations(self, problem_services: List[Dict[str, Any]], 
                                        categories: Dict[str, List[str]]) -> List[str]:
        """Generate actionable recommendations based on problem analysis."""
        recommendations = []
        
        critical_count = len(categories.get('critical_issues', []))
        disk_count = len(categories.get('disk_problems', []))
        network_count = len(categories.get('network_problems', []))
        
        if critical_count > 0:
            recommendations.append(f"🚨 {critical_count} critical issue(s) require immediate attention")
        
        if disk_count > 0:
            recommendations.append(f"💾 {disk_count} disk/storage issue(s) - check disk space and performance")
        
        if network_count > 0:
            recommendations.append(f"🌐 {network_count} network issue(s) - verify connectivity and interface status")
        
        unhandled_count = len([s for s in problem_services if not self._is_service_handled(s)])
        if unhandled_count > 0:
            recommendations.append(f"⚠️  {unhandled_count} unacknowledged problem(s) need review")
        
        if len(problem_services) > 10:
            recommendations.append("📊 Consider using filters to focus on specific hosts or service types")
        
        return recommendations
    
    def _identify_recurring_issues(self, problem_services: List[Dict[str, Any]]) -> List[str]:
        """Identify services that may have recurring issues."""
        # This is a simplified implementation - in practice you'd track history
        recurring = []
        
        # Look for services with specific patterns that suggest recurring issues
        for service in problem_services:
            output = self._get_service_output(service).lower()
            if any(keyword in output for keyword in ['flapping', 'intermittent', 'unstable']):
                service_key = f"{self._get_service_host(service)}/{self._get_service_description(service)}"
                recurring.append(service_key)
        
        return recurring
    
    def _generate_health_message(self, health_summary: Dict[str, Any], 
                                problem_analysis: Dict[str, Any]) -> str:
        """Generate human-readable health message."""
        health_pct = health_summary['health_percentage']
        problems = health_summary['problems']
        
        if health_pct >= 95:
            return f"Excellent health! {health_pct:.1f}% of services are OK"
        elif health_pct >= 90:
            return f"Good health with {problems} service(s) needing attention"
        elif health_pct >= 80:
            return f"Moderate issues detected - {problems} service problems to review"
        else:
            return f"Multiple issues require attention - {problems} service problems detected"
    
    def _get_overall_status_icon(self, health_summary: Dict[str, Any]) -> str:
        """Get overall status icon based on health."""
        if health_summary['states']['critical'] > 0:
            return "🔴"
        elif health_summary['states']['warning'] > 0:
            return "🟡"
        elif health_summary['states']['unknown'] > 0:
            return "🟤"
        else:
            return "🟢"
    
    def _get_status_message(self, health_summary: Dict[str, Any]) -> str:
        """Get concise status message."""
        problems = health_summary['problems']
        if problems == 0:
            return "All services OK"
        elif problems == 1:
            return "1 service problem"
        else:
            return f"{problems} service problems"
    
    def _calculate_urgency_score(self, extensions: Dict[str, Any]) -> int:
        """Calculate urgency score (0-10) based on service attributes."""
        score = 0
        
        state = extensions.get('state', 0)
        if state == 2:  # Critical
            score += 5
        elif state == 1:  # Warning
            score += 2
        
        # Add points for not being handled
        if not extensions.get('acknowledged', 0):
            score += 2
        if not extensions.get('scheduled_downtime_depth', 0):
            score += 1
        
        # Add points based on check attempts
        current_attempt = extensions.get('current_attempt', 1)
        max_attempts = extensions.get('max_check_attempts', 3)
        if current_attempt >= max_attempts:
            score += 2
        
        return min(score, 10)
    
    def _get_severity_level(self, state: int) -> str:
        """Get severity level description."""
        if state == 2:
            return "Critical"
        elif state == 1:
            return "Warning"
        elif state == 3:
            return "Unknown"
        else:
            return "OK"
    
    def _format_time_ago(self, time_delta: timedelta) -> str:
        """Format time delta as human-readable string."""
        total_seconds = int(time_delta.total_seconds())
        
        if total_seconds < 60:
            return f"{total_seconds}s ago"
        elif total_seconds < 3600:
            minutes = total_seconds // 60
            return f"{minutes}m ago"
        elif total_seconds < 86400:
            hours = total_seconds // 3600
            return f"{hours}h ago"
        else:
            days = total_seconds // 86400
            return f"{days}d ago"
    
    def _is_service_handled(self, service: Dict[str, Any]) -> bool:
        """Check if service problem is handled (acknowledged or in downtime)."""
        extensions = service.get('extensions', {})
        return (extensions.get('acknowledged', 0) > 0 or 
                extensions.get('scheduled_downtime_depth', 0) > 0)
    
    def _get_service_state(self, service: Dict[str, Any]) -> int:
        """Extract service state from service data."""
        return service.get('extensions', {}).get('state', 0)
    
    def _get_service_host(self, service: Dict[str, Any]) -> str:
        """Extract host name from service data."""
        return service.get('extensions', {}).get('host_name', 'Unknown')
    
    def _get_service_description(self, service: Dict[str, Any]) -> str:
        """Extract service description from service data."""
        return service.get('extensions', {}).get('description', 'Unknown')
    
    def _get_service_output(self, service: Dict[str, Any]) -> str:
        """Extract service output from service data."""
        return service.get('extensions', {}).get('plugin_output', '')
    
    def _is_service_acknowledged(self, service: Dict[str, Any]) -> bool:
        """Check if service is acknowledged."""
        return service.get('extensions', {}).get('acknowledged', 0) > 0
    
    def _is_service_in_downtime(self, service: Dict[str, Any]) -> bool:
        """Check if service is in downtime."""
        return service.get('extensions', {}).get('scheduled_downtime_depth', 0) > 0
    
    # Enhanced host dashboard helper methods
    
    def _analyze_host_problems_by_category(self, problem_services: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze host problems by category and type."""
        categories = {
            'critical_issues': [],
            'warning_issues': [],
            'disk_problems': [],
            'network_problems': [],
            'performance_issues': [],
            'connectivity_issues': [],
            'monitoring_issues': [],
            'other_issues': []
        }
        
        category_counts = {
            'disk': 0, 'network': 0, 'performance': 0, 
            'connectivity': 0, 'monitoring': 0, 'other': 0
        }
        
        for service in problem_services:
            state = self._get_service_state(service)
            description = self._get_service_description(service).lower()
            output = self._get_service_output(service).lower()
            
            service_info = {
                'description': self._get_service_description(service),
                'state': state,
                'state_name': self.STATE_NAMES.get(state, 'UNKNOWN'),
                'output': self._get_service_output(service)[:100],
                'urgency_score': self._calculate_urgency_score(service.get('extensions', {}))
            }
            
            # Categorize by state
            if state == 2:
                categories['critical_issues'].append(service_info)
            elif state == 1:
                categories['warning_issues'].append(service_info)
            
            # Categorize by service type with more granular detection
            if any(keyword in description for keyword in ['disk', 'filesystem', 'storage', 'mount', 'space']):
                categories['disk_problems'].append(service_info)
                category_counts['disk'] += 1
            elif any(keyword in description for keyword in ['network', 'interface', 'ping', 'port', 'tcp', 'udp']):
                categories['network_problems'].append(service_info)
                category_counts['network'] += 1
            elif any(keyword in description for keyword in ['cpu', 'memory', 'load', 'performance', 'utilization']):
                categories['performance_issues'].append(service_info)
                category_counts['performance'] += 1
            elif any(keyword in output for keyword in ['connection', 'timeout', 'refused', 'unreachable']):
                categories['connectivity_issues'].append(service_info)
                category_counts['connectivity'] += 1
            elif any(keyword in description for keyword in ['check_mk', 'agent', 'monitoring', 'snmp']):
                categories['monitoring_issues'].append(service_info)
                category_counts['monitoring'] += 1
            else:
                categories['other_issues'].append(service_info)
                category_counts['other'] += 1
        
        # Add summary statistics
        categories['summary'] = {
            'total_problems': len(problem_services),
            'category_distribution': category_counts,
            'most_affected_category': max(category_counts.items(), key=lambda x: x[1])[0] if any(category_counts.values()) else 'none'
        }
        
        return categories
    
    def _identify_host_urgent_issues(self, problem_services: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Identify most urgent issues for this specific host."""
        urgent_issues = []
        
        for service in problem_services:
            if self._is_service_handled(service):
                continue
                
            state = self._get_service_state(service)
            extensions = service.get('extensions', {})
            urgency_score = self._calculate_urgency_score(extensions)
            
            # Host-specific urgency criteria
            is_critical_service = self._is_critical_host_service(service)
            
            if state == 2 or urgency_score >= 7 or is_critical_service:
                urgent_issues.append({
                    'description': self._get_service_description(service),
                    'state': state,
                    'state_name': self.STATE_NAMES.get(state, 'UNKNOWN'),
                    'output': self._get_service_output(service)[:150],
                    'urgency_score': urgency_score,
                    'is_critical_service': is_critical_service,
                    'recommended_action': self._get_service_recommended_action(service)
                })
        
        # Sort by urgency (state priority, then urgency score)
        urgent_issues.sort(
            key=lambda x: (self.STATE_PRIORITIES.get(x['state'], 0), x['urgency_score']), 
            reverse=True
        )
        
        return urgent_issues[:5]  # Return top 5 most urgent
    
    def _generate_host_maintenance_recommendations(self, problem_services: List[Dict[str, Any]], 
                                                 problem_analysis: Dict[str, Any]) -> List[str]:
        """Generate maintenance recommendations specific to this host."""
        recommendations = []
        summary = problem_analysis.get('summary', {})
        category_counts = summary.get('category_distribution', {})
        
        # Critical issues
        critical_count = len(problem_analysis.get('critical_issues', []))
        if critical_count > 0:
            recommendations.append(f"🚨 {critical_count} critical issue(s) require immediate attention")
        
        # Category-specific recommendations
        if category_counts.get('disk', 0) > 0:
            recommendations.append(f"💾 Disk issues detected - check filesystem usage and disk health")
        
        if category_counts.get('performance', 0) > 0:
            recommendations.append(f"⚡ Performance issues detected - monitor CPU/memory usage")
        
        if category_counts.get('network', 0) > 0:
            recommendations.append(f"🌐 Network issues detected - verify interface configuration and connectivity")
        
        if category_counts.get('connectivity', 0) > 0:
            recommendations.append(f"🔌 Connectivity issues detected - check service dependencies and firewall rules")
        
        # Host-specific recommendations
        unhandled_count = len([s for s in problem_services if not self._is_service_handled(s)])
        if unhandled_count > 0:
            recommendations.append(f"⚠️  {unhandled_count} unacknowledged problem(s) need review")
        
        # Health-based recommendations
        if len(problem_services) > 5:
            recommendations.append("📋 Consider scheduling maintenance window for comprehensive fixes")
        
        if category_counts.get('monitoring', 0) > 0:
            recommendations.append("🔍 Monitoring system issues detected - check agent connectivity")
        
        return recommendations
    
    def _analyze_recent_service_changes(self, services: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze recent service state changes (simulated - would use historical data)."""
        # This is a simplified simulation - in practice would query historical data
        changes = {
            'recently_recovered': [],
            'recently_failed': [],
            'state_changes_count': 0,
            'stability_score': 85.0  # Simulated stability score
        }
        
        # Simulate some recent changes based on service characteristics
        for service in services[:5]:  # Check first 5 services
            state = self._get_service_state(service)
            description = self._get_service_description(service)
            
            # Simulate recent recovery for OK services
            if state == 0 and len(changes['recently_recovered']) < 2:
                changes['recently_recovered'].append({
                    'description': description,
                    'recovered_ago': f"{15 + len(changes['recently_recovered']) * 10}m ago"
                })
                changes['state_changes_count'] += 1
            
            # Simulate recent failures for problem services
            elif state != 0 and len(changes['recently_failed']) < 2:
                changes['recently_failed'].append({
                    'description': description,
                    'failed_ago': f"{30 + len(changes['recently_failed']) * 15}m ago",
                    'state_name': self.STATE_NAMES.get(state, 'UNKNOWN')
                })
                changes['state_changes_count'] += 1
        
        return changes
    
    def _calculate_health_trend(self, host_health: float, infra_health: float) -> str:
        """Calculate health trend indicator."""
        diff = host_health - infra_health
        
        if diff >= 5:
            return "improving"
        elif diff <= -5:
            return "declining"
        else:
            return "stable"
    
    def _get_host_status_icon(self, state_counts: Dict[str, int]) -> str:
        """Get host status icon based on service states."""
        if state_counts.get('critical', 0) > 0:
            return "🔴"
        elif state_counts.get('warning', 0) > 0:
            return "🟡"
        elif state_counts.get('unknown', 0) > 0:
            return "🟤"
        else:
            return "🟢"
    
    def _get_health_grade(self, health_percentage: float) -> str:
        """Get letter grade for health percentage."""
        if health_percentage >= 95:
            return "A+"
        elif health_percentage >= 90:
            return "A"
        elif health_percentage >= 85:
            return "B+"
        elif health_percentage >= 80:
            return "B"
        elif health_percentage >= 75:
            return "C+"
        elif health_percentage >= 70:
            return "C"
        elif health_percentage >= 60:
            return "D"
        else:
            return "F"
    
    def _generate_host_summary_message(self, health_percentage: float, 
                                     problem_count: int, urgent_issues: List[Dict[str, Any]]) -> str:
        """Generate host-specific summary message."""
        if health_percentage >= 95 and problem_count == 0:
            return f"Excellent! Host is running perfectly with {health_percentage:.1f}% health"
        elif health_percentage >= 90:
            return f"Host is healthy ({health_percentage:.1f}%) with {problem_count} minor issue(s)"
        elif health_percentage >= 80:
            return f"Host needs attention - {problem_count} service problem(s) detected"
        elif len(urgent_issues) > 0:
            return f"Host requires immediate attention - {len(urgent_issues)} urgent issue(s)"
        else:
            return f"Host has significant issues - {problem_count} service problems detected"
    
    def _is_critical_host_service(self, service: Dict[str, Any]) -> bool:
        """Determine if a service is critical for host operations."""
        description = self._get_service_description(service).lower()
        
        # Define critical services
        critical_services = [
            'check_mk', 'agent', 'ping', 'ssh', 'filesystem /', 
            'memory', 'cpu', 'load', 'disk', 'root'
        ]
        
        return any(critical in description for critical in critical_services)
    
    def _get_service_recommended_action(self, service: Dict[str, Any]) -> str:
        """Get recommended action for a service problem."""
        state = self._get_service_state(service)
        description = self._get_service_description(service).lower()
        output = self._get_service_output(service).lower()
        
        if state == 2:  # Critical
            if 'disk' in description or 'filesystem' in description:
                return "Check disk space and clean up files"
            elif 'memory' in description:
                return "Investigate memory usage and restart services if needed"
            elif 'cpu' in description or 'load' in description:
                return "Identify high CPU processes and optimize"
            elif 'ping' in description or 'network' in description:
                return "Check network connectivity and interface status"
            else:
                return "Investigate immediately - critical service failure"
        elif state == 1:  # Warning
            if 'threshold' in output or 'limit' in output:
                return "Monitor trends and consider adjusting thresholds"
            else:
                return "Monitor and investigate if condition persists"
        else:
            return "Investigate unknown service state"