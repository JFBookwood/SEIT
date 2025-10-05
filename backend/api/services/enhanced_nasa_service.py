import aiohttp
import asyncio
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import os
import base64
import json

class EnhancedNASAService:
    """Enhanced service for NASA Earthdata and GIBS integration"""
    
    def __init__(self):
        # Your provided JWT token
        self.jwt_token = "eyJ0eXAiOiJKV1QiLCJvcmlnaW4iOiJFYXJ0aGRhdGEgTG9naW4iLCJzaWciOiJlZGxqd3RwdWJrZXlfb3BzIiwiYWxnIjoiUlMyNTYifQ.eyJ0eXBlIjoiVXNlciIsInVpZCI6Implc3NlX2IiLCJleHAiOjE3NjQ3Njc3MzAsImlhdCI6MTc1OTU4MzczMCwiaXNzIjoiaHR0cHM6Ly91cnMuZWFydGhkYXRhLm5hc2EuZ292IiwiaWRlbnRpdHlfcHJvdmlkZXIiOiJlZGxfb3BzIiwiYWNyIjoiZWRsIiwiYXNzdXJhbmNlX2xldmVsIjozfQ.S6Dr2dUD-VOPn2TzFYOoLb99HfjC7_mjqAyfjyGPt3oYfSiAztBMtgYzIZ8l3nW6_pIs2rQH1sxuvasUfNkEtdMWz6Ny9d1inaMmYJUIwxX0d0ZliIF7kIonbQQx9C9ZYlp5iFm2Dka53fpNnD6i3ymVf51L-9mCH8DZ2QK6wHWs3Upt_bE8v9bzC2weoqSY-YkPd_cq6X37b2wwYi-Ufhvn8Un9nD4OWqw72n-k2KLrTlniEB6IMMakRDumU0MCc9fIepXldoi5Q_9kK0DQhaIVbFofE8E3KvPeC1RaLXucdYL--cQq3dHokcS92wX5Tt957iJilKP329wqcnMm2A"
        
        # API endpoints
        self.gibs_base_url = "https://gibs.earthdata.nasa.gov/wmts/epsg4326/best"
        self.cmr_url = "https://cmr.earthdata.nasa.gov"
        self.harmony_url = "https://harmony.earthdata.nasa.gov"
        
        # Parse JWT to get user info
        self.user_info = self._parse_jwt_token()
        
    def _parse_jwt_token(self) -> Dict:
        """Parse JWT token to extract user information"""
        try:
            # JWT tokens have 3 parts separated by dots
            parts = self.jwt_token.split('.')
            if len(parts) != 3:
                return {}
            
            # Decode the payload (second part)
            payload = parts[1]
            # Add padding if needed
            payload += '=' * (4 - len(payload) % 4)
            
            decoded = base64.urlsafe_b64decode(payload)
            return json.loads(decoded)
        except Exception as e:
            print(f"Error parsing JWT token: {e}")
            return {}
    
    async def get_gibs_layers(self) -> List[Dict]:
        """Get available GIBS layers with enhanced metadata"""
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
                "category": "temperature",
                "unit": "Kelvin"
            },
            {
                "id": "MODIS_Terra_Aerosol",
                "title": "MODIS Terra Aerosol Optical Depth",
                "description": "Aerosol Optical Depth from MODIS Terra",
                "format": "png",
                "temporal": True,
                "start_date": "2000-02-24",
                "resolution": "10km",
                "category": "atmospheric",
                "unit": "dimensionless"
            },
            {
                "id": "AIRS_L2_Surface_Air_Temperature_Day",
                "title": "AIRS Surface Air Temperature",
                "description": "Surface Air Temperature from AIRS",
                "format": "png",
                "temporal": True,
                "start_date": "2002-08-30",
                "resolution": "45km",
                "category": "temperature",
                "unit": "Kelvin"
            },
            {
                "id": "VIIRS_SNPP_DayNightBand_ENCC",
                "title": "VIIRS Day/Night Band",
                "description": "Day/Night Band Enhanced Near Constant Contrast",
                "format": "jpeg",
                "temporal": True,
                "start_date": "2012-01-19",
                "resolution": "750m",
                "category": "imagery"
            }
        ]
        return layers
    
    def generate_gibs_tile_url(
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
            
            # Construct URL
            url = f"{self.gibs_base_url}/{layer_id}/default/{formatted_date}/{tile_matrix_set}/{z}/{y}/{x}.{format_ext}"
            
            return url
            
        except Exception as e:
            raise Exception(f"Error generating GIBS tile URL: {str(e)}")
    
    async def search_granules(
        self, 
        collection_id: str, 
        bbox: List[float],
        start_date: str,
        end_date: str,
        limit: int = 50
    ) -> List[Dict]:
        """Search for granules using CMR"""
        try:
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
            
            async with aiohttp.ClientSession() as session:
                url = f"{self.cmr_url}/search/granules.json"
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
                        return []
                        
        except Exception as e:
            print(f"CMR granule search failed: {e}")
            return []
    
    async def get_environmental_data_layers(self, bbox: List[float], date: str) -> Dict:
        """Get environmental data from multiple NASA sources"""
        try:
            # Get data from different environmental layers
            layers_data = {}
            
            environmental_layers = [
                "MODIS_Terra_Land_Surface_Temp_Day",
                "MODIS_Terra_Aerosol",
                "AIRS_L2_Surface_Air_Temperature_Day"
            ]
            
            for layer_id in environmental_layers:
                try:
                    # For demonstration, we'll return metadata
                    # In production, you'd fetch actual raster data
                    layer_info = {
                        "layer_id": layer_id,
                        "date": date,
                        "bbox": bbox,
                        "tile_urls": [],
                        "metadata": {
                            "source": "NASA GIBS",
                            "resolution": self._get_layer_resolution(layer_id),
                            "unit": self._get_layer_unit(layer_id),
                            "valid": True
                        }
                    }
                    
                    # Generate some sample tile URLs for the area
                    for zoom in [3, 5, 7]:
                        # Calculate tile coordinates for bbox center
                        center_lat = (bbox[1] + bbox[3]) / 2
                        center_lon = (bbox[0] + bbox[2]) / 2
                        
                        # Simple tile calculation (not precise)
                        tile_x = int((center_lon + 180) / 360 * (2 ** zoom))
                        tile_y = int((1 - (center_lat + 90) / 180) * (2 ** zoom))
                        
                        tile_url = self.generate_gibs_tile_url(
                            layer_id, date, zoom, tile_x, tile_y, "png"
                        )
                        
                        layer_info["tile_urls"].append({
                            "zoom": zoom,
                            "x": tile_x,
                            "y": tile_y,
                            "url": tile_url
                        })
                    
                    layers_data[layer_id] = layer_info
                    
                except Exception as e:
                    continue
            
            return layers_data
            
        except Exception as e:
            print(f"Error getting environmental data layers: {e}")
            return {}
    
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
            
            # Fallback to global bbox
            return [-180, -90, 180, 90]
            
        except Exception:
            return [-180, -90, 180, 90]
    
    def _extract_granule_size(self, granule: Dict) -> float:
        """Extract granule file size in MB"""
        try:
            for link in granule.get("links", []):
                if "data#" in link.get("rel", ""):
                    # Look for size information in link metadata
                    return 50.0  # Default size estimate
            return 0.0
        except Exception:
            return 0.0
    
    def _get_layer_resolution(self, layer_id: str) -> str:
        """Get layer resolution"""
        resolution_map = {
            "MODIS_Terra_CorrectedReflectance_TrueColor": "250m",
            "MODIS_Terra_Land_Surface_Temp_Day": "1km",
            "MODIS_Terra_Aerosol": "10km",
            "AIRS_L2_Surface_Air_Temperature_Day": "45km"
        }
        return resolution_map.get(layer_id, "1km")
    
    def _get_layer_unit(self, layer_id: str) -> str:
        """Get layer measurement unit"""
        unit_map = {
            "MODIS_Terra_Land_Surface_Temp_Day": "Kelvin",
            "MODIS_Terra_Aerosol": "dimensionless",
            "AIRS_L2_Surface_Air_Temperature_Day": "Kelvin"
        }
        return unit_map.get(layer_id, "")
