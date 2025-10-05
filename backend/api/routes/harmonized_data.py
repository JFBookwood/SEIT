from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from ..database import get_db
from ..services.data_ingestion_service import DataIngestionService
from ..services.harmonization_service import DataHarmonizationService
from ..services.quality_control_service import SensorQualityControlService
from ..services.calibration_service import SensorCalibrationService
from ..models.harmonized_models import SensorHarmonized, SensorCalibration

router = APIRouter()

@router.post("/ingest/all-sources")
async def trigger_comprehensive_ingestion(
    bbox: Optional[str] = None,
    sources: List[str] = None,
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db)
):
    """Trigger comprehensive data ingestion from all sources"""
    try:
        if sources is None:
            sources = ['purpleair', 'sensor_community', 'openaq']
        
        ingestion_service = DataIngestionService(db)
        
        # Run ingestion
        result = await ingestion_service.ingest_all_sources(bbox, sources)
        
        return {
            "message": "Data ingestion completed",
            "result": result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")

@router.get("/harmonized/sensors")
async def get_harmonized_sensors(
    bbox: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    source: Optional[str] = None,
    include_qc_flags: bool = True,
    include_calibrated: bool = True,
    limit: int = 1000,
    db: Session = Depends(get_db)
):
    """Get harmonized sensor data with optional filtering"""
    try:
        query = db.query(SensorHarmonized)
        
        # Apply filters
        if bbox:
            west, south, east, north = map(float, bbox.split(','))
            query = query.filter(
                SensorHarmonized.lon >= west,
                SensorHarmonized.lon <= east,
                SensorHarmonized.lat >= south,
                SensorHarmonized.lat <= north
            )
        
        if start_date:
            start_dt = datetime.fromisoformat(start_date)
            query = query.filter(SensorHarmonized.timestamp_utc >= start_dt)
        
        if end_date:
            end_dt = datetime.fromisoformat(end_date)
            query = query.filter(SensorHarmonized.timestamp_utc <= end_dt)
        
        if source:
            query = query.filter(SensorHarmonized.source == source)
        
        # Execute query
        results = query.order_by(SensorHarmonized.timestamp_utc.desc()).limit(limit).all()
        
        # Format response
        sensors = []
        calibration_service = SensorCalibrationService(db)
        
        for result in results:
            sensor_data = {
                "id": result.id,
                "sensor_id": result.sensor_id,
                "sensor_type": result.sensor_type,
                "latitude": float(result.lat),
                "longitude": float(result.lon),
                "timestamp_utc": result.timestamp_utc.isoformat(),
                "raw_pm2_5": float(result.raw_pm2_5) if result.raw_pm2_5 else None,
                "raw_pm10": float(result.raw_pm10) if result.raw_pm10 else None,
                "temperature": float(result.temperature) if result.temperature else None,
                "humidity": float(result.rh) if result.rh else None,
                "pressure": float(result.pressure) if result.pressure else None,
                "source": result.source,
                "data_quality_score": float(result.data_quality_score) if result.data_quality_score else None
            }
            
            # Include QC flags if requested
            if include_qc_flags:
                sensor_data["qc_flags"] = result.qc_flags or []
            
            # Include calibrated values if requested
            if include_calibrated:
                calibrated_data = calibration_service.apply_calibration(result.sensor_id, sensor_data)
                sensor_data.update({
                    "pm2_5_corrected": calibrated_data.get('pm2_5_corrected'),
                    "calibration_applied": calibrated_data.get('calibration_applied', False),
                    "sigma_i": calibrated_data.get('sigma_i'),
                    "calibration_method": calibrated_data.get('calibration_method')
                })
            
            sensors.append(sensor_data)
        
        return {
            "sensors": sensors,
            "total": len(sensors),
            "filters_applied": {
                "bbox": bbox,
                "start_date": start_date,
                "end_date": end_date,
                "source": source
            },
            "data_options": {
                "include_qc_flags": include_qc_flags,
                "include_calibrated": include_calibrated
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving harmonized sensors: {str(e)}")

@router.get("/calibration/diagnostics/{sensor_id}")
async def get_sensor_calibration_diagnostics(
    sensor_id: str,
    db: Session = Depends(get_db)
):
    """Get detailed calibration diagnostics for a sensor"""
    try:
        calibration_service = SensorCalibrationService(db)
        diagnostics = calibration_service.get_calibration_diagnostics(sensor_id)
        
        if 'error' in diagnostics:
            raise HTTPException(status_code=404, detail=diagnostics['error'])
        
        return diagnostics
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving diagnostics: {str(e)}")

@router.post("/calibration/auto-calibrate")
async def trigger_auto_calibration(
    source_filter: Optional[str] = None,
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db)
):
    """Trigger automatic calibration for sensors"""
    try:
        calibration_service = SensorCalibrationService(db)
        
        # Run auto-calibration
        result = calibration_service.auto_calibrate_sensors(source_filter)
        
        return {
            "message": "Auto-calibration completed",
            "result": result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Auto-calibration failed: {str(e)}")

@router.get("/quality-control/summary")
async def get_qc_summary(
    sensor_id: Optional[str] = None,
    hours_back: int = 24,
    db: Session = Depends(get_db)
):
    """Get quality control summary statistics"""
    try:
        qc_service = SensorQualityControlService(db)
        summary = qc_service.get_qc_summary(sensor_id, hours_back)
        
        return summary
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving QC summary: {str(e)}")

@router.get("/harmonization/stats")
async def get_harmonization_statistics(
    hours_back: int = 24,
    db: Session = Depends(get_db)
):
    """Get data harmonization statistics"""
    try:
        ingestion_service = DataIngestionService(db)
        stats = ingestion_service.get_ingestion_summary(hours_back)
        
        return stats
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving harmonization stats: {str(e)}")

@router.post("/sensors/validate-batch")
async def validate_sensor_batch(
    sensor_data: List[Dict[str, Any]],
    source: str,
    db: Session = Depends(get_db)
):
    """Validate a batch of sensor data before storage"""
    try:
        harmonization_service = DataHarmonizationService()
        
        # Harmonize the batch
        harmonized_batch = harmonization_service.harmonize_sensor_batch(sensor_data, source)
        
        # Get validation statistics
        validation_stats = harmonization_service.get_harmonization_stats()
        
        return {
            "original_count": len(sensor_data),
            "harmonized_count": len(harmonized_batch),
            "validation_stats": validation_stats,
            "sample_harmonized": harmonized_batch[:5] if harmonized_batch else [],
            "source": source
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch validation failed: {str(e)}")

@router.get("/sensors/by-quality")
async def get_sensors_by_quality(
    min_quality_score: float = 0.7,
    bbox: Optional[str] = None,
    limit: int = 500,
    db: Session = Depends(get_db)
):
    """Get sensors filtered by data quality score"""
    try:
        query = db.query(SensorHarmonized).filter(
            SensorHarmonized.data_quality_score >= min_quality_score,
            SensorHarmonized.raw_pm2_5.isnot(None)
        )
        
        if bbox:
            west, south, east, north = map(float, bbox.split(','))
            query = query.filter(
                SensorHarmonized.lon >= west,
                SensorHarmonized.lon <= east,
                SensorHarmonized.lat >= south,
                SensorHarmonized.lat <= north
            )
        
        results = query.order_by(
            SensorHarmonized.data_quality_score.desc(),
            SensorHarmonized.timestamp_utc.desc()
        ).limit(limit).all()
        
        # Format response
        high_quality_sensors = []
        for result in results:
            sensor_data = {
                "sensor_id": result.sensor_id,
                "sensor_type": result.sensor_type,
                "latitude": float(result.lat),
                "longitude": float(result.lon),
                "timestamp_utc": result.timestamp_utc.isoformat(),
                "raw_pm2_5": float(result.raw_pm2_5) if result.raw_pm2_5 else None,
                "data_quality_score": float(result.data_quality_score),
                "qc_flags": result.qc_flags or [],
                "source": result.source
            }
            high_quality_sensors.append(sensor_data)
        
        return {
            "sensors": high_quality_sensors,
            "total": len(high_quality_sensors),
            "quality_threshold": min_quality_score,
            "bbox": bbox
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving high-quality sensors: {str(e)}")
