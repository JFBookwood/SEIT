import aiohttp
import asyncio
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging

from .redis_cache_service import cache_service
from .rate_limiter import rate_limited

logger = logging.getLogger(__name__)

class AsyncOpenAQService:
    """Enhanced async OpenAQ service with caching and rate limiting"""
    
    def __init__(self):
        self.api_key = "dfc2eec721e2f738e90fd6731f14f76ab92f7352698f1efe3010c6234da1a731"
        self.base_url = "https://api.openaq.org/v2"
        
        self.session_config = {
            'timeout': aiohttp.ClientTimeout(total=45, connect=10),
            'connector': aiohttp.TCPConnector(
                limit=20,
                limit_per_host=10,
                keepalive_timeout=90,
                enable_cleanup_closed=True
            )
        }
    
    @rate_limited('openaq')
    async def get_latest_measurements_cached(self, bbox: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """Get latest measurements with caching"""
        cache_key = cache_service.generate_cache_key(
            'openaq_latest',
            {'bbox': bbox or 'global', 'limit': limit}
        )
        
        async def fetch_latest():
            return await self._fetch_latest_measurements(bbox, limit)
        
        return await cache_service.get_or_set(
            cache_key,
            fetch_latest,
            cache_type='openaq_data'
        )
    
    async def _fetch_latest_measurements(self, bbox: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """Fetch latest measurements from OpenAQ API"""
        headers = {"X-API-Key": self.api_key}
        params = {
            "limit": limit,
            "order_by": "datetime",
            "sort": "desc"
        }
        
        if bbox:
            west, south, east, north = map(float, bbox.split(','))
            params["coordinates"] = f"{west},{south},{east},{north}"
        
        async with aiohttp.ClientSession(**self.session_config) as session:
            url = f"{self.base_url}/latest"
            async with session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Group measurements by location
                    location_data = {}
                    for measurement in data.get("results", []):
                        location_id = measurement.get("location")
                        if location_id not in location_data:
                            coords = measurement.get("coordinates", {})
                            location_data[location_id] = {
                                "sensor_id": f"openaq_{location_id}",
                                "location": measurement.get("location"),
                                "city": measurement.get("city"),
                                "country": measurement.get("country"),
                                "latitude": coords.get("latitude"),
                                "longitude": coords.get("longitude"),
                                "timestamp": measurement.get("date", {}).get("utc"),
                                "source": "openaq",
                                "measurements": {}
                            }
                        
                        # Add parameter measurement
                        param = measurement.get("parameter")
                        value = measurement.get("value")
                        unit = measurement.get("unit")
                        
                        if param and value is not None:
                            location_data[location_id][param] = value
                            location_data[location_id]["measurements"][param] = {
                                "value": value,
                                "unit": unit
                            }
                    
                    return list(location_data.values())
                else:
                    logger.warning(f"OpenAQ API error: {response.status}")
                    return self._generate_mock_openaq_data(bbox, limit)
    
    @rate_limited('openaq')
    async def get_measurements_for_location_cached(
        self, 
        location_id: str, 
        parameter: str = "pm25", 
        hours_back: int = 24
    ) -> List[Dict]:
        """Get measurements for specific location with caching"""
        cache_key = cache_service.generate_cache_key(
            'openaq_location',
            {
                'location': location_id,
                'parameter': parameter,
                'hours': hours_back
            }
        )
        
        async def fetch_measurements():
            return await self._fetch_location_measurements(location_id, parameter, hours_back)
        
        return await cache_service.get_or_set(
            cache_key,
            fetch_measurements,
            cache_type='openaq_data'
        )
    
    async def _fetch_location_measurements(
        self, 
        location_id: str, 
        parameter: str = "pm25", 
        hours_back: int = 24
    ) -> List[Dict]:
        """Fetch measurements for specific location"""
        headers = {"X-API-Key": self.api_key}
        
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(hours=hours_back)
        
        params = {
            "location": location_id,
            "parameter": parameter,
            "date_from": start_date.isoformat(),
            "date_to": end_date.isoformat(),
            "limit": 1000,
            "order_by": "datetime",
            "sort": "desc"
        }
        
        async with aiohttp.ClientSession(**self.session_config) as session:
            url = f"{self.base_url}/measurements"
            async with session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    measurements = []
                    
                    for measurement in data.get("results", []):
                        meas_data = {
                            "location_id": measurement.get("locationId"),
                            "parameter": measurement.get("parameter"),
                            "value": measurement.get("value"),
                            "unit": measurement.get("unit"),
                            "datetime": measurement.get("date", {}).get("utc"),
                            "coordinates": measurement.get("coordinates"),
                            "source": "openaq"
                        }
                        measurements.append(meas_data)
                    
                    return measurements
                else:
                    return []
    
    async def batch_fetch_multiple_locations(self, location_ids: List[str], parameter: str = "pm25") -> Dict[str, List[Dict]]:
        """Fetch measurements for multiple locations concurrently"""
        results = {}
        
        # Create semaphore for controlled concurrency
        semaphore = asyncio.Semaphore(6)  # Max 6 concurrent requests
        
        async def fetch_with_limit(location_id: str):
            async with semaphore:
                try:
                    return await self.get_measurements_for_location_cached(location_id, parameter)
                except Exception as e:
                    logger.warning(f"Failed to fetch location {location_id}: {e}")
                    return []
        
        tasks = {loc_id: fetch_with_limit(loc_id) for loc_id in location_ids}
        completed_tasks = await asyncio.gather(*tasks.values(), return_exceptions=True)
        
        # Map results
        for loc_id, result in zip(location_ids, completed_tasks):
            if result and not isinstance(result, Exception):
                results[loc_id] = result
            else:
                results[loc_id] = []
        
        return results
    
    def _generate_mock_openaq_data(self, bbox: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """Generate mock OpenAQ data"""
        import random
        
        # Global cities for realistic distribution
        if bbox:
            try:
                west, south, east, north = map(float, bbox.split(','))
            except:
                west, south, east, north = -74.05, 40.65, -73.95, 40.85
        else:
            west, south, east, north = -74.05, 40.65, -73.95, 40.85
        
        # Major cities on land
        cities = [
            {"lat": 40.7589, "lng": -73.9851, "name": "Manhattan"},
            {"lat": 40.6892, "lng": -73.9442, "name": "Brooklyn"},
            {"lat": 40.7282, "lng": -73.7949, "name": "Queens"},
            {"lat": 40.8448, "lng": -73.8648, "name": "Bronx"},
            {"lat": 40.5795, "lng": -74.1502, "name": "Staten Island"}
        ]
        
        sensors = []
        for i in range(min(limit, 20)):
            city = random.choice(cities)
            lat = city["lat"] + (random.random() - 0.5) * 0.01
            lng = city["lng"] + (random.random() - 0.5) * 0.01
            
            sensor = {
                "sensor_id": f"openaq_{i}",
                "location": f"NYC_Location_{i}",
                "city": city["name"],
                "country": "US",
                "latitude": round(lat, 6),
                "longitude": round(lng, 6),
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "pm25": round(random.uniform(8, 45), 1),
                "pm10": round(random.uniform(15, 80), 1),
                "no2": round(random.uniform(10, 60), 1),
                "o3": round(random.uniform(20, 120), 1),
                "so2": round(random.uniform(0, 20), 1),
                "co": round(random.uniform(0.2, 2.5), 2),
                "source": "openaq"
            }
            sensors.append(sensor)
        
        return sensors
