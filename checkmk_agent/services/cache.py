"""Caching layer for frequently accessed data."""

import asyncio
import hashlib
import json
import logging
import time
from typing import Optional, Dict, Any, TypeVar, Generic, Callable, Union
from datetime import datetime, timedelta
from functools import wraps

from pydantic import BaseModel, Field
from .host_service import HostService


T = TypeVar('T')


class CacheEntry(BaseModel, Generic[T]):
    """A single cache entry with metadata."""
    key: str
    value: T
    created_at: float = Field(default_factory=time.time)
    expires_at: Optional[float] = None
    access_count: int = 0
    last_accessed: float = Field(default_factory=time.time)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    def is_expired(self) -> bool:
        """Check if this entry has expired."""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at
    
    def access(self) -> T:
        """Access the value and update metadata."""
        self.access_count += 1
        self.last_accessed = time.time()
        return self.value


class CacheStats(BaseModel):
    """Cache statistics."""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    expired_evictions: int = 0
    size_evictions: int = 0
    total_entries: int = 0
    memory_usage_bytes: int = 0
    
    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


class LRUCache:
    """Simple async-safe LRU cache implementation."""
    
    def __init__(self, max_size: int = 1000, default_ttl: int = 300):
        """
        Initialize LRU cache.
        
        Args:
            max_size: Maximum number of entries
            default_ttl: Default time-to-live in seconds
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = asyncio.Lock()
        self._stats = CacheStats()
        self.logger = logging.getLogger(__name__)
    
    def _make_key(self, *args, **kwargs) -> str:
        """Create a cache key from arguments."""
        key_data = {
            'args': args,
            'kwargs': sorted(kwargs.items())
        }
        key_str = json.dumps(key_data, sort_keys=True, default=str)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        async with self._lock:
            entry = self._cache.get(key)
            
            if entry is None:
                self._stats.misses += 1
                return None
            
            if entry.is_expired():
                # Remove expired entry
                del self._cache[key]
                self._stats.misses += 1
                self._stats.expired_evictions += 1
                return None
            
            # Move to end (most recently used)
            del self._cache[key]
            self._cache[key] = entry
            
            self._stats.hits += 1
            return entry.access()
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        ttl: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Set value in cache."""
        async with self._lock:
            # Calculate expiration
            ttl = ttl or self.default_ttl
            expires_at = time.time() + ttl if ttl > 0 else None
            
            # Create entry
            entry = CacheEntry(
                key=key,
                value=value,
                expires_at=expires_at,
                metadata=metadata or {}
            )
            
            # Remove oldest entry if at capacity
            if len(self._cache) >= self.max_size and key not in self._cache:
                # Remove least recently used (first item)
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
                self._stats.evictions += 1
                self._stats.size_evictions += 1
            
            # Add/update entry
            self._cache[key] = entry
            self._stats.total_entries = len(self._cache)
    
    async def invalidate(self, key: str) -> bool:
        """Remove entry from cache."""
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                self._stats.total_entries = len(self._cache)
                return True
            return False
    
    async def clear(self) -> None:
        """Clear all cache entries."""
        async with self._lock:
            self._cache.clear()
            self._stats.total_entries = 0
    
    async def cleanup_expired(self) -> int:
        """Remove all expired entries."""
        async with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.is_expired()
            ]
            
            for key in expired_keys:
                del self._cache[key]
                self._stats.expired_evictions += 1
            
            self._stats.total_entries = len(self._cache)
            return len(expired_keys)
    
    def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        return self._stats.model_copy()


class CachingService:
    """Mixin to add caching capabilities to services."""
    
    def __init__(self, *args, cache_ttl: int = 300, cache_size: int = 1000, **kwargs):
        # For multiple inheritance, let other classes handle their init first
        super().__init__(*args, **kwargs)
        self._cache = LRUCache(max_size=cache_size, default_ttl=cache_ttl)
        # Don't overwrite existing logger if it exists
        if not hasattr(self, 'logger'):
            self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def cached(
        self, 
        ttl: Optional[int] = None,
        key_prefix: Optional[str] = None,
        invalidate_on_error: bool = True
    ):
        """
        Decorator to cache async method results.
        
        Args:
            ttl: Time-to-live for cache entry (seconds)
            key_prefix: Optional prefix for cache key
            invalidate_on_error: Remove from cache if method raises exception
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Get the service instance from the outer scope
                service_instance = self
                
                # Build cache key
                base_key = service_instance._cache._make_key(*args, **kwargs)
                cache_key = f"{key_prefix}:{base_key}" if key_prefix else base_key
                
                # Try to get from cache
                cached_value = await service_instance._cache.get(cache_key)
                if cached_value is not None:
                    service_instance.logger.debug(f"Cache hit for {func.__name__}: {cache_key}")
                    return cached_value
                
                # Execute function
                try:
                    result = await func(*args, **kwargs)
                    
                    # Cache the result
                    await service_instance._cache.set(
                        cache_key, 
                        result, 
                        ttl=ttl,
                        metadata={
                            'function': func.__name__,
                            'args': str(args)[:100],
                            'kwargs': str(kwargs)[:100]
                        }
                    )
                    
                    return result
                    
                except Exception as e:
                    if invalidate_on_error:
                        await service_instance._cache.invalidate(cache_key)
                    raise
            
            return wrapper
        return decorator
    
    async def invalidate_cache_pattern(self, pattern: str) -> int:
        """
        Invalidate cache entries matching a pattern.
        
        Args:
            pattern: Pattern to match (simple wildcard support)
            
        Returns:
            Number of entries invalidated
        """
        invalidated = 0
        
        # Convert simple wildcards to regex
        import re
        regex_pattern = pattern.replace('*', '.*')
        regex = re.compile(regex_pattern)
        
        # Get all keys (need to copy to avoid modification during iteration)
        async with self._cache._lock:
            keys = list(self._cache._cache.keys())
        
        # Invalidate matching keys
        for key in keys:
            if regex.match(key):
                if await self._cache.invalidate(key):
                    invalidated += 1
        
        self.logger.info(f"Invalidated {invalidated} cache entries matching '{pattern}'")
        return invalidated
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        stats = self._cache.get_stats()
        return {
            'hits': stats.hits,
            'misses': stats.misses,
            'hit_rate': f"{stats.hit_rate:.2%}",
            'total_entries': stats.total_entries,
            'evictions': stats.evictions,
            'expired_evictions': stats.expired_evictions,
            'size_evictions': stats.size_evictions
        }


class CachedHostService(CachingService, HostService):
    """Example of cached service implementation."""
    
    @property
    def cached(self):
        """Access the decorator as a property to use instance cache."""
        return super().cached
    
    async def list_hosts(self, search: Optional[str] = None, folder: Optional[str] = None):
        """List hosts with caching."""
        @self.cached(ttl=60, key_prefix="list_hosts")
        async def _cached_list_hosts(search: Optional[str] = None, folder: Optional[str] = None):
            # Actual implementation
            return await self.checkmk.list_hosts(search=search, folder=folder)
        
        return await _cached_list_hosts(search, folder)
    
    async def get_host(self, name: str):
        """Get host details with caching."""
        @self.cached(ttl=300, key_prefix="get_host")
        async def _cached_get_host(name: str):
            # Actual implementation
            return await self.checkmk.get_host(name)
        
        return await _cached_get_host(name)
    
    async def create_host(self, name: str, **kwargs):
        """Create host and invalidate relevant caches."""
        result = await self.checkmk.create_host(name, **kwargs)
        
        # Invalidate affected caches
        await self.invalidate_cache_pattern("list_hosts:*")
        await self.invalidate_cache_pattern(f"get_host:*{name}*")
        
        return result