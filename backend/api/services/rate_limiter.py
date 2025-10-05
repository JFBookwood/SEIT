import asyncio
import time
import logging
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict, deque
import random

logger = logging.getLogger(__name__)

@dataclass
class RateLimitConfig:
    """Configuration for rate limiting"""
    requests_per_second: float = 1.0
    burst_capacity: int = 5
    max_backoff_seconds: float = 300.0  # 5 minutes
    base_backoff_seconds: float = 1.0
    jitter_factor: float = 0.1

class ExponentialBackoffRateLimiter:
    """Advanced rate limiter with exponential backoff and jitter"""
    
    def __init__(self, service_name: str, config: RateLimitConfig):
        self.service_name = service_name
        self.config = config
        
        # Track request timestamps for rate limiting
        self.request_timestamps = deque(maxlen=config.burst_capacity * 2)
        
        # Track consecutive failures for backoff
        self.consecutive_failures = 0
        self.last_failure_time = None
        self.current_backoff = config.base_backoff_seconds
        
        # Lock for thread safety
        self._lock = asyncio.Lock()
    
    async def acquire(self) -> Tuple[bool, float]:
        """
        Acquire permission to make request
        Returns: (allowed, wait_time)
        """
        async with self._lock:
            now = time.time()
            
            # Check if we're in backoff period
            if self.last_failure_time:
                time_since_failure = now - self.last_failure_time
                if time_since_failure < self.current_backoff:
                    wait_time = self.current_backoff - time_since_failure
                    logger.debug(f"{self.service_name}: In backoff period, wait {wait_time:.2f}s")
                    return False, wait_time
            
            # Clean old timestamps
            cutoff_time = now - 1.0  # Keep timestamps from last second
            while self.request_timestamps and self.request_timestamps[0] <= cutoff_time:
                self.request_timestamps.popleft()
            
            # Check rate limit
            current_rate = len(self.request_timestamps)
            
            if current_rate >= self.config.requests_per_second:
                # Rate limit exceeded
                oldest_request = self.request_timestamps[0] if self.request_timestamps else now
                wait_time = 1.0 - (now - oldest_request)
                logger.debug(f"{self.service_name}: Rate limit exceeded, wait {wait_time:.2f}s")
                return False, max(0.1, wait_time)
            
            # Check burst capacity
            if len(self.request_timestamps) >= self.config.burst_capacity:
                wait_time = 1.0 / self.config.requests_per_second
                logger.debug(f"{self.service_name}: Burst capacity exceeded, wait {wait_time:.2f}s")
                return False, wait_time
            
            # Request allowed
            self.request_timestamps.append(now)
            return True, 0.0
    
    async def report_success(self):
        """Report successful request to reset backoff"""
        async with self._lock:
            if self.consecutive_failures > 0:
                logger.info(f"{self.service_name}: Request succeeded, resetting backoff")
                self.consecutive_failures = 0
                self.last_failure_time = None
                self.current_backoff = self.config.base_backoff_seconds
    
    async def report_failure(self):
        """Report failed request to trigger backoff"""
        async with self._lock:
            self.consecutive_failures += 1
            self.last_failure_time = time.time()
            
            # Calculate exponential backoff with jitter
            base_backoff = self.config.base_backoff_seconds * (2 ** (self.consecutive_failures - 1))
            jitter = random.uniform(-self.config.jitter_factor, self.config.jitter_factor) * base_backoff
            self.current_backoff = min(
                self.config.max_backoff_seconds,
                base_backoff + jitter
            )
            
            logger.warning(f"{self.service_name}: Failure #{self.consecutive_failures}, "
                         f"backoff for {self.current_backoff:.2f}s")
    
    def get_status(self) -> Dict:
        """Get current rate limiter status"""
        now = time.time()
        recent_requests = len([ts for ts in self.request_timestamps if now - ts <= 1.0])
        
        return {
            'service': self.service_name,
            'recent_requests_per_second': recent_requests,
            'consecutive_failures': self.consecutive_failures,
            'current_backoff_seconds': self.current_backoff,
            'in_backoff': bool(self.last_failure_time and 
                             (now - self.last_failure_time) < self.current_backoff),
            'requests_in_burst_window': len(self.request_timestamps)
        }

class GlobalRateLimitManager:
    """Global manager for all API rate limiters"""
    
    def __init__(self):
        self.limiters = {}
        
        # Service-specific configurations
        self.service_configs = {
            'purpleair': RateLimitConfig(
                requests_per_second=0.5,   # Conservative for PurpleAir
                burst_capacity=3,
                max_backoff_seconds=600.0  # 10 minutes max
            ),
            'sensor_community': RateLimitConfig(
                requests_per_second=1.0,   # More permissive
                burst_capacity=5,
                max_backoff_seconds=300.0  # 5 minutes max
            ),
            'openaq': RateLimitConfig(
                requests_per_second=2.0,   # Higher rate for OpenAQ
                burst_capacity=8,
                max_backoff_seconds=180.0  # 3 minutes max
            ),
            'nasa_gibs': RateLimitConfig(
                requests_per_second=2.0,   # GIBS is generally permissive
                burst_capacity=10,
                max_backoff_seconds=120.0  # 2 minutes max
            ),
            'nasa_cmr': RateLimitConfig(
                requests_per_second=1.0,   # Conservative for CMR
                burst_capacity=5,
                max_backoff_seconds=300.0  # 5 minutes max
            ),
            'open_meteo': RateLimitConfig(
                requests_per_second=5.0,   # Open-Meteo is very permissive
                burst_capacity=15,
                max_backoff_seconds=60.0   # 1 minute max
            )
        }
    
    def get_limiter(self, service_name: str) -> ExponentialBackoffRateLimiter:
        """Get or create rate limiter for service"""
        if service_name not in self.limiters:
            config = self.service_configs.get(service_name, RateLimitConfig())
            self.limiters[service_name] = ExponentialBackoffRateLimiter(service_name, config)
        
        return self.limiters[service_name]
    
    async def with_rate_limit(self, service_name: str, fetch_function):
        """Execute function with rate limiting"""
        limiter = self.get_limiter(service_name)
        
        # Wait for rate limit clearance
        while True:
            allowed, wait_time = await limiter.acquire()
            if allowed:
                break
            
            logger.debug(f"Rate limited for {service_name}, waiting {wait_time:.2f}s")
            await asyncio.sleep(wait_time)
        
        # Execute the function
        try:
            result = await fetch_function()
            await limiter.report_success()
            return result
        except Exception as e:
            await limiter.report_failure()
            raise
    
    def get_all_status(self) -> Dict:
        """Get status of all rate limiters"""
        return {
            service: limiter.get_status() 
            for service, limiter in self.limiters.items()
        }

# Global rate limit manager
rate_limit_manager = GlobalRateLimitManager()

def rate_limited(service_name: str):
    """Decorator for rate-limited async functions"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await rate_limit_manager.with_rate_limit(
                service_name, 
                lambda: func(*args, **kwargs)
            )
        return wrapper
    return decorator
