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
