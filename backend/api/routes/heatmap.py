from fastapi import APIRouter, HTTPException, Depends, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import json
import time

from ..database import get_db
from ..services.idw_interpolation_service import idw_interpolation_service
from ..services.vector_tile_service import vector_tile_service
from ..services.heatmap_cache_service import create_heatmap_cache_service
from ..services.calibration_engine_service import CalibrationEngineService
from ..services.kriging_interpolation_service import kriging_interpolation_service
from ..services.kriging_vector_tile_service import kriging_vector_tile_service
from ..models.harmonized_models import SensorHarmonized

router = APIRouter()

@router.get("/heatmap/grid")
async def get_heatmap_grid(
    west: float = Query(..., ge=-180, le=180),
    south: float = Query(..., ge=-90, le=90),
    east: float = Query(..., ge=-180, le=180),
    north: float = Query(..., ge=-90, le=90),
    resolution: int = Query(250, ge=100, le=1000),
    timestamp: Optional[str] = None,
    method: str = Query('idw', regex='^(idw|kriging)$'),
    force_refresh: bool = False,
    db: Session = Depends(get_db)
):
    """Generate PM2.5 heatmap grid with IDW interpolation"""
    try:
        bbox = [west, south, east, north]
        
        # Validate bounding box
        if west >= east or south >= north:
            raise HTTPException(status_code=400, detail="Invalid bounding box coordinates")
        
        # Initialize services
        cache_service = create_heatmap_cache_service(db)
        calibration_service = CalibrationEngineService(db)
        
        # Validate grid resolution
        resolution_validation = cache_service.validate_grid_resolution(bbox, resolution)
        if not resolution_validation['valid']:
            raise HTTPException(status_code=400, detail=resolution_validation['error'])
        
        # Check cache unless force refresh
        if not force_refresh:
            cached_grid = await cache_service.get_cached_grid(bbox, resolution, timestamp, method)
            if cached_grid:
                return cached_grid
        
        # Get sensor data for interpolation
        start_time = time.time()
        
        # Get sensors in area with recent data
        if timestamp:
            target_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            time_window = timedelta(hours=2)  # ±2 hours from target time
            
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
        
        if len(sensor_records) < 2:
            raise HTTPException(
                status_code=404, 
                detail=f"Insufficient sensor data: {len(sensor_records)} sensors found in area"
            )
        
        # Convert to format expected by interpolation service
        sensor_data = []
        for record in sensor_records:
            # Apply calibration
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
        
        # Perform interpolation
        if method == 'idw':
            grid_result = idw_interpolation_service.interpolate_grid(
                sensor_data, bbox, resolution_m, timestamp
            )
        elif method == 'kriging':
            grid_result = await kriging_interpolation_service.interpolate_grid_with_covariates(
                sensor_data, bbox, resolution_m, timestamp, include_nasa_covariates=True
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported interpolation method: {method}")
        
        # Calculate processing time
        processing_time_ms = (time.time() - start_time) * 1000
        
        # Cache the result
        await cache_service.store_grid_cache(
            bbox, resolution, grid_result, processing_time_ms, timestamp, method
        )
        
        # Add processing metadata
        grid_result['processing'] = {
            'processing_time_ms': round(processing_time_ms, 2),
            'sensors_used': len(sensor_data),
            'cache_stored': True,
            'resolution_validation': resolution_validation
        }
        
        logger.info(f"Heatmap grid generated: {len(sensor_data)} sensors -> {len(grid_result['features'])} grid points ({processing_time_ms:.1f}ms)")
        
        return grid_result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Heatmap grid generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Grid generation failed: {str(e)}")

@router.get("/heatmap/tiles/{z}/{x}/{y}")
async def get_vector_tile(
    z: int,
    x: int, 
    y: int,
    timestamp: Optional[str] = None,
    method: str = Query('idw', regex='^(idw|kriging)$'),
    layer_type: str = Query('points', regex='^(points|contours|uncertainty|all)$'),
    db: Session = Depends(get_db)
):
    """Generate vector tile for heatmap visualization"""
    try:
        # Validate tile coordinates
        if not (0 <= x < 2**z and 0 <= y < 2**z):
            raise HTTPException(status_code=400, detail="Invalid tile coordinates")
        
        if z < 0 or z > 18:
            raise HTTPException(status_code=400, detail="Invalid zoom level")
        
        # Initialize services
        cache_service = create_heatmap_cache_service(db)
        
        # Check cache first
        cached_tile = await cache_service.get_cached_vector_tile(z, x, y, timestamp, method)
        if cached_tile:
            return Response(
                content=cached_tile,
                media_type="application/x-protobuf",
                headers={
                    "Cache-Control": "public, max-age=3600",
                    "Content-Encoding": "gzip"
                }
            )
        
        # Calculate tile bounds
        tile_bounds = vector_tile_service._tile_to_bounds(z, x, y)
        
        # Get grid data for tile area (with buffer)
        buffered_bounds = vector_tile_service._add_buffer_to_bounds(tile_bounds, 0.2)
        
        try:
            # Get grid data for this tile area
            grid_response = await get_heatmap_grid(
                west=buffered_bounds[0],
                south=buffered_bounds[1], 
                east=buffered_bounds[2],
                north=buffered_bounds[3],
                resolution=500,  # Use coarser resolution for tiles
                timestamp=timestamp,
                method=method,
                force_refresh=False,
                db=db
            )
            
            # Generate vector tile
            vector_tile_data = vector_tile_service.generate_heatmap_tile(
                z, x, y, grid_response, layer_type
            )
            
            # Cache the tile
            await cache_service.store_vector_tile(z, x, y, vector_tile_data, timestamp, method)
            
            return Response(
                content=vector_tile_data,
                media_type="application/x-protobuf",
                headers={
                    "Cache-Control": "public, max-age=3600",
                    "Access-Control-Allow-Origin": "*"
                }
            )
            
        except HTTPException as he:
            if he.status_code == 404:
                # No data in this tile area, return empty tile
                empty_tile = vector_tile_service._encode_empty_tile()
                return Response(
                    content=empty_tile,
                    media_type="application/x-protobuf",
                    headers={"Cache-Control": "public, max-age=1800"}
                )
            else:
                raise
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Vector tile generation failed for {z}/{x}/{y}: {e}")
        raise HTTPException(status_code=500, detail="Vector tile generation failed")

@router.get("/heatmap/metadata")
async def get_heatmap_metadata(
    bbox: str = Query(..., description="Bounding box as 'west,south,east,north'"),
    db: Session = Depends(get_db)
):
    """Get heatmap metadata for given area"""
    try:
        west, south, east, north = map(float, bbox.split(','))
        bounds = [west, south, east, north]
        
        # Get sensor count in area
        sensor_count = db.query(SensorHarmonized).filter(
            SensorHarmonized.lon >= west,
            SensorHarmonized.lon <= east,
            SensorHarmonized.lat >= south,
            SensorHarmonized.lat <= north,
            SensorHarmonized.raw_pm2_5.isnot(None)
        ).count()
        
        # Get available timestamps
        recent_cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        timestamps = db.query(SensorHarmonized.timestamp_utc).filter(
            SensorHarmonized.lon >= west,
            SensorHarmonized.lon <= east,
            SensorHarmonized.lat >= south,
            SensorHarmonized.lat <= north,
            SensorHarmonized.timestamp_utc >= recent_cutoff
        ).distinct().order_by(SensorHarmonized.timestamp_utc.desc()).limit(168).all()  # Last week, hourly
        
        available_timestamps = [t[0].isoformat() for t in timestamps]
        
        # Calculate resolution recommendations
        area_deg2 = (east - west) * (north - south)
        cache_service = create_heatmap_cache_service(db)
        
        resolution_options = []
        for res in [100, 250, 500, 1000]:
            validation = cache_service.validate_grid_resolution(bounds, res)
            if validation['valid']:
                resolution_options.append({
                    'resolution_m': res,
                    'estimated_points': validation['estimated_points'],
                    'estimated_processing_time_s': validation['processing_time_estimate_seconds']
                })
        
        return {
            'bbox': bounds,
            'sensor_count': sensor_count,
            'available_timestamps': available_timestamps,
            'latest_timestamp': available_timestamps[0] if available_timestamps else None,
            'time_range': {
                'start': available_timestamps[-1] if available_timestamps else None,
                'end': available_timestamps[0] if available_timestamps else None
            },
            'supported_resolutions': resolution_options,
            'recommended_resolution': cache_service._suggest_resolution(area_deg2),
            'interpolation_methods': ['idw'],  # kriging coming in future milestone
            'metadata_timestamp': datetime.now(timezone.utc).isoformat()
        }
        
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=f"Invalid bbox format: {str(ve)}")
    except Exception as e:
        logger.error(f"Error generating heatmap metadata: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate metadata")

@router.delete("/heatmap/cache")
async def clear_heatmap_cache(
    bbox: Optional[str] = None,
    older_than_hours: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Clear heatmap cache with optional filters"""
    try:
        cache_service = create_heatmap_cache_service(db)
        
        if bbox:
            # Clear cache for specific area
            west, south, east, north = map(float, bbox.split(','))
            bbox_pattern = f"*bbox{west:.4f}_{south:.4f}_{east:.4f}_{north:.4f}*"
            
            cleared_count = await cache_service.clear_pattern(bbox_pattern)
            
            return {
                'message': f'Cleared heatmap cache for bbox: {bbox}',
                'cleared_entries': cleared_count,
                'area_cleared': bbox
            }
        elif older_than_hours:
            # Clean up old entries
            cleanup_result = await cache_service.cleanup_expired_cache()
            return {
                'message': f'Cleaned up cache entries older than {older_than_hours} hours',
                'cleanup_result': cleanup_result
            }
        else:
            # Clear all heatmap cache
            cleared_redis = await cache_service.clear_pattern("heatmap*")
            
            # Clear database artifacts
            cleared_db = db.query(ArtifactCache).filter(
                ArtifactCache.cache_key.like('heatmap%')
            ).delete()
            db.commit()
            
            return {
                'message': 'All heatmap cache cleared',
                'redis_entries_cleared': cleared_redis,
                'database_entries_cleared': cleared_db
            }
        
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=f"Invalid parameters: {str(ve)}")
    except Exception as e:
        logger.error(f"Cache clearing failed: {e}")
        raise HTTPException(status_code=500, detail="Cache clearing failed")

@router.get("/heatmap/status")
async def get_heatmap_status(db: Session = Depends(get_db)):
    """Get heatmap generation status and performance metrics"""
    try:
        # Get cache statistics
        cache_service = create_heatmap_cache_service(db)
        
        # Count cached grids
        cached_grids = db.query(ArtifactCache).filter(
            ArtifactCache.cache_key.like('heatmap%'),
            ArtifactCache.expires_at > datetime.now(timezone.utc)
        ).count()
        
        # Get recent processing statistics
        recent_artifacts = db.query(ArtifactCache).filter(
            ArtifactCache.cache_key.like('heatmap%'),
            ArtifactCache.created_at >= datetime.now(timezone.utc) - timedelta(hours=24)
        ).all()
        
        if recent_artifacts:
            avg_processing_time = sum(a.processing_time_ms for a in recent_artifacts) / len(recent_artifacts)
            total_size_mb = sum(a.file_size_bytes for a in recent_artifacts) / (1024 * 1024)
        else:
            avg_processing_time = 0
            total_size_mb = 0
        
        # Get sensor availability
        total_sensors = db.query(SensorHarmonized).filter(
            SensorHarmonized.raw_pm2_5.isnot(None)
        ).count()
        
        calibrated_sensors = db.query(SensorHarmonized).join(
            SensorCalibration,
            SensorHarmonized.sensor_id == SensorCalibration.sensor_id
        ).filter(
            SensorHarmonized.raw_pm2_5.isnot(None),
            SensorCalibration.is_active == True
        ).count()
        
        return {
            'service_status': 'operational',
            'interpolation_methods': {
                'idw': {
                    'available': True,
                    'default_power': idw_interpolation_service.power,
                    'search_radius_m': idw_interpolation_service.search_radius_m
                },
                'kriging': {
                    'available': False,
                    'message': 'Planned for future release'
                }
            },
            'grid_configurations': {
                'default_resolution_m': idw_interpolation_service.default_resolution_m,
                'supported_resolutions': [100, 250, 500, 1000],
                'max_grid_cells': idw_interpolation_service.max_grid_cells
            },
            'cache_status': {
                'cached_grids': cached_grids,
                'recent_generations_24h': len(recent_artifacts),
                'average_processing_time_ms': round(avg_processing_time, 2),
                'cache_size_mb': round(total_size_mb, 2)
            },
            'data_availability': {
                'total_sensors': total_sensors,
                'calibrated_sensors': calibrated_sensors,
                'calibration_rate': calibrated_sensors / total_sensors if total_sensors > 0 else 0
            },
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting heatmap status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get status")

@router.post("/heatmap/precompute")
async def precompute_heatmap_snapshots(
    bbox: str = Query(..., description="Bounding box as 'west,south,east,north'"),
    resolution: int = Query(250, ge=100, le=1000),
    hours_back: int = Query(24, ge=1, le=168),
    interval_hours: int = Query(1, ge=1, le=24),
    db: Session = Depends(get_db)
):
    """Precompute heatmap snapshots for smooth time animation"""
    try:
        west, south, east, north = map(float, bbox.split(','))
        bounds = [west, south, east, north]
        
        # Calculate timestamps for precomputation
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=hours_back)
        
        timestamps = []
        current_time = start_time
        while current_time <= end_time:
            timestamps.append(current_time.isoformat())
            current_time += timedelta(hours=interval_hours)
        
        # Precompute grids for each timestamp
        precompute_results = {
            'bbox': bounds,
            'resolution_m': resolution,
            'time_range': {
                'start': start_time.isoformat(),
                'end': end_time.isoformat(),
                'interval_hours': interval_hours
            },
            'snapshots_generated': 0,
            'snapshots_cached': 0,
            'processing_errors': [],
            'total_processing_time_ms': 0
        }
        
        total_start_time = time.time()
        
        for timestamp in timestamps:
            try:
                # Generate grid for this timestamp
                grid_result = await get_heatmap_grid(
                    west=west, south=south, east=east, north=north,
                    resolution=resolution,
                    timestamp=timestamp,
                    method='idw',
                    force_refresh=False,  # Use cache if available
                    db=db
                )
                
                if grid_result and grid_result.get('features'):
                    precompute_results['snapshots_generated'] += 1
                    
                    if grid_result.get('processing', {}).get('cache_stored'):
                        precompute_results['snapshots_cached'] += 1
                    
                    processing_time = grid_result.get('processing', {}).get('processing_time_ms', 0)
                    precompute_results['total_processing_time_ms'] += processing_time
                
            except Exception as e:
                precompute_results['processing_errors'].append(f"Timestamp {timestamp}: {str(e)}")
                continue
        
        precompute_results['total_processing_time_ms'] = (time.time() - total_start_time) * 1000
        
        logger.info(f"Precomputation completed: {precompute_results['snapshots_generated']}/{len(timestamps)} snapshots")
        
        return precompute_results
        
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=f"Invalid parameters: {str(ve)}")
    except Exception as e:
        logger.error(f"Precomputation failed: {e}")
        raise HTTPException(status_code=500, detail="Precomputation failed")

@router.get("/heatmap/time-series")
async def get_heatmap_time_series(
    west: float, south: float, east: float, north: float,
    lat: float = Query(..., ge=-90, le=90), 
    lon: float = Query(..., ge=-180, le=180),
    hours_back: int = Query(24, ge=1, le=168),
    interval_hours: int = Query(1, ge=1, le=24),
    method: str = Query('idw'),
    db: Session = Depends(get_db)
):
    """Get time series of interpolated PM2.5 values for a specific location"""
    try:
        bbox = [west, south, east, north]
        
        # Generate timestamps
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=hours_back)
        
        time_series_data = []
        current_time = start_time
        
        while current_time <= end_time:
            timestamp_str = current_time.isoformat()
            
            try:
                # Get grid data for this timestamp
                grid_data = await get_heatmap_grid(
                    west=west, south=south, east=east, north=north,
                    resolution=500,  # Use coarser resolution for time series
                    timestamp=timestamp_str,
                    method=method,
                    db=db
                )
                
                # Find closest grid point to requested location
                closest_feature = None
                min_distance = float('inf')
                
                for feature in grid_data.get('features', []):
                    feature_coords = feature['geometry']['coordinates']
                    distance = idw_interpolation_service._haversine_distance(
                        lat, lon, feature_coords[1], feature_coords[0]
                    )
                    
                    if distance < min_distance:
                        min_distance = distance
                        closest_feature = feature
                
                if closest_feature and min_distance <= 2000:  # Within 2km
                    time_series_data.append({
                        'timestamp': timestamp_str,
                        'pm25_interpolated': closest_feature['properties']['c_hat'],
                        'uncertainty': closest_feature['properties']['uncertainty'],
                        'distance_to_grid_point_m': round(min_distance, 1),
                        'neighbors_used': closest_feature['properties']['n_eff']
                    })
                
            except Exception as e:
                logger.debug(f"Time series point failed for {timestamp_str}: {e}")
                continue
            
            current_time += timedelta(hours=interval_hours)
        
        return {
            'location': {'latitude': lat, 'longitude': lon},
            'bbox': bbox,
            'time_range': {
                'start': start_time.isoformat(),
                'end': end_time.isoformat(),
                'interval_hours': interval_hours
            },
            'method': method,
            'time_series': time_series_data,
            'total_points': len(time_series_data)
        }
        
    except Exception as e:
        logger.error(f"Time series generation failed: {e}")
        raise HTTPException(status_code=500, detail="Time series generation failed")
