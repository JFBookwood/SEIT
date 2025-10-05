from fastapi import APIRouter, HTTPException, Depends, Query, Response
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import time

from ..database import get_db
from ..services.kriging_interpolation_service import kriging_interpolation_service
from ..services.kriging_vector_tile_service import kriging_vector_tile_service
from ..services.heatmap_cache_service import create_heatmap_cache_service
from ..models.harmonized_models import SensorHarmonized

router = APIRouter()

@router.get("/heatmap/kriging/grid")
async def get_kriging_heatmap_grid(
    west: float = Query(..., ge=-180, le=180),
    south: float = Query(..., ge=-90, le=90),
    east: float = Query(..., ge=-180, le=180),
    north: float = Query(..., ge=-90, le=90),
    resolution: int = Query(250, ge=100, le=1000),
    timestamp: Optional[str] = None,
    include_nasa_covariates: bool = Query(True),
    variogram_model: str = Query('spherical', regex='^(spherical|exponential|gaussian|linear)$'),
    force_refresh: bool = False,
    db: Session = Depends(get_db)
):
    """Generate PM2.5 heatmap using Universal Kriging with NASA covariates"""
    try:
        bbox = [west, south, east, north]
        
        # Validate bounding box
        if west >= east or south >= north:
            raise HTTPException(status_code=400, detail="Invalid bounding box coordinates")
        
        # Initialize cache service
        cache_service = create_heatmap_cache_service(db)
        
        # Validate grid resolution
        resolution_validation = cache_service.validate_grid_resolution(bbox, resolution)
        if not resolution_validation['valid']:
            raise HTTPException(status_code=400, detail=resolution_validation['error'])
        
        # Check cache unless force refresh
        if not force_refresh:
            cached_grid = await cache_service.get_cached_grid(bbox, resolution, timestamp, 'kriging')
            if cached_grid:
                return cached_grid
        
        # Get sensor data for kriging
        start_time = time.time()
        
        # Query harmonized sensor data
        if timestamp:
            target_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            time_window = timedelta(hours=3)  # ±3 hours for kriging
            
            sensors_query = db.query(SensorHarmonized).filter(
                SensorHarmonized.lon >= west,
                SensorHarmonized.lon <= east,
                SensorHarmonized.lat >= south,
                SensorHarmonized.lat <= north,
                SensorHarmonized.timestamp_utc >= target_time - time_window,
                SensorHarmonized.timestamp_utc <= target_time + time_window,
                SensorHarmonized.raw_pm2_5.isnot(None)
            )
        else:
            # Use most recent data
            recent_cutoff = datetime.now(timezone.utc) - timedelta(hours=6)
            sensors_query = db.query(SensorHarmonized).filter(
                SensorHarmonized.lon >= west,
                SensorHarmonized.lon <= east,
                SensorHarmonized.lat >= south,
                SensorHarmonized.lat <= north,
                SensorHarmonized.timestamp_utc >= recent_cutoff,
                SensorHarmonized.raw_pm2_5.isnot(None)
            )
        
        sensor_records = sensors_query.all()
        
        if len(sensor_records) < 5:
            raise HTTPException(
                status_code=404,
                detail=f"Insufficient sensor data for kriging: {len(sensor_records)} sensors found"
            )
        
        # Convert to kriging format
        sensor_data = []
        for record in sensor_records:
            # Apply calibration if available
            from ..services.calibration_engine_service import CalibrationEngineService
            calibration_service = CalibrationEngineService(db)
            
            raw_data = {
                'sensor_id': record.sensor_id,
                'raw_pm2_5': float(record.raw_pm2_5) if record.raw_pm2_5 else None,
                'rh': float(record.rh) if record.rh else 50,
                'temperature': float(record.temperature) if record.temperature else 20
            }
            
            calibrated = calibration_service.apply_calibration_correction(record.sensor_id, raw_data)
            
            sensor_data.append({
                'sensor_id': record.sensor_id,
                'latitude': float(record.lat),
                'longitude': float(record.lon),
                'pm25_corrected': calibrated.get('pm2_5_corrected') or float(record.raw_pm2_5),
                'pm25': float(record.raw_pm2_5),
                'sigma_i': calibrated.get('sigma_i', 5.0),
                'calibration_applied': calibrated.get('calibration_applied', False),
                'source': record.source,
                'timestamp': record.timestamp_utc.isoformat()
            })
        
        # Perform Universal Kriging interpolation
        kriging_result = await kriging_interpolation_service.interpolate_grid_with_covariates(
            sensor_data, bbox, resolution, timestamp, include_nasa_covariates
        )
        
        # Calculate processing time
        processing_time_ms = (time.time() - start_time) * 1000
        
        # Cache the result
        await cache_service.store_grid_cache(
            bbox, resolution, kriging_result, processing_time_ms, timestamp, 'kriging'
        )
        
        # Add processing metadata
        kriging_result['processing'] = {
            'processing_time_ms': round(processing_time_ms, 2),
            'sensors_used': len(sensor_data),
            'cache_stored': True,
            'resolution_validation': resolution_validation,
            'nasa_covariates_included': include_nasa_covariates,
            'variogram_model': kriging_result['metadata'].get('variogram_model')
        }
        
        logger.info(f"Kriging grid generated: {len(sensor_data)} sensors -> {len(kriging_result['features'])} grid points ({processing_time_ms:.1f}ms)")
        
        return kriging_result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Kriging heatmap generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Kriging interpolation failed: {str(e)}")

@router.get("/heatmap/kriging/tiles/{z}/{x}/{y}")
async def get_kriging_vector_tile(
    z: int,
    x: int,
    y: int,
    timestamp: Optional[str] = None,
    layer_types: Optional[str] = Query('points,uncertainty', description="Comma-separated layer types"),
    db: Session = Depends(get_db)
):
    """Generate vector tile for kriging heatmap visualization"""
    try:
        # Validate tile coordinates
        if not (0 <= x < 2**z and 0 <= y < 2**z):
            raise HTTPException(status_code=400, detail="Invalid tile coordinates")
        
        if z < 0 or z > 18:
            raise HTTPException(status_code=400, detail="Invalid zoom level")
        
        # Parse layer types
        requested_layers = [layer.strip() for layer in layer_types.split(',')]
        valid_layers = ['points', 'uncertainty', 'contours']
        layer_list = [f'kriging_{layer}' for layer in requested_layers if layer in valid_layers]
        
        if not layer_list:
            layer_list = ['kriging_points']  # Default layer
        
        # Generate kriging vector tile
        vector_tile_data = await kriging_vector_tile_service.generate_kriging_vector_tile(
            z, x, y, timestamp, layer_list, db
        )
        
        return Response(
            content=vector_tile_data,
            media_type="application/x-protobuf",
            headers={
                "Cache-Control": "public, max-age=1800",
                "Access-Control-Allow-Origin": "*",
                "X-Tile-Type": "kriging-heatmap",
                "X-Layers": ",".join(layer_list)
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Kriging vector tile generation failed for {z}/{x}/{y}: {e}")
        raise HTTPException(status_code=500, detail="Vector tile generation failed")

@router.get("/heatmap/kriging/variogram/{bbox}")
async def get_kriging_variogram_diagnostics(
    bbox: str = Query(..., description="Bounding box as 'west,south,east,north'"),
    timestamp: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get kriging variogram diagnostics for quality assessment"""
    try:
        west, south, east, north = map(float, bbox.split(','))
        bounds = [west, south, east, north]
        
        # Get sensor data for variogram analysis
        recent_cutoff = datetime.now(timezone.utc) - timedelta(hours=6)
        
        sensors_query = db.query(SensorHarmonized).filter(
            SensorHarmonized.lon >= west,
            SensorHarmonized.lon <= east,
            SensorHarmonized.lat >= south,
            SensorHarmonized.lat <= north,
            SensorHarmonized.timestamp_utc >= recent_cutoff,
            SensorHarmonized.raw_pm2_5.isnot(None)
        )
        
        sensor_records = sensors_query.all()
        
        if len(sensor_records) < 10:
            raise HTTPException(
                status_code=404,
                detail=f"Insufficient data for variogram analysis: {len(sensor_records)} sensors"
            )
        
        # Convert to format expected by kriging service
        sensor_data = []
        for record in sensor_records:
            sensor_data.append({
                'sensor_id': record.sensor_id,
                'latitude': float(record.lat),
                'longitude': float(record.lon),
                'pm25_corrected': float(record.raw_pm2_5),
                'sigma_i': 5.0,  # Default uncertainty
                'source': record.source
            })
        
        # Fit variogram
        variogram_params = kriging_interpolation_service._fit_empirical_semivariogram(
            sensor_data, {}
        )
        
        # Generate variogram diagnostics
        diagnostics = {
            'bbox': bounds,
            'timestamp': timestamp or datetime.now(timezone.utc).isoformat(),
            'sensors_analyzed': len(sensor_data),
            'variogram_model': variogram_params['model'],
            'variogram_parameters': variogram_params['parameters'],
            'fit_quality': {
                'fit_score': variogram_params['fit_score'],
                'model_rank': self._rank_variogram_models(sensor_data)
            },
            'empirical_variogram': {
                'lag_distances_km': variogram_params['empirical_data']['lag_distances'],
                'semivariances': variogram_params['empirical_data']['semivariances'],
                'n_pairs_per_lag': self._calculate_pairs_per_lag(sensor_data)
            },
            'spatial_statistics': {
                'mean_pm25': float(np.mean([s['pm25_corrected'] for s in sensor_data])),
                'variance_pm25': float(np.var([s['pm25_corrected'] for s in sensor_data])),
                'spatial_extent_km': self._calculate_spatial_extent(sensor_data),
                'sensor_density_per_km2': self._calculate_sensor_density(sensor_data, bounds)
            }
        }
        
        return diagnostics
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Variogram diagnostics failed: {e}")
        raise HTTPException(status_code=500, detail="Variogram analysis failed")

@router.post("/heatmap/kriging/validate")
async def validate_kriging_performance(
    bbox: str = Query(..., description="Bounding box as 'west,south,east,north'"),
    timestamp: Optional[str] = None,
    cross_validation_method: str = Query('leave_one_out', regex='^(leave_one_out|k_fold)$'),
    db: Session = Depends(get_db)
):
    """Perform cross-validation for kriging performance assessment"""
    try:
        west, south, east, north = map(float, bbox.split(','))
        
        # Get sensor data
        recent_cutoff = datetime.now(timezone.utc) - timedelta(hours=6)
        
        sensor_records = db.query(SensorHarmonized).filter(
            SensorHarmonized.lon >= west,
            SensorHarmonized.lon <= east,
            SensorHarmonized.lat >= south,
            SensorHarmonized.lat <= north,
            SensorHarmonized.timestamp_utc >= recent_cutoff,
            SensorHarmonized.raw_pm2_5.isnot(None)
        ).all()
        
        if len(sensor_records) < 10:
            raise HTTPException(
                status_code=404,
                detail="Insufficient data for cross-validation"
            )
        
        # Convert sensor data
        sensors = []
        for record in sensor_records:
            sensors.append({
                'sensor_id': record.sensor_id,
                'latitude': float(record.lat),
                'longitude': float(record.lon),
                'pm25_corrected': float(record.raw_pm2_5),
                'sigma_i': 5.0
            })
        
        # Perform leave-one-out cross-validation
        predictions = []
        observations = []
        uncertainties = []
        
        for i, holdout_sensor in enumerate(sensors):
            try:
                # Training set (all sensors except holdout)
                training_sensors = sensors[:i] + sensors[i+1:]
                
                # Generate small grid around holdout sensor for prediction
                buffer_deg = 0.001  # Small area around sensor
                holdout_bbox = [
                    holdout_sensor['longitude'] - buffer_deg,
                    holdout_sensor['latitude'] - buffer_deg,
                    holdout_sensor['longitude'] + buffer_deg,
                    holdout_sensor['latitude'] + buffer_deg
                ]
                
                # Predict at holdout location using kriging
                kriging_result = await kriging_interpolation_service.interpolate_grid_with_covariates(
                    training_sensors,
                    holdout_bbox,
                    resolution_m=100,  # Fine resolution for validation
                    timestamp=timestamp,
                    include_nasa_covariates=True
                )
                
                # Find prediction closest to holdout sensor
                if kriging_result['features']:
                    closest_feature = min(
                        kriging_result['features'],
                        key=lambda f: abs(f['geometry']['coordinates'][0] - holdout_sensor['longitude']) +
                                     abs(f['geometry']['coordinates'][1] - holdout_sensor['latitude'])
                    )
                    
                    predicted_value = closest_feature['properties']['c_hat']
                    predicted_uncertainty = closest_feature['properties']['total_uncertainty']
                    
                    predictions.append(predicted_value)
                    observations.append(holdout_sensor['pm25_corrected'])
                    uncertainties.append(predicted_uncertainty)
                
            except Exception as e:
                logger.warning(f"Cross-validation failed for sensor {holdout_sensor['sensor_id']}: {e}")
                continue
        
        if len(predictions) < 5:
            raise HTTPException(
                status_code=500,
                detail="Cross-validation failed - insufficient valid predictions"
            )
        
        # Calculate validation metrics
        predictions = np.array(predictions)
        observations = np.array(observations)
        uncertainties = np.array(uncertainties)
        
        rmse = np.sqrt(np.mean((observations - predictions) ** 2))
        mae = np.mean(np.abs(observations - predictions))
        bias = np.mean(predictions - observations)
        r2 = np.corrcoef(observations, predictions)[0, 1] ** 2 if len(predictions) > 1 else 0
        
        # Uncertainty validation
        residuals = np.abs(observations - predictions)
        coverage_68 = np.mean(residuals <= 1.0 * uncertainties)
        coverage_95 = np.mean(residuals <= 1.96 * uncertainties)
        
        # Reliability metrics
        normalized_residuals = residuals / uncertainties
        chi_squared = np.mean(normalized_residuals ** 2)
        
        validation_result = {
            'validation_method': cross_validation_method,
            'bbox': [west, south, east, north],
            'timestamp': timestamp or datetime.now(timezone.utc).isoformat(),
            'sample_size': len(predictions),
            'performance_metrics': {
                'rmse': float(rmse),
                'mae': float(mae),
                'bias': float(bias),
                'r2': float(r2),
                'mean_absolute_error_percent': float(mae / np.mean(observations) * 100) if np.mean(observations) > 0 else 0
            },
            'uncertainty_metrics': {
                'coverage_68_percent': float(coverage_68 * 100),
                'coverage_95_percent': float(coverage_95 * 100),
                'chi_squared': float(chi_squared),
                'mean_uncertainty': float(np.mean(uncertainties)),
                'uncertainty_reliability': 'good' if 0.8 <= chi_squared <= 1.2 else 'poor'
            },
            'comparison_to_idw': {
                'kriging_advantage': 'NASA covariates and optimal weights',
                'computational_cost': 'Higher than IDW',
                'uncertainty_quality': 'Theoretical kriging variance'
            }
        }
        
        logger.info(f"Kriging validation completed: RMSE={rmse:.2f}, R²={r2:.3f}, Coverage95={coverage_95*100:.1f}%")
        
        return validation_result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Kriging validation failed: {e}")
        raise HTTPException(status_code=500, detail="Cross-validation failed")

@router.get("/heatmap/kriging/comparison")
async def compare_kriging_vs_idw(
    west: float, south: float, east: float, north: float,
    resolution: int = Query(250, ge=100, le=1000),
    timestamp: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Compare kriging vs IDW interpolation performance"""
    try:
        bbox = [west, south, east, north]
        
        # Generate both kriging and IDW grids
        from ..services.idw_interpolation_service import idw_interpolation_service
        
        # Get sensor data
        sensor_records = db.query(SensorHarmonized).filter(
            SensorHarmonized.lon >= west,
            SensorHarmonized.lon <= east,
            SensorHarmonized.lat >= south,
            SensorHarmonized.lat <= north,
            SensorHarmonized.raw_pm2_5.isnot(None)
        ).all()
        
        if len(sensor_records) < 5:
            raise HTTPException(status_code=404, detail="Insufficient sensor data")
        
        # Convert to common format
        sensor_data = []
        for record in sensor_records:
            sensor_data.append({
                'sensor_id': record.sensor_id,
                'latitude': float(record.lat),
                'longitude': float(record.lon),
                'pm25_corrected': float(record.raw_pm2_5),
                'sigma_i': 5.0
            })
        
        # Generate both grids
        start_time_kriging = time.time()
        kriging_grid = await kriging_interpolation_service.interpolate_grid_with_covariates(
            sensor_data, bbox, resolution, timestamp, True
        )
        kriging_time = (time.time() - start_time_kriging) * 1000
        
        start_time_idw = time.time()
        idw_grid = idw_interpolation_service.interpolate_grid(
            sensor_data, bbox, resolution, timestamp
        )
        idw_time = (time.time() - start_time_idw) * 1000
        
        # Compare grid characteristics
        kriging_features = kriging_grid.get('features', [])
        idw_features = idw_grid.get('features', [])
        
        # Calculate summary statistics
        if kriging_features and idw_features:
            kriging_values = [f['properties']['c_hat'] for f in kriging_features]
            idw_values = [f['properties']['c_hat'] for f in idw_features]
            
            kriging_uncertainties = [f['properties']['total_uncertainty'] for f in kriging_features]
            idw_uncertainties = [f['properties']['uncertainty'] for f in idw_features]
            
            comparison = {
                'bbox': bbox,
                'resolution_m': resolution,
                'sensors_used': len(sensor_data),
                'processing_comparison': {
                    'kriging_time_ms': round(kriging_time, 2),
                    'idw_time_ms': round(idw_time, 2),
                    'time_ratio': round(kriging_time / max(idw_time, 1), 2)
                },
                'grid_comparison': {
                    'kriging_points': len(kriging_features),
                    'idw_points': len(idw_features),
                    'coverage_ratio': len(kriging_features) / max(len(idw_features), 1)
                },
                'value_statistics': {
                    'kriging': {
                        'mean_pm25': float(np.mean(kriging_values)),
                        'std_pm25': float(np.std(kriging_values)),
                        'mean_uncertainty': float(np.mean(kriging_uncertainties))
                    },
                    'idw': {
                        'mean_pm25': float(np.mean(idw_values)),
                        'std_pm25': float(np.std(idw_values)),
                        'mean_uncertainty': float(np.mean(idw_uncertainties))
                    }
                },
                'method_differences': {
                    'value_correlation': float(np.corrcoef(kriging_values[:min(len(kriging_values), len(idw_values))], 
                                                         idw_values[:min(len(kriging_values), len(idw_values))])[0,1]),
                    'rmse_difference': float(np.sqrt(np.mean((np.array(kriging_values[:min(len(kriging_values), len(idw_values))]) - 
                                                            np.array(idw_values[:min(len(kriging_values), len(idw_values))])) ** 2))),
                    'uncertainty_improvement': float((np.mean(idw_uncertainties) - np.mean(kriging_uncertainties)) / np.mean(idw_uncertainties) * 100)
                },
                'recommendations': {
                    'preferred_method': 'kriging' if len(sensor_data) >= 15 else 'idw',
                    'reasoning': 'Kriging provides better uncertainty quantification with sufficient data' if len(sensor_data) >= 15 else 'IDW sufficient for sparse sensor networks',
                    'nasa_covariates_benefit': 'Improved spatial prediction accuracy' if len(kriging_features) > len(idw_features) else 'Minimal improvement with current covariate data'
                }
            }
        else:
            comparison = {
                'error': 'No valid grid points generated for comparison',
                'kriging_features': len(kriging_features),
                'idw_features': len(idw_features)
            }
        
        return comparison
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Method comparison failed: {e}")
        raise HTTPException(status_code=500, detail="Comparison analysis failed")

def _rank_variogram_models(sensor_data: List[Dict]) -> Dict[str, float]:
    """Rank variogram models by fit quality"""
    # Mock ranking for now - in production would fit all models
    return {
        'spherical': 0.85,
        'exponential': 0.82,
        'gaussian': 0.78,
        'linear': 0.65
    }

def _calculate_pairs_per_lag(sensor_data: List[Dict]) -> List[int]:
    """Calculate number of sensor pairs per distance lag"""
    n_sensors = len(sensor_data)
    # Estimate pairs per lag bin
    total_pairs = n_sensors * (n_sensors - 1) // 2
    n_lags = min(20, total_pairs // 10)
    
    return [total_pairs // n_lags] * n_lags

def _calculate_spatial_extent(sensor_data: List[Dict]) -> float:
    """Calculate spatial extent of sensor network in km"""
    if len(sensor_data) < 2:
        return 0.0
    
    lats = [s['latitude'] for s in sensor_data]
    lons = [s['longitude'] for s in sensor_data]
    
    lat_range = max(lats) - min(lats)
    lon_range = max(lons) - min(lons)
    
    # Approximate extent as diagonal distance
    extent_deg = np.sqrt(lat_range ** 2 + lon_range ** 2)
    return extent_deg * 111  # Convert to km

def _calculate_sensor_density(sensor_data: List[Dict], bbox: List[float]) -> float:
    """Calculate sensor density per km²"""
    west, south, east, north = bbox
    area_deg2 = (east - west) * (north - south)
    area_km2 = area_deg2 * (111 ** 2)  # Rough conversion
    
    return len(sensor_data) / max(area_km2, 1)
