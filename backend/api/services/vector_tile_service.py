import json
import logging
from typing import Dict, List, Optional, Any
import math
import mapbox_vector_tile
from shapely.geometry import Point, Polygon, box
import geojson
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class VectorTileService:
    """Service for generating vector tiles for heatmap visualization"""
    
    def __init__(self):
        # Tile configuration
        self.tile_size = 256  # Standard tile size
        self.buffer_size = 64  # Buffer around tile edges
        self.simplification_tolerance = 1.0  # Geometry simplification
        
        # Layer configurations
        self.layer_configs = {
            'heatmap_points': {
                'type': 'point',
                'simplify': False,
                'quantize_bounds': [-180, -90, 180, 90]
            },
            'heatmap_contours': {
                'type': 'polygon',
                'simplify': True,
                'quantize_bounds': [-180, -90, 180, 90]
            },
            'uncertainty_overlay': {
                'type': 'polygon',
                'simplify': True,
                'quantize_bounds': [-180, -90, 180, 90]
            }
        }
    
    def generate_heatmap_tile(self, z: int, x: int, y: int, grid_data: Dict, 
                             layer_type: str = 'points') -> bytes:
        """Generate vector tile for heatmap data"""
        try:
            # Calculate tile bounds
            tile_bounds = self._tile_to_bounds(z, x, y)
            
            # Filter grid data to tile bounds with buffer
            buffered_bounds = self._add_buffer_to_bounds(tile_bounds)
            filtered_features = self._filter_features_by_bounds(
                grid_data.get('features', []), 
                buffered_bounds
            )
            
            if not filtered_features:
                logger.debug(f"No features in tile {z}/{x}/{y}")
                return self._encode_empty_tile()
            
            # Generate layers based on type
            layers = {}
            
            if layer_type == 'points' or layer_type == 'all':
                layers['heatmap_points'] = self._create_point_layer(filtered_features)
            
            if layer_type == 'contours' or layer_type == 'all':
                layers['heatmap_contours'] = self._create_contour_layer(filtered_features, tile_bounds)
            
            if layer_type == 'uncertainty' or layer_type == 'all':
                layers['uncertainty_overlay'] = self._create_uncertainty_layer(filtered_features)
            
            # Encode as vector tile
            vector_tile = mapbox_vector_tile.encode(layers, quantize_bounds=tile_bounds)
            
            logger.debug(f"Generated vector tile {z}/{x}/{y} with {len(filtered_features)} features")
            
            return vector_tile
            
        except Exception as e:
            logger.error(f"Vector tile generation failed for {z}/{x}/{y}: {e}")
            return self._encode_empty_tile()
    
    def _create_point_layer(self, features: List[Dict]) -> List[Dict]:
        """Create point layer for vector tile"""
        point_features = []
        
        for feature in features:
            coords = feature['geometry']['coordinates']
            props = feature['properties']
            
            # Create point feature for vector tile
            point_feature = {
                'geometry': Point(coords),
                'properties': {
                    'c_hat': props.get('c_hat', 0),
                    'uncertainty': props.get('uncertainty', 0),
                    'n_eff': props.get('n_eff', 0),
                    'color': props.get('color', '#10b981'),
                    'opacity': props.get('opacity', 1.0),
                    'size': self._calculate_point_size(props.get('c_hat', 0)),
                    'quality': self._calculate_quality_score(props.get('uncertainty', 0))
                }
            }
            point_features.append(point_feature)
        
        return point_features
    
    def _create_contour_layer(self, features: List[Dict], tile_bounds: List[float]) -> List[Dict]:
        """Create contour polygons for smooth heatmap visualization"""
        contour_features = []
        
        try:
            # Group features by PM2.5 level for contouring
            pm25_levels = [12, 35, 55, 150]  # WHO air quality thresholds
            
            for level in pm25_levels:
                # Find features above this level
                above_level = [f for f in features if f['properties'].get('c_hat', 0) >= level]
                
                if len(above_level) >= 3:  # Need minimum points for contouring
                    # Create approximate contour polygon
                    contour_polygon = self._create_contour_polygon(above_level, level, tile_bounds)
                    
                    if contour_polygon:
                        contour_features.append({
                            'geometry': contour_polygon,
                            'properties': {
                                'level': level,
                                'color': self._get_pm25_color(level),
                                'opacity': 0.3,
                                'stroke_color': self._get_pm25_color(level),
                                'stroke_width': 2
                            }
                        })
        
        except Exception as e:
            logger.warning(f"Contour generation failed: {e}")
        
        return contour_features
    
    def _create_uncertainty_layer(self, features: List[Dict]) -> List[Dict]:
        """Create uncertainty overlay layer"""
        uncertainty_features = []
        
        for feature in features:
            coords = feature['geometry']['coordinates']
            uncertainty = feature['properties'].get('uncertainty', 0)
            
            if uncertainty > 10:  # Only show high uncertainty areas
                # Create uncertainty polygon (small square around point)
                point_size = 0.001  # ~100m at equator
                
                uncertainty_polygon = Polygon([
                    [coords[0] - point_size, coords[1] - point_size],
                    [coords[0] + point_size, coords[1] - point_size],
                    [coords[0] + point_size, coords[1] + point_size],
                    [coords[0] - point_size, coords[1] + point_size],
                    [coords[0] - point_size, coords[1] - point_size]
                ])
                
                uncertainty_features.append({
                    'geometry': uncertainty_polygon,
                    'properties': {
                        'uncertainty': uncertainty,
                        'color': '#ff6b6b',  # Red for high uncertainty
                        'opacity': min(0.8, uncertainty / 20),  # Scale opacity with uncertainty
                        'pattern': 'diagonal-hatch'
                    }
                })
        
        return uncertainty_features
    
    def _tile_to_bounds(self, z: int, x: int, y: int) -> List[float]:
        """Convert tile coordinates to geographic bounds"""
        n = 2.0 ** z
        
        lon_west = x / n * 360.0 - 180.0
        lon_east = (x + 1) / n * 360.0 - 180.0
        
        lat_north_rad = math.atan(math.sinh(math.pi * (1 - 2 * y / n)))
        lat_south_rad = math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n)))
        
        lat_north = math.degrees(lat_north_rad)
        lat_south = math.degrees(lat_south_rad)
        
        return [lon_west, lat_south, lon_east, lat_north]
    
    def _add_buffer_to_bounds(self, bounds: List[float], buffer_ratio: float = 0.1) -> List[float]:
        """Add buffer to bounds for edge handling"""
        west, south, east, north = bounds
        
        width = east - west
        height = north - south
        
        buffer_x = width * buffer_ratio
        buffer_y = height * buffer_ratio
        
        return [
            west - buffer_x,
            south - buffer_y,
            east + buffer_x,
            north + buffer_y
        ]
    
    def _filter_features_by_bounds(self, features: List[Dict], bounds: List[float]) -> List[Dict]:
        """Filter features that intersect with tile bounds"""
        west, south, east, north = bounds
        filtered = []
        
        for feature in features:
            coords = feature['geometry']['coordinates']
            lon, lat = coords[0], coords[1]
            
            if west <= lon <= east and south <= lat <= north:
                filtered.append(feature)
        
        return filtered
    
    def _create_contour_polygon(self, features: List[Dict], level: float, 
                              tile_bounds: List[float]) -> Optional[Polygon]:
        """Create approximate contour polygon for features above threshold"""
        try:
            # Extract coordinates of features above level
            coords = []
            for feature in features:
                if feature['properties'].get('c_hat', 0) >= level:
                    coords.append(feature['geometry']['coordinates'])
            
            if len(coords) < 3:
                return None
            
            # Create convex hull as simple contour approximation
            from scipy.spatial import ConvexHull
            
            points = np.array(coords)
            hull = ConvexHull(points)
            
            # Create polygon from hull vertices
            hull_coords = []
            for vertex in hull.vertices:
                hull_coords.append([points[vertex][0], points[vertex][1]])
            hull_coords.append(hull_coords[0])  # Close polygon
            
            return Polygon(hull_coords)
            
        except Exception as e:
            logger.debug(f"Contour polygon creation failed: {e}")
            return None
    
    def _calculate_point_size(self, pm25_value: float) -> int:
        """Calculate point size based on PM2.5 value"""
        if pm25_value <= 12:
            return 6
        elif pm25_value <= 35:
            return 8
        elif pm25_value <= 55:
            return 10
        else:
            return 12
    
    def _calculate_quality_score(self, uncertainty: float) -> str:
        """Calculate quality score based on uncertainty"""
        if uncertainty <= 5:
            return 'high'
        elif uncertainty <= 15:
            return 'medium'
        else:
            return 'low'
    
    def _encode_empty_tile(self) -> bytes:
        """Encode empty vector tile"""
        return mapbox_vector_tile.encode({})

# Singleton instance
vector_tile_service = VectorTileService()
