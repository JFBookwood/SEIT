import numpy as np
import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timezone
from scipy.spatial.distance import cdist
from sklearn.preprocessing import StandardScaler

from .nasa_satellite_processor import nasa_satellite_processor
from .spatial_alignment_service import spatial_alignment_service

logger = logging.getLogger(__name__)

class CovariateIntegrationService:
    """Service for integrating satellite covariates with sensor data for enhanced interpolation"""
    
    def __init__(self):
        self.covariate_weights = {
            'aod_550nm': 0.3,  # Moderate correlation with PM2.5
            'surface_air_temperature_c': 0.2,  # Meteorological influence
            'relative_humidity_percent': 0.25,  # Strong influence on optical sensors
            'surface_pressure_hpa': 0.1,  # Weak but measurable correlation
            'elevation_m': 0.15  # Topographic influence
        }
        
        # Distance thresholds for covariate matching
        self.matching_config = {
            'max_distance_km': 10,  # Maximum distance for covariate assignment
            'interpolation_method': 'inverse_distance',
            'distance_decay_power': 2.0
        }
    
    async def integrate_satellite_covariates_for_sensors(
        self,
        sensor_data: List[Dict],
        date: str,
        include_aod: bool = True,
        include_temperature: bool = True
    ) -> List[Dict]:
        """Integrate satellite covariates with sensor measurements"""
        try:
            if not sensor_data:
                return []
            
            # Calculate bounding box for all sensors
            sensor_bbox = self._calculate_sensor_bbox(sensor_data)
            
            # Fetch satellite covariates
            covariates = {}
            
            if include_aod:
                aod_data = await nasa_satellite_processor.fetch_modis_aod_for_sensors(
                    sensor_data, date, sensor_bbox
                )
                if aod_data and aod_data.get('grid_data'):
                    covariates['aod'] = aod_data
            
            if include_temperature:
                temp_data = await nasa_satellite_processor.fetch_airs_temperature_for_sensors(
                    sensor_data, date, sensor_bbox
                )
                if temp_data and temp_data.get('grid_data'):
                    covariates['temperature'] = temp_data
            
            # Integrate covariates with sensor data
            enhanced_sensors = []
            for sensor in sensor_data:
                enhanced_sensor = sensor.copy()
                enhanced_sensor['satellite_covariates'] = self._match_covariates_to_sensor(
                    sensor, covariates
                )
                enhanced_sensors.append(enhanced_sensor)
            
            logger.info(f"Integrated satellite covariates for {len(enhanced_sensors)} sensors")
            return enhanced_sensors
            
        except Exception as e:
            logger.error(f"Covariate integration failed: {e}")
            # Return sensors without covariates if integration fails
            return sensor_data
    
    def _match_covariates_to_sensor(
        self, 
        sensor: Dict, 
        covariates: Dict[str, Dict]
    ) -> Dict:
        """Match satellite covariates to individual sensor location"""
        sensor_lat = sensor.get('latitude')
        sensor_lon = sensor.get('longitude')
        
        if not sensor_lat or not sensor_lon:
            return {}
        
        matched_covariates = {}
        
        for covariate_type, covariate_data in covariates.items():
            try:
                grid_data = covariate_data.get('grid_data', [])
                if not grid_data:
                    continue
                
                # Find nearest grid points
                covariate_coords = np.array([
                    [point['latitude'], point['longitude']]
                    for point in grid_data
                ])
                
                if len(covariate_coords) == 0:
                    continue
                
                # Calculate distances
                sensor_coord = np.array([[sensor_lat, sensor_lon]])
                distances = cdist(sensor_coord, covariate_coords, metric='euclidean')[0]
                
                # Convert to kilometers (rough approximation)
                distances_km = distances * 111  # Degrees to km
                
                # Find points within threshold
                within_threshold = distances_km <= self.matching_config['max_distance_km']
                
                if not np.any(within_threshold):
                    # Use nearest point if none within threshold
                    nearest_idx = np.argmin(distances_km)
                    within_threshold[nearest_idx] = True
                
                # Extract covariate values for matching points
                matching_points = [
                    grid_data[i] for i, matches in enumerate(within_threshold) if matches
                ]
                matching_distances = distances_km[within_threshold]
                
                # Interpolate covariate value using inverse distance weighting
                if len(matching_points) == 1:
                    covariate_values = self._extract_covariate_values(matching_points[0], covariate_type)
                else:
                    weights = 1.0 / (matching_distances ** self.matching_config['distance_decay_power'])
                    weights = weights / np.sum(weights)  # Normalize weights
                    
                    covariate_values = {}
                    for point, weight in zip(matching_points, weights):
                        point_values = self._extract_covariate_values(point, covariate_type)
                        for key, value in point_values.items():
                            if key not in covariate_values:
                                covariate_values[key] = 0
                            covariate_values[key] += weight * value
                
                # Add distance information
                covariate_values['nearest_distance_km'] = float(np.min(matching_distances))
                covariate_values['covariate_type'] = covariate_type
                
                matched_covariates[covariate_type] = covariate_values
                
            except Exception as e:
                logger.warning(f"Failed to match {covariate_type} covariates to sensor {sensor.get('sensor_id')}: {e}")
                continue
        
        return matched_covariates
    
    def _extract_covariate_values(self, grid_point: Dict, covariate_type: str) -> Dict:
        """Extract relevant covariate values from grid point"""
        if covariate_type == 'aod':
            return {
                'aod_550nm': grid_point.get('aod_550nm', 0),
                'quality_flag': grid_point.get('quality_flag', 2)
            }
        elif covariate_type == 'temperature':
            return {
                'surface_air_temperature_c': grid_point.get('surface_air_temperature_c', 20),
                'surface_air_temperature_k': grid_point.get('surface_air_temperature_k', 293),
                'relative_humidity_percent': grid_point.get('relative_humidity_percent', 60),
                'surface_pressure_hpa': grid_point.get('surface_pressure_hpa', 1013),
                'quality_flag': grid_point.get('quality_flag', 2)
            }
        else:
            return {}
    
    def _calculate_sensor_bbox(self, sensors: List[Dict]) -> List[float]:
        """Calculate bounding box for sensor array"""
        lats = [s['latitude'] for s in sensors if s.get('latitude')]
        lons = [s['longitude'] for s in sensors if s.get('longitude')]
        
        if not lats or not lons:
            return [-122.5, 37.2, -121.9, 37.9]  # Default area
        
        buffer_deg = 0.1  # 10km buffer approximately
        return [
            min(lons) - buffer_deg,
            min(lats) - buffer_deg,
            max(lons) + buffer_deg,
            max(lats) + buffer_deg
        ]
    
    def calculate_covariate_influence_weights(
        self, 
        sensor_with_covariates: List[Dict]
    ) -> Dict[str, float]:
        """Calculate relative influence weights for different covariates"""
        try:
            # Extract PM2.5 and covariate data
            pm25_values = []
            covariate_arrays = {}
            
            for sensor in sensor_with_covariates:
                pm25 = sensor.get('pm25_corrected') or sensor.get('pm25')
                if pm25 is None:
                    continue
                
                pm25_values.append(pm25)
                
                # Extract covariate values
                sat_covariates = sensor.get('satellite_covariates', {})
                for cov_type, cov_data in sat_covariates.items():
                    if cov_type not in covariate_arrays:
                        covariate_arrays[cov_type] = []
                    
                    # Get primary covariate value
                    if cov_type == 'aod':
                        cov_value = cov_data.get('aod_550nm', 0)
                    elif cov_type == 'temperature':
                        cov_value = cov_data.get('surface_air_temperature_c', 20)
                    else:
                        cov_value = 0
                    
                    covariate_arrays[cov_type].append(cov_value)
            
            if len(pm25_values) < 5:  # Need minimum data for correlation
                return self.covariate_weights  # Use default weights
            
            # Calculate correlations
            pm25_array = np.array(pm25_values)
            correlations = {}
            
            for cov_type, cov_values in covariate_arrays.items():
                if len(cov_values) == len(pm25_values):
                    cov_array = np.array(cov_values)
                    correlation = np.corrcoef(pm25_array, cov_array)[0, 1]
                    correlations[cov_type] = abs(correlation) if not np.isnan(correlation) else 0
            
            # Normalize correlations to weights
            total_correlation = sum(correlations.values()) or 1.0
            influence_weights = {
                cov_type: correlation / total_correlation
                for cov_type, correlation in correlations.items()
            }
            
            logger.info(f"Calculated covariate influence weights: {influence_weights}")
            return influence_weights
            
        except Exception as e:
            logger.warning(f"Failed to calculate covariate weights: {e}")
            return self.covariate_weights

# Singleton instance
covariate_integration_service = CovariateIntegrationService()
