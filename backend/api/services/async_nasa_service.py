import aiohttp
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import os
import logging
import json

from .redis_cache_service import cache_service
from .rate_limiter import rate_limited

logger = logging.getLogger(__name__)

class AsyncNASAService:
    """Enhanced async NASA service with authentication, caching, and rate limiting"""
    
    def __init__(self):
        self.jwt_token = os.getenv("NASA_EARTHDATA_TOKEN")
        self.username = os.getenv("EARTHDATA_USERNAME")
        self.password = os.getenv("EARTHDATA_PASSWORD")
        
        # NASA API endpoints
        self.gibs_base_url = "https://gibs.earthdata.nasa.gov/wmts/epsg4326/best"
        self.cmr_base_url = "https://cmr.earthdata.nasa.gov"
        self.harmony_base_url = "https://harmony.earthdata.nasa.gov"
        
        if not self.jwt_token and not (self.username and self.password):
            logger.warning("NASA credentials not found. Using mock data.")
        
        # Session configuration optimized for NASA APIs
        self.session_config = {
            'timeout': aiohttp.ClientTimeout(total=60, connect=15),
            'connector': aiohttp.TCPConnector(
                limit=20,
                limit_per_host=10,
                keepalive_timeout=120,
                enable_cleanup_closed=True
            )
        }
    
    @rate_limited('nasa_gibs')
    async def get_gibs_layers_cached(self) -> List[Dict]:
        """Get GIBS layers with caching"""
        cache_key = "nasa_gibs_layers"
        
        async def fetch_layers():
            return await self._fetch_gibs_layers()
        
        return await cache_service.get_or_set(
            cache_key,
            fetch_layers,
            cache_type='gibs_layers'
        )
    
    async def _fetch_gibs_layers(self) -> List[Dict]:
        """Fetch available GIBS layers"""
        # Static layer definitions (GIBS doesn't have a dynamic API for this)
        layers = [
            {
                "id": "MODIS_Terra_CorrectedReflectance_TrueColor",
                "title": "MODIS Terra True Color",
                "description": "Corrected Reflectance True Color from MODIS Terra",
                "format": "jpeg",
                "temporal": True,
                "start_date": "2000-02-24",
                "resolution": "250m",
                "category": "imagery"
            },
            {
                "id": "MODIS_Aqua_CorrectedReflectance_TrueColor",
                "title": "MODIS Aqua True Color",
                "description": "Corrected Reflectance True Color from MODIS Aqua", 
                "format": "jpeg",
                "temporal": True,
                "start_date": "2002-07-04",
                "resolution": "250m",
                "category": "imagery"
            },
            {
                "id": "MODIS_Terra_Land_Surface_Temp_Day",
                "title": "MODIS Terra LST Day",
                "description": "Land Surface Temperature (Day) from MODIS Terra",
                "format": "png",
                "temporal": True,
                "start_date": "2000-02-24", 
                "resolution": "1km",
                "category": "temperature"
            },
            {
                "id": "MODIS_Terra_Aerosol",
                "title": "MODIS Terra Aerosol Optical Depth",
                "description": "Aerosol Optical Depth from MODIS Terra",
                "format": "png",
                "temporal": True,
                "start_date": "2000-02-24",
                "resolution": "10km",
                "category": "atmospheric"
            },
            {
                "id": "AIRS_L2_Surface_Air_Temperature_Day",
                "title": "AIRS Surface Air Temperature",
                "description": "Surface Air Temperature from AIRS",
                "format": "png",
                "temporal": True,
                "start_date": "2002-08-30",
                "resolution": "45km",
                "category": "temperature"
            }
        ]
        
        logger.info(f"Loaded {len(layers)} GIBS layer definitions")
        return layers
    
    @rate_limited('nasa_gibs')
    async def generate_tile_url_cached(
        self, 
        layer_id: str, 
        date: str, 
        z: int, 
        x: int, 
        y: int, 
        format_ext: str = "jpeg"
    ) -> str:
        """Generate GIBS tile URL with caching"""
        cache_key = cache_service.generate_cache_key(
            'gibs_tile_url',
            {
                'layer': layer_id,
                'date': date,
                'z': z,
                'x': x,
                'y': y,
                'format': format_ext
            }
        )
        
        async def generate_url():
            return self._generate_gibs_tile_url(layer_id, date, z, x, y, format_ext)
        
        return await cache_service.get_or_set(
            cache_key,
            generate_url,
            cache_type='nasa_satellite',
            custom_ttl=3600  # 1 hour TTL for tile URLs
        )
    
    def _generate_gibs_tile_url(
        self, 
        layer_id: str, 
        date: str, 
        z: int, 
        x: int, 
        y: int, 
        format_ext: str = "jpeg"
    ) -> str:
        """Generate GIBS WMTS tile URL"""
        try:
            # Format date
            date_obj = datetime.fromisoformat(date.replace('Z', '+00:00'))
            formatted_date = date_obj.strftime('%Y-%m-%d')
            
            # Determine tile matrix set based on zoom level
            if z <= 2:
                tile_matrix_set = "2km"
            elif z <= 5:
                tile_matrix_set = "1km"
            elif z <= 7:
                tile_matrix_set = "500m"
            else:
                tile_matrix_set = "250m"
            
            url = f"{self.gibs_base_url}/{layer_id}/default/{formatted_date}/{tile_matrix_set}/{z}/{y}/{x}.{format_ext}"
            return url
            
        except Exception as e:
            raise Exception(f"Error generating GIBS tile URL: {str(e)}")
    
    @rate_limited('nasa_cmr')
    async def search_granules_cached(
        self, 
        collection_id: str, 
        bbox: List[float],
        start_date: str,
        end_date: str,
        limit: int = 50
    ) -> List[Dict]:
        """Search for granules with caching"""
        cache_key = cache_service.generate_cache_key(
            'nasa_granules',
            {
                'collection': collection_id,
                'bbox': '_'.join(map(str, bbox)),
                'start': start_date,
                'end': end_date,
                'limit': limit
            }
        )
        
        async def search_cmr():
            return await self._search_cmr_granules(collection_id, bbox, start_date, end_date, limit)
        
        return await cache_service.get_or_set(
            cache_key,
            search_cmr,
            cache_type='nasa_satellite'
        )
    
    async def _search_cmr_granules(
        self, 
        collection_id: str, 
        bbox: List[float],
        start_date: str,
        end_date: str,
        limit: int = 50
    ) -> List[Dict]:
        """Search CMR for granules"""
        if not self.jwt_token:
            return self._generate_mock_granules(collection_id, bbox, start_date, end_date)
        
        headers = {
            "Authorization": f"Bearer {self.jwt_token}",
            "Content-Type": "application/json"
        }
        
        west, south, east, north = bbox
        params = {
            "collection_concept_id": collection_id,
            "temporal": f"{start_date},{end_date}",
            "bounding_box": f"{west},{south},{east},{north}",
            "page_size": limit,
            "format": "json"
        }
        
        async with aiohttp.ClientSession(**self.session_config) as session:
            url = f"{self.cmr_base_url}/search/granules.json"
            async with session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    granules = []
                    
                    for item in data.get("feed", {}).get("entry", []):
                        granule = {
                            "id": item.get("id"),
                            "title": item.get("title"),
                            "time_start": item.get("time_start"),
                            "time_end": item.get("time_end"),
                            "updated": item.get("updated"),
                            "data_center": item.get("data_center"),
                            "links": item.get("links", []),
                            "bbox": self._extract_bbox_from_granule(item),
                            "size_mb": self._extract_granule_size(item)
                        }
                        granules.append(granule)
                    
                    return granules
                else:
                    logger.warning(f"CMR search failed: {response.status}")
                    return self._generate_mock_granules(collection_id, bbox, start_date, end_date)
    
    async def fetch_modis_aod_cached(self, bbox: List[float], date: str) -> Optional[Dict]:
        """Fetch MODIS AOD data with caching"""
        cache_key = cache_service.generate_cache_key(
            'modis_aod',
            {
                'bbox': '_'.join(map(str, bbox)),
                'date': date
            }
        )
        
        async def fetch_aod():
            return await self._fetch_modis_aod_data(bbox, date)
        
        return await cache_service.get_or_set(
            cache_key,
            fetch_aod,
            cache_type='nasa_satellite'
        )
    
    async def _fetch_modis_aod_data(self, bbox: List[float], date: str) -> Optional[Dict]:
        """Fetch MODIS Aerosol Optical Depth data"""
        try:
            # In production, this would use NASA Harmony or direct data access
            # For now, return mock data structure
            west, south, east, north = bbox
            
            # Generate mock AOD grid
            import numpy as np
            grid_size = 20
            lats = np.linspace(south, north, grid_size)
            lons = np.linspace(west, east, grid_size)
            
            aod_data = []
            for i, lat in enumerate(lats):
                for j, lon in enumerate(lons):
                    aod_value = 0.1 + np.random.exponential(0.2)  # Realistic AOD distribution
                    aod_data.append({
                        'latitude': float(lat),
                        'longitude': float(lon),
                        'aod_550nm': round(float(aod_value), 4),
                        'quality_flag': np.random.choice([0, 1, 2], p=[0.8, 0.15, 0.05])
                    })
            
            return {
                'date': date,
                'bbox': bbox,
                'grid_data': aod_data,
                'metadata': {
                    'product': 'MOD04_L2',
                    'resolution': '10km',
                    'source': 'NASA MODIS Terra'
                }
            }
            
        except Exception as e:
            logger.error(f"Error fetching MODIS AOD data: {e}")
            return None
    
    def _extract_bbox_from_granule(self, granule: Dict) -> List[float]:
        """Extract bounding box from granule metadata"""
        try:
            polygons = granule.get("polygons", [])
            if polygons:
                coords_str = polygons[0]
                coords = [float(x) for x in coords_str.split()]
                # Assuming lat,lon pairs
                lats = coords[1::2]
                lons = coords[0::2]
                return [min(lons), min(lats), max(lons), max(lats)]
            return [-180, -90, 180, 90]
        except Exception:
            return [-180, -90, 180, 90]
    
    def _extract_granule_size(self, granule: Dict) -> float:
        """Extract granule file size in MB"""
        try:
            for link in granule.get("links", []):
                if "data#" in link.get("rel", ""):
                    return 50.0  # Default size estimate
            return 0.0
        except Exception:
            return 0.0
    
    def _generate_mock_granules(self, collection_id: str, bbox: List[float], 
                               start_date: str, end_date: str) -> List[Dict]:
        """Generate mock granules for demo"""
        import uuid
        
        granules = []
        start = datetime.fromisoformat(start_date)
        end = datetime.fromisoformat(end_date)
        
        current = start
        count = 0
        while current <= end and count < 10:
            granule_id = f"{collection_id}.A{current.strftime('%Y%j')}.{str(uuid.uuid4())[:8]}"
            
            granule = {
                'id': granule_id,
                'title': f"{collection_id} {current.strftime('%Y-%m-%d')}",
                'time_start': current.strftime('%Y-%m-%dT00:00:00Z'),
                'time_end': (current + timedelta(days=1)).strftime('%Y-%m-%dT00:00:00Z'),
                'links': [],
                'bbox': bbox
            }
            
            granules.append(granule)
            current += timedelta(days=1)
            count += 1
        
        return granules
