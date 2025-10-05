import numpy as np
import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timezone
import math
from scipy.optimize import minimize_scalar
from scipy.spatial.distance import cdist
from scipy.linalg import solve, LinAlgError
import json

from .nasa_satellite_processor import nasa_satellite_processor
from .covariate_integration_service import covariate_integration_service

logger = logging.getLogger(__name__)

class KrigingInterpolationService:
    """Universal Kriging with external drift covariates for advanced spatial interpolation"""
    
    def __init__(self):
        # Kriging configuration
        self.config = {
            'default_resolution_m': 250,
            'max_grid_cells': 8000,  # Computational limit
            'min_neighbors': 5,      # Minimum neighbors for kriging
            'max_neighbors': 20,     # Maximum neighbors to consider
            'search_radius_m': 10000, # 10km search radius
            'nugget_default': 0.1,   # Default nugget effect
            'sill_default': 1.0,     # Default sill value
            'range_default': 5000    # Default range in meters
        }
        
        # Supported variogram models
        self.variogram_models = {
            'spherical': self._spherical_model,
            'exponential': self._exponential_model,
            'gaussian': self._gaussian_model,
            'linear': self._linear_model
        }
        
        # Covariate weights for external drift
        self.drift_weights = {
            'aod_550nm': 0.4,                    # Strong correlation with PM2.5
            'surface_air_temperature_c': 0.3,   # Meteorological influence
            'relative_humidity_percent': 0.2,   # Optical sensor bias
            'elevation_m': 0.1                  # Topographic effects
        }
    
    async def interpolate_grid_with_covariates(
        self, 
        sensors: List[Dict], 
        grid_bounds: List[float],
        resolution_m: float = None,
        timestamp: str = None,
        include_nasa_covariates: bool = True
    ) -> Dict:
        """Generate Universal Kriging interpolation with NASA covariates"""
        try:
            resolution_m = resolution_m or self.config['default_resolution_m']
            
            if not sensors:
                raise ValueError("No sensor data provided for kriging")
            
            # Validate and prepare sensor data
            valid_sensors = self._validate_sensor_data(sensors)
            if len(valid_sensors) < self.config['min_neighbors']:
                raise ValueError(f"Insufficient valid sensors: {len(valid_sensors)} < {self.config['min_neighbors']}")
            
            # Fetch NASA covariates if requested
            covariate_data = {}
            if include_nasa_covariates and timestamp:
                covariate_data = await self._fetch_nasa_covariates(grid_bounds, timestamp)
            
            # Generate spatial grid
            grid_coords = self._generate_kriging_grid(grid_bounds, resolution_m)
            
            if len(grid_coords['lats']) * len(grid_coords['lons']) > self.config['max_grid_cells']:
                raise ValueError(f"Grid too large for kriging: {len(grid_coords['lats']) * len(grid_coords['lons'])} > {self.config['max_grid_cells']}")
            
            # Fit semivariogram
            variogram_params = self._fit_empirical_semivariogram(valid_sensors, covariate_data)
            
            # Perform Universal Kriging
            kriging_results = self._perform_universal_kriging(
                valid_sensors, 
                grid_coords, 
                variogram_params,
                covariate_data,
                timestamp
            )
            
            # Format results as GeoJSON
            geojson_result = self._format_kriging_results(
                kriging_results, 
                grid_coords, 
                variogram_params,
                covariate_data
            )
            
            logger.info(f"Universal Kriging completed: {len(kriging_results['predictions'])} grid points")
            
            return geojson_result
            
        except Exception as e:
            logger.error(f"Universal Kriging failed: {e}")
            raise
    
    def _fit_empirical_semivariogram(
        self, 
        sensors: List[Dict],
        covariate_data: Dict = None
    ) -> Dict:
        """Fit empirical semivariogram and theoretical model"""
        try:
            # Extract sensor coordinates and values            n_sensors = len(sensors)
            coordinates = np.array([[s['latitude'], s['longitude']] for s in sensors])
            pm25_values = np.array([s.get('pm25_corrected', s.get('pm25', 0)) for s in sensors])
            
            # Remove residual trend using external drift if available
            if covariate_data:
                trend_residuals = self._remove_external_drift(sensors, pm25_values, covariate_data)
            else:
                trend_residuals = pm25_values - np.mean(pm25_values)  # Simple detrending
            
            # Calculate empirical semivariogram
            max_distance_km = self.config['search_radius_m'] / 1000
            lag_distances, semivariances = self._calculate_empirical_semivariogram(
                coordinates, trend_residuals, max_distance_km
            )
            
            # Fit theoretical semivariogram model
            best_model = None
            best_params = None
            best_fit_score = float('inf')
            
            for model_name in ['spherical', 'exponential', 'gaussian']:
                try:
                    params = self._fit_variogram_model(lag_distances, semivariances, model_name)
                    fit_score = self._evaluate_variogram_fit(lag_distances, semivariances, params, model_name)
                    
                    if fit_score < best_fit_score:
                        best_fit_score = fit_score
                        best_model = model_name
                        best_params = params
                        
                except Exception as e:
                    logger.warning(f"Failed to fit {model_name} model: {e}")
                    continue
            
            if best_model is None:
                # Use default parameters if all models fail
                best_model = 'spherical'
                best_params = {
                    'nugget': self.config['nugget_default'],
                    'sill': self.config['sill_default'],
                    'range': self.config['range_default']
                }
            
            return {
                'model': best_model,
                'parameters': best_params,
                'fit_score': best_fit_score,
                'empirical_data': {
                    'lag_distances': lag_distances.tolist(),
                    'semivariances': semivariances.tolist()
                },
                'n_sensors': n_sensors
            }
            
        except Exception as e:
            logger.error(f"Semivariogram fitting failed: {e}")
            return self._get_default_variogram()
    
    def _calculate_empirical_semivariogram(
        self, 
        coordinates: np.ndarray, 
        residuals: np.ndarray, 
        max_distance_km: float
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Calculate empirical semivariogram from sensor data"""
        # Calculate all pairwise distances
        distances_deg = cdist(coordinates, coordinates, metric='euclidean')
        distances_km = distances_deg * 111  # Convert to km
        
        # Calculate squared differences
        value_matrix = residuals.reshape(-1, 1)
        squared_diffs = (value_matrix - value_matrix.T) ** 2
        
        # Create distance bins
        max_distance = min(max_distance_km, np.max(distances_km))
        n_bins = min(20, int(max_distance / 0.5))  # 500m bins
        bin_edges = np.linspace(0, max_distance, n_bins + 1)
        
        lag_distances = []
        semivariances = []
        
        for i in range(n_bins):
            # Find pairs in this distance bin
            mask = (distances_km >= bin_edges[i]) & (distances_km < bin_edges[i + 1])
            mask = mask & (distances_km > 0)  # Exclude zero distances
            
            if np.sum(mask) > 5:  # Need minimum pairs for reliable estimate
                bin_center = (bin_edges[i] + bin_edges[i + 1]) / 2
                bin_semivariance = np.mean(squared_diffs[mask]) / 2  # Semivariogram = 0.5 * E[(Z(x) - Z(x+h))²]
                
                lag_distances.append(bin_center)
                semivariances.append(bin_semivariance)
        
        return np.array(lag_distances), np.array(semivariances)
    
    def _fit_variogram_model(
        self, 
        lag_distances: np.ndarray, 
        semivariances: np.ndarray, 
        model_name: str
    ) -> Dict:
        """Fit theoretical variogram model to empirical data"""
        if len(lag_distances) < 3:
            return self._get_default_variogram()['parameters']
        
        def objective_function(params):
            nugget, sill, range_param = params
            
            # Ensure valid parameter bounds
            if nugget < 0 or sill <= nugget or range_param <= 0:
                return 1e6
            
            # Calculate theoretical semivariogram
            theoretical = np.zeros_like(lag_distances)
            for i, h in enumerate(lag_distances):
                theoretical[i] = self.variogram_models[model_name](h, nugget, sill, range_param)
            
            # Mean squared error
            mse = np.mean((semivariances - theoretical) ** 2)
            return mse
        
        # Initial parameter estimates
        max_semivariance = np.max(semivariances)
        max_distance = np.max(lag_distances)
        
        initial_params = [
            max_semivariance * 0.1,  # nugget
            max_semivariance * 0.9,  # sill
            max_distance * 0.3       # range
        ]
        
        # Optimize parameters
        try:
            from scipy.optimize import minimize
            
            bounds = [
                (0, max_semivariance * 0.5),           # nugget bounds
                (max_semivariance * 0.1, max_semivariance * 2), # sill bounds
                (max_distance * 0.05, max_distance)    # range bounds
            ]
            
            result = minimize(
                objective_function,
                initial_params,
                method='L-BFGS-B',
                bounds=bounds
            )
            
            if result.success:
                nugget, sill, range_param = result.x
                return {
                    'nugget': float(nugget),
                    'sill': float(sill),
                    'range': float(range_param)
                }
            else:
                logger.warning("Variogram optimization failed, using default parameters")
                return self._get_default_variogram()['parameters']
                
        except Exception as e:
            logger.warning(f"Variogram fitting error: {e}")
            return self._get_default_variogram()['parameters']
    
    def _spherical_model(self, h: float, nugget: float, sill: float, range_param: float) -> float:
        """Spherical variogram model"""
        if h == 0:
            return 0
        elif h <= range_param:
            return nugget + (sill - nugget) * (1.5 * h / range_param - 0.5 * (h / range_param) ** 3)
        else:
            return sill
    
    def _exponential_model(self, h: float, nugget: float, sill: float, range_param: float) -> float:
        """Exponential variogram model"""
        if h == 0:
            return 0
        else:
            return nugget + (sill - nugget) * (1 - np.exp(-3 * h / range_param))
    
    def _gaussian_model(self, h: float, nugget: float, sill: float, range_param: float) -> float:
        """Gaussian variogram model"""
        if h == 0:
            return 0
        else:
            return nugget + (sill - nugget) * (1 - np.exp(-3 * (h / range_param) ** 2))
    
    def _linear_model(self, h: float, nugget: float, sill: float, range_param: float) -> float:
        """Linear variogram model"""
        slope = (sill - nugget) / range_param
        return nugget + slope * min(h, range_param)
    
    def _perform_universal_kriging(
        self, 
        sensors: List[Dict], 
        grid_coords: Dict,
        variogram_params: Dict,
        covariate_data: Dict,
        timestamp: str = None
    ) -> Dict:
        """Perform Universal Kriging with external drift"""
        try:
            n_sensors = len(sensors)
            sensor_coords = np.array([[s['latitude'], s['longitude']] for s in sensors])
            sensor_values = np.array([s.get('pm25_corrected', s.get('pm25', 0)) for s in sensors])
            
            # Build covariance matrix
            C = self._build_covariance_matrix(sensor_coords, variogram_params)
            
            # Prepare external drift matrix
            drift_matrix = self._prepare_drift_matrix(sensors, covariate_data)
            n_drift = drift_matrix.shape[1] if drift_matrix.size > 0 else 1
            
            # Augment system with drift terms
            # [C  X] [λ]   [c]
            # [X' 0] [μ] = [x]
            
            if drift_matrix.size > 0:
                X = drift_matrix
            else:
                X = np.ones((n_sensors, 1))  # Constant drift (ordinary kriging)
            
            # Build augmented matrix
            zeros = np.zeros((n_drift, n_drift))
            
            augmented_matrix = np.block([
                [C, X],
                [X.T, zeros]
            ])
            
            # Perform kriging for each grid point
            predictions = []
            variances = []
            
            lats = grid_coords['lats']
            lons = grid_coords['lons']
            
            for i, lat in enumerate(lats):
                for j, lon in enumerate(lons):
                    try:
                        # Find neighbors within search radius
                        point_coord = np.array([[lat, lon]])
                        distances_m = cdist(point_coord, sensor_coords, metric='euclidean')[0] * 111320
                        
                        neighbor_mask = distances_m <= self.config['search_radius_m']
                        neighbor_indices = np.where(neighbor_mask)[0]
                        
                        if len(neighbor_indices) < self.config['min_neighbors']:
                            predictions.append(np.nan)
                            variances.append(np.nan)
                            continue
                        
                        # Limit to maximum neighbors (computational efficiency)
                        if len(neighbor_indices) > self.config['max_neighbors']:
                            sorted_indices = neighbor_indices[np.argsort(distances_m[neighbor_indices])]
                            neighbor_indices = sorted_indices[:self.config['max_neighbors']]
                        
                        # Build local kriging system
                        local_coords = sensor_coords[neighbor_indices]
                        local_values = sensor_values[neighbor_indices]
                        local_drift = X[neighbor_indices] if X.size > 0 else np.ones((len(neighbor_indices), 1))
                        
                        # Build local covariance matrix
                        C_local = self._build_covariance_matrix(local_coords, variogram_params)
                        
                        # Kriging system
                        n_local = len(neighbor_indices)
                        n_drift_local = local_drift.shape[1]
                        
                        augmented_local = np.block([
                            [C_local, local_drift],
                            [local_drift.T, np.zeros((n_drift_local, n_drift_local))]
                        ])
                        
                        # Covariance vector from target point to sensors
                        c_vector = self._calculate_covariance_vector(
                            point_coord, local_coords, variogram_params
                        )
                        
                        # External drift at target point
                        target_drift = self._get_target_drift(lat, lon, covariate_data)
                        
                        # Right-hand side
                        rhs = np.concatenate([c_vector, target_drift])
                        
                        # Solve kriging system
                        weights = solve(augmented_local, rhs)
                        
                        # Kriging prediction
                        lambda_weights = weights[:n_local]
                        c_hat = np.sum(lambda_weights * local_values)
                        
                        # Kriging variance
                        kriging_variance = variogram_params['parameters']['sill'] - np.dot(weights[:n_local], c_vector)
                        kriging_variance = max(0, kriging_variance)  # Ensure non-negative
                        
                        predictions.append(c_hat)
                        variances.append(kriging_variance)
                        
                    except LinAlgError as e:
                        logger.warning(f"Kriging system singular at ({lat:.4f}, {lon:.4f}): {e}")
                        predictions.append(np.nan)
                        variances.append(np.nan)
                    except Exception as e:
                        logger.debug(f"Kriging failed at ({lat:.4f}, {lon:.4f}): {e}")
                        predictions.append(np.nan)
                        variances.append(np.nan)
            
            return {
                'predictions': np.array(predictions),
                'variances': np.array(variances),
                'variogram_params': variogram_params,
                'covariate_data': covariate_data,
                'grid_shape': (len(lats), len(lons))
            }
            
        except Exception as e:
            logger.error(f"Universal kriging computation failed: {e}")
            raise
    
    def _build_covariance_matrix(self, coordinates: np.ndarray, variogram_params: Dict) -> np.ndarray:
        """Build covariance matrix from variogram parameters"""
        n_points = len(coordinates)
        C = np.zeros((n_points, n_points))
        
        params = variogram_params['parameters']
        model_name = variogram_params['model']
        variogram_func = self.variogram_models[model_name]
        
        # Calculate distances
        distances_deg = cdist(coordinates, coordinates, metric='euclidean')
        distances_km = distances_deg * 111  # Convert to km
        
        # Fill covariance matrix: C(h) = sill - γ(h)
        for i in range(n_points):
            for j in range(n_points):
                h = distances_km[i, j]
                semivariance = variogram_func(h, params['nugget'], params['sill'], params['range'])
                C[i, j] = params['sill'] - semivariance
        
        # Ensure positive definiteness
        min_eigenval = np.min(np.linalg.eigvals(C))
        if min_eigenval <= 0:
            C += np.eye(n_points) * (abs(min_eigenval) + 1e-6)
        
        return C
    
    def _prepare_drift_matrix(self, sensors: List[Dict], covariate_data: Dict) -> np.ndarray:
        """Prepare external drift matrix from NASA covariates"""
        if not covariate_data:
            # Constant drift only (ordinary kriging)
            return np.ones((len(sensors), 1))
        
        n_sensors = len(sensors)
        drift_components = []
        
        # Add constant term
        drift_components.append(np.ones(n_sensors))
        
        # Add spatial trend terms
        sensor_lats = np.array([s['latitude'] for s in sensors])
        sensor_lons = np.array([s['longitude'] for s in sensors])
        
        # Linear spatial trends
        drift_components.append(sensor_lats - np.mean(sensor_lats))
        drift_components.append(sensor_lons - np.mean(sensor_lons))
        
        # Add NASA covariate terms
        for covariate_type, covariate_values in covariate_data.items():
            if covariate_type in ['aod', 'temperature']:
                covariate_grid = covariate_values.get('grid_data', [])
                if covariate_grid:
                    sensor_covariates = self._interpolate_covariates_to_sensors(
                        sensors, covariate_grid, covariate_type
                    )
                    if len(sensor_covariates) == n_sensors:
                        # Normalize covariate values
                        normalized_cov = (sensor_covariates - np.mean(sensor_covariates)) / (np.std(sensor_covariates) + 1e-6)
                        drift_components.append(normalized_cov)
        
        return np.column_stack(drift_components)
    
    def _interpolate_covariates_to_sensors(
        self, 
        sensors: List[Dict], 
        covariate_grid: List[Dict],
        covariate_type: str
    ) -> np.ndarray:
        """Interpolate NASA covariate data to sensor locations"""
        sensor_values = []
        
        for sensor in sensors:
            sensor_lat = sensor['latitude']
            sensor_lon = sensor['longitude']
            
            # Find nearest covariate grid points
            min_distance = float('inf')
            nearest_value = 0
            
            for grid_point in covariate_grid:
                grid_lat = grid_point['latitude']
                grid_lon = grid_point['longitude']
                
                distance = self._haversine_distance(sensor_lat, sensor_lon, grid_lat, grid_lon)
                
                if distance < min_distance:
                    min_distance = distance
                    
                    # Extract appropriate value based on covariate type
                    if covariate_type == 'aod':
                        nearest_value = grid_point.get('aod_550nm', 0.15)
                    elif covariate_type == 'temperature':
                        nearest_value = grid_point.get('surface_air_temperature_c', 20)
                    else:
                        nearest_value = 0
            
            sensor_values.append(nearest_value)
        
        return np.array(sensor_values)
    
    def _calculate_covariance_vector(
        self, 
        target_coord: np.ndarray, 
        sensor_coords: np.ndarray,
        variogram_params: Dict
    ) -> np.ndarray:
        """Calculate covariance vector from target point to sensors"""
        n_sensors = len(sensor_coords)
        c_vector = np.zeros(n_sensors)
        
        params = variogram_params['parameters']
        model_name = variogram_params['model']
        variogram_func = self.variogram_models[model_name]
        
        # Calculate distances from target to each sensor
        distances_deg = cdist(target_coord, sensor_coords, metric='euclidean')[0]
        distances_km = distances_deg * 111
        
        for i, h in enumerate(distances_km):
            semivariance = variogram_func(h, params['nugget'], params['sill'], params['range'])
            c_vector[i] = params['sill'] - semivariance
        
        return c_vector
    
    def _get_target_drift(self, lat: float, lon: float, covariate_data: Dict) -> np.ndarray:
        """Get external drift values at target location"""
        drift_values = [1.0]  # Constant term
        
        # Add spatial trend terms (assuming these were included in fitting)
        drift_values.append(0.0)  # Latitude trend (centered)
        drift_values.append(0.0)  # Longitude trend (centered)
        
        # Add NASA covariate values at target location
        if covariate_data:
            for covariate_type, covariate_values in covariate_data.items():
                if covariate_type in ['aod', 'temperature']:
                    covariate_grid = covariate_values.get('grid_data', [])
                    if covariate_grid:
                        # Find nearest covariate value
                        min_distance = float('inf')
                        nearest_value = 0
                        
                        for grid_point in covariate_grid:
                            distance = self._haversine_distance(
                                lat, lon,
                                grid_point['latitude'], grid_point['longitude']
                            )
                            
                            if distance < min_distance:
                                min_distance = distance
                                if covariate_type == 'aod':
                                    nearest_value = grid_point.get('aod_550nm', 0.15)
                                elif covariate_type == 'temperature':
                                    nearest_value = grid_point.get('surface_air_temperature_c', 20)
                        
                        drift_values.append(nearest_value)
        
        return np.array(drift_values)
    
    def _remove_external_drift(
        self, 
        sensors: List[Dict], 
        values: np.ndarray,
        covariate_data: Dict
    ) -> np.ndarray:
        """Remove external drift using covariates"""
        if not covariate_data:
            return values - np.mean(values)
        
        # Prepare drift matrix
        drift_matrix = self._prepare_drift_matrix(sensors, covariate_data)
        
        try:
            # Fit drift model using least squares
            drift_coeffs = np.linalg.lstsq(drift_matrix, values, rcond=None)[0]
            
            # Calculate drift component
            drift_component = drift_matrix @ drift_coeffs
            
            # Return residuals
            return values - drift_component
            
        except Exception as e:
            logger.warning(f"Drift removal failed: {e}")
            return values - np.mean(values)
    
    async def _fetch_nasa_covariates(self, bbox: List[float], timestamp: str) -> Dict:
        """Fetch NASA satellite covariates for external drift"""
        try:
            # Parse timestamp
            target_date = timestamp.split('T')[0] if 'T' in timestamp else timestamp
            
            # Create mock sensor locations for covariate grid
            west, south, east, north = bbox
            mock_sensors = []
            
            # Create grid of locations for covariate sampling
            lat_step = (north - south) / 10
            lon_step = (east - west) / 10
            
            for i in range(11):
                for j in range(11):
                    lat = south + i * lat_step
                    lon = west + j * lon_step
                    mock_sensors.append({
                        'latitude': lat,
                        'longitude': lon,
                        'sensor_id': f'grid_{i}_{j}'
                    })
            
            # Fetch MODIS AOD
            aod_data = await nasa_satellite_processor.fetch_modis_aod_for_sensors(
                mock_sensors, target_date, bbox
            )
            
            # Fetch AIRS temperature
            temperature_data = await nasa_satellite_processor.fetch_airs_temperature_for_sensors(
                mock_sensors, target_date, bbox
            )
            
            covariate_result = {}
            if aod_data:
                covariate_result['aod'] = aod_data
            if temperature_data:
                covariate_result['temperature'] = temperature_data
            
            logger.info(f"Fetched {len(covariate_result)} NASA covariate datasets")
            
            return covariate_result
            
        except Exception as e:
            logger.warning(f"NASA covariate fetch failed: {e}")
            return {}
    
    def _format_kriging_results(
        self, 
        kriging_results: Dict, 
        grid_coords: Dict,
        variogram_params: Dict,
        covariate_data: Dict
    ) -> Dict:
        """Format kriging results as GeoJSON with uncertainty"""
        features = []
        
        predictions = kriging_results['predictions'].reshape(kriging_results['grid_shape'])
        variances = kriging_results['variances'].reshape(kriging_results['grid_shape'])
        
        lats = grid_coords['lats']
        lons = grid_coords['lons']
        
        for i, lat in enumerate(lats):
            for j, lon in enumerate(lons):
                c_hat = predictions[i, j]
                kriging_variance = variances[i, j]
                
                if not np.isnan(c_hat) and not np.isnan(kriging_variance):
                    # Calculate total uncertainty (kriging + calibration)
                    kriging_std = np.sqrt(max(0, kriging_variance))
                    calibration_uncertainty = 3.0  # Average calibration uncertainty
                    total_uncertainty = np.sqrt(kriging_std ** 2 + calibration_uncertainty ** 2)
                    
                    feature = {
                        'type': 'Feature',
                        'geometry': {
                            'type': 'Point',
                            'coordinates': [lon, lat]
                        },
                        'properties': {
                            'c_hat': round(max(0, c_hat), 2),
                            'kriging_variance': round(float(kriging_variance), 4),
                            'kriging_std': round(float(kriging_std), 2),
                            'total_uncertainty': round(float(total_uncertainty), 2),
                            'grid_i': i,
                            'grid_j': j,
                            'method': 'universal_kriging',
                            'color': self._get_pm25_color(max(0, c_hat)),
                            'opacity': self._get_uncertainty_opacity(total_uncertainty),
                            'covariates_used': len(covariate_data) > 0
                        }
                    }
                    features.append(feature)
        
        return {
            'type': 'FeatureCollection',
            'features': features,
            'metadata': {
                'interpolation_method': 'universal_kriging',
                'variogram_model': variogram_params['model'],
                'variogram_parameters': variogram_params['parameters'],
                'grid_resolution_m': grid_coords['resolution_m'],
                'bbox': grid_coords['bounds'],
                'nasa_covariates': list(covariate_data.keys()),
                'processing_timestamp': datetime.now(timezone.utc).isoformat(),
                'total_grid_points': len(features),
                'uncertainty_source': 'kriging_variance_plus_calibration'
            }
        }
    
    def _validate_sensor_data(self, sensors: List[Dict]) -> List[Dict]:
        """Validate sensor data for kriging interpolation"""
        valid_sensors = []
        
        for sensor in sensors:
            try:
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
                
                valid_sensor = {
                    'sensor_id': sensor.get('sensor_id'),
                    'latitude': float(lat),
                    'longitude': float(lon),
                    'pm25_corrected': pm25_float,
                    'sigma_i': sensor.get('sigma_i', 5.0),
                    'source': sensor.get('source', 'unknown'),
                    'timestamp': sensor.get('timestamp')
                }
                valid_sensors.append(valid_sensor)
                
            except Exception as e:
                logger.debug(f"Invalid sensor data skipped: {e}")
                continue
        
        return valid_sensors
    
    def _generate_kriging_grid(self, bbox: List[float], resolution_m: float) -> Dict:
        """Generate spatial grid for kriging interpolation"""
        west, south, east, north = bbox
        
        # Convert resolution to degrees
        resolution_deg = resolution_m / 111320
        
        # Generate coordinate arrays
        lons = np.arange(west, east, resolution_deg)
        lats = np.arange(south, north, resolution_deg)
        
        # Validate grid size
        if len(lats) * len(lons) > self.config['max_grid_cells']:
            max_dim = int(np.sqrt(self.config['max_grid_cells']))
            lats = np.linspace(south, north, max_dim)
            lons = np.linspace(west, east, max_dim)
            logger.warning(f"Grid reduced to {max_dim}x{max_dim} for computational efficiency")
        
        return {
            'lats': lats,
            'lons': lons,
            'bounds': bbox,
            'resolution_m': resolution_m,
            'actual_resolution_deg': resolution_deg
        }
    
    def _evaluate_variogram_fit(
        self, 
        lag_distances: np.ndarray, 
        semivariances: np.ndarray,
        params: Dict,
        model_name: str
    ) -> float:
        """Evaluate quality of variogram model fit"""
        variogram_func = self.variogram_models[model_name]
        
        theoretical_values = np.array([
            variogram_func(h, params['nugget'], params['sill'], params['range'])
            for h in lag_distances
        ])
        
        # Calculate weighted sum of squared errors
        weights = 1.0 / (semivariances + 1e-6)  # Weight by inverse variance
        wsse = np.sum(weights * (semivariances - theoretical_values) ** 2)
        
        return wsse
    
    def _get_default_variogram(self) -> Dict:
        """Get default variogram parameters"""
        return {
            'model': 'spherical',
            'parameters': {
                'nugget': self.config['nugget_default'],
                'sill': self.config['sill_default'],
                'range': self.config['range_default']
            },
            'fit_score': float('inf')
        }
    
    def _haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance using Haversine formula"""
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
        """Get color for PM2.5 value based on WHO guidelines"""
        if pm25_value <= 12:
            return '#10b981'  # Good - Green
        elif pm25_value <= 35:
            return '#f59e0b'  # Moderate - Yellow
        elif pm25_value <= 55:
            return '#ef4444'  # Unhealthy for Sensitive - Orange
        elif pm25_value <= 150:
            return '#dc2626'  # Unhealthy - Red
        else:
            return '#991b1b'  # Very Unhealthy - Dark Red
    
    def _get_uncertainty_opacity(self, uncertainty: float) -> float:
        """Calculate opacity based on uncertainty"""
        max_uncertainty = 50.0
        normalized_uncertainty = min(1.0, uncertainty / max_uncertainty)
        opacity = 1.0 - (normalized_uncertainty * 0.6)
        return round(max(0.4, opacity), 2)

# Singleton instance
kriging_interpolation_service = KrigingInterpolationService()
