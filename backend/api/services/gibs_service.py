import requests
from datetime import datetime
from typing import Dict, List, Optional
import os

class GIBSService:
    """Service for interacting with NASA GIBS WMTS tiles"""
    
    def __init__(self):
        self.base_url = "https://gibs.earthdata.nasa.gov/wmts/epsg4326/best"
        self.tile_matrix_set = "250m"  # Default resolution
        
    def generate_tile_url(
        self, 
        layer_id: str, 
        date: str, 
        z: int, 
        x: int, 
        y: int, 
        format_ext: str = "jpeg"
    ) -> str:
        """
        Generate GIBS WMTS tile URL following the pattern:
        {base_url}/{LayerIdentifier}/default/{Time}/{TileMatrixSet}/{TileMatrix}/{TileRow}/{TileCol}.{FormatExt}
        """
        try:
            # Validate and format date
            date_obj = datetime.fromisoformat(date.replace('Z', '+00:00'))
            formatted_date = date_obj.strftime('%Y-%m-%d')
            
            # Adjust tile matrix set based on zoom level
            if z <= 2:
                tile_matrix_set = "2km"
            elif z <= 5:
                tile_matrix_set = "1km"
            else:
                tile_matrix_set = "500m"
            
            # Construct URL
            url = f"{self.base_url}/{layer_id}/default/{formatted_date}/{tile_matrix_set}/{z}/{y}/{x}.{format_ext}"
            
            return url
            
        except Exception as e:
            raise Exception(f"Error generating tile URL: {str(e)}")
    
    def get_layer_capabilities(self, layer_id: str) -> Dict:
        """Get layer capabilities and metadata"""
        try:
            # In a real implementation, you'd query GIBS capabilities
            # This is a mock response with common layer configurations
            layer_configs = {
                "MODIS_Terra_CorrectedReflectance_TrueColor": {
                    "title": "MODIS Terra Corrected Reflectance (True Color)",
                    "abstract": "True-color corrected reflectance imagery from MODIS Terra",
                    "format": "image/jpeg",
                    "temporal": True,
                    "start_date": "2000-02-24",
                    "end_date": None,  # Current
                    "zoom_levels": {"min": 0, "max": 9},
                    "tile_matrix_sets": ["250m", "500m", "1km", "2km"]
                },
                "MODIS_Aqua_CorrectedReflectance_TrueColor": {
                    "title": "MODIS Aqua Corrected Reflectance (True Color)", 
                    "abstract": "True-color corrected reflectance imagery from MODIS Aqua",
                    "format": "image/jpeg",
                    "temporal": True,
                    "start_date": "2002-07-04",
                    "end_date": None,
                    "zoom_levels": {"min": 0, "max": 9},
                    "tile_matrix_sets": ["250m", "500m", "1km", "2km"]
                },
                "MODIS_Terra_Land_Surface_Temp_Day": {
                    "title": "MODIS Terra Land Surface Temperature (Day)",
                    "abstract": "Daytime land surface temperature from MODIS Terra",
                    "format": "image/png",
                    "temporal": True,
                    "start_date": "2000-02-24",
                    "end_date": None,
                    "zoom_levels": {"min": 0, "max": 7},
                    "tile_matrix_sets": ["1km", "2km"]
                },
                "AIRS_L2_Surface_Air_Temperature_Day": {
                    "title": "AIRS Surface Air Temperature (Day)",
                    "abstract": "Daytime surface air temperature from AIRS",
                    "format": "image/png",
                    "temporal": True,
                    "start_date": "2002-08-30",
                    "end_date": None,
                    "zoom_levels": {"min": 0, "max": 5},
                    "tile_matrix_sets": ["2km"]
                }
            }
            
            return layer_configs.get(layer_id, {
                "title": layer_id,
                "abstract": "Layer configuration not found",
                "format": "image/jpeg",
                "temporal": True,
                "zoom_levels": {"min": 0, "max": 9},
                "tile_matrix_sets": ["250m", "500m", "1km", "2km"]
            })
            
        except Exception as e:
            raise Exception(f"Error getting layer capabilities: {str(e)}")
    
    def validate_tile_request(
        self, 
        layer_id: str, 
        date: str, 
        z: int, 
        x: int, 
        y: int
    ) -> bool:
        """Validate if a tile request is valid"""
        try:
            capabilities = self.get_layer_capabilities(layer_id)
            
            # Check zoom level
            min_zoom = capabilities.get("zoom_levels", {}).get("min", 0)
            max_zoom = capabilities.get("zoom_levels", {}).get("max", 9)
            
            if not (min_zoom <= z <= max_zoom):
                return False
            
            # Check date range
            if capabilities.get("temporal", False):
                start_date = capabilities.get("start_date")
                end_date = capabilities.get("end_date")
                
                if start_date:
                    request_date = datetime.fromisoformat(date.replace('Z', '+00:00'))
                    layer_start = datetime.fromisoformat(start_date)
                    
                    if request_date < layer_start:
                        return False
                
                if end_date:
                    layer_end = datetime.fromisoformat(end_date)
                    if request_date > layer_end:
                        return False
            
            # Check tile coordinates (basic validation)
            max_tiles = 2 ** z
            if not (0 <= x < max_tiles and 0 <= y < max_tiles):
                return False
            
            return True
            
        except Exception:
            return False
    
    def get_available_dates(self, layer_id: str, start_date: str, end_date: str) -> List[str]:
        """Get available dates for a temporal layer"""
        try:
            capabilities = self.get_layer_capabilities(layer_id)
            
            if not capabilities.get("temporal", False):
                return []
            
            # In a real implementation, you'd query GIBS for available dates
            # For demo, generate daily dates in range
            from datetime import timedelta
            
            start = datetime.fromisoformat(start_date)
            end = datetime.fromisoformat(end_date)
            
            dates = []
            current = start
            while current <= end:
                dates.append(current.strftime('%Y-%m-%d'))
                current += timedelta(days=1)
            
            # Limit to reasonable number for demo
            return dates[:30]
            
        except Exception as e:
            raise Exception(f"Error getting available dates: {str(e)}")
