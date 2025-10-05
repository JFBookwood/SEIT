from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
import requests
import os
from ..database import get_db
from ..models import SatelliteData
from ..services.gibs_service import GIBSService
from ..services.harmony_service import HarmonyService
from ..services.nasa_satellite_processor import nasa_satellite_processor
from ..services.spatial_alignment_service import spatial_alignment_service
from ..services.satellite_artifact_cache import SatelliteArtifactCache

router = APIRouter()

@router.get("/gibs/layers")
async def get_available_layers():
    """Get available GIBS layers for visualization"""
    layers = [
        {
            "id": "MODIS_Terra_CorrectedReflectance_TrueColor",
            "title": "MODIS Terra True Color",
            "description": "Corrected Reflectance True Color from MODIS Terra",
            "format": "jpeg",
            "temporal": True
        },
        {
            "id": "MODIS_Aqua_CorrectedReflectance_TrueColor", 
            "title": "MODIS Aqua True Color",
            "description": "Corrected Reflectance True Color from MODIS Aqua",
            "format": "jpeg",
            "temporal": True
        },
        {
            "id": "MODIS_Terra_Land_Surface_Temp_Day",
            "title": "MODIS Terra LST Day",
            "description": "Land Surface Temperature (Day) from MODIS Terra",
            "format": "png",
            "temporal": True
        },
        {
            "id": "AIRS_L2_Surface_Air_Temperature_Day",
            "title": "AIRS Surface Air Temperature",
            "description": "Surface Air Temperature from AIRS",
            "format": "png", 
            "temporal": True
        }
    ]
    return {"layers": layers}

@router.get("/gibs/tile-url")
async def generate_tile_url(
    layer: str,
    date: str,
    z: int,
    x: int,
    y: int,
    format: str = "jpeg"
):
    """Generate GIBS WMTS tile URL"""
    try:
        gibs_service = GIBSService()
        tile_url = gibs_service.generate_tile_url(layer, date, z, x, y, format)
        return {"tile_url": tile_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/products")
async def get_satellite_products():
    """Get available satellite products for analysis"""
    products = [
        {
            "id": "MOD11A2.061",
            "title": "MODIS Terra LST 8-Day",
            "description": "Land Surface Temperature 8-day composite",
            "temporal_resolution": "8 days",
            "spatial_resolution": "1km",
            "variables": ["LST_Day_1km", "LST_Night_1km"]
        },
        {
            "id": "AIRS2RET.010",
            "title": "AIRS Level 2 Standard Retrieval",
            "description": "Atmospheric temperature and moisture profiles",
            "temporal_resolution": "daily",
            "spatial_resolution": "45km",
            "variables": ["SurfAirTemp", "RelHum", "SurfPres"]
        },
        {
            "id": "MYD04_L2.061",
            "title": "MODIS Aqua Aerosol",
            "description": "Aerosol optical depth and properties",
            "temporal_resolution": "daily",
            "spatial_resolution": "10km",
            "variables": ["Optical_Depth_Land_And_Ocean"]
        }
    ]
    return {"products": products}

@router.post("/products/query")
async def query_satellite_data(
    product_id: str,
    start_date: str,
    end_date: str,
    bbox: List[float],  # [west, south, east, north]
    db: Session = Depends(get_db)
):
    """Query and fetch satellite data via Harmony/CMR"""
    try:
        harmony_service = HarmonyService()
        
        # Query CMR for granules
        granules = await harmony_service.query_granules(
            product_id, start_date, end_date, bbox
        )
        
        if not granules:
            return {"message": "No granules found for the specified criteria", "granules": []}
        
        # For demo, return first 10 granules
        limited_granules = granules[:10]
        
        return {
            "product_id": product_id,
            "total_granules": len(granules),
            "returned_granules": len(limited_granules),
            "granules": limited_granules
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error querying satellite data: {str(e)}")

@router.post("/products/subset")
async def request_data_subset(
    product_id: str,
    granule_id: str,
    bbox: List[float],
    variables: List[str],
    db: Session = Depends(get_db)
):
    """Request data subset via Harmony"""
    try:
        harmony_service = HarmonyService()
        
        # Submit subsetting request
        job_id = await harmony_service.submit_subset_request(
            product_id, granule_id, bbox, variables
        )
        
        # Store job in database
        satellite_data = SatelliteData(
            product_id=product_id,
            granule_id=granule_id,
            timestamp=datetime.utcnow(),
            bbox=str(bbox),
            file_path="",  # Will be updated when job completes
            metadata={"job_id": job_id, "variables": variables}
        )
        db.add(satellite_data)
        db.commit()
        
        return {
            "job_id": job_id,
            "status": "submitted",
            "message": "Subset request submitted successfully"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error requesting subset: {str(e)}")

@router.get("/products/job/{job_id}")
async def check_job_status(job_id: str):
    """Check status of Harmony job"""
    try:
        harmony_service = HarmonyService()
        status = await harmony_service.check_job_status(job_id)
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error checking job status: {str(e)}")

@router.get("/modis/aod")
async def fetch_modis_aod_data(
    bbox: str,  # "west,south,east,north"
    date: str,  # "YYYY-MM-DD"
    sensor_locations: Optional[str] = None,  # JSON string of sensor locations
    alignment_method: str = "bilinear",
    db: Session = Depends(get_db)
):
    """Fetch MODIS AOD data with spatial alignment to sensor grid"""
    try:
        # Parse inputs
        bbox_coords = list(map(float, bbox.split(',')))
        
        sensors = []
        if sensor_locations:
            import json
            sensors = json.loads(sensor_locations)
        
        # Initialize cache service
        cache_service = SatelliteArtifactCache(db)
        
        # Check cache first
        cached_data = await cache_service.get_cached_satellite_data(
            'MOD04_L2',
            date,
            bbox_coords,
            {'alignment_method': alignment_method}
        )
        
        if cached_data:
            return {
                'success': True,
                'data': cached_data,
                'cache_hit': True
            }
        
        # Fetch fresh data
        modis_data = await nasa_satellite_processor.fetch_modis_aod_for_sensors(
            sensors,
            date,
            bbox_coords
        )
        
        if not modis_data:
            raise HTTPException(status_code=404, detail="No MODIS AOD data available for specified parameters")
        
        # Perform spatial alignment if sensors provided
        if sensors and len(sensors) > 0:
            aligned_data = spatial_alignment_service.align_satellite_to_sensor_grid(
                modis_data,
                sensors,
                target_resolution_m=1000,
                method=alignment_method
            )
            
            # Cache aligned data
            await cache_service.store_satellite_artifact(
                'MOD04_L2',
                date,
                bbox_coords,
                aligned_data,
                {'alignment_method': alignment_method},
                {'aligned_to_sensors': True, 'sensor_count': len(sensors)}
            )
            
            return {
                'success': True,
                'data': aligned_data,
                'cache_hit': False,
                'processing_info': {
                    'spatial_alignment': True,
                    'method': alignment_method,
                    'target_sensors': len(sensors)
                }
            }
        else:
            # Cache raw data
            await cache_service.store_satellite_artifact(
                'MOD04_L2',
                date,
                bbox_coords,
                modis_data
            )
            
            return {
                'success': True,
                'data': modis_data,
                'cache_hit': False,
                'processing_info': {
                    'spatial_alignment': False
                }
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"MODIS AOD fetch failed: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching MODIS AOD data: {str(e)}")

@router.get("/airs/temperature")
async def fetch_airs_temperature_data(
    bbox: str,  # "west,south,east,north"
    date: str,  # "YYYY-MM-DD"
    sensor_locations: Optional[str] = None,  # JSON string of sensor locations
    variables: List[str] = ["SurfAirTemp", "RelHum", "SurfPres"],
    alignment_method: str = "bilinear",
    db: Session = Depends(get_db)
):
    """Fetch AIRS surface temperature data with spatial alignment"""
    try:
        bbox_coords = list(map(float, bbox.split(',')))
        
        sensors = []
        if sensor_locations:
            import json
            sensors = json.loads(sensor_locations)
        
        cache_service = SatelliteArtifactCache(db)
        
        # Check cache
        cache_params = {
            'alignment_method': alignment_method,
            'variables': sorted(variables)
        }
        
        cached_data = await cache_service.get_cached_satellite_data(
            'AIRS2RET',
            date,
            bbox_coords,
            cache_params
        )
        
        if cached_data:
            return {
                'success': True,
                'data': cached_data,
                'cache_hit': True
            }
        
        # Fetch fresh AIRS data
        airs_data = await nasa_satellite_processor.fetch_airs_temperature_for_sensors(
            sensors,
            date,
            bbox_coords
        )
        
        if not airs_data:
            raise HTTPException(status_code=404, detail="No AIRS temperature data available")
        
        # Spatial alignment if needed
        if sensors and len(sensors) > 0:
            aligned_data = spatial_alignment_service.align_satellite_to_sensor_grid(
                airs_data,
                sensors,
                target_resolution_m=1000,
                method=alignment_method
            )
            
            # Cache result
            await cache_service.store_satellite_artifact(
                'AIRS2RET',
                date,
                bbox_coords,
                aligned_data,
                cache_params,
                {'aligned_to_sensors': True, 'variables': variables}
            )
            
            return {
                'success': True,
                'data': aligned_data,
                'cache_hit': False,
                'processing_info': {
                    'spatial_alignment': True,
                    'method': alignment_method,
                    'variables': variables,
                    'target_sensors': len(sensors)
                }
            }
        else:
            # Cache raw data
            await cache_service.store_satellite_artifact(
                'AIRS2RET',
                date,
                bbox_coords,
                airs_data,
                cache_params
            )
            
            return {
                'success': True,
                'data': airs_data,
                'cache_hit': False
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"AIRS temperature fetch failed: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching AIRS data: {str(e)}")

@router.get("/satellite-covariates")
async def get_comprehensive_satellite_covariates(
    bbox: str,
    date: str,
    sensor_locations: str,  # JSON string required
    include_aod: bool = True,
    include_temperature: bool = True,
    alignment_method: str = "bilinear",
    db: Session = Depends(get_db)
):
    """Get comprehensive satellite covariates for sensor interpolation"""
    try:
        bbox_coords = list(map(float, bbox.split(',')))
        sensors = json.loads(sensor_locations)
        
        if not sensors:
            raise HTTPException(status_code=400, detail="Sensor locations required for covariate alignment")
        
        cache_service = SatelliteArtifactCache(db)
        
        # Check for comprehensive cache
        cache_key = f"comprehensive_covariates_{date}_{hash(sensor_locations) % 10000}_{alignment_method}"
        cached_comprehensive = await cache_service.get_cached_satellite_data(
            'COMPREHENSIVE_COVARIATES',
            date,
            bbox_coords,
            {
                'include_aod': include_aod,
                'include_temperature': include_temperature,
                'alignment_method': alignment_method
            }
        )
        
        if cached_comprehensive:
            return {
                'success': True,
                'data': cached_comprehensive,
                'cache_hit': True
            }
        
        # Fetch data concurrently
        tasks = {}
        
        if include_aod:
            tasks['aod'] = nasa_satellite_processor.fetch_modis_aod_for_sensors(
                sensors, date, bbox_coords
            )
        
        if include_temperature:
            tasks['temperature'] = nasa_satellite_processor.fetch_airs_temperature_for_sensors(
                sensors, date, bbox_coords
            )
        
        # Execute concurrent requests
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        
        # Process results
        covariates = {
            'date': date,
            'bbox': bbox_coords,
            'sensor_count': len(sensors),
            'alignment_method': alignment_method,
            'covariates': {},
            'processing_timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        # Process task results
        for task_name, result in zip(tasks.keys(), results):
            if result and not isinstance(result, Exception):
                # Align to sensor grid
                aligned_result = spatial_alignment_service.align_satellite_to_sensor_grid(
                    result,
                    sensors,
                    target_resolution_m=1000,
                    method=alignment_method
                )
                covariates['covariates'][task_name] = aligned_result
            else:
                error_msg = str(result) if isinstance(result, Exception) else "No data returned"
                covariates['covariates'][task_name] = {'error': error_msg}
        
        # Cache comprehensive result
        await cache_service.store_satellite_artifact(
            'COMPREHENSIVE_COVARIATES',
            date,
            bbox_coords,
            covariates,
            {
                'include_aod': include_aod,
                'include_temperature': include_temperature,
                'alignment_method': alignment_method
            }
        )
        
        return {
            'success': True,
            'data': covariates,
            'cache_hit': False,
            'processing_info': {
                'concurrent_requests': len(tasks),
                'spatial_alignment': True,
                'target_sensors': len(sensors)
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Comprehensive satellite covariates fetch failed: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching satellite covariates: {str(e)}")

@router.post("/cache/clear")
async def clear_satellite_cache(
    product_filter: Optional[str] = None,
    older_than_hours: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Clear satellite data cache with optional filters"""
    try:
        cache_service = SatelliteArtifactCache(db)
        
        if older_than_hours:
            # Clear old artifacts
            cleanup_result = await cache_service.cleanup_expired_artifacts()
            return {
                'message': f"Cleared artifacts older than {older_than_hours} hours",
                'cleanup_result': cleanup_result
            }
        else:
            # Clear all satellite cache
            cleared_db = self.db.query(ArtifactCache).delete()
            self.db.commit()
            
            # Clear Redis cache
            cleared_redis = await cache_service.clear_pattern("sat_*")
            
            return {
                'message': 'Satellite cache cleared',
                'database_entries_cleared': cleared_db,
                'redis_entries_cleared': cleared_redis
            }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error clearing satellite cache: {str(e)}")

@router.get("/cache/stats")
async def get_satellite_cache_stats(db: Session = Depends(get_db)):
    """Get satellite cache statistics"""
    try:
        cache_service = SatelliteArtifactCache(db)
        stats = await cache_service.get_cache_statistics()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting cache stats: {str(e)}")
@router.get("/covariate-integration")
async def get_integrated_sensor_covariates(
    bbox: str,
    date: str,
    sensor_data: str,  # JSON string of sensor measurements
    db: Session = Depends(get_db)
):
    """Get sensor data enhanced with satellite covariates"""
    try:
        from ..services.covariate_integration_service import covariate_integration_service
        
        sensors = json.loads(sensor_data)
        
        enhanced_sensors = await covariate_integration_service.integrate_satellite_covariates_for_sensors(
            sensors,
            date,
            include_aod=True,
            include_temperature=True
        )
        
        # Calculate influence weights
        influence_weights = covariate_integration_service.calculate_covariate_influence_weights(
            enhanced_sensors
        )
        
        return {
            'enhanced_sensors': enhanced_sensors,
            'covariate_influence_weights': influence_weights,
            'processing_timestamp': datetime.utcnow().isoformat(),
            'total_sensors': len(enhanced_sensors)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error integrating covariates: {str(e)}")