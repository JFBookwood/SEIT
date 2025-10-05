import numpy as np
import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timezone
import math
import geojson
from shapely.geometry import Point, Polygon
import json

logger = logging.getLogger(__name__)

class IDWInterpolationService:
    """Service for Inverse Distance Weighting interpolation with uncertainty quantification"""
    
    def __init__(self, power: float = 2.0, search_radius_m: float = 5000):
        self.power = power  # IDW power parameter
        self.search_radius_m = search_radius_m  # Search radius in meters
        
        # Grid configuration
        self.default_resolution_m = 250  # 250m default resolution
        self.max_grid_cells = 10000  # Prevent excessive computation
        self.min_neighbors = 3  # Minimum neighbors for interpolation
        
        # Uncertainty parameters
        self.baseline_uncertainty = 5.0  # Baseline uncertainty (μg/m³)
        self.max_uncertainty = 50.0  # Maximum uncertainty cap
    
    def interpolate_grid(self, sensors: List[Dict], grid_bounds: List[float], 
                        resolution_m: float = None, timestamp: str = None) -> Dict:
        """Generate IDW interpolation grid with uncertainty"""
        try:
            resolution_m = resolution_m or self.default_resolution_m
            
            if not sensors:
                raise ValueError("No sensor data provided for interpolation")
            
            # Validate and prepare sensor data
            valid_sensors = self._validate_sensor_data(sensors)
            if len(valid_sensors) < 2:
                raise ValueError(f"Insufficient valid sensors: {len(valid_sensors)} < 2")
            
            # Generate spatial grid
            grid_coords = self._generate_spatial_grid(grid_bounds, resolution_m)
            
            if len(grid_coords['lats']) * len(grid_coords['lons']) > self.max_grid_cells:
                raise ValueError(f"Grid too large: {len(grid_coords['lats']) * len(grid_coords['lons'])} > {self.max_grid_cells}")
            
            # Perform IDW interpolation
            grid_results = []
            processing_stats = {
                'total_points': 0,
                'interpolated_points': 0,
                'points_with_uncertainty': 0,
                'average_neighbors': 0
            }
            
            for i, lat in enumerate(grid_coords['lats']):
                for j, lon in enumerate(grid_coords['lons']):
                    processing_stats['total_points'] += 1
                    
                    # Perform interpolation for this grid point
                    result = self._interpolate_point(lon, lat, valid_sensors)
                    
                    if result:
                        grid_point = {
                            'type': 'Feature',
                            'geometry': {
                                'type': 'Point',
                                'coordinates': [lon, lat]
                            },
                            'properties': {
                                'c_hat': round(result['c_hat'], 2),
                                'uncertainty': round(result['uncertainty'], 2),
                                'n_eff': result['n_eff'],
                                'grid_i': i,
                                'grid_j': j,
                                'timestamp_utc': timestamp or datetime.now(timezone.utc).isoformat(),
                                'color': self._get_pm25_color(result['c_hat']),
                                'opacity': self._get_uncertainty_opacity(result['uncertainty'])
                            }
                        }
                        grid_results.append(grid_point)
                        processing_stats['interpolated_points'] += 1
                        processing_stats['points_with_uncertainty'] += 1
                        processing_stats['average_neighbors'] += result['n_eff']
            
            # Calculate final statistics
            if processing_stats['interpolated_points'] > 0:
                processing_stats['average_neighbors'] /= processing_stats['interpolated_points']
            
            interpolation_result = {
                'type': 'FeatureCollection',
                'features': grid_results,
                'metadata': {
                    'interpolation_method': 'idw',
                    'power': self.power,
                    'search_radius_m': self.search_radius_m,
                    'grid_resolution_m': resolution_m,
                    'bbox': grid_bounds,
                    'timestamp': timestamp or datetime.now(timezone.utc).isoformat(),
                    'sensors_used': len(valid_sensors),
                    'processing_stats': processing_stats
                }
            }
            
            logger.info(f"IDW interpolation completed: {processing_stats['interpolated_points']}/{processing_stats['total_points']} grid points")
            
            return interpolation_result
            
        except Exception as e:
            logger.error(f"IDW interpolation failed: {e}")
            raise
    
    def _interpolate_point(self, lon: float, lat: float, sensors: List[Dict]) -> Optional[Dict]:
        """Perform IDW interpolation for a single point"""
        try:
            weights = []
            values = []
            uncertainties = []
            
            for sensor in sensors:
                # Calculate distance
                distance_m = self._haversine_distance(
                    lat, lon, 
                    sensor['latitude'], sensor['longitude']
                )
                
                if distance_m <= self.search_radius_m:
                    # IDW weight calculation
                    if distance_m < 1.0:  # Avoid division by zero for co-located points
                        distance_weight = 1.0 / (1.0 ** self.power)
                    else:
                        distance_weight = 1.0 / (distance_m ** self.power)
                    
                    # Calibration uncertainty weight (inverse variance weighting)
                    sensor_sigma = sensor.get('sigma_i', self.baseline_uncertainty)
                    calibration_weight = 1.0 / (sensor_sigma ** 2)
                    
                    # Combined weight
                    final_weight = distance_weight * calibration_weight
                    
                    weights.append(final_weight)
                    values.append(sensor.get('pm25_corrected', sensor.get('pm25', 0)))
                    uncertainties.append(sensor_sigma)
            
            if len(weights) < self.min_neighbors:
                return None  # Insufficient neighbors
            
            weights = np.array(weights)
            values = np.array(values)
            uncertainties = np.array(uncertainties)
            
            # Weighted interpolation
            c_hat = np.sum(weights * values) / np.sum(weights)
            
            # Uncertainty calculation (inverse variance weighting)
            interpolation_uncertainty = 1.0 / np.sqrt(np.sum(weights))
            
            # Combined uncertainty (calibration + interpolation)
            calibration_uncertainty = np.sqrt(np.sum(weights * (uncertainties ** 2)) / np.sum(weights))
            total_uncertainty = np.sqrt(interpolation_uncertainty ** 2 + calibration_uncertainty ** 2)
            
            # Cap uncertainty at reasonable maximum
            total_uncertainty = min(total_uncertainty, self.max_uncertainty)
            
            return {
                'c_hat': max(0.0, c_hat),  # Ensure non-negative
                'uncertainty': total_uncertainty,
                'n_eff': len(weights),
                'interpolation_uncertainty': interpolation_uncertainty,
                'calibration_uncertainty': calibration_uncertainty,
                'neighbors_used': len(weights)
            }
            
        except Exception as e:
            logger.error(f"Point interpolation failed for ({lat}, {lon}): {e}")
            return None
    
    def _validate_sensor_data(self, sensors: List[Dict]) -> List[Dict]:
        """Validate sensor data for interpolation"""
        valid_sensors = []
        
        for sensor in sensors:
            try:
                # Check required fields
                lat = sensor.get('latitude')
                lon = sensor.get('longitude')
                pm25 = sensor.get('pm25_corrected') or sensor.get('pm25')
                
                if lat is None or lon is None or pm25 is None:
                    continue
                
                # Validate coordinates
                if not (-90 <= float(lat) <= 90 and -180 <= float(lon) <= 180):
                    continue
                
                # Validate PM2.5 value
                pm25_float = float(pm25)
                if pm25_float < 0 or pm25_float > 1000:
                    continue
                
                # Add sensor with normalized values
                valid_sensor = {
                    'sensor_id': sensor.get('sensor_id'),
                    'latitude': float(lat),
                    'longitude': float(lon),
                    'pm25_corrected': pm25_float,
                    'pm25': sensor.get('pm25', pm25_float),
                    'sigma_i': sensor.get('sigma_i', self.baseline_uncertainty),
                    'calibration_applied': sensor.get('calibration_applied', False),
                    'source': sensor.get('source', 'unknown'),
                    'timestamp': sensor.get('timestamp')
                }
                valid_sensors.append(valid_sensor)
                
            except Exception as e:
                logger.debug(f"Invalid sensor data skipped: {e}")
                continue
        
        logger.info(f"Validated {len(valid_sensors)}/{len(sensors)} sensors for interpolation")
        return valid_sensors
    
    def _generate_spatial_grid(self, bbox: List[float], resolution_m: float) -> Dict:
        """Generate spatial grid coordinates"""
        west, south, east, north = bbox
        
        # Convert resolution from meters to degrees (approximate)
        resolution_deg = resolution_m / 111320  # ~111320 meters per degree at equator
        
        # Generate coordinate arrays
        lons = np.arange(west, east, resolution_deg)
        lats = np.arange(south, north, resolution_deg)
        
        # Ensure we don't exceed maximum grid size
        if len(lats) * len(lons) > self.max_grid_cells:
            # Reduce resolution to stay within limits
            max_dim = int(np.sqrt(self.max_grid_cells))
            lat_step = (north - south) / max_dim
            lon_step = (east - west) / max_dim
            
            lats = np.linspace(south, north, max_dim)
            lons = np.linspace(west, east, max_dim)
            
            logger.warning(f"Grid size reduced to {max_dim}x{max_dim} to stay within computational limits")
        
        return {
            'lats': lats,
            'lons': lons,
            'resolution_deg': resolution_deg,
            'actual_resolution_m': resolution_deg * 111320
        }
    
    def _haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two points using Haversine formula"""
        R = 6371000  # Earth's radius in meters
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        
        a = (math.sin(delta_lat / 2) ** 2 + 
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c
    
    def _get_pm25_color(self, pm25_value: float) -> str:
        """Get color for PM2.5 value based on WHO air quality guidelines"""
        if pm25_value <= 12:
            return '#10b981'  # Good - Green
        elif pm25_value <= 35:
            return '#f59e0b'  # Moderate - Yellow
        elif pm25_value <= 55:
            return '#ef4444'  # Unhealthy for Sensitive Groups - Orange
        elif pm25_value <= 150:
            return '#dc2626'  # Unhealthy - Red
        else:
            return '#991b1b'  # Very Unhealthy - Dark Red
    
    def _get_uncertainty_opacity(self, uncertainty: float) -> float:
        """Calculate opacity based on uncertainty (lower uncertainty = higher opacity)"""
        # Scale uncertainty to opacity (0.3 to 1.0)
        normalized_uncertainty = min(1.0, uncertainty / self.max_uncertainty)
        opacity = 1.0 - (normalized_uncertainty * 0.7)  # Keep minimum 30% opacity
        return round(max(0.3, opacity), 2)

# Singleton instance
idw_interpolation_service = IDWInterpolationService()
