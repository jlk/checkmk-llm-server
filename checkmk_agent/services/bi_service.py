"""Business Intelligence service - provides access to Checkmk BI aggregations and business logic."""

import logging
from typing import Optional, Dict, Any, List

from .base import BaseService, ServiceResult
from ..async_api_client import AsyncCheckmkClient
from ..api_client import CheckmkAPIError
from ..config import AppConfig


class BIAggregation:
    """Business Intelligence aggregation information."""
    
    def __init__(self, aggregation_id: str, aggregation_data: Dict[str, Any]):
        self.aggregation_id = aggregation_id
        self.state = aggregation_data.get('state', 'unknown')
        self.output = aggregation_data.get('output', '')
        self.acknowledged = aggregation_data.get('acknowledged', False)
        self.in_downtime = aggregation_data.get('in_downtime', False)
        self.scheduled_downtime_depth = aggregation_data.get('scheduled_downtime_depth', 0)
        self.in_service_period = aggregation_data.get('in_service_period', True)
        self.raw_data = aggregation_data


class BIPack:
    """Business Intelligence pack information."""
    
    def __init__(self, pack_data: Dict[str, Any]):
        self.id = pack_data.get('id', '')
        self.title = pack_data.get('title', '')
        self.contact_groups = pack_data.get('contact_groups', [])
        self.public = pack_data.get('public', False)
        self.aggregations = pack_data.get('aggregations', [])
        self.rules = pack_data.get('rules', [])
        self.raw_data = pack_data


class BIService(BaseService):
    """Business Intelligence service - provides access to BI aggregations and business logic."""
    
    def __init__(self, checkmk_client: AsyncCheckmkClient, config: AppConfig):
        super().__init__(checkmk_client, config)
        self.logger = logging.getLogger(__name__)
    
    async def get_bi_aggregation_states(
        self,
        filter_names: Optional[List[str]] = None,
        filter_groups: Optional[List[str]] = None
    ) -> ServiceResult[Dict[str, BIAggregation]]:
        """
        Get current state of BI aggregations.
        
        Args:
            filter_names: Optional list of aggregation names to filter by
            filter_groups: Optional list of group names to filter by
            
        Returns:
            ServiceResult containing dict of BIAggregation objects keyed by aggregation ID
        """
        async def _get_bi_aggregation_states_operation():
            # Build request parameters
            params = {}
            if filter_names:
                params['filter_names'] = filter_names
            if filter_groups:
                params['filter_groups'] = filter_groups
            
            # Make API request
            response = await self._make_api_request(
                'GET',
                '/domain-types/bi_aggregation/actions/aggregation_state/invoke',
                params=params
            )
            
            # Parse aggregation states
            aggregations = {}
            aggregation_data = response.get('aggregations', {})
            
            for agg_id, agg_state in aggregation_data.items():
                aggregations[agg_id] = BIAggregation(agg_id, agg_state)
            
            return aggregations
        
        return await self._execute_with_error_handling(
            _get_bi_aggregation_states_operation, 
            "get_bi_aggregation_states"
        )
    
    async def get_bi_aggregation_state(
        self,
        aggregation_name: str
    ) -> ServiceResult[BIAggregation]:
        """
        Get state of a specific BI aggregation.
        
        Args:
            aggregation_name: Name of the aggregation to query
            
        Returns:
            ServiceResult containing BIAggregation object
        """
        async def _get_bi_aggregation_state_operation():
            result = await self.get_bi_aggregation_states(filter_names=[aggregation_name])
            if not result.success:
                raise CheckmkAPIError(f"Failed to get BI aggregation state: {result.error}")
            
            aggregations = result.data
            if aggregation_name not in aggregations:
                raise CheckmkAPIError(f"BI aggregation '{aggregation_name}' not found")
            
            return aggregations[aggregation_name]
        
        return await self._execute_with_error_handling(
            _get_bi_aggregation_state_operation, 
            f"get_bi_aggregation_state_{aggregation_name}"
        )
    
    async def list_bi_packs(self) -> ServiceResult[List[BIPack]]:
        """
        List all available BI packs.
        
        Returns:
            ServiceResult containing list of BIPack objects
        """
        async def _list_bi_packs_operation():
            # Make API request
            response = await self._make_api_request(
                'GET',
                '/domain-types/bi_pack/collections/all'
            )
            
            # Parse BI packs
            packs = []
            for pack_data in response.get('value', []):
                packs.append(BIPack(pack_data))
            
            return packs
        
        return await self._execute_with_error_handling(_list_bi_packs_operation, "list_bi_packs")
    
    async def get_business_status_summary(
        self,
        filter_groups: Optional[List[str]] = None
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Get a business-level status summary from BI aggregations.
        
        Args:
            filter_groups: Optional list of groups to filter by
            
        Returns:
            ServiceResult containing business status summary
        """
        async def _get_business_status_summary_operation():
            # Get all aggregation states
            result = await self.get_bi_aggregation_states(filter_groups=filter_groups)
            if not result.success:
                raise CheckmkAPIError(f"Failed to get BI aggregation states: {result.error}")
            
            aggregations = result.data
            
            # Calculate summary statistics
            summary = {
                "total_aggregations": len(aggregations),
                "states": {"ok": 0, "warn": 0, "crit": 0, "unknown": 0},
                "acknowledged_count": 0,
                "in_downtime_count": 0,
                "critical_aggregations": [],
                "warning_aggregations": []
            }
            
            for agg_id, agg in aggregations.items():
                # Count states (map Checkmk states to our simplified states)
                state_map = {0: "ok", 1: "warn", 2: "crit"}
                state_name = state_map.get(agg.state, "unknown")
                summary["states"][state_name] += 1
                
                # Count special conditions
                if agg.acknowledged:
                    summary["acknowledged_count"] += 1
                if agg.in_downtime:
                    summary["in_downtime_count"] += 1
                
                # Track critical and warning aggregations
                if agg.state == 2:  # Critical
                    summary["critical_aggregations"].append({
                        "id": agg_id,
                        "output": agg.output,
                        "acknowledged": agg.acknowledged,
                        "in_downtime": agg.in_downtime
                    })
                elif agg.state == 1:  # Warning
                    summary["warning_aggregations"].append({
                        "id": agg_id,
                        "output": agg.output,
                        "acknowledged": agg.acknowledged,
                        "in_downtime": agg.in_downtime
                    })
            
            return summary
        
        return await self._execute_with_error_handling(
            _get_business_status_summary_operation,
            "get_business_status_summary"
        )
    
    async def get_critical_business_services(self) -> ServiceResult[List[Dict[str, Any]]]:
        """
        Get list of critical business services from BI aggregations.
        
        Returns:
            ServiceResult containing list of critical business services
        """
        async def _get_critical_business_services_operation():
            # Get all aggregation states
            result = await self.get_bi_aggregation_states()
            if not result.success:
                raise CheckmkAPIError(f"Failed to get BI aggregation states: {result.error}")
            
            aggregations = result.data
            critical_services = []
            
            for agg_id, agg in aggregations.items():
                if agg.state == 2:  # Critical state
                    critical_service = {
                        "aggregation_id": agg_id,
                        "state": "critical",
                        "output": agg.output,
                        "acknowledged": agg.acknowledged,
                        "in_downtime": agg.in_downtime,
                        "in_service_period": agg.in_service_period
                    }
                    critical_services.append(critical_service)
            
            # Sort by acknowledged status (unacknowledged first)
            critical_services.sort(key=lambda x: x["acknowledged"])
            
            return critical_services
        
        return await self._execute_with_error_handling(
            _get_critical_business_services_operation,
            "get_critical_business_services"
        )
    
    async def _make_api_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make an API request using the underlying client."""
        try:
            # Use the sync client through the async wrapper
            sync_client = self.checkmk.sync_client
            return sync_client._make_request(method, endpoint, **kwargs)
        except Exception as e:
            self.logger.error(f"BI API request failed: {e}")
            raise CheckmkAPIError(f"BI API request failed: {e}")