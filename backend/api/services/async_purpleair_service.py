import aiohttp
import asyncio
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import os
import logging

from .redis_cache_service import cache_service
from .rate_limiter import rate_limited

logger = logging.getLogger(__name__)

class AsyncPurpleAirService:
    """Enhanced async PurpleAir service with caching and rate limiting"""
    
    def __init__(self):
        self.api_key = os.getenv("PURPLEAIR_API_KEY")
        self.base_url = "https://api.purpleair.com/v1"
        
        if not self.api_key:
            logger.warning("PURPLEAIR_API_KEY not found. Using mock data.")
        
        # Request session with optimized settings
        self.session_config = {
            'timeout': aiohttp.ClientTimeout(total=30, connect=10),
            'connector': aiohttp.TCPConnector(
                limit=10,  # Connection pool size
                limit_per_host=5,
                keepalive_timeout=60,
                enable_cleanup_closed=True
            )
        }
    
    @rate_limited('purpleair')
    async def get_sensors_cached(self, bbox: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """Get PurpleAir sensors with caching and rate limiting"""
        try:
            # Generate cache key
            cache_key = cache_service.generate_cache_key(
                'purpleair_sensors',
                {'bbox': bbox or 'global', 'limit': limit}
            )
            
            # Try cache first
            async def fetch_fresh_data():
                return await self._fetch_sensors_from_api(bbox, limit)
            
            sensors = await cache_service.get_or_set(
                cache_key,
                fetch_fresh_data,
                cache_type='purpleair_sensors'
            )
            
            logger.info(f"Retrieved {len(sensors)} PurpleAir sensors (bbox: {bbox})")
            return sensors
            
        except Exception as e:
            logger.error(f"PurpleAir sensor fetch failed: {e}")
            return self._generate_mock_sensors(bbox, limit)
    
    async def _fetch_sensors_from_api(self, bbox: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """Fetch sensors directly from PurpleAir API"""
        if not self.api_key:
            return self._generate_mock_sensors(bbox, limit)
        
        headers = {"X-API-Key": self.api_key}
        params = {
            "fields": "sensor_index,name,latitude,longitude,altitude,location_type,pm2.5,temperature,humidity,pressure,last_seen"
        }
        
        if bbox:
            west, south, east, north = map(float, bbox.split(','))
            params.update({
                "nwlat": north,
                "nwlng": west, 
                "selat": south,
                "selng": east
            })
        
        async with aiohttp.ClientSession(**self.session_config) as session:
            url = f"{self.base_url}/sensors"
            async with session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    sensors = data.get("data", [])
                    
                    # Convert to standardized format
                    formatted_sensors = []
                    for sensor in sensors[:limit]:
                        if len(sensor) >= 6:  # Ensure minimum required fields
                            formatted_sensor = {
                                "sensor_index": sensor[0],
                                "name": sensor[1] if len(sensor) > 1 else f"Sensor {sensor[0]}",
                                "latitude": sensor[2],
                                "longitude": sensor[3],
                                "altitude": sensor[4] if len(sensor) > 4 else None,
                                "location_type": sensor[5] if len(sensor) > 5 else None,
                                "pm25": sensor[6] if len(sensor) > 6 else None,
                                "temperature": sensor[7] if len(sensor) > 7 else None,
                                "humidity": sensor[8] if len(sensor) > 8 else None,
                                "pressure": sensor[9] if len(sensor) > 9 else None,
                                "last_seen": sensor[10] if len(sensor) > 10 else None,
                                "source": "purpleair"
                            }
                            formatted_sensors.append(formatted_sensor)
                    
                    return formatted_sensors
                else:
                    logger.warning(f"PurpleAir API error: {response.status}")
                    raise aiohttp.ClientResponseError(
                        request_info=response.request_info,
                        history=response.history,
                        status=response.status
                    )
    
    @rate_limited('purpleair')
    async def get_sensor_history_cached(
        self, 
        sensor_id: int, 
        start_timestamp: int, 
        end_timestamp: int, 
        average: int = 60
    ) -> List[Dict]:
        """Get historical data with caching"""
        try:
            cache_key = cache_service.generate_cache_key(
                'purpleair_history',
                {
                    'sensor_id': sensor_id,
                    'start': start_timestamp,
                    'end': end_timestamp,
                    'avg': average
                }
            )
            
            async def fetch_history():
                return await self._fetch_history_from_api(sensor_id, start_timestamp, end_timestamp, average)
            
            history = await cache_service.get_or_set(
                cache_key,
                fetch_history,
                cache_type='sensor_data'
            )
            
            return history
            
        except Exception as e:
            logger.error(f"PurpleAir history fetch failed for sensor {sensor_id}: {e}")
            return self._generate_mock_history(sensor_id, start_timestamp, end_timestamp)
    
    async def _fetch_history_from_api(
        self, 
        sensor_id: int, 
        start_timestamp: int, 
        end_timestamp: int, 
        average: int = 60
    ) -> List[Dict]:
        """Fetch historical data from API"""
        if not self.api_key:
            return self._generate_mock_history(sensor_id, start_timestamp, end_timestamp)
        
        headers = {"X-API-Key": self.api_key}
        params = {
            "start_timestamp": start_timestamp,
            "end_timestamp": end_timestamp,
            "average": average,
            "fields": "pm2.5_atm,pm10.0_atm,temperature,humidity,pressure"
        }
        
        async with aiohttp.ClientSession(**self.session_config) as session:
            url = f"{self.base_url}/sensors/{sensor_id}/history"
            async with session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    history = []
                    for record in data.get("data", []):
                        if len(record) >= 1:  # At least timestamp
                            formatted_record = {
                                "time_stamp": record[0],
                                "pm2.5_atm": record[1] if len(record) > 1 else None,
                                "pm10.0_atm": record[2] if len(record) > 2 else None,
                                "temperature": record[3] if len(record) > 3 else None,
                                "humidity": record[4] if len(record) > 4 else None,
                                "pressure": record[5] if len(record) > 5 else None
                            }
                            history.append(formatted_record)
                    
                    return history
                else:
                    raise aiohttp.ClientResponseError(
                        request_info=response.request_info,
                        history=response.history,
                        status=response.status
                    )
    
    async def batch_fetch_sensors(self, sensor_ids: List[int]) -> Dict[int, Dict]:
        """Fetch multiple sensors with optimal batching"""
        results = {}
        
        # Process in batches to avoid overwhelming the API
        batch_size = 10
        for i in range(0, len(sensor_ids), batch_size):
            batch = sensor_ids[i:i + batch_size]
            
            # Create concurrent tasks for this batch
            tasks = []
            for sensor_id in batch:
                task = self.get_single_sensor_cached(sensor_id)
                tasks.append(task)
            
            # Execute batch concurrently
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for sensor_id, result in zip(batch, batch_results):
                if not isinstance(result, Exception):
                    results[sensor_id] = result
                else:
                    logger.warning(f"Failed to fetch sensor {sensor_id}: {result}")
        
        return results
    
    @rate_limited('purpleair')
    async def get_single_sensor_cached(self, sensor_id: int) -> Optional[Dict]:
        """Get single sensor data with caching"""
        cache_key = f"purpleair_sensor:{sensor_id}"
        
        async def fetch_sensor():
            return await self._fetch_single_sensor(sensor_id)
        
        try:
            return await cache_service.get_or_set(
                cache_key,
                fetch_sensor,
                cache_type='sensor_data',
                custom_ttl=300  # 5 minutes for individual sensors
            )
        except Exception as e:
            logger.error(f"Error fetching sensor {sensor_id}: {e}")
            return None
    
    async def _fetch_single_sensor(self, sensor_id: int) -> Optional[Dict]:
        """Fetch single sensor from API"""
        if not self.api_key:
            return None
        
        headers = {"X-API-Key": self.api_key}
        params = {
            "fields": "sensor_index,name,latitude,longitude,pm2.5,temperature,humidity,pressure,last_seen"
        }
        
        async with aiohttp.ClientSession(**self.session_config) as session:
            url = f"{self.base_url}/sensors/{sensor_id}"
            async with session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    sensor = data.get("sensor", {})
                    return {
                        "sensor_index": sensor.get("sensor_index"),
                        "name": sensor.get("name"),
                        "latitude": sensor.get("latitude"),
                        "longitude": sensor.get("longitude"),
                        "pm25": sensor.get("pm2.5"),
                        "temperature": sensor.get("temperature"),
                        "humidity": sensor.get("humidity"),
                        "pressure": sensor.get("pressure"),
                        "last_seen": sensor.get("last_seen"),
                        "source": "purpleair"
                    }
                else:
                    return None
    
    def _generate_mock_sensors(self, bbox: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """Generate mock sensor data for testing"""
        import random
        
        # San Francisco Bay Area coordinates
        if bbox:
            try:
                west, south, east, north = map(float, bbox.split(','))
            except:
                west, south, east, north = -122.45, 37.35, -122.15, 37.75
        else:
            west, south, east, north = -122.45, 37.35, -122.15, 37.75
        
        sensors = []
        for i in range(min(limit, 25)):  # Limit mock data
            sensor = {
                "sensor_index": 100000 + i,
                "name": f"Mock PurpleAir Sensor {i + 1}",
                "latitude": round(random.uniform(south, north), 6),
                "longitude": round(random.uniform(west, east), 6),
                "altitude": random.randint(0, 500),
                "location_type": random.choice(["outside", "inside"]),
                "pm25": round(random.uniform(5, 50), 1),
                "temperature": round(random.uniform(15, 30), 1),
                "humidity": round(random.uniform(30, 80), 1),
                "pressure": round(random.uniform(1000, 1030), 1),
                "last_seen": int(datetime.utcnow().timestamp()),
                "source": "purpleair"
            }
            sensors.append(sensor)
        
        return sensors
    
    def _generate_mock_history(self, sensor_id: int, start_timestamp: int, end_timestamp: int) -> List[Dict]:
        """Generate mock historical data"""
        import random
        
        history = []
        current = start_timestamp
        
        while current <= end_timestamp and len(history) < 100:
            record = {
                "time_stamp": current,
                "pm2.5_atm": round(random.uniform(8, 35), 1),
                "pm10.0_atm": round(random.uniform(15, 60), 1),
                "temperature": round(random.uniform(18, 28), 1),
                "humidity": round(random.uniform(40, 75), 1),
                "pressure": round(random.uniform(1005, 1025), 1)
            }
            history.append(record)
            current += 3600  # Add 1 hour
        
        return history
