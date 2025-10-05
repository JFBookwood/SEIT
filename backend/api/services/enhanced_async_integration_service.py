import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from .async_purpleair_service import AsyncPurpleAirService
from .async_nasa_service import AsyncNASAService
from .async_weather_service import AsyncWeatherService
from .async_openaq_service import AsyncOpenAQService
from .redis_cache_service import cache_service
from .rate_limiter import rate_limit_manager

logger = logging.getLogger(__name__)

class EnhancedAsyncIntegrationService:
    """Centralized async service for coordinating multi-source data integration"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
        
        # Initialize async services
        self.purpleair_service = AsyncPurpleAirService()
        self.nasa_service = AsyncNASAService()
        self.weather_service = AsyncWeatherService()
        self.openaq_service = AsyncOpenAQService()
        
        # Integration statistics
        self.integration_stats = {
            'total_requests': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'rate_limit_delays': 0,
            'errors': []
        }
    
    async def get_comprehensive_data(
        self,
        bbox: Optional[str] = None,
        include_satellite: bool = True,
        include_weather: bool = True,
        date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get comprehensive environmental data from all sources"""
        try:
            if not date:
                date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
            
            # Create cache key for comprehensive integration
            cache_key = cache_service.generate_cache_key(
                'comprehensive_env_data',
                {
                    'bbox': bbox or 'global',
                    'satellite': include_satellite,
                    'weather': include_weather,
                    'date': date
                }
            )
            
            # Check cache first
            cached_data = await cache_service.get(cache_key, 'sensor_data')
            if cached_data:
                self.integration_stats['cache_hits'] += 1
                logger.info("Comprehensive data served from cache")
                return cached_data
            
            self.integration_stats['cache_misses'] += 1
            
            # Fetch fresh data from all sources concurrently
            logger.info("Fetching fresh comprehensive environmental data")
            
            # Create concurrent tasks
            tasks = {
                'purpleair': self.purpleair_service.get_sensors_cached(bbox, 50),
                'sensor_community': self._get_sensor_community_data(bbox),
                'openaq': self.openaq_service.get_latest_measurements_cached(bbox, 50)
            }
            
            if include_weather:
                tasks['weather'] = self._get_regional_weather(bbox)
            
            if include_satellite:
                tasks['satellite'] = self._get_satellite_layers(bbox, date)
            
            # Execute all tasks with timeout
            try:
                results = await asyncio.wait_for(
                    asyncio.gather(*tasks.values(), return_exceptions=True),
                    timeout=45.0  # 45 second timeout for all requests
                )
            except asyncio.TimeoutError:
                logger.warning("Comprehensive data fetch timed out, using partial results")
                results = [None] * len(tasks)
            
            # Process results
            task_names = list(tasks.keys())
            processed_data = {
                'sensors': [],
                'weather': [],
                'satellite': {},
                'statistics': {
                    'total': 0,
                    'purpleair': 0,
                    'sensor_community': 0,
                    'openaq': 0,
                    'weather_points': 0,
                    'satellite_layers': 0,
                    'errors': []
                },
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
            # Process sensor data
            for i, task_name in enumerate(task_names[:3]):  # First 3 are sensor tasks
                result = results[i] if i < len(results) else None
                if result and not isinstance(result, Exception):
                    if task_name == 'purpleair':
                        processed_data['sensors'].extend(self._format_purpleair_data(result))
                        processed_data['statistics']['purpleair'] = len(result)
                    elif task_name == 'sensor_community':
                        processed_data['sensors'].extend(self._format_sensor_community_data(result))
                        processed_data['statistics']['sensor_community'] = len(result)
                    elif task_name == 'openaq':
                        processed_data['sensors'].extend(self._format_openaq_data(result))
                        processed_data['statistics']['openaq'] = len(result)
                else:
                    error_msg = str(result) if isinstance(result, Exception) else "No data returned"
                    processed_data['statistics']['errors'].append(f"{task_name}: {error_msg}")
            
            # Process weather data
            if include_weather and len(results) > 3:
                weather_result = results[3]
                if weather_result and not isinstance(weather_result, Exception):
                    processed_data['weather'] = weather_result
                    processed_data['statistics']['weather_points'] = len(weather_result)
            
            # Process satellite data
            if include_satellite and len(results) > (4 if include_weather else 3):
                satellite_index = 4 if include_weather else 3
                satellite_result = results[satellite_index]
                if satellite_result and not isinstance(satellite_result, Exception):
                    processed_data['satellite'] = satellite_result
                    processed_data['statistics']['satellite_layers'] = len(satellite_result.get('layers', {}))
            
            # Calculate total sensors
            processed_data['statistics']['total'] = len(processed_data['sensors'])
            
            # Cache the results
            await cache_service.set(cache_key, processed_data, 'sensor_data')
            self.integration_stats['total_requests'] += 1
            
            logger.info(f"Comprehensive data integration completed: {processed_data['statistics']['total']} sensors")
            return processed_data
            
        except Exception as e:
            logger.error(f"Comprehensive data integration failed: {e}")
            self.integration_stats['errors'].append(str(e))
            
            # Return fallback mock data
            return self._generate_fallback_data(bbox, include_satellite, include_weather, date)
    
    async def _get_sensor_community_data(self, bbox: Optional[str] = None) -> List[Dict]:
        """Get Sensor.Community data with error handling"""
        try:
            # Import the existing service
            from .sensor_community_service import SensorCommunityService
            sc_service = SensorCommunityService()
            return await sc_service.get_current_data(bbox)
        except Exception as e:
            logger.warning(f"Sensor.Community fetch failed: {e}")
            return []
    
    async def _get_regional_weather(self, bbox: Optional[str] = None) -> List[Dict]:
        """Get regional weather data"""
        try:
            if bbox:
                bbox_coords = list(map(float, bbox.split(',')))
                return await self.weather_service.get_regional_weather_cached(bbox_coords, 0.5)
            else:
                # Get weather for a few global points
                global_coords = [
                    (37.7749, -122.4194),  # San Francisco
                    (40.7128, -74.0060),   # New York
                    (51.5074, -0.1278),    # London
                    (35.6762, 139.6503)    # Tokyo
                ]
                weather_data = await self.weather_service.batch_weather_fetch(global_coords)
                return list(weather_data.values())
        except Exception as e:
            logger.warning(f"Weather data fetch failed: {e}")
            return []
    
    async def _get_satellite_layers(self, bbox: Optional[str] = None, date: str = None) -> Dict:
        """Get satellite layer information"""
        try:
            layers = await self.nasa_service.get_gibs_layers_cached()
            
            if bbox:
                bbox_coords = list(map(float, bbox.split(',')))
                # Get AOD data for the region
                aod_data = await self.nasa_service.fetch_modis_aod_cached(bbox_coords, date)
                
                return {
                    'available_layers': layers,
                    'aod_data': aod_data,
                    'date': date
                }
            else:
                return {
                    'available_layers': layers,
                    'date': date
                }
        except Exception as e:
            logger.warning(f"Satellite data fetch failed: {e}")
            return {'available_layers': [], 'error': str(e)}
    
    def _format_purpleair_data(self, raw_data: List[Dict]) -> List[Dict]:
        """Format PurpleAir data to standard schema"""
        formatted = []
        for sensor in raw_data:
            if sensor.get('latitude') and sensor.get('longitude'):
                formatted_sensor = {
                    'sensor_id': str(sensor.get('sensor_index', sensor.get('sensor_id'))),
                    'name': sensor.get('name', f"PurpleAir {sensor.get('sensor_index')}"),
                    'latitude': float(sensor['latitude']),
                    'longitude': float(sensor['longitude']),
                    'pm25': sensor.get('pm25'),
                    'pm10': sensor.get('pm10'),
                    'temperature': sensor.get('temperature'),
                    'humidity': sensor.get('humidity'),
                    'pressure': sensor.get('pressure'),
                    'timestamp': datetime.utcnow().isoformat(),
                    'source': 'purpleair',
                    'metadata': {
                        'altitude': sensor.get('altitude'),
                        'location_type': sensor.get('location_type'),
                        'last_seen': sensor.get('last_seen')
                    }
                }
                formatted.append(formatted_sensor)
        return formatted
    
    def _format_sensor_community_data(self, raw_data: List[Dict]) -> List[Dict]:
        """Format Sensor.Community data to standard schema"""
        formatted = []
        for sensor in raw_data:
            if sensor.get('latitude') and sensor.get('longitude'):
                formatted_sensor = {
                    'sensor_id': sensor.get('sensor_id'),
                    'name': f"Sensor.Community {sensor.get('sensor_id')}",
                    'latitude': float(sensor['latitude']),
                    'longitude': float(sensor['longitude']),
                    'pm25': sensor.get('pm25'),
                    'pm10': sensor.get('pm10'),
                    'temperature': sensor.get('temperature'),
                    'humidity': sensor.get('humidity'),
                    'pressure': sensor.get('pressure'),
                    'timestamp': sensor.get('timestamp'),
                    'source': 'sensor_community',
                    'metadata': sensor.get('metadata', {})
                }
                formatted.append(formatted_sensor)
        return formatted
    
    def _format_openaq_data(self, raw_data: List[Dict]) -> List[Dict]:
        """Format OpenAQ data to standard schema"""
        formatted = []
        for sensor in raw_data:
            if sensor.get('latitude') and sensor.get('longitude'):
                formatted_sensor = {
                    'sensor_id': sensor.get('sensor_id'),
                    'name': sensor.get('location', f"OpenAQ {sensor.get('sensor_id')}"),
                    'latitude': float(sensor['latitude']),
                    'longitude': float(sensor['longitude']),
                    'pm25': sensor.get('pm25'),
                    'pm10': sensor.get('pm10'),
                    'no2': sensor.get('no2'),
                    'o3': sensor.get('o3'),
                    'so2': sensor.get('so2'),
                    'co': sensor.get('co'),
                    'timestamp': sensor.get('timestamp'),
                    'source': 'openaq',
                    'metadata': {
                        'city': sensor.get('city'),
                        'country': sensor.get('country'),
                        'measurements': sensor.get('measurements', {})
                    }
                }
                formatted.append(formatted_sensor)
        return formatted
    
    def _generate_fallback_data(
        self, 
        bbox: Optional[str] = None, 
        include_satellite: bool = True, 
        include_weather: bool = True, 
        date: str = None
    ) -> Dict:
        """Generate comprehensive fallback data"""
        # Use existing mock data generation
        from ..routes.enhanced_sensors import _generate_comprehensive_mock_sensors
        
        mock_sensors = _generate_comprehensive_mock_sensors(bbox)
        
        return {
            'sensors': mock_sensors,
            'weather': self._generate_mock_weather(bbox) if include_weather else [],
            'satellite': {'available_layers': []} if include_satellite else {},
            'statistics': {
                'total': len(mock_sensors),
                'purpleair': len([s for s in mock_sensors if s['source'] == 'purpleair']),
                'sensor_community': len([s for s in mock_sensors if s['source'] == 'sensor_community']),
                'openaq': len([s for s in mock_sensors if s['source'] == 'openaq']),
                'weather_points': 4 if include_weather else 0,
                'satellite_layers': 0,
                'errors': ['Using fallback mock data']
            },
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
    
    def _generate_mock_weather(self, bbox: Optional[str] = None) -> List[Dict]:
        """Generate mock weather data"""
        import random
        
        if bbox:
            try:
                west, south, east, north = map(float, bbox.split(','))
            except:
                west, south, east, north = -122.5, 37.2, -121.9, 37.9
        else:
            west, south, east, north = -122.5, 37.2, -121.9, 37.9
        
        weather_points = []
        for i in range(4):
            lat = random.uniform(south, north)
            lng = random.uniform(west, east)
            
            weather_point = {
                "latitude": round(lat, 4),
                "longitude": round(lng, 4),
                "temperature": round(random.uniform(15, 25), 1),
                "humidity": round(random.uniform(50, 80), 1),
                "pressure": round(random.uniform(1010, 1020), 1),
                "wind_speed": round(random.uniform(2, 15), 1),
                "wind_direction": random.randint(0, 360),
                "cloud_cover": random.randint(10, 80),
                "timestamp": datetime.utcnow().isoformat(),
                "source": "open_meteo"
            }
            weather_points.append(weather_point)
        
        return weather_points
    
    async def get_integration_statistics(self) -> Dict:
        """Get integration service statistics"""
        rate_limit_stats = rate_limit_manager.get_all_status()
        cache_stats = cache_service.get_cache_stats()
        
        return {
            'integration_stats': self.integration_stats,
            'rate_limit_status': rate_limit_stats,
            'cache_performance': cache_stats,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
    
    async def clear_cache_for_bbox(self, bbox: str) -> int:
        """Clear cached data for specific geographic area"""
        patterns = [
            f"*bbox*{bbox.replace(',', '_')}*",
            f"comprehensive_env_data*{bbox.replace(',', '_')}*"
        ]
        
        total_cleared = 0
        for pattern in patterns:
            cleared = await cache_service.clear_pattern(pattern)
            total_cleared += cleared
        
        logger.info(f"Cleared {total_cleared} cache entries for bbox: {bbox}")
        return total_cleared
    
    async def refresh_all_caches(self) -> Dict:
        """Refresh all cached data"""
        try:
            # Clear all cached data
            await cache_service.clear_pattern("*")
            
            # Pre-warm cache with fresh data for common regions
            common_regions = [
                "-122.5,37.2,-121.9,37.9",  # SF Bay Area
                "-118.7,33.7,-118.0,34.3",  # Los Angeles
                "-74.3,40.5,-73.7,40.9"     # New York
            ]
            
            refresh_results = {}
            for region in common_regions:
                try:
                    data = await self.get_comprehensive_data(region, True, True)
                    refresh_results[region] = {
                        'sensors': data['statistics']['total'],
                        'success': True
                    }
                except Exception as e:
                    refresh_results[region] = {
                        'error': str(e),
                        'success': False
                    }
            
            return {
                'message': 'Cache refresh completed',
                'regions_refreshed': refresh_results,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Cache refresh failed: {e}")
            return {'error': str(e)}
