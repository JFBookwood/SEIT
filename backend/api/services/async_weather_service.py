import aiohttp
import asyncio
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging

from .redis_cache_service import cache_service
from .rate_limiter import rate_limited

logger = logging.getLogger(__name__)

class AsyncWeatherService:
    """Enhanced async weather service with caching and rate limiting"""
    
    def __init__(self):
        self.base_url = "https://api.open-meteo.com/v1"
        # Open-Meteo is free and doesn't require API keys
        
        self.session_config = {
            'timeout': aiohttp.ClientTimeout(total=30, connect=10),
            'connector': aiohttp.TCPConnector(
                limit=15,
                limit_per_host=8,
                keepalive_timeout=60,
                enable_cleanup_closed=True
            )
        }
    
    @rate_limited('open_meteo')
    async def get_current_weather_cached(self, latitude: float, longitude: float) -> Dict:
        """Get current weather with caching"""
        cache_key = cache_service.generate_cache_key(
            'weather_current',
            {'lat': round(latitude, 4), 'lon': round(longitude, 4)}
        )
        
        async def fetch_weather():
            return await self._fetch_current_weather(latitude, longitude)
        
        return await cache_service.get_or_set(
            cache_key,
            fetch_weather,
            cache_type='weather_data'
        )
    
    async def _fetch_current_weather(self, latitude: float, longitude: float) -> Dict:
        """Fetch current weather from Open-Meteo"""
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": [
                "temperature_2m",
                "relative_humidity_2m",
                "apparent_temperature",
                "precipitation",
                "weather_code",
                "cloud_cover",
                "surface_pressure",
                "wind_speed_10m",
                "wind_direction_10m"
            ]
        }
        
        async with aiohttp.ClientSession(**self.session_config) as session:
            url = f"{self.base_url}/forecast"
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    current = data.get("current", {})
                    
                    return {
                        "latitude": data.get("latitude"),
                        "longitude": data.get("longitude"),
                        "timestamp": current.get("time"),
                        "temperature": current.get("temperature_2m"),
                        "apparent_temperature": current.get("apparent_temperature"),
                        "humidity": current.get("relative_humidity_2m"),
                        "pressure": current.get("surface_pressure"),
                        "wind_speed": current.get("wind_speed_10m"),
                        "wind_direction": current.get("wind_direction_10m"),
                        "cloud_cover": current.get("cloud_cover"),
                        "weather_code": current.get("weather_code"),
                        "precipitation": current.get("precipitation", 0),
                        "source": "open_meteo"
                    }
                else:
                    raise aiohttp.ClientResponseError(
                        request_info=response.request_info,
                        history=response.history,
                        status=response.status
                    )
    
    @rate_limited('open_meteo')
    async def get_regional_weather_cached(self, bbox: List[float], grid_resolution: float = 0.5) -> List[Dict]:
        """Get weather for region with caching"""
        cache_key = cache_service.generate_cache_key(
            'weather_regional',
            {
                'bbox': '_'.join(map(str, bbox)),
                'resolution': grid_resolution
            }
        )
        
        async def fetch_regional():
            return await self._fetch_regional_weather(bbox, grid_resolution)
        
        return await cache_service.get_or_set(
            cache_key,
            fetch_regional,
            cache_type='weather_data'
        )
    
    async def _fetch_regional_weather(self, bbox: List[float], grid_resolution: float = 0.5) -> List[Dict]:
        """Fetch weather data for region using grid points"""
        west, south, east, north = bbox
        weather_points = []
        
        # Create grid of weather stations
        lat = south
        tasks = []
        
        while lat <= north:
            lng = west
            while lng <= east:
                task = self._fetch_current_weather(lat, lng)
                tasks.append(task)
                lng += grid_resolution
            lat += grid_resolution
        
        # Limit concurrent requests to avoid overwhelming the API
        semaphore = asyncio.Semaphore(5)  # Max 5 concurrent requests
        
        async def bounded_fetch(task):
            async with semaphore:
                try:
                    return await task
                except Exception as e:
                    logger.warning(f"Weather fetch failed for grid point: {e}")
                    return None
        
        bounded_tasks = [bounded_fetch(task) for task in tasks]
        results = await asyncio.gather(*bounded_tasks, return_exceptions=True)
        
        # Filter successful results
        for result in results:
            if result and not isinstance(result, Exception):
                weather_points.append(result)
        
        return weather_points
    
    async def batch_weather_fetch(self, coordinates: List[Tuple[float, float]]) -> Dict[Tuple, Dict]:
        """Fetch weather for multiple coordinates efficiently"""
        results = {}
        
        # Create tasks with semaphore for controlled concurrency
        semaphore = asyncio.Semaphore(8)  # Limit concurrent requests
        
        async def fetch_with_limit(lat: float, lon: float):
            async with semaphore:
                try:
                    return await self.get_current_weather_cached(lat, lon)
                except Exception as e:
                    logger.warning(f"Weather fetch failed for {lat}, {lon}: {e}")
                    return None
        
        tasks = {coords: fetch_with_limit(coords[0], coords[1]) for coords in coordinates}
        
        # Execute all tasks
        completed_tasks = await asyncio.gather(*tasks.values(), return_exceptions=True)
        
        # Map results back to coordinates
        for coords, result in zip(coordinates, completed_tasks):
            if result and not isinstance(result, Exception):
                results[coords] = result
        
        logger.info(f"Fetched weather for {len(results)}/{len(coordinates)} coordinates")
        return results
