"""Tests for caching functionality."""

import pytest
import asyncio
import time
import logging
from unittest.mock import AsyncMock, Mock

from checkmk_agent.services.cache import (
    LRUCache, CacheEntry, CacheStats, CachingService, CachedHostService
)
from checkmk_agent.config import AppConfig


class MockCachingService(CachingService):
    """Mock service for testing caching functionality."""
    
    def __init__(self, config, *args, **kwargs):
        # Initialize the cache components directly since there's no meaningful parent
        self._cache = LRUCache(max_size=kwargs.get('cache_size', 1000), 
                             default_ttl=kwargs.get('cache_ttl', 300))
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.config = config
        self.call_count = 0
    
    async def expensive_operation(self, param: str):
        """Mock expensive operation for testing."""
        self.call_count += 1
        await asyncio.sleep(0.01)  # Simulate work
        return f"result_{param}_{self.call_count}"


@pytest.fixture
def cache():
    """Create a test cache."""
    return LRUCache(max_size=5, default_ttl=60)


@pytest.fixture
def mock_config():
    """Mock configuration."""
    return Mock(spec=AppConfig)


class TestCacheEntry:
    """Test CacheEntry functionality."""
    
    def test_cache_entry_creation(self):
        """Test creating a cache entry."""
        entry = CacheEntry(key="test_key", value="test_value")
        
        assert entry.key == "test_key"
        assert entry.value == "test_value"
        assert entry.access_count == 0
        assert not entry.is_expired()
    
    def test_cache_entry_expiration(self):
        """Test cache entry expiration."""
        # Create entry that expires immediately
        entry = CacheEntry(
            key="test_key",
            value="test_value",
            expires_at=time.time() - 1
        )
        
        assert entry.is_expired()
    
    def test_cache_entry_access(self):
        """Test cache entry access tracking."""
        entry = CacheEntry(key="test_key", value="test_value")
        
        # Access the entry
        value = entry.access()
        
        assert value == "test_value"
        assert entry.access_count == 1
        assert entry.last_accessed > entry.created_at


class TestLRUCache:
    """Test LRUCache functionality."""
    
    @pytest.mark.asyncio
    async def test_cache_set_get(self, cache):
        """Test basic cache set and get operations."""
        await cache.set("key1", "value1")
        
        result = await cache.get("key1")
        assert result == "value1"
        
        # Test miss
        result = await cache.get("nonexistent")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_cache_expiration(self, cache):
        """Test cache entry expiration."""
        # Set with short TTL
        await cache.set("key1", "value1", ttl=0.1)
        
        # Should exist immediately
        result = await cache.get("key1")
        assert result == "value1"
        
        # Wait for expiration
        await asyncio.sleep(0.2)
        
        # Should be expired
        result = await cache.get("key1")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_cache_lru_eviction(self, cache):
        """Test LRU eviction when cache is full."""
        # Fill cache to capacity (5 items)
        for i in range(5):
            await cache.set(f"key{i}", f"value{i}")
        
        # All items should be present
        for i in range(5):
            assert await cache.get(f"key{i}") == f"value{i}"
        
        # Add one more item (should evict oldest)
        await cache.set("key5", "value5")
        
        # First item should be evicted
        assert await cache.get("key0") is None
        assert await cache.get("key5") == "value5"
    
    @pytest.mark.asyncio
    async def test_cache_lru_ordering(self, cache):
        """Test LRU ordering is maintained."""
        # Add items
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        await cache.set("key3", "value3")
        
        # Access key1 (moves it to end)
        await cache.get("key1")
        
        # Add more items to trigger eviction
        await cache.set("key4", "value4")
        await cache.set("key5", "value5")
        await cache.set("key6", "value6")  # Should evict key2
        
        # key1 should still exist (was accessed recently)
        assert await cache.get("key1") == "value1"
        # key2 should be evicted (oldest unaccessed)
        assert await cache.get("key2") is None
    
    @pytest.mark.asyncio
    async def test_cache_invalidation(self, cache):
        """Test cache invalidation."""
        await cache.set("key1", "value1")
        assert await cache.get("key1") == "value1"
        
        # Invalidate
        result = await cache.invalidate("key1")
        assert result is True
        assert await cache.get("key1") is None
        
        # Invalidate non-existent key
        result = await cache.invalidate("nonexistent")
        assert result is False
    
    @pytest.mark.asyncio
    async def test_cache_clear(self, cache):
        """Test cache clearing."""
        # Add items
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        
        # Clear cache
        await cache.clear()
        
        # All items should be gone
        assert await cache.get("key1") is None
        assert await cache.get("key2") is None
    
    @pytest.mark.asyncio
    async def test_cache_cleanup_expired(self, cache):
        """Test cleanup of expired entries."""
        # Add items with different TTL
        await cache.set("key1", "value1", ttl=0.1)  # Short TTL
        await cache.set("key2", "value2", ttl=60)   # Long TTL
        
        # Wait for first item to expire
        await asyncio.sleep(0.2)
        
        # Cleanup expired entries
        cleaned = await cache.cleanup_expired()
        
        assert cleaned == 1
        assert await cache.get("key1") is None
        assert await cache.get("key2") == "value2"
    
    @pytest.mark.asyncio
    async def test_cache_stats(self, cache):
        """Test cache statistics."""
        # Add some items
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        
        # Generate hits and misses
        await cache.get("key1")  # Hit
        await cache.get("key1")  # Hit
        await cache.get("nonexistent")  # Miss
        
        stats = cache.get_stats()
        assert stats.hits == 2
        assert stats.misses == 1
        assert stats.hit_rate == 2/3
        assert stats.total_entries == 2


class TestCachingService:
    """Test CachingService functionality."""
    
    @pytest.fixture
    def caching_service(self, mock_config):
        """Create a caching service."""
        return MockCachingService(mock_config, cache_ttl=60, cache_size=10)
    
    @pytest.mark.asyncio
    async def test_cached_decorator(self, caching_service):
        """Test the cached decorator."""
        # Decorate method
        @caching_service.cached(ttl=60)
        async def test_method(self, param):
            return await self.expensive_operation(param)
        
        # Bind method to service
        bound_method = test_method.__get__(caching_service, MockCachingService)
        
        # First call should execute method
        result1 = await bound_method("test")
        assert caching_service.call_count == 1
        assert "result_test_1" in result1
        
        # Second call should use cache
        result2 = await bound_method("test")
        assert caching_service.call_count == 1  # No additional call
        assert result1 == result2
        
        # Different parameter should execute method
        result3 = await bound_method("other")
        assert caching_service.call_count == 2
        assert "result_other_2" in result3
    
    @pytest.mark.asyncio
    async def test_cache_invalidation_pattern(self, caching_service):
        """Test cache invalidation by pattern."""
        # Add some cached data
        await caching_service._cache.set("user:123:profile", "profile_data")
        await caching_service._cache.set("user:123:settings", "settings_data")
        await caching_service._cache.set("user:456:profile", "other_profile")
        await caching_service._cache.set("other:data", "other_data")
        
        # Invalidate user 123 data
        invalidated = await caching_service.invalidate_cache_pattern("user:123:*")
        
        assert invalidated == 2
        assert await caching_service._cache.get("user:123:profile") is None
        assert await caching_service._cache.get("user:123:settings") is None
        assert await caching_service._cache.get("user:456:profile") == "other_profile"
        assert await caching_service._cache.get("other:data") == "other_data"
    
    @pytest.mark.asyncio
    async def test_cache_stats_integration(self, caching_service):
        """Test cache statistics integration."""
        # Generate some cache activity
        await caching_service._cache.set("key1", "value1")
        await caching_service._cache.get("key1")  # Hit
        await caching_service._cache.get("missing")  # Miss
        
        stats = await caching_service.get_cache_stats()
        
        assert "hits" in stats
        assert "misses" in stats
        assert "hit_rate" in stats
        assert "total_entries" in stats


class TestCachedHostService:
    """Test CachedHostService functionality."""
    
    @pytest.fixture
    def cached_host_service(self, mock_config):
        """Create a cached host service."""
        mock_client = AsyncMock()
        return CachedHostService(mock_client, mock_config)
    
    @pytest.mark.asyncio
    async def test_cached_list_hosts(self, cached_host_service):
        """Test cached list_hosts method."""
        # Mock API response
        mock_response = {"hosts": ["host1", "host2"]}
        cached_host_service.checkmk.list_hosts = AsyncMock(return_value=mock_response)
        
        # First call should hit API
        result1 = await cached_host_service.list_hosts(search="test")
        assert cached_host_service.checkmk.list_hosts.call_count == 1
        assert result1 == mock_response
        
        # Second call with same parameters should use cache
        result2 = await cached_host_service.list_hosts(search="test")
        assert cached_host_service.checkmk.list_hosts.call_count == 1  # No additional call
        assert result1 == result2
        
        # Different parameters should hit API again
        result3 = await cached_host_service.list_hosts(search="other")
        assert cached_host_service.checkmk.list_hosts.call_count == 2
    
    @pytest.mark.asyncio
    async def test_cached_get_host(self, cached_host_service):
        """Test cached get_host method."""
        # Mock API response
        mock_response = {"name": "host1", "attributes": {}}
        cached_host_service.checkmk.get_host = AsyncMock(return_value=mock_response)
        
        # First call should hit API
        result1 = await cached_host_service.get_host("host1")
        assert cached_host_service.checkmk.get_host.call_count == 1
        
        # Second call should use cache
        result2 = await cached_host_service.get_host("host1")
        assert cached_host_service.checkmk.get_host.call_count == 1
        assert result1 == result2
    
    @pytest.mark.asyncio
    async def test_cache_invalidation_on_create(self, cached_host_service):
        """Test cache invalidation when creating hosts."""
        # Mock API responses
        cached_host_service.checkmk.list_hosts = AsyncMock(return_value={"hosts": []})
        cached_host_service.checkmk.create_host = AsyncMock(return_value={"id": "new_host"})
        
        # Cache some data
        await cached_host_service.list_hosts()
        assert cached_host_service.checkmk.list_hosts.call_count == 1
        
        # Create a new host (should invalidate cache)
        await cached_host_service.create_host("new_host")
        
        # Next list_hosts call should hit API again
        await cached_host_service.list_hosts()
        assert cached_host_service.checkmk.list_hosts.call_count == 2


@pytest.mark.asyncio
async def test_cache_concurrency():
    """Test cache behavior under concurrent access."""
    cache = LRUCache(max_size=10, default_ttl=60)
    
    async def concurrent_operation(i):
        key = f"key_{i % 5}"  # Create some overlap
        value = f"value_{i}"
        
        await cache.set(key, value)
        result = await cache.get(key)
        return result
    
    # Run concurrent operations
    tasks = [concurrent_operation(i) for i in range(20)]
    results = await asyncio.gather(*tasks)
    
    # All operations should complete successfully
    assert len(results) == 20
    assert all(result is not None for result in results)


@pytest.mark.asyncio
async def test_cache_memory_efficiency():
    """Test cache memory usage characteristics."""
    cache = LRUCache(max_size=1000, default_ttl=60)
    
    # Add many items
    for i in range(500):
        await cache.set(f"key_{i}", f"value_{i}")
    
    stats = cache.get_stats()
    assert stats.total_entries == 500
    
    # Add more items to trigger eviction
    for i in range(500, 1200):
        await cache.set(f"key_{i}", f"value_{i}")
    
    stats = cache.get_stats()
    assert stats.total_entries == 1000  # Should not exceed max_size
    assert stats.evictions > 0


@pytest.mark.asyncio
async def test_cache_error_handling():
    """Test cache behavior with errors."""
    service = MockCachingService(Mock())
    
    # Mock method that sometimes fails
    call_count = 0
    
    async def failing_method(param):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("First call fails")
        return f"success_{param}"
    
    # Decorate with cache
    @service.cached(ttl=60, invalidate_on_error=True)
    async def cached_failing_method(self, param):
        return await failing_method(param)
    
    bound_method = cached_failing_method.__get__(service, MockCachingService)
    
    # First call should fail and not cache
    with pytest.raises(Exception, match="First call fails"):
        await bound_method("test")
    
    # Second call should succeed and cache
    result = await bound_method("test")
    assert result == "success_test"
    assert call_count == 2
    
    # Third call should use cache
    result2 = await bound_method("test")
    assert result2 == "success_test"
    assert call_count == 2  # No additional call