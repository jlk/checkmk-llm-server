"""Status service - core business logic for service status monitoring and health dashboards."""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from collections import defaultdict

from .base import BaseService, ServiceResult
from .models.status import (
    HealthDashboard, ProblemSummary, ServiceProblem, HostStatus,
    StatusFilterOptions, StatusQueryResult, ProblemSeverity, ProblemCategory
)
from .models.services import ServiceState
from .models.hosts import HostState
from ..async_api_client import AsyncCheckmkClient
from ..api_client import CheckmkAPIError
from ..config import AppConfig


class StatusService(BaseService):
    """Core status monitoring service - presentation agnostic."""
    
    # Service state mappings
    STATE_NAMES = {
        0: ServiceState.OK,
        1: ServiceState.WARNING,
        2: ServiceState.CRITICAL,
        3: ServiceState.UNKNOWN
    }
    
    STATE_PRIORITIES = {
        ServiceState.OK: 0,        # Lowest priority
        ServiceState.WARNING: 2,   # Medium priority
        ServiceState.UNKNOWN: 1,   # Low-medium priority
        ServiceState.CRITICAL: 3   # Highest priority
    }
    
    PROBLEM_CATEGORIES = {
        # Performance-related services
        'cpu': ProblemCategory.PERFORMANCE,
        'load': ProblemCategory.PERFORMANCE,
        'memory': ProblemCategory.MEMORY,
        'mem': ProblemCategory.MEMORY,
        'ram': ProblemCategory.MEMORY,
        
        # Disk-related services
        'disk': ProblemCategory.DISK,
        'filesystem': ProblemCategory.DISK,
        'df': ProblemCategory.DISK,
        'mount': ProblemCategory.DISK,
        
        # Network-related services
        'network': ProblemCategory.NETWORK,
        'interface': ProblemCategory.NETWORK,
        'ping': ProblemCategory.CONNECTIVITY,
        'ssh': ProblemCategory.CONNECTIVITY,
        'tcp': ProblemCategory.CONNECTIVITY,
        'http': ProblemCategory.CONNECTIVITY,
        'https': ProblemCategory.CONNECTIVITY,
        
        # Monitoring-related services
        'check_mk': ProblemCategory.MONITORING,
        'agent': ProblemCategory.MONITORING,
        'cmk': ProblemCategory.MONITORING,
    }
    
    def __init__(self, checkmk_client: AsyncCheckmkClient, config: AppConfig):
        super().__init__(checkmk_client, config)
        self.logger = logging.getLogger(__name__)
    
    async def get_health_dashboard(self) -> ServiceResult[HealthDashboard]:
        """
        Generate comprehensive service health dashboard.
        
        Returns:
            ServiceResult containing HealthDashboard
        """
        async def _dashboard_operation():
            # Get overall health summary
            health_summary = await self.checkmk.get_service_health_summary()
            
            # Get problem services for detailed analysis
            problem_services = await self.checkmk.list_problem_services()
            
            # Get acknowledged and downtime services
            acknowledged_services = await self.checkmk.get_acknowledged_services()
            downtime_services = await self.checkmk.get_services_in_downtime()
            
            # Analyze problems
            problem_summary = self._analyze_problem_summary(problem_services)
            critical_problems = self._get_critical_problems(problem_services)
            urgent_problems = self._identify_urgent_problems(problem_services)
            
            # Get host statuses
            host_statuses = await self._calculate_host_statuses()
            worst_hosts = sorted(host_statuses, key=lambda h: h.health_percentage)[:5]
            
            # Calculate overall metrics
            total_services = health_summary.get('total_services', 0)
            service_states = health_summary.get('state_counts', {})
            ok_services = service_states.get('ok', 0)
            
            overall_health = self._calculate_health_percentage(ok_services, total_services)
            health_grade = self._get_health_grade(overall_health)
            
            # Generate recommendations and alerts
            recommendations = self._generate_health_recommendations(problem_summary, critical_problems)
            alerts = self._generate_health_alerts(critical_problems, urgent_problems)
            
            # Determine health trend
            health_trend = self._calculate_health_trend(problem_summary)
            
            dashboard = HealthDashboard(
                overall_health_percentage=overall_health,
                overall_health_grade=health_grade,
                total_hosts=health_summary.get('total_hosts', 0),
                total_services=total_services,
                service_states=service_states,
                host_states=health_summary.get('host_state_counts', {}),
                problem_summary=problem_summary,
                critical_problems=critical_problems,
                urgent_problems=urgent_problems,
                host_statuses=host_statuses,
                worst_performing_hosts=worst_hosts,
                health_trend=health_trend,
                recommendations=recommendations,
                alerts=alerts,
                last_updated=datetime.now(),
                data_freshness=self._calculate_data_freshness()
            )
            
            return dashboard
        
        return await self._execute_with_error_handling(_dashboard_operation, "get_health_dashboard")
    
    async def list_problems(
        self,
        severity: Optional[str] = None,
        host_filter: Optional[str] = None,
        category: Optional[str] = None,
        limit: Optional[int] = None
    ) -> ServiceResult[List[ServiceProblem]]:
        """
        List service problems with filtering options.
        
        Args:
            severity: Filter by severity (critical, warning, unknown)
            host_filter: Filter by host name pattern
            category: Filter by problem category
            limit: Maximum number of problems to return
            
        Returns:
            ServiceResult containing list of ServiceProblem
        """
        async def _list_problems_operation():
            # Get problem services from API
            problem_services = await self.checkmk.list_problem_services(host_filter)
            
            # Convert to ServiceProblem models
            problems = []
            for service_data in problem_services:
                problem = self._convert_service_to_problem(service_data)
                problems.append(problem)
            
            # Apply filters
            filtered_problems = self._apply_problem_filters(problems, severity, category)
            
            # Sort by urgency/severity
            filtered_problems.sort(key=lambda p: (p.urgency_score, p.severity), reverse=True)
            
            # Apply limit
            if limit:
                filtered_problems = filtered_problems[:limit]
            
            return filtered_problems
        
        return await self._execute_with_error_handling(_list_problems_operation, "list_problems")
    
    async def query_status(self, filters: StatusFilterOptions) -> ServiceResult[StatusQueryResult]:
        """
        Execute a complex status query with filtering and sorting.
        
        Args:
            filters: StatusFilterOptions with query parameters
            
        Returns:
            ServiceResult containing StatusQueryResult
        """
        async def _query_operation():
            start_time = datetime.now()
            
            # Get base data
            if filters.state_filter and ServiceState.OK not in filters.state_filter:
                # Only get problem services if we're not looking for OK services
                service_data = await self.checkmk.list_problem_services(filters.host_filter)
            else:
                # Get all services if we need OK services too
                service_data = await self.checkmk.list_all_services(filters.host_filter)
            
            # Convert to problems
            all_problems = [self._convert_service_to_problem(s) for s in service_data]
            
            # Apply all filters
            filtered_problems = self._apply_comprehensive_filters(all_problems, filters)
            
            # Get host statuses if needed
            host_statuses = []
            if filters.host_filter:
                host_statuses = await self._calculate_host_statuses(filters.host_filter)
            
            # Sort results
            sorted_problems = self._sort_problems(filtered_problems, filters.sort_by, filters.sort_order)
            
            # Apply limit
            total_matches = len(sorted_problems)
            if filters.limit:
                sorted_problems = sorted_problems[:filters.limit]
            
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            
            return StatusQueryResult(
                success=True,
                message=f"Found {total_matches} matching problems",
                problems=sorted_problems,
                host_statuses=host_statuses,
                filter_applied=filters,
                total_matches=total_matches,
                query_time=datetime.now(),
                execution_time_ms=execution_time
            )
        
        return await self._execute_with_error_handling(_query_operation, "query_status")
    
    def _analyze_problem_summary(self, problem_services: List[Dict[str, Any]]) -> ProblemSummary:
        """Analyze problem services and create summary."""
        total = len(problem_services)
        critical = warning = unknown = 0
        unacknowledged = urgent = 0
        categories = defaultdict(int)
        hosts = defaultdict(int)
        
        current_time = datetime.now()
        new_last_hour = resolved_last_hour = 0
        
        for service in problem_services:
            state = self._get_service_state_from_data(service)
            
            if state == ServiceState.CRITICAL:
                critical += 1
            elif state == ServiceState.WARNING:
                warning += 1
            elif state == ServiceState.UNKNOWN:
                unknown += 1
            
            if not self._is_service_acknowledged(service):
                unacknowledged += 1
            
            if self._is_service_urgent(service):
                urgent += 1
            
            # Categorize problem
            category = self._categorize_service_problem(service)
            categories[category.value] += 1
            
            # Count by host
            host_name = service.get('host_name', 'unknown')
            hosts[host_name] += 1
            
            # Check if problem is recent (last hour)
            last_state_change = service.get('last_state_change')
            if last_state_change:
                change_time = datetime.fromtimestamp(last_state_change)
                if (current_time - change_time).total_seconds() < 3600:
                    new_last_hour += 1
        
        return ProblemSummary(
            total_problems=total,
            critical_problems=critical,
            warning_problems=warning,
            unknown_problems=unknown,
            unacknowledged_problems=unacknowledged,
            urgent_problems=urgent,
            problems_by_category=dict(categories),
            problems_by_host=dict(hosts),
            new_problems_last_hour=new_last_hour,
            resolved_problems_last_hour=resolved_last_hour  # Would need historical data
        )
    
    def _convert_service_to_problem(self, service_data: Dict[str, Any]) -> ServiceProblem:
        """Convert service data to ServiceProblem model."""
        state = self._get_service_state_from_data(service_data)
        severity = self._map_state_to_severity(state)
        category = self._categorize_service_problem(service_data)
        
        # Calculate duration
        last_change = service_data.get('last_state_change')
        if last_change:
            change_time = datetime.fromtimestamp(last_change)
            duration = self._format_duration(datetime.now() - change_time)
        else:
            duration = "Unknown"
        
        # Calculate urgency score
        urgency_score = self._calculate_urgency_score(service_data, state, category)
        
        # Assess business impact
        business_impact = self._assess_business_impact(service_data, state, category)
        
        return ServiceProblem(
            host_name=service_data.get('host_name', ''),
            service_name=service_data.get('service_description', ''),
            state=state,
            severity=severity,
            category=category,
            plugin_output=service_data.get('plugin_output', ''),
            duration=duration,
            last_state_change=datetime.fromtimestamp(last_change) if last_change else datetime.now(),
            acknowledged=self._is_service_acknowledged(service_data),
            in_downtime=self._is_service_in_downtime(service_data),
            urgency_score=urgency_score,
            business_impact=business_impact
        )
    
    def _get_critical_problems(self, problem_services: List[Dict[str, Any]]) -> List[ServiceProblem]:
        """Get list of critical problems."""
        critical_services = [
            s for s in problem_services 
            if self._get_service_state_from_data(s) == ServiceState.CRITICAL
        ]
        
        return [self._convert_service_to_problem(s) for s in critical_services]
    
    def _identify_urgent_problems(self, problem_services: List[Dict[str, Any]]) -> List[ServiceProblem]:
        """Identify problems that need urgent attention."""
        urgent_services = [
            s for s in problem_services 
            if self._is_service_urgent(s)
        ]
        
        problems = [self._convert_service_to_problem(s) for s in urgent_services]
        return sorted(problems, key=lambda p: p.urgency_score, reverse=True)
    
    async def _calculate_host_statuses(self, host_filter: Optional[str] = None) -> List[HostStatus]:
        """Calculate status summary for each host."""
        try:
            # Get host service data
            hosts_data = await self.checkmk.get_hosts_with_services(host_filter)
            
            host_statuses = []
            for host_data in hosts_data:
                host_status = self._calculate_single_host_status(host_data)
                host_statuses.append(host_status)
            
            return host_statuses
        except Exception as e:
            self.logger.warning(f"Could not calculate host statuses: {e}")
            return []
    
    def _calculate_single_host_status(self, host_data: Dict[str, Any]) -> HostStatus:
        """Calculate status for a single host."""
        services = host_data.get('services', [])
        
        total_services = len(services)
        ok = warning = critical = unknown = 0
        urgent_problems = acknowledged_problems = 0
        
        for service in services:
            state = self._get_service_state_from_data(service)
            
            if state == ServiceState.OK:
                ok += 1
            elif state == ServiceState.WARNING:
                warning += 1
            elif state == ServiceState.CRITICAL:
                critical += 1
            elif state == ServiceState.UNKNOWN:
                unknown += 1
            
            if self._is_service_urgent(service):
                urgent_problems += 1
            
            if self._is_service_acknowledged(service):
                acknowledged_problems += 1
        
        health_percentage = self._calculate_health_percentage(ok, total_services)
        health_grade = self._get_health_grade(health_percentage)
        
        # Determine host state
        host_state = HostState.UP  # Default, would need actual host status from API
        if 'host_state' in host_data:
            host_state = HostState(host_data['host_state'])
        
        return HostStatus(
            name=host_data.get('name', ''),
            state=host_state,
            total_services=total_services,
            ok_services=ok,
            warning_services=warning,
            critical_services=critical,
            unknown_services=unknown,
            health_percentage=health_percentage,
            health_grade=health_grade,
            urgent_problems=urgent_problems,
            acknowledged_problems=acknowledged_problems
        )
    
    def _get_service_state_from_data(self, service_data: Dict[str, Any]) -> ServiceState:
        """Extract service state from API data."""
        state_code = service_data.get('state', 0)
        return self.STATE_NAMES.get(state_code, ServiceState.UNKNOWN)
    
    def _map_state_to_severity(self, state: ServiceState) -> ProblemSeverity:
        """Map service state to problem severity."""
        if state == ServiceState.CRITICAL:
            return ProblemSeverity.CRITICAL
        elif state == ServiceState.WARNING:
            return ProblemSeverity.WARNING
        else:
            return ProblemSeverity.UNKNOWN
    
    def _categorize_service_problem(self, service_data: Dict[str, Any]) -> ProblemCategory:
        """Categorize a service problem based on service name and output."""
        service_name = service_data.get('service_description', '').lower()
        
        # Check for category keywords in service name
        for keyword, category in self.PROBLEM_CATEGORIES.items():
            if keyword in service_name:
                return category
        
        # Default category
        return ProblemCategory.OTHER
    
    def _calculate_urgency_score(self, service_data: Dict[str, Any], state: ServiceState, category: ProblemCategory) -> int:
        """Calculate urgency score (0-100) for a service problem."""
        score = 0
        
        # Base score by state
        if state == ServiceState.CRITICAL:
            score += 50
        elif state == ServiceState.WARNING:
            score += 30
        else:
            score += 10
        
        # Category impact
        if category in [ProblemCategory.CONNECTIVITY]:
            score += 20
        elif category in [ProblemCategory.PERFORMANCE, ProblemCategory.DISK]:
            score += 15
        else:
            score += 5
        
        # Duration impact
        last_change = service_data.get('last_state_change')
        if last_change:
            hours_ago = (datetime.now() - datetime.fromtimestamp(last_change)).total_seconds() / 3600
            if hours_ago > 24:
                score += 15  # Long-standing issues are more urgent
            elif hours_ago > 6:
                score += 10
        
        # Acknowledgment status
        if not self._is_service_acknowledged(service_data):
            score += 10
        
        return min(score, 100)
    
    def _assess_business_impact(self, service_data: Dict[str, Any], state: ServiceState, category: ProblemCategory) -> str:
        """Assess business impact of a service problem."""
        if state == ServiceState.CRITICAL:
            if category == ProblemCategory.CONNECTIVITY:
                return "High - Service unavailable to users"
            elif category == ProblemCategory.PERFORMANCE:
                return "High - Severe performance degradation"
            elif category == ProblemCategory.DISK:
                return "High - Risk of data loss or service failure"
            else:
                return "Medium-High - Service functionality impaired"
        elif state == ServiceState.WARNING:
            return "Medium - Degraded performance or approaching limits"
        else:
            return "Low-Medium - Monitoring issue or unknown state"
    
    def _is_service_acknowledged(self, service_data: Dict[str, Any]) -> bool:
        """Check if service problem is acknowledged."""
        return service_data.get('acknowledged', False)
    
    def _is_service_in_downtime(self, service_data: Dict[str, Any]) -> bool:
        """Check if service is in scheduled downtime."""
        return service_data.get('in_downtime', False)
    
    def _is_service_urgent(self, service_data: Dict[str, Any]) -> bool:
        """Check if service problem is urgent."""
        state = self._get_service_state_from_data(service_data)
        
        # Critical services are always urgent
        if state == ServiceState.CRITICAL:
            return True
        
        # Unacknowledged warnings that have been ongoing
        if state == ServiceState.WARNING and not self._is_service_acknowledged(service_data):
            last_change = service_data.get('last_state_change')
            if last_change:
                hours_ago = (datetime.now() - datetime.fromtimestamp(last_change)).total_seconds() / 3600
                if hours_ago > 6:  # Warning for more than 6 hours
                    return True
        
        return False
    
    def _format_duration(self, duration: timedelta) -> str:
        """Format duration in human-readable format."""
        days = duration.days
        hours, remainder = divmod(duration.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        
        if days > 0:
            return f"{days}d {hours}h {minutes}m"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"
    
    def _apply_problem_filters(self, problems: List[ServiceProblem], severity: Optional[str], category: Optional[str]) -> List[ServiceProblem]:
        """Apply filtering to problems list."""
        filtered = problems
        
        if severity:
            severity_enum = ProblemSeverity(severity.upper())
            filtered = [p for p in filtered if p.severity == severity_enum]
        
        if category:
            category_enum = ProblemCategory(category.lower())
            filtered = [p for p in filtered if p.category == category_enum]
        
        return filtered
    
    def _apply_comprehensive_filters(self, problems: List[ServiceProblem], filters: StatusFilterOptions) -> List[ServiceProblem]:
        """Apply comprehensive filtering based on StatusFilterOptions."""
        filtered = problems
        
        # State filter
        if filters.state_filter:
            filtered = [p for p in filtered if p.state in filters.state_filter]
        
        # Severity filter
        if filters.severity_filter:
            filtered = [p for p in filtered if p.severity in filters.severity_filter]
        
        # Category filter
        if filters.category_filter:
            filtered = [p for p in filtered if p.category in filters.category_filter]
        
        # Service filter
        if filters.service_filter:
            filtered = self._apply_text_filter(filtered, filters.service_filter, ["service_name"])
        
        # Time-based filters
        if filters.problems_since:
            filtered = [p for p in filtered if p.last_state_change >= filters.problems_since]
        
        # Acknowledgment filter
        if filters.acknowledged_filter is not None:
            filtered = [p for p in filtered if p.acknowledged == filters.acknowledged_filter]
        
        # Downtime filter
        if filters.downtime_filter is not None:
            filtered = [p for p in filtered if p.in_downtime == filters.downtime_filter]
        
        return filtered
    
    def _sort_problems(self, problems: List[ServiceProblem], sort_by: str, sort_order: str) -> List[ServiceProblem]:
        """Sort problems by specified criteria."""
        reverse = sort_order.lower() == "desc"
        
        if sort_by == "urgency":
            return sorted(problems, key=lambda p: p.urgency_score, reverse=reverse)
        elif sort_by == "severity":
            priority_map = {ProblemSeverity.CRITICAL: 3, ProblemSeverity.WARNING: 2, ProblemSeverity.UNKNOWN: 1}
            return sorted(problems, key=lambda p: priority_map.get(p.severity, 0), reverse=reverse)
        elif sort_by == "duration":
            return sorted(problems, key=lambda p: p.last_state_change, reverse=not reverse)  # Older problems first for asc
        elif sort_by == "host":
            return sorted(problems, key=lambda p: p.host_name, reverse=reverse)
        elif sort_by == "service":
            return sorted(problems, key=lambda p: p.service_name, reverse=reverse)
        else:
            return problems
    
    def _generate_health_recommendations(self, problem_summary: ProblemSummary, critical_problems: List[ServiceProblem]) -> List[str]:
        """Generate maintenance recommendations based on current status."""
        recommendations = []
        
        if critical_problems:
            recommendations.append(f"Address {len(critical_problems)} critical service(s) immediately")
        
        if problem_summary.unacknowledged_problems > 5:
            recommendations.append("Review and acknowledge known issues to reduce noise")
        
        # Category-specific recommendations
        categories = problem_summary.problems_by_category
        if categories.get(ProblemCategory.DISK.value, 0) > 3:
            recommendations.append("Multiple disk issues detected - consider storage maintenance")
        
        if categories.get(ProblemCategory.PERFORMANCE.value, 0) > 3:
            recommendations.append("Performance issues detected - review system capacity")
        
        return recommendations
    
    def _generate_health_alerts(self, critical_problems: List[ServiceProblem], urgent_problems: List[ServiceProblem]) -> List[str]:
        """Generate important alerts based on current status."""
        alerts = []
        
        if len(critical_problems) > 10:
            alerts.append("⚠️ Large number of critical services - possible infrastructure issue")
        
        if len(urgent_problems) > 20:
            alerts.append("⚠️ Many urgent problems require attention")
        
        # Check for patterns in urgent problems
        if urgent_problems:
            hosts_with_problems = set(p.host_name for p in urgent_problems)
            if len(hosts_with_problems) == 1:
                alerts.append(f"⚠️ All urgent problems on single host: {list(hosts_with_problems)[0]}")
        
        return alerts
    
    def _calculate_health_trend(self, problem_summary: ProblemSummary) -> str:
        """Calculate health trend based on recent changes."""
        # This is simplified - in a real implementation, you'd compare with historical data
        if problem_summary.new_problems_last_hour > problem_summary.resolved_problems_last_hour:
            return "degrading"
        elif problem_summary.resolved_problems_last_hour > problem_summary.new_problems_last_hour:
            return "improving"
        else:
            return "stable"
    
    def _calculate_data_freshness(self) -> str:
        """Calculate how fresh the dashboard data is."""
        # In a real implementation, this would check the age of the data
        return "Real-time"
    
    async def get_critical_problems(
        self,
        severity_filter: Optional[List[str]] = None,
        category_filter: Optional[List[str]] = None,
        include_acknowledged: bool = False
    ) -> ServiceResult[Dict[str, Any]]:
        """Get current critical problems requiring immediate attention."""
        # Use existing list_problems method with individual parameters
        severity = severity_filter[0] if severity_filter and len(severity_filter) > 0 else "CRITICAL"
        category = category_filter[0] if category_filter and len(category_filter) > 0 else None
        
        problems_result = await self.list_problems(
            severity=severity,
            category=category
        )
        
        if problems_result.success:
            # Convert list result to summary format
            problems = problems_result.data
            summary = {
                "total_problems": len(problems),
                "critical_problems": len([p for p in problems if p.severity == ProblemSeverity.CRITICAL]),
                "warning_problems": len([p for p in problems if p.severity == ProblemSeverity.WARNING]),
                "problems": [
                    {
                        "host_name": p.host_name,
                        "service_name": p.service_name,
                        "state": p.state.value,
                        "severity": p.severity.value,
                        "output": p.plugin_output,
                        "acknowledged": p.acknowledged
                    }
                    for p in problems[:20]  # Limit to 20 problems
                ]
            }
            return ServiceResult(success=True, data=summary)
        else:
            return problems_result
    
    async def get_performance_metrics(self) -> ServiceResult[Dict[str, Any]]:
        """Get real-time performance metrics and trends."""
        async def _metrics_operation():
            # For now, return mock data structure
            # In real implementation, would aggregate performance data
            return {
                "cpu_usage": {"current": 45.2, "trend": "stable", "threshold": 80},
                "memory_usage": {"current": 62.5, "trend": "increasing", "threshold": 90},
                "disk_usage": {"current": 78.3, "trend": "increasing", "threshold": 85},
                "network_throughput": {"in": 125.4, "out": 89.2, "unit": "Mbps"},
                "service_response_times": {"avg": 0.125, "p95": 0.450, "p99": 1.200, "unit": "seconds"},
                "timestamp": datetime.now().isoformat()
            }
        
        return await self._execute_with_error_handling(_metrics_operation)
    
    async def analyze_host_health(
        self,
        host_name: str,
        include_grade: bool = True,
        include_recommendations: bool = True,
        compare_to_peers: bool = False
    ) -> ServiceResult[Dict[str, Any]]:
        """Analyze the health of a specific host with recommendations."""
        async def _analyze_operation():
            # Get host services
            services_data = await self.checkmk.list_host_services(host_name)
            services = services_data.get('value', [])
            
            # Calculate health metrics
            total = len(services)
            states = {"ok": 0, "warning": 0, "critical": 0, "unknown": 0}
            problems = []
            
            for service in services:
                state = self._get_service_state_from_data(service)
                if state == ServiceState.OK:
                    states["ok"] += 1
                elif state == ServiceState.WARNING:
                    states["warning"] += 1
                elif state == ServiceState.CRITICAL:
                    states["critical"] += 1
                    problems.append(service.get('title', 'Unknown service'))
                else:
                    states["unknown"] += 1
            
            health_percentage = (states["ok"] / total * 100) if total > 0 else 0
            grade = self._get_health_grade(health_percentage) if include_grade else None
            
            result = {
                "host_name": host_name,
                "health_percentage": health_percentage,
                "grade": grade,
                "service_states": states,
                "total_services": total,
                "critical_services": problems[:5],  # Top 5 critical
                "timestamp": datetime.now().isoformat()
            }
            
            if include_recommendations:
                result["recommendations"] = self._generate_host_recommendations(states, problems)
            
            if compare_to_peers:
                result["peer_comparison"] = {
                    "average_health": 85.0,  # Mock data
                    "ranking": "Above Average" if health_percentage > 85 else "Below Average"
                }
            
            return result
        
        return await self._execute_with_error_handling(_analyze_operation)
    
    async def get_host_problems(
        self,
        host_name: str,
        include_services: bool = True
    ) -> ServiceResult[Dict[str, Any]]:
        """Get problems for a specific host."""
        problems_result = await self.list_problems(host_filter=host_name)
        
        if problems_result.success:
            problems = problems_result.data
            result = {
                "host_name": host_name,
                "problem_count": len(problems),
                "problems_by_severity": {
                    "critical": len([p for p in problems if p.severity == ProblemSeverity.CRITICAL]),
                    "warning": len([p for p in problems if p.severity == ProblemSeverity.WARNING]),
                    "unknown": len([p for p in problems if p.severity == ProblemSeverity.UNKNOWN])
                }
            }
            
            if include_services and problems:
                result["problem_services"] = [
                    {
                        "service_name": p.service_name,
                        "state": p.state.value,
                        "output": p.plugin_output,
                        "duration": str(datetime.now() - p.last_state_change)
                    }
                    for p in problems[:10]  # Limit to 10
                ]
            
            return ServiceResult(success=True, data=result)
        else:
            return problems_result
    
    async def get_infrastructure_summary(
        self,
        include_trends: bool = True,
        time_range_hours: int = 24
    ) -> ServiceResult[Dict[str, Any]]:
        """Get comprehensive infrastructure summary."""
        dashboard_result = await self.get_health_dashboard()
        
        if dashboard_result.success:
            summary = {
                "total_hosts": dashboard_result.data.total_hosts,
                "hosts_up": dashboard_result.data.hosts_up,
                "hosts_down": dashboard_result.data.hosts_down,
                "total_services": dashboard_result.data.total_services,
                "services_ok": dashboard_result.data.services_ok,
                "services_warning": dashboard_result.data.services_warning,
                "services_critical": dashboard_result.data.services_critical,
                "services_unknown": dashboard_result.data.services_unknown,
                "overall_health": dashboard_result.data.overall_health_percentage,
                "timestamp": datetime.now().isoformat()
            }
            
            if include_trends:
                # Mock trend data - in real implementation would analyze historical data
                summary["trends"] = {
                    "health_trend": "stable",
                    "new_problems_last_hour": dashboard_result.data.problem_summary.new_problems_last_hour,
                    "resolved_last_hour": dashboard_result.data.problem_summary.resolved_problems_last_hour,
                    "time_range_hours": time_range_hours
                }
            
            return ServiceResult(success=True, data=summary)
        else:
            return dashboard_result
    
    async def get_problem_trends(
        self,
        time_range_hours: int = 24,
        category_breakdown: bool = True
    ) -> ServiceResult[Dict[str, Any]]:
        """Get problem trends over time."""
        problems_result = await self.list_problems()
        
        if problems_result.success:
            problems = problems_result.data
            trends = {
                "time_range_hours": time_range_hours,
                "current_problems": len(problems),
                "new_problems": 0,  # Mock data - would need historical tracking
                "resolved_problems": 0,  # Mock data - would need historical tracking
                "trend": "stable",  # Mock data
                "timestamp": datetime.now().isoformat()
            }
            
            if category_breakdown:
                category_counts = {}
                for problem in problems:
                    cat = problem.category.value
                    category_counts[cat] = category_counts.get(cat, 0) + 1
                trends["problems_by_category"] = category_counts
            
            return ServiceResult(success=True, data=trends)
        else:
            return problems_result
    
    def _generate_host_recommendations(self, states: Dict[str, int], problems: List[str]) -> List[str]:
        """Generate recommendations for a specific host."""
        recommendations = []
        
        if states["critical"] > 0:
            recommendations.append(f"Address {states['critical']} critical service(s) immediately")
        
        if states["warning"] > 5:
            recommendations.append("High number of warnings - schedule maintenance window")
        
        if states["unknown"] > 0:
            recommendations.append("Investigate unknown service states - possible monitoring issues")
        
        # Pattern detection
        if any("disk" in p.lower() or "filesystem" in p.lower() for p in problems):
            recommendations.append("Disk-related issues detected - check storage capacity")
        
        if any("cpu" in p.lower() or "load" in p.lower() for p in problems):
            recommendations.append("Performance issues detected - review system load")
        
        return recommendations[:5]  # Limit to 5 recommendations