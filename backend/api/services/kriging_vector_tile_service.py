import json
import logging
from typing import Dict, List, Optional, Any
import numpy as np
import mapbox_vector_tile
from shapely.geometry import Point, Polygon
import geojson
from datetime import datetime, timezone

from .kriging_interpolation_service import kriging_interpolation_service
from .heatmap_cache_service import create_heatmap_cache_service

logger = logging.getLogger(__name__)

class KrigingVectorTileService:
    """Vector tile service specialized for kriging-based heatmaps"""
    
    def __init__(self):
        self.tile_config = {
            'tile_size': 512,  # Higher resolution for kriging details
            'buffer_pixels': 128,
            'simplification_tolerance': 0.5,
            'max_features_per_tile': 1000
        }
        
        # Kriging-specific layer configurations
        self.kriging_layers = {
            'kriging_points': {
                'type': 'circle',
                'paint': {
                    'circle-radius': ['interpolate', ['linear'], ['get', 'total_uncertainty'],
                                    0, 4, 25, 12],
                    'circle-color': ['get', 'color'],
                    'circle-opacity': ['get', 'opacity']
                }
            },
            'kriging_uncertainty': {
                'type': 'circle',
                'paint': {
                    'circle-radius': ['*', ['get', 'total_uncertainty'], 0.5],
                    'circle-color': '#ff6b6b',
                    'circle-opacity': 0.3,
                    'circle-stroke-width': 1,
                    'circle-stroke-color': '#ff6b6b'
                }
            },
            'kriging_contours': {
                'type': 'fill',
                'paint': {
                    'fill-color': ['get', 'color'],
                    'fill-opacity': 0.2
                }
            }
        }
    
    async def generate_kriging_vector_tile(
        self, 
        z: int, 
        x: int, 
        y: int,
        timestamp: str = None,
        layer_types: List[str] = None,
        db_session = None
    ) -> bytes:
        """Generate vector tile for kriging-based heatmap"""
        try:
            if layer_types is None:
                layer_types = ['kriging_points', 'kriging_uncertainty']
            
            # Calculate tile bounds
            tile_bounds = self._tile_to_bounds(z, x, y)
            
            # Add buffer for edge effects
            buffered_bounds = self._add_buffer_to_bounds(tile_bounds, 0.2)
            
            # Check cache first
            cache_service = create_heatmap_cache_service(db_session)
            cached_tile = await cache_service.get_cached_vector_tile(
                z, x, y, timestamp, 'kriging'
            )
            
            if cached_tile:
                return cached_tile
            
            # Generate fresh kriging grid for tile area
            try:
                # Mock sensor data for tile area - in production would query database
                tile_sensors = self._generate_tile_area_sensors(buffered_bounds)
                
                if len(tile_sensors) < 3:
                    return self._encode_empty_tile()
                
                # Generate kriging grid
                kriging_grid = await kriging_interpolation_service.interpolate_grid_with_covariates(
                    tile_sensors,
                    buffered_bounds,
                    resolution_m=500,  # Coarser for tiles
                    timestamp=timestamp,
                    include_nasa_covariates=True
                )
                
                # Convert to vector tile layers
                vector_tile_data = self._create_vector_tile_layers(
                    kriging_grid, 
                    tile_bounds,
                    layer_types
                )
                
                # Encode as vector tile
                encoded_tile = mapbox_vector_tile.encode(vector_tile_data)
                
                # Cache the result
                await cache_service.store_vector_tile(
                    z, x, y, encoded_tile, timestamp, 'kriging'
                )
                
                logger.debug(f"Generated kriging vector tile {z}/{x}/{y}")
                return encoded_tile
                
            except Exception as grid_error:
                logger.warning(f"Kriging grid generation failed for tile {z}/{x}/{y}: {grid_error}")
                return self._encode_empty_tile()
            
        except Exception as e:
            logger.error(f"Kriging vector tile generation failed for {z}/{x}/{y}: {e}")
            return self._encode_empty_tile()
    
    def _create_vector_tile_layers(
        self, 
        kriging_grid: Dict, 
        tile_bounds: List[float],
        layer_types: List[str]
    ) -> Dict:
        """Create vector tile layers from kriging grid"""
        layers = {}
        
        # Filter features to tile bounds
        features = kriging_grid.get('features', [])
        tile_features = self._filter_features_by_bounds(features, tile_bounds)
        
        if not tile_features:
            return {}
        
        # Create point layer
        if 'kriging_points' in layer_types:
            layers['kriging_points'] = self._create_kriging_points_layer(tile_features)
        
        # Create uncertainty layer
        if 'kriging_uncertainty' in layer_types:
            layers['kriging_uncertainty'] = self._create_uncertainty_layer(tile_features)
        
        # Create contour layer
        if 'kriging_contours' in layer_types:
            layers['kriging_contours'] = self._create_contour_layer(tile_features, tile_bounds)
        
        return layers
    
    def _create_kriging_points_layer(self, features: List[Dict]) -> List[Dict]:
        """Create point layer with kriging predictions"""
        point_features = []
        
        for feature in features:
            coords = feature['geometry']['coordinates']
            props = feature['properties']
            
            point_feature = {
                'geometry': Point(coords),
                'properties': {
                    'c_hat': props.get('c_hat', 0),
                    'kriging_variance': props.get('kriging_variance', 0),
                    'kriging_std': props.get('kriging_std', 0),
                    'total_uncertainty': props.get('total_uncertainty', 0),
                    'color': props.get('color', '#10b981'),
                    'opacity': props.get('opacity', 1.0),
                    'method': 'kriging',
                    'covariates_used': props.get('covariates_used', False),
                    # Size based on confidence (lower uncertainty = larger point)
                    'point_size': max(6, 15 - int(props.get('total_uncertainty', 10))),
                    'confidence_level': self._calculate_confidence_level(props.get('total_uncertainty', 10))
                }
            }
            point_features.append(point_feature)
        
        return point_features
    
    def _create_uncertainty_layer(self, features: List[Dict]) -> List[Dict]:
        """Create uncertainty visualization layer"""
        uncertainty_features = []
        
        for feature in features:
            coords = feature['geometry']['coordinates']
            uncertainty = feature['properties'].get('total_uncertainty', 0)
            
            if uncertainty > 8:  # Only show high uncertainty areas
                # Create uncertainty circle
                uncertainty_radius_deg = (uncertainty * 50) / 111320  # Scale uncertainty to degrees
                
                # Create polygon approximating circle
                n_points = 16
                angles = np.linspace(0, 2 * np.pi, n_points)
                circle_coords = []
                
                for angle in angles:
                    lat = coords[1] + uncertainty_radius_deg * np.sin(angle)
                    lon = coords[0] + uncertainty_radius_deg * np.cos(angle)
                    circle_coords.append([lon, lat])
                
                circle_coords.append(circle_coords[0])  # Close polygon
                
                uncertainty_polygon = Polygon([circle_coords])
                
                uncertainty_features.append({
                    'geometry': uncertainty_polygon,
                    'properties': {
                        'uncertainty_value': uncertainty,
                        'uncertainty_level': 'high' if uncertainty > 15 else 'medium',
                        'color': '#ff6b6b',
                        'opacity': min(0.6, uncertainty / 20),
                        'stroke_color': '#dc2626',
                        'stroke_width': 1,
                        'pattern': 'diagonal-lines'
                    }
                })
        
        return uncertainty_features
    
    def _create_contour_layer(self, features: List[Dict], tile_bounds: List[float]) -> List[Dict]:
        """Create contour polygons for smooth visualization"""
        contour_features = []
        
        try:
            # WHO air quality thresholds for contouring
            pm25_levels = [12, 35, 55, 150]
            
            for level in pm25_levels:
                # Find features above this level
                above_level = [f for f in features if f['properties'].get('c_hat', 0) >= level]
                
                if len(above_level) >= 4:  # Need minimum points for contouring
                    # Create approximate contour using convex hull
                    contour_coords = []
                    for feature in above_level:
                        coords = feature['geometry']['coordinates']
                        contour_coords.append(coords)
                    
                    if len(contour_coords) >= 3:
                        try:
                            from scipy.spatial import ConvexHull
                            
                            points = np.array(contour_coords)
                            hull = ConvexHull(points)
                            
                            # Create polygon from hull
                            hull_coords = []
                            for vertex in hull.vertices:
                                hull_coords.append([points[vertex][0], points[vertex][1]])
                            hull_coords.append(hull_coords[0])  # Close polygon
                            
                            contour_polygon = Polygon([hull_coords])
                            
                            contour_features.append({
                                'geometry': contour_polygon,
                                'properties': {
                                    'pm25_level': level,
                                    'color': self._get_level_color(level),
                                    'opacity': 0.25,
                                    'stroke_color': self._get_level_color(level),
                                    'stroke_width': 2,
                                    'level_name': self._get_level_name(level)
                                }
                            })
                            
                        except Exception as e:
                            logger.debug(f"Contour generation failed for level {level}: {e}")
                            continue
        
        except Exception as e:
            logger.warning(f"Contour layer creation failed: {e}")
        
        return contour_features
    
    def _generate_tile_area_sensors(self, bounds: List[float]) -> List[Dict]:
        """Generate mock sensor data for tile area"""
        west, south, east, north = bounds
        
        # Generate sensors for demonstration
        import random
        np.random.seed(42)  # Reproducible
        
        n_sensors = min(25, int((east - west) * (north - south) * 10000))  # Density-based
        sensors = []
        
        for i in range(n_sensors):
            lat = random.uniform(south, north)
            lon = random.uniform(west, east)
            
            # Generate realistic PM2.5 with spatial correlation
            base_pm25 = 20 + np.random.lognormal(0, 0.5)
            
            # Add spatial pattern (higher near urban centers)
            urban_centers = [(37.7749, -122.4194), (34.0522, -118.2437)]  # SF, LA
            urban_factor = 1.0
            
            for center_lat, center_lon in urban_centers:
                distance_km = self._haversine_distance(lat, lon, center_lat, center_lon) / 1000
                if distance_km < 50:  # Within 50km of city
                    urban_factor *= (1 + 0.5 * np.exp(-distance_km / 10))
            
            pm25_value = base_pm25 * urban_factor
            pm25_value = min(200, max(2, pm25_value))  # Realistic bounds
            
            sensor = {
                'sensor_id': f'tile_sensor_{i}',
                'latitude': lat,
                'longitude': lon,
                'pm25_corrected': round(pm25_value, 1),
                'sigma_i': 3.0 + np.random.uniform(1, 4),  # Variable calibration uncertainty
                'source': 'kriging_demo',
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            sensors.append(sensor)
        
        return sensors
    
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
        """Add buffer to bounds for edge effects"""
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
        """Filter features within tile bounds"""
        west, south, east, north = bounds
        filtered = []
        
        for feature in features:
            coords = feature['geometry']['coordinates']
            lon, lat = coords[0], coords[1]
            
            if west <= lon <= east and south <= lat <= north:
                filtered.append(feature)
        
        return filtered
    
    def _calculate_confidence_level(self, uncertainty: float) -> str:
        """Calculate confidence level based on uncertainty"""
        if uncertainty <= 5:
            return 'very_high'
        elif uncertainty <= 10:
            return 'high'
        elif uncertainty <= 20:
            return 'medium'
        else:
            return 'low'
    
    def _get_level_color(self, pm25_level: float) -> str:
        """Get color for PM2.5 threshold level"""
        level_colors = {
            12: '#10b981',   # Good
            35: '#f59e0b',   # Moderate
            55: '#ef4444',   # Unhealthy for sensitive
            150: '#dc2626'   # Unhealthy
        }
        return level_colors.get(pm25_level, '#991b1b')
    
    def _get_level_name(self, pm25_level: float) -> str:
        """Get WHO air quality level name"""
        level_names = {
            12: 'Good',
            35: 'Moderate',
            55: 'Unhealthy for Sensitive Groups',
            150: 'Unhealthy'
        }
        return level_names.get(pm25_level, 'Very Unhealthy')
    
    def _encode_empty_tile(self) -> bytes:
        """Encode empty vector tile"""
        return mapbox_vector_tile.encode({})

# Singleton instance
kriging_vector_tile_service = KrigingVectorTileService()
