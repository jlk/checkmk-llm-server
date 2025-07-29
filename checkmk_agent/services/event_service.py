"""Event Console service - provides access to Checkmk Event Console for service history and event management."""

import logging
from typing import Optional, Dict, Any, List

from .base import BaseService, ServiceResult
from ..async_api_client import AsyncCheckmkClient
from ..api_client import CheckmkAPIError
from ..config import AppConfig


class EventInfo:
    """Event Console event information."""
    
    def __init__(self, event_data: Dict[str, Any]):
        self.event_id = event_data.get('id', '')
        self.host_name = event_data.get('extensions', {}).get('host_name', '')
        self.service_description = event_data.get('extensions', {}).get('service_description', '')
        self.application = event_data.get('extensions', {}).get('application', '')
        self.text = event_data.get('extensions', {}).get('text', '')
        self.state = event_data.get('extensions', {}).get('state', 'unknown')
        self.phase = event_data.get('extensions', {}).get('phase', 'open')
        self.first_time = event_data.get('extensions', {}).get('first', '')
        self.last_time = event_data.get('extensions', {}).get('last', '')
        self.count = event_data.get('extensions', {}).get('count', 1)
        self.comment = event_data.get('extensions', {}).get('comment', '')
        self.contact = event_data.get('extensions', {}).get('contact', '')
        self.raw_data = event_data


class EventService(BaseService):
    """Event Console service - provides access to event history and management."""
    
    def __init__(self, checkmk_client: AsyncCheckmkClient, config: AppConfig):
        super().__init__(checkmk_client, config)
        self.logger = logging.getLogger(__name__)
    
    async def list_events(
        self,
        query: Optional[Dict[str, Any]] = None,
        host: Optional[str] = None,
        application: Optional[str] = None,
        state: Optional[str] = None,
        phase: Optional[str] = None,
        site_id: Optional[str] = None
    ) -> ServiceResult[List[EventInfo]]:
        """
        List Event Console events with optional filtering.
        
        Args:
            query: Livestatus query expression for the eventconsoleevents table
            host: Filter by host name
            application: Filter by application name
            state: Filter by event state (ok, warning, critical, unknown)
            phase: Filter by event phase (open, ack)
            site_id: Filter by site ID
            
        Returns:
            ServiceResult containing list of EventInfo objects
        """
        async def _list_events_operation():
            # Build request parameters
            params = {}
            if query:
                params['query'] = query
            if host:
                params['host'] = host
            if application:
                params['application'] = application
            if state:
                params['state'] = state
            if phase:
                params['phase'] = phase
            if site_id:
                params['site_id'] = site_id
            
            # Use the API client's list_events method
            sync_client = self.checkmk.sync_client
            events_data = sync_client.list_events(**params)
            
            # Convert to EventInfo objects
            events = []
            for event_data in events_data:
                events.append(EventInfo(event_data))
            
            return events
        
        return await self._execute_with_error_handling(_list_events_operation, "list_events")
    
    async def get_event(self, event_id: str, site_id: Optional[str] = None) -> ServiceResult[EventInfo]:
        """
        Get specific event by ID.
        
        Args:
            event_id: Event ID
            site_id: Optional site ID
            
        Returns:
            ServiceResult containing EventInfo object
        """
        async def _get_event_operation():
            params = {}
            if site_id:
                params['site_id'] = site_id
            
            response = await self._make_api_request(
                'GET',
                f'/objects/event_console/{event_id}',
                params=params
            )
            
            return EventInfo(response)
        
        return await self._execute_with_error_handling(_get_event_operation, f"get_event_{event_id}")
    
    async def list_service_events(
        self,
        host_name: str,
        service_name: str,
        limit: int = 50,
        state_filter: Optional[str] = None
    ) -> ServiceResult[List[EventInfo]]:
        """
        List events for a specific service.
        
        Args:
            host_name: Host name
            service_name: Service name
            limit: Maximum number of events to return
            state_filter: Optional state filter (ok, warning, critical, unknown)
            
        Returns:
            ServiceResult containing list of EventInfo objects for the service
        """
        async def _list_service_events_operation():
            # Build query to filter events for this specific service
            query = {
                "op": "and",
                "expr": [
                    {"op": "=", "left": "eventconsoleevents.event_host", "right": host_name}
                ]
            }
            
            # Add service filter if service_name is not empty
            if service_name and service_name.strip():
                query["expr"].append({
                    "op": "~", "left": "eventconsoleevents.event_text", "right": service_name
                })
            
            # Add state filter if provided
            if state_filter:
                state_map = {"ok": "0", "warning": "1", "critical": "2", "unknown": "3"}
                if state_filter.lower() in state_map:
                    query["expr"].append({
                        "op": "=", "left": "eventconsoleevents.event_state", "right": state_map[state_filter.lower()]
                    })
            
            # Use the API client's list_events method directly
            sync_client = self.checkmk.sync_client
            events_data = sync_client.list_events(query=query, host=host_name)
            
            # Convert to EventInfo objects
            events = []
            for event_data in events_data:
                events.append(EventInfo(event_data))
            
            # Sort by time (most recent first) and limit
            events.sort(key=lambda e: e.last_time or e.first_time, reverse=True)
            if limit > 0:
                events = events[:limit]
            
            return events
        
        return await self._execute_with_error_handling(
            _list_service_events_operation, 
            f"list_service_events_{host_name}_{service_name}"
        )
    
    async def list_host_events(
        self,
        host_name: str,
        limit: int = 100,
        state_filter: Optional[str] = None
    ) -> ServiceResult[List[EventInfo]]:
        """
        List events for a specific host.
        
        Args:
            host_name: Host name
            limit: Maximum number of events to return
            state_filter: Optional state filter (ok, warning, critical, unknown)
            
        Returns:
            ServiceResult containing list of EventInfo objects for the host
        """
        async def _list_host_events_operation():
            # Build query to filter events for this host
            query = {
                "op": "=",
                "left": "eventconsoleevents.event_host",
                "right": host_name
            }
            
            # Add state filter if provided
            if state_filter:
                state_map = {"ok": "0", "warning": "1", "critical": "2", "unknown": "3"}
                if state_filter.lower() in state_map:
                    query = {
                        "op": "and",
                        "expr": [
                            query,
                            {"op": "=", "left": "eventconsoleevents.event_state", "right": state_map[state_filter.lower()]}
                        ]
                    }
            
            # Use the API client's list_events method directly
            sync_client = self.checkmk.sync_client
            events_data = sync_client.list_events(query=query, host=host_name)
            
            # Convert to EventInfo objects
            events = []
            for event_data in events_data:
                events.append(EventInfo(event_data))
            
            # Sort by time (most recent first) and limit
            events.sort(key=lambda e: e.last_time or e.first_time, reverse=True)
            if limit > 0:
                events = events[:limit]
            
            return events
        
        return await self._execute_with_error_handling(
            _list_host_events_operation, 
            f"list_host_events_{host_name}"
        )
    
    async def get_recent_critical_events(self, limit: int = 20) -> ServiceResult[List[EventInfo]]:
        """
        Get recent critical events across all hosts.
        
        Args:
            limit: Maximum number of events to return
            
        Returns:
            ServiceResult containing list of recent critical EventInfo objects
        """
        async def _get_recent_critical_events_operation():
            # Query for critical events
            query = {
                "op": "=",
                "left": "eventconsoleevents.event_state",
                "right": "2"  # Critical state
            }
            
            # Use the API client's list_events method directly
            sync_client = self.checkmk.sync_client
            events_data = sync_client.list_events(query=query, state="critical")
            
            # Convert to EventInfo objects
            events = []
            for event_data in events_data:
                events.append(EventInfo(event_data))
            
            # Sort by time (most recent first) and limit
            events.sort(key=lambda e: e.last_time or e.first_time, reverse=True)
            if limit > 0:
                events = events[:limit]
            
            return events
        
        return await self._execute_with_error_handling(_get_recent_critical_events_operation, "get_recent_critical_events")
    
    async def acknowledge_event(
        self,
        event_id: str,
        comment: str,
        contact: Optional[str] = None,
        site_id: Optional[str] = None
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Acknowledge an event in the Event Console.
        
        Args:
            event_id: Event ID to acknowledge
            comment: Comment for the acknowledgment
            contact: Optional contact name
            site_id: Optional site ID
            
        Returns:
            ServiceResult containing acknowledgment response
        """
        async def _acknowledge_event_operation():
            data = {
                "comment": comment
            }
            if contact:
                data["contact"] = contact
            if site_id:
                data["site_id"] = site_id
            
            response = await self._make_api_request(
                'POST',
                f'/objects/event_console/{event_id}/actions/update_and_acknowledge/invoke',
                json=data
            )
            
            return response
        
        return await self._execute_with_error_handling(
            _acknowledge_event_operation, 
            f"acknowledge_event_{event_id}"
        )
    
    async def change_event_state(
        self,
        event_id: str,
        new_state: str,
        comment: Optional[str] = None,
        site_id: Optional[str] = None
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Change the state of an event.
        
        Args:
            event_id: Event ID
            new_state: New state (ok, warning, critical, unknown)
            comment: Optional comment
            site_id: Optional site ID
            
        Returns:
            ServiceResult containing state change response
        """
        async def _change_event_state_operation():
            # Map state names to numbers
            state_map = {"ok": 0, "warning": 1, "critical": 2, "unknown": 3}
            if new_state.lower() not in state_map:
                raise ValueError(f"Invalid state: {new_state}. Must be one of: {list(state_map.keys())}")
            
            data = {
                "new_state": state_map[new_state.lower()]
            }
            if comment:
                data["comment"] = comment
            if site_id:
                data["site_id"] = site_id
            
            response = await self._make_api_request(
                'POST',
                f'/objects/event_console/{event_id}/actions/change_state/invoke',
                json=data
            )
            
            return response
        
        return await self._execute_with_error_handling(
            _change_event_state_operation, 
            f"change_event_state_{event_id}"
        )
    
    async def search_events(
        self,
        search_term: str,
        limit: int = 50,
        state_filter: Optional[str] = None,
        host_filter: Optional[str] = None
    ) -> ServiceResult[List[EventInfo]]:
        """
        Search events by text content.
        
        Args:
            search_term: Text to search for in event messages
            limit: Maximum number of events to return
            state_filter: Optional state filter (ok, warning, critical, unknown)
            host_filter: Optional host name filter
            
        Returns:
            ServiceResult containing list of matching EventInfo objects
        """
        async def _search_events_operation():
            # Build query with text search
            query_parts = [
                {"op": "~", "left": "eventconsoleevents.event_text", "right": search_term}
            ]
            
            # Add state filter if provided
            if state_filter:
                state_map = {"ok": "0", "warning": "1", "critical": "2", "unknown": "3"}
                if state_filter.lower() in state_map:
                    query_parts.append({
                        "op": "=", "left": "eventconsoleevents.event_state", "right": state_map[state_filter.lower()]
                    })
            
            # Add host filter if provided
            if host_filter:
                query_parts.append({
                    "op": "=", "left": "eventconsoleevents.event_host", "right": host_filter
                })
            
            # Combine query parts
            if len(query_parts) == 1:
                query = query_parts[0]
            else:
                query = {"op": "and", "expr": query_parts}
            
            # Use the API client's list_events method directly
            sync_client = self.checkmk.sync_client
            events_data = sync_client.list_events(query=query, host=host_filter, state=state_filter)
            
            # Convert to EventInfo objects
            events = []
            for event_data in events_data:
                events.append(EventInfo(event_data))
            
            # Sort by time (most recent first) and limit
            events.sort(key=lambda e: e.last_time or e.first_time, reverse=True)
            if limit > 0:
                events = events[:limit]
            
            return events
        
        return await self._execute_with_error_handling(_search_events_operation, f"search_events_{search_term}")
    
    async def _make_api_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make an API request using the underlying client."""
        # Since we don't have direct HTTP access in the async client,
        # we need to add these methods to the main API client
        # For now, we'll implement this as a fallback
        try:
            # Use the sync client through the async wrapper
            sync_client = self.checkmk.sync_client
            if method == 'GET':
                return sync_client._make_request(method, endpoint, **kwargs)
            else:
                return sync_client._make_request(method, endpoint, **kwargs)
        except Exception as e:
            self.logger.error(f"API request failed: {e}")
            raise CheckmkAPIError(f"Event Console API request failed: {e}")