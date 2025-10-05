import redis
import json
import logging
from typing import Any, Dict, Optional, List
from datetime import datetime, timedelta
import pickle
import os
from functools import wraps
import asyncio

logger = logging.getLogger(__name__)

class RedisCacheService:
    """Enhanced Redis caching service with TTL management and async support"""
    
    def __init__(self):
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        try:
            self.redis_client = redis.from_url(redis_url, decode_responses=False)
            # Test connection
            self.redis_client.ping()
            logger.info("Redis connection established successfully")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}. Using in-memory fallback.")
            self.redis_client = None
            self.memory_cache = {}
        
        # Cache TTL configurations (in seconds)
        self.ttl_config = {
            'sensor_data': 300,           # 5 minutes
            'purpleair_sensors': 600,     # 10 minutes  
            'sensor_community': 900,      # 15 minutes
            'openaq_data': 1200,          # 20 minutes
            'nasa_satellite': 3600,       # 1 hour
            'weather_data': 1800,         # 30 minutes
            'gibs_layers': 86400,         # 24 hours
            'heatmap_tiles': 1800,        # 30 minutes
            'analysis_results': 7200,     # 2 hours
            'calibration_params': 43200,  # 12 hours
        }
    
    async def get(self, key: str, cache_type: str = 'default') -> Optional[Any]:
        """Get value from cache with async support"""
        try:
            if self.redis_client:
                # Use Redis
                cached_data = self.redis_client.get(key)
                if cached_data:
                    try:
                        return pickle.loads(cached_data)
                    except (pickle.PickleError, EOFError):
                        # Try JSON fallback
                        try:
                            return json.loads(cached_data.decode('utf-8'))
                        except (json.JSONDecodeError, UnicodeDecodeError):
                            logger.warning(f"Failed to deserialize cached data for key: {key}")
                            return None
            else:
                # Use memory fallback
                if key in self.memory_cache:
                    cached_item = self.memory_cache[key]
                    # Check if expired
                    if datetime.now() < cached_item['expires_at']:
                        return cached_item['data']
                    else:
                        del self.memory_cache[key]
            
            return None
            
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            return None
    
    async def set(self, key: str, value: Any, cache_type: str = 'default', 
                  custom_ttl: Optional[int] = None) -> bool:
        """Set value in cache with TTL"""
        try:
            ttl = custom_ttl or self.ttl_config.get(cache_type, 300)
            
            if self.redis_client:
                # Use Redis with pickle for complex objects
                try:
                    serialized_data = pickle.dumps(value)
                    self.redis_client.setex(key, ttl, serialized_data)
                except pickle.PickleError:
                    # Fallback to JSON for simple objects
                    try:
                        serialized_data = json.dumps(value)
                        self.redis_client.setex(key, ttl, serialized_data)
                    except (TypeError, ValueError):
                        logger.warning(f"Failed to serialize data for key: {key}")
                        return False
            else:
                # Use memory fallback
                expires_at = datetime.now() + timedelta(seconds=ttl)
                self.memory_cache[key] = {
                    'data': value,
                    'expires_at': expires_at
                }
                
                # Clean up expired entries periodically
                await self._cleanup_memory_cache()
            
            return True
            
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete value from cache"""
        try:
            if self.redis_client:
                self.redis_client.delete(key)
            else:
                self.memory_cache.pop(key, None)
            return True
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            return False
    
    async def get_or_set(self, key: str, fetch_function, cache_type: str = 'default', 
                        custom_ttl: Optional[int] = None) -> Any:
        """Get from cache or fetch and set if not found"""
        try:
            # Try to get from cache first
            cached_value = await self.get(key, cache_type)
            if cached_value is not None:
                logger.debug(f"Cache hit for key: {key}")
                return cached_value
            
            # Cache miss - fetch data
            logger.debug(f"Cache miss for key: {key}, fetching fresh data")
            fresh_data = await fetch_function()
            
            # Store in cache
            await self.set(key, fresh_data, cache_type, custom_ttl)
            return fresh_data
            
        except Exception as e:
            logger.error(f"Cache get_or_set error for key {key}: {e}")
            # If caching fails, still return fresh data
            try:
                return await fetch_function()
            except Exception as fetch_error:
                logger.error(f"Both cache and fetch failed for key {key}: {fetch_error}")
                raise
    
    async def _cleanup_memory_cache(self):
        """Clean up expired entries in memory cache"""
        if not hasattr(self, 'memory_cache'):
            return
        
        now = datetime.now()
        expired_keys = [
            key for key, item in self.memory_cache.items()
            if now >= item['expires_at']
        ]
        
        for key in expired_keys:
            del self.memory_cache[key]
        
        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
    
    def generate_cache_key(self, prefix: str, params: Dict) -> str:
        """Generate standardized cache key"""
        # Sort parameters for consistent key generation
        sorted_params = sorted(params.items())
        param_str = "_".join([f"{k}={v}" for k, v in sorted_params])
        return f"{prefix}:{param_str}"
    
    async def clear_pattern(self, pattern: str) -> int:
        """Clear all keys matching pattern"""
        try:
            if self.redis_client:
                keys = self.redis_client.keys(pattern)
                if keys:
                    count = self.redis_client.delete(*keys)
                    logger.info(f"Cleared {count} cache entries matching pattern: {pattern}")
                    return count
            else:
                # Memory cache pattern matching
                matching_keys = [key for key in self.memory_cache.keys() if pattern.replace('*', '') in key]
                for key in matching_keys:
                    del self.memory_cache[key]
                return len(matching_keys)
            return 0
        except Exception as e:
            logger.error(f"Error clearing cache pattern {pattern}: {e}")
            return 0
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        try:
            if self.redis_client:
                info = self.redis_client.info()
                return {
                    'type': 'redis',
                    'connected_clients': info.get('connected_clients', 0),
                    'used_memory': info.get('used_memory_human', 'Unknown'),
                    'keyspace_hits': info.get('keyspace_hits', 0),
                    'keyspace_misses': info.get('keyspace_misses', 0),
                    'hit_rate': info.get('keyspace_hits', 0) / max(1, info.get('keyspace_hits', 0) + info.get('keyspace_misses', 0))
                }
            else:
                return {
                    'type': 'memory',
                    'cached_keys': len(self.memory_cache),
                    'memory_usage': 'In-memory fallback'
                }
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {'type': 'error', 'message': str(e)}

# Singleton instance
cache_service = RedisCacheService()
