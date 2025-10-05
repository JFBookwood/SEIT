import numpy as np
import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timezone
from scipy.spatial.distance import cdist
from sklearn.metrics import mean_squared_error

logger = logging.getLogger(__name__)

class UncertaintyQuantificationService:
    """Service for calculating and propagating uncertainty in spatial interpolation"""
    
    def __init__(self):
        # Uncertainty sources and weights
        self.uncertainty_sources = {
            'calibration': 0.4,     # Sensor calibration uncertainty
            'interpolation': 0.3,   # Spatial interpolation uncertainty  
            'temporal': 0.2,        # Temporal mismatch uncertainty
            'measurement': 0.1      # Base measurement uncertainty
        }
        
        # Default uncertainty parameters
        self.default_params = {
            'baseline_measurement_uncertainty': 2.0,  # μg/m³
            'max_interpolation_distance_km': 5.0,     # km
            'temporal_decay_hours': 6.0,              # hours
            'uncertainty_floor': 1.0,                 # μg/m³ minimum
            'uncertainty_ceiling': 50.0               # μg/m³ maximum
        }
    
    def calculate_interpolation_uncertainty(
        self, 
        target_coords: Tuple[float, float],
        sensor_data: List[Dict],
        interpolation_weights: np.ndarray,
        method: str = 'idw'
    ) -> float:
        """Calculate uncertainty for interpolated value"""
        try:
            target_lat, target_lon = target_coords
            
            # Calculate distance-based uncertainty
            distances_km = []
            for sensor in sensor_data:
                distance_m = self._haversine_distance(
                    target_lat, target_lon,
                    sensor['latitude'], sensor['longitude']
                )
                distances_km.append(distance_m / 1000)
            
            distances_km = np.array(distances_km)
            
            # Distance uncertainty (increases with distance)
            max_distance = self.default_params['max_interpolation_distance_km']
            distance_uncertainty = np.mean(distances_km) / max_distance * 10  # Scale to ~10 μg/m³ at max distance
            
            # Calibration uncertainty propagation
            calibration_uncertainties = np.array([
                sensor.get('sigma_i', self.default_params['baseline_measurement_uncertainty']) 
                for sensor in sensor_data
            ])
            
            # Weighted average of calibration uncertainties
            calibration_uncertainty = np.sqrt(
                np.sum(interpolation_weights * (calibration_uncertainties ** 2)) / 
                np.sum(interpolation_weights)
            )
            
            # Neighbor count uncertainty (fewer neighbors = higher uncertainty)
            neighbor_count = len(sensor_data)
            neighbor_uncertainty = max(0, (5 - neighbor_count) * 2)  # 2 μg/m³ per missing neighbor below 5
            
            # Combine uncertainty sources
            total_uncertainty = np.sqrt(
                (calibration_uncertainty ** 2) +
                (distance_uncertainty ** 2) + 
                (neighbor_uncertainty ** 2) +
                (self.default_params['baseline_measurement_uncertainty'] ** 2)
            )
            
            # Apply floor and ceiling
            total_uncertainty = max(self.default_params['uncertainty_floor'], total_uncertainty)
            total_uncertainty = min(self.default_params['uncertainty_ceiling'], total_uncertainty)
            
            return float(total_uncertainty)
            
        except Exception as e:
            logger.error(f"Uncertainty calculation failed: {e}")
            return self.default_params['baseline_measurement_uncertainty'] * 3
    
    def calculate_temporal_uncertainty(
        self, 
        target_time: datetime,
        sensor_timestamps: List[datetime]
    ) -> float:
        """Calculate uncertainty due to temporal mismatch"""
        try:
            if not sensor_timestamps:
                return self.default_params['baseline_measurement_uncertainty']
            
            # Calculate time differences in hours
            time_diffs = []
            for sensor_time in sensor_timestamps:
                if sensor_time:
                    diff_hours = abs((target_time - sensor_time).total_seconds() / 3600)
                    time_diffs.append(diff_hours)
            
            if not time_diffs:
                return self.default_params['baseline_measurement_uncertainty']
            
            # Average time difference
            avg_time_diff = np.mean(time_diffs)
            
            # Temporal uncertainty increases with time difference
            decay_rate = 1.0 / self.default_params['temporal_decay_hours']
            temporal_uncertainty = avg_time_diff * decay_rate * 2  # 2 μg/m³ per decay constant
            
            return min(15.0, temporal_uncertainty)  # Cap at 15 μg/m³
            
        except Exception as e:
            logger.error(f"Temporal uncertainty calculation failed: {e}")
            return 3.0  # Default temporal uncertainty
    
    def propagate_uncertainty_through_calibration(
        self,
        raw_pm25: float,
        raw_uncertainty: float,
        calibration_params: Dict
    ) -> Tuple[float, float]:
        """Propagate uncertainty through calibration transformation"""
        try:
            # Extract calibration coefficients
            alpha = calibration_params.get('alpha', 0)
            beta = calibration_params.get('beta', 1)
            gamma = calibration_params.get('gamma', 0)
            delta = calibration_params.get('delta', 0)
            sigma_i = calibration_params.get('sigma_i', 5.0)  # Calibration uncertainty
            
            # Assume typical meteorological values for uncertainty propagation
            rh = calibration_params.get('rh', 50)  # %
            temperature = calibration_params.get('temperature', 20)  # °C
            
            # Apply calibration: c_corr = alpha + beta*c_raw + gamma*rh + delta*t
            c_corrected = alpha + beta * raw_pm25 + gamma * rh + delta * temperature
            
            # Uncertainty propagation using partial derivatives
            # δc_corr/δc_raw = beta
            # δc_corr/δrh = gamma  
            # δc_corr/δt = delta
            
            # Assume meteorological uncertainties
            rh_uncertainty = 5.0  # 5% typical RH uncertainty
            temp_uncertainty = 1.0  # 1°C typical temperature uncertainty
            
            # Total uncertainty using error propagation
            propagated_uncertainty = np.sqrt(
                (beta * raw_uncertainty) ** 2 +  # Raw measurement uncertainty
                (gamma * rh_uncertainty) ** 2 +  # Humidity uncertainty
                (delta * temp_uncertainty) ** 2 + # Temperature uncertainty
                sigma_i ** 2  # Calibration model uncertainty
            )
            
            return float(max(0, c_corrected)), float(propagated_uncertainty)
            
        except Exception as e:
            logger.error(f"Uncertainty propagation failed: {e}")
            return float(max(0, raw_pm25)), float(raw_uncertainty * 1.5)  # Conservative fallback
    
    def calculate_grid_uncertainty_map(
        self,
        grid_coords: np.ndarray,
        sensor_data: List[Dict],
        interpolation_method: str = 'idw'
    ) -> np.ndarray:
        """Calculate uncertainty map for entire interpolation grid"""
        try:
            # Extract sensor coordinates
            sensor_coords = np.array([
                [sensor['latitude'], sensor['longitude']] 
                for sensor in sensor_data
            ])
            
            # Calculate distances from each grid point to all sensors
            distances = cdist(grid_coords, sensor_coords, metric='euclidean')
            
            # Convert to kilometers (approximate)
            distances_km = distances * 111  # Degrees to km approximation
            
            # Calculate uncertainty for each grid point
            uncertainty_map = []
            
            for i, grid_point in enumerate(grid_coords):
                point_distances = distances_km[i]
                
                # Find sensors within search radius
                within_radius = point_distances <= self.default_params['max_interpolation_distance_km']
                
                if not np.any(within_radius):
                    # No sensors within radius - high uncertainty
                    uncertainty_map.append(self.default_params['uncertainty_ceiling'])
                else:
                    # Calculate weighted uncertainty
                    nearby_distances = point_distances[within_radius]
                    nearby_sensors = [sensor_data[j] for j in np.where(within_radius)[0]]
                    
                    # IDW weights
                    if interpolation_method == 'idw':
                        weights = 1.0 / (nearby_distances ** 2 + 0.001)  # Add small constant to avoid division by zero
                        weights = weights / np.sum(weights)
                    else:
                        weights = np.ones(len(nearby_distances)) / len(nearby_distances)
                    
                    # Weighted calibration uncertainty
                    calibration_uncertainties = np.array([
                        sensor.get('sigma_i', self.default_params['baseline_measurement_uncertainty'])
                        for sensor in nearby_sensors
                    ])
                    
                    weighted_calibration_uncertainty = np.sqrt(
                        np.sum(weights * (calibration_uncertainties ** 2))
                    )
                    
                    # Distance penalty
                    avg_distance = np.mean(nearby_distances)
                    distance_penalty = (avg_distance / self.default_params['max_interpolation_distance_km']) * 5
                    
                    # Total uncertainty
                    total_uncertainty = np.sqrt(
                        weighted_calibration_uncertainty ** 2 + distance_penalty ** 2
                    )
                    
                    uncertainty_map.append(
                        np.clip(total_uncertainty, 
                               self.default_params['uncertainty_floor'],
                               self.default_params['uncertainty_ceiling'])
                    )
            
            return np.array(uncertainty_map)
            
        except Exception as e:
            logger.error(f"Grid uncertainty calculation failed: {e}")
            # Return conservative high uncertainty
            return np.full(len(grid_coords), self.default_params['uncertainty_ceiling'])
    
    def validate_uncertainty_estimates(
        self,
        predictions: np.ndarray,
        observations: np.ndarray, 
        uncertainties: np.ndarray,
        confidence_level: float = 0.95
    ) -> Dict[str, float]:
        """Validate uncertainty estimates using observation data"""
        try:
            residuals = np.abs(predictions - observations)
            
            # Calculate coverage for different confidence levels
            confidence_levels = [0.68, 0.90, 0.95, 0.99]
            coverage_stats = {}
            
            for conf_level in confidence_levels:
                # Z-score for confidence level
                z_score = {0.68: 1.0, 0.90: 1.645, 0.95: 1.96, 0.99: 2.576}[conf_level]
                
                # Check coverage
                within_bounds = residuals <= (z_score * uncertainties)
                coverage = np.mean(within_bounds)
                
                coverage_stats[f'coverage_{int(conf_level*100)}'] = float(coverage)
            
            # Reliability metrics
            normalized_residuals = residuals / uncertainties
            chi_squared = np.mean(normalized_residuals ** 2)
            
            # Bias in uncertainty estimates
            uncertainty_bias = np.mean(uncertainties - residuals)
            
            return {
                **coverage_stats,
                'chi_squared': float(chi_squared),
                'uncertainty_bias': float(uncertainty_bias),
                'mean_uncertainty': float(np.mean(uncertainties)),
                'mean_residual': float(np.mean(residuals)),
                'n_validation_points': len(predictions)
            }
            
        except Exception as e:
            logger.error(f"Uncertainty validation failed: {e}")
            return {'error': str(e)}
    
    def _haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance using Haversine formula"""
        R = 6371000  # Earth's radius in meters
        
        lat1_rad = np.radians(lat1)
        lat2_rad = np.radians(lat2)
        delta_lat = np.radians(lat2 - lat1)
        delta_lon = np.radians(lon2 - lon1)
        
        a = (np.sin(delta_lat / 2) ** 2 + 
             np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(delta_lon / 2) ** 2)
        c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
        
        return R * c

# Singleton instance
uncertainty_quantification_service = UncertaintyQuantificationService()
