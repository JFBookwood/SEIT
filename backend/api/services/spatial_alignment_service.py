import numpy as np
import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timezone
from scipy.interpolate import griddata, RegularGridInterpolator
from scipy.ndimage import zoom, gaussian_filter
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import Matern, WhiteKernel

logger = logging.getLogger(__name__)

class SpatialAlignmentService:
    """Advanced spatial alignment and downscaling for satellite data"""
    
    def __init__(self):
        # Alignment configurations
        self.alignment_methods = {
            'bilinear': {'order': 1, 'preserve_gradients': True},
            'nearest': {'order': 0, 'preserve_boundaries': True},
            'cubic': {'order': 3, 'smooth_interpolation': True},
            'gaussian_process': {'ml_approach': True, 'uncertainty_quantification': True}
        }
        
        # Quality thresholds
        self.quality_thresholds = {
            'min_valid_pixels': 10,
            'max_interpolation_distance_km': 50,
            'uncertainty_threshold': 0.3
        }
    
    def align_satellite_to_sensor_grid(
        self,
        satellite_data: Dict,
        sensor_locations: List[Dict],
        target_resolution_m: float = 1000,
        method: str = 'bilinear'
    ) -> Dict:
        """Comprehensive spatial alignment of satellite data to sensor grid"""
        try:
            # Extract grid data
            grid_data = satellite_data.get('grid_data', [])
            if not grid_data:
                raise ValueError("No grid data in satellite product")
            
            # Convert to numpy arrays
            sat_coords, sat_values = self._extract_coordinate_arrays(grid_data, satellite_data['product'])
            
            # Generate target grid around sensors
            target_grid = self._generate_target_grid(
                sensor_locations, 
                target_resolution_m
            )
            
            # Perform spatial alignment
            if method == 'gaussian_process':
                aligned_data, alignment_uncertainty = self._gaussian_process_alignment(
                    sat_coords, sat_values, target_grid
                )
            else:
                aligned_data = self._interpolation_alignment(
                    sat_coords, sat_values, target_grid, method
                )
                alignment_uncertainty = self._estimate_interpolation_uncertainty(
                    sat_coords, target_grid, method
                )
            
            # Create aligned grid response
            aligned_result = self._format_aligned_grid(
                target_grid,
                aligned_data,
                alignment_uncertainty,
                satellite_data,
                method
            )
            
            logger.info(f"Spatial alignment completed: {len(grid_data)} -> {len(aligned_result['grid_data'])} cells")
            
            return aligned_result
            
        except Exception as e:
            logger.error(f"Spatial alignment failed: {e}")
            return self._generate_alignment_fallback(satellite_data, sensor_locations)
    
    def _extract_coordinate_arrays(
        self, 
        grid_data: List[Dict], 
        product_type: str
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Extract coordinates and values from grid data"""
        coords = []
        values = []
        
        value_field = self._get_primary_value_field(product_type)
        
        for point in grid_data:
            lat = point.get('latitude')
            lon = point.get('longitude')
            val = point.get(value_field)
            
            if lat is not None and lon is not None and val is not None:
                coords.append([lat, lon])
                values.append(val)
        
        if not coords:
            raise ValueError(f"No valid coordinates found in {product_type} data")
        
        return np.array(coords), np.array(values)
    
    def _get_primary_value_field(self, product_type: str) -> str:
        """Get primary value field for different products"""
        field_mapping = {
            'MOD04_L2': 'aod_550nm',
            'MYD04_L2': 'aod_550nm', 
            'AIRS2RET': 'surface_air_temperature_k',
            'MOD04_L2_MOCK': 'aod_550nm',
            'AIRS2RET_MOCK': 'surface_air_temperature_k'
        }
        
        return field_mapping.get(product_type, 'value')
    
    def _generate_target_grid(
        self, 
        sensor_locations: List[Dict], 
        resolution_m: float
    ) -> Dict:
        """Generate target grid around sensor locations"""
        # Calculate bounds with buffer
        lats = [s['latitude'] for s in sensor_locations if s.get('latitude')]
        lons = [s['longitude'] for s in sensor_locations if s.get('longitude')]
        
        if not lats or not lons:
            # Default SF Bay Area
            west, south, east, north = -122.5, 37.2, -121.9, 37.9
        else:
            buffer_deg = (resolution_m * 5) / 111320  # 5-pixel buffer
            west = min(lons) - buffer_deg
            east = max(lons) + buffer_deg
            south = min(lats) - buffer_deg
            north = max(lats) + buffer_deg
        
        # Convert resolution to degrees
        resolution_deg = resolution_m / 111320
        
        # Generate coordinate arrays
        target_lons = np.arange(west, east, resolution_deg)
        target_lats = np.arange(south, north, resolution_deg)
        
        # Create coordinate grids
        lon_grid, lat_grid = np.meshgrid(target_lons, target_lats)
        
        return {
            'lats': target_lats,
            'lons': target_lons,
            'lat_grid': lat_grid,
            'lon_grid': lon_grid,
            'bounds': [west, south, east, north],
            'resolution_m': resolution_m,
            'shape': lat_grid.shape
        }
    
    def _interpolation_alignment(
        self,
        sat_coords: np.ndarray,
        sat_values: np.ndarray,
        target_grid: Dict,
        method: str
    ) -> np.ndarray:
        """Perform interpolation-based spatial alignment"""
        # Create target coordinate pairs
        target_coords = np.column_stack((
            target_grid['lat_grid'].ravel(),
            target_grid['lon_grid'].ravel()
        ))
        
        # Map method names to scipy interpolation methods
        method_mapping = {
            'bilinear': 'linear',
            'nearest': 'nearest', 
            'cubic': 'cubic'
        }
        
        scipy_method = method_mapping.get(method, 'linear')
        
        # Perform interpolation
        interpolated_values = griddata(
            sat_coords,
            sat_values,
            target_coords,
            method=scipy_method,
            fill_value=np.nan
        )
        
        # Reshape to grid
        aligned_grid = interpolated_values.reshape(target_grid['shape'])
        
        # Apply quality filtering
        if method == 'cubic':
            # Smooth cubic interpolation
            aligned_grid = gaussian_filter(aligned_grid, sigma=0.5)
        
        return aligned_grid
    
    def _gaussian_process_alignment(
        self,
        sat_coords: np.ndarray,
        sat_values: np.ndarray,
        target_grid: Dict
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Advanced ML-based spatial alignment with uncertainty"""
        try:
            # Remove NaN values
            valid_mask = ~np.isnan(sat_values)
            coords_clean = sat_coords[valid_mask]
            values_clean = sat_values[valid_mask]
            
            if len(coords_clean) < 5:
                # Fall back to bilinear if insufficient data
                aligned = self._interpolation_alignment(sat_coords, sat_values, target_grid, 'bilinear')
                uncertainty = np.full(aligned.shape, 0.5)
                return aligned, uncertainty
            
            # Set up Gaussian Process
            kernel = Matern(length_scale=0.1, nu=1.5) + WhiteKernel(noise_level=0.01)
            gp = GaussianProcessRegressor(
                kernel=kernel,
                alpha=1e-6,
                normalize_y=True,
                n_restarts_optimizer=2
            )
            
            # Fit GP model
            gp.fit(coords_clean, values_clean)
            
            # Predict on target grid
            target_coords = np.column_stack((
                target_grid['lat_grid'].ravel(),
                target_grid['lon_grid'].ravel()
            ))
            
            mean_pred, std_pred = gp.predict(target_coords, return_std=True)
            
            # Reshape to grid
            aligned_grid = mean_pred.reshape(target_grid['shape'])
            uncertainty_grid = std_pred.reshape(target_grid['shape'])
            
            logger.info("Gaussian Process alignment completed with uncertainty quantification")
            
            return aligned_grid, uncertainty_grid
            
        except Exception as e:
            logger.warning(f"Gaussian Process alignment failed: {e}, falling back to bilinear")
            aligned = self._interpolation_alignment(sat_coords, sat_values, target_grid, 'bilinear')
            uncertainty = np.full(aligned.shape, 0.3)
            return aligned, uncertainty
    
    def _estimate_interpolation_uncertainty(
        self,
        sat_coords: np.ndarray,
        target_grid: Dict,
        method: str
    ) -> np.ndarray:
        """Estimate uncertainty for interpolation methods"""
        # Calculate distance to nearest satellite pixel for each target point
        target_coords = np.column_stack((
            target_grid['lat_grid'].ravel(),
            target_grid['lon_grid'].ravel()
        ))
        
        # Simple distance-based uncertainty
        uncertainties = []
        for target_point in target_coords:
            distances = np.linalg.norm(sat_coords - target_point, axis=1)
            min_distance = np.min(distances)
            
            # Convert distance to uncertainty (higher uncertainty for distant points)
            distance_km = min_distance * 111  # Rough conversion to km
            uncertainty = min(1.0, distance_km / 50)  # Max uncertainty at 50km
            
            uncertainties.append(uncertainty)
        
        uncertainty_grid = np.array(uncertainties).reshape(target_grid['shape'])
        
        return uncertainty_grid
    
    def _format_aligned_grid(
        self,
        target_grid: Dict,
        aligned_data: np.ndarray,
        uncertainty: np.ndarray,
        source_data: Dict,
        method: str
    ) -> Dict:
        """Format aligned grid data for storage and API response"""
        grid_points = []
        
        lat_grid = target_grid['lat_grid']
        lon_grid = target_grid['lon_grid']
        
        for i in range(lat_grid.shape[0]):
            for j in range(lat_grid.shape[1]):
                if not np.isnan(aligned_data[i, j]):
                    point = {
                        'latitude': float(lat_grid[i, j]),
                        'longitude': float(lon_grid[i, j]),
                        'value': float(aligned_data[i, j]),
                        'uncertainty': float(uncertainty[i, j]),
                        'grid_i': i,
                        'grid_j': j
                    }
                    
                    # Add product-specific fields
                    if 'AOD' in source_data['product']:
                        point['aod_550nm'] = point['value']
                    elif 'AIRS' in source_data['product']:
                        point['surface_air_temperature_k'] = point['value']
                        point['surface_air_temperature_c'] = point['value'] - 273.15
                    
                    grid_points.append(point)
        
        return {
            'product': f"{source_data['product']}_ALIGNED",
            'source_product': source_data['product'],
            'date': source_data['date'],
            'bbox': target_grid['bounds'],
            'grid_data': grid_points,
            'spatial_resolution_m': target_grid['resolution_m'],
            'alignment_method': method,
            'processing_timestamp': datetime.now(timezone.utc).isoformat(),
            'metadata': {
                'source_resolution_m': source_data.get('metadata', {}).get('native_resolution_m'),
                'target_resolution_m': target_grid['resolution_m'],
                'downscaling_factor': source_data.get('metadata', {}).get('native_resolution_m', 10000) / target_grid['resolution_m'],
                'valid_cells': len(grid_points),
                'total_cells': lat_grid.size,
                'coverage_percent': len(grid_points) / lat_grid.size * 100
            }
        }
    
    def _generate_alignment_fallback(
        self, 
        satellite_data: Dict, 
        sensor_locations: List[Dict]
    ) -> Dict:
        """Generate fallback aligned data when processing fails"""
        bounds = self._calculate_sensor_bounds(sensor_locations)
        
        return {
            'product': f"{satellite_data.get('product', 'UNKNOWN')}_FALLBACK",
            'date': satellite_data.get('date'),
            'bbox': bounds,
            'grid_data': [],
            'spatial_resolution_m': 1000,
            'alignment_method': 'fallback',
            'processing_timestamp': datetime.now(timezone.utc).isoformat(),
            'metadata': {
                'error': 'Spatial alignment failed, using fallback',
                'valid_cells': 0
            }
        }
    
    def _calculate_sensor_bounds(self, sensor_locations: List[Dict]) -> List[float]:
        """Calculate bounds for sensor locations"""
        if not sensor_locations:
            return [-122.5, 37.2, -121.9, 37.9]  # Default SF Bay Area
        
        lats = [s['latitude'] for s in sensor_locations if s.get('latitude')]
        lons = [s['longitude'] for s in sensor_locations if s.get('longitude')]
        
        if not lats or not lons:
            return [-122.5, 37.2, -121.9, 37.9]
        
        buffer_deg = 0.05  # ~5km buffer
        return [
            min(lons) - buffer_deg,
            min(lats) - buffer_deg,
            max(lons) + buffer_deg,
            max(lats) + buffer_deg
        ]

# Singleton instance
spatial_alignment_service = SpatialAlignmentService()
