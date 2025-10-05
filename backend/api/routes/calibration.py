from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from ..database import get_db
from ..services.calibration_engine_service import CalibrationEngineService
from ..services.sensor_qc_service import SensorQCService
from ..services.data_harmonization_service import DataHarmonizationService
from ..services.automated_calibration_pipeline import automated_pipeline
from ..models.harmonized_models import SensorCalibration

router = APIRouter()

@router.post("/sensors/calibrate")
async def calibrate_sensor(
    sensor_id: str,
    reference_data: List[Dict[str, Any]],
    sensor_type: str = "generic",
    db: Session = Depends(get_db)
):
    """Calibrate a specific sensor with reference data"""
    try:
        calibration_service = CalibrationEngineService(db)
        
        # Fit calibration model
        calibration_params = calibration_service.fit_calibration_model(sensor_id, reference_data)
        
        # Store calibration parameters
        success = calibration_service.store_calibration_parameters(
            sensor_id, sensor_type, calibration_params
        )
        
        if success:
            # Perform cross-validation
            cv_results = calibration_service.perform_cross_validation(sensor_id, reference_data)
            
            return {
                'sensor_id': sensor_id,
                'calibration_status': 'completed',
                'calibration_parameters': calibration_params,
                'cross_validation': cv_results,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to store calibration parameters")
        
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Calibration failed: {str(e)}")

@router.post("/sensors/auto-calibrate")
async def trigger_auto_calibration(
    source_filter: Optional[str] = None,
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db)
):
    """Trigger automatic calibration for sensors that need it"""
    try:
        calibration_service = CalibrationEngineService(db)
        
        # Run auto-calibration
        result = calibration_service.auto_calibrate_sensors(source_filter)
        
        return {
            'status': 'completed',
            'result': result,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Auto-calibration failed: {str(e)}")

@router.get("/sensors/calibration/diagnostics/{sensor_id}")
async def get_calibration_diagnostics(
    sensor_id: str,
    db: Session = Depends(get_db)
):
    """Get detailed calibration diagnostics for a sensor"""
    try:
        calibration_service = CalibrationEngineService(db)
        diagnostics = calibration_service.get_calibration_diagnostics(sensor_id)
        
        if 'error' in diagnostics:
            raise HTTPException(status_code=404, detail=diagnostics['error'])
        
        return diagnostics
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving diagnostics: {str(e)}")

@router.get("/sensors/calibration/drift/{sensor_id}")
async def check_calibration_drift(
    sensor_id: str,
    days_back: int = 30,
    db: Session = Depends(get_db)
):
    """Check for calibration drift"""
    try:
        calibration_service = CalibrationEngineService(db)
        drift_analysis = calibration_service.detect_calibration_drift(sensor_id, days_back)
        
        if 'error' in drift_analysis:
            raise HTTPException(status_code=404, detail=drift_analysis['error'])
        
        return drift_analysis
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Drift analysis failed: {str(e)}")

@router.post("/data/quality-control")
async def apply_quality_control(
    sensor_data: Dict[str, Any],
    db: Session = Depends(get_db)
):
    """Apply quality control rules to sensor data"""
    try:
        qc_service = SensorQCService(db)
        
        # Apply QC rules
        processed_data = qc_service.apply_qc_rules(sensor_data)
        
        return {
            'original_data': sensor_data,
            'processed_data': processed_data,
            'qc_flags': processed_data.get('qc_flags', []),
            'processing_timestamp': datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Quality control failed: {str(e)}")

@router.get("/data/qc-summary")
async def get_qc_summary(
    sensor_id: Optional[str] = None,
    hours_back: int = 24,
    db: Session = Depends(get_db)
):
    """Get quality control summary statistics"""
    try:
        qc_service = SensorQCService(db)
        summary = qc_service.get_qc_summary(sensor_id, hours_back)
        
        return summary
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving QC summary: {str(e)}")

@router.post("/data/harmonize")
async def harmonize_sensor_data(
    raw_data_list: List[Dict[str, Any]],
    source: str,
    db: Session = Depends(get_db)
):
    """Harmonize raw sensor data to canonical schema"""
    try:
        harmonization_service = DataHarmonizationService()
        
        # Process each record
        harmonized_records = []
        for raw_data in raw_data_list:
            harmonized = harmonization_service.harmonize_data(raw_data, source)
            if harmonized:  # Only include valid records
                harmonized_records.append(harmonized)
        
        # Get harmonization statistics
        stats = harmonization_service.get_harmonization_stats()
        
        return {
            'original_count': len(raw_data_list),
            'harmonized_count': len(harmonized_records),
            'harmonized_data': harmonized_records,
            'harmonization_stats': stats,
            'source': source,
            'processing_timestamp': datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Harmonization failed: {str(e)}")

@router.get("/calibration/status")
async def get_calibration_status(
    source: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get overall calibration status for sensors"""
    try:
        query = db.query(SensorCalibration)
        
        if source:
            # Filter by source through sensor harmonized data
            sensor_ids = db.query(SensorHarmonized.sensor_id).filter(
                SensorHarmonized.source == source
            ).distinct().all()
            sensor_id_list = [sid[0] for sid in sensor_ids]
            query = query.filter(SensorCalibration.sensor_id.in_(sensor_id_list))
        
        calibrations = query.all()
        
        # Calculate status statistics
        total_sensors = len(calibrations)
        active_calibrations = len([c for c in calibrations if c.is_active])
        recent_calibrations = len([c for c in calibrations 
                                 if c.last_calibrated and 
                                 (datetime.now(timezone.utc) - c.last_calibrated).days <= 30])
        
        # Performance distribution
        r2_values = [float(c.calibration_r2) for c in calibrations if c.calibration_r2]
        sigma_values = [float(c.sigma_i) for c in calibrations if c.sigma_i]
        
        status_summary = {
            'total_sensors': total_sensors,
            'active_calibrations': active_calibrations,
            'recent_calibrations': recent_calibrations,
            'calibration_rate': active_calibrations / total_sensors if total_sensors > 0 else 0,
            'performance_stats': {
                'mean_r2': float(np.mean(r2_values)) if r2_values else None,
                'mean_sigma_i': float(np.mean(sigma_values)) if sigma_values else None,
                'high_quality_count': len([r2 for r2 in r2_values if r2 > 0.8])
            },
            'source_filter': source,
            'query_timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        return status_summary
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving calibration status: {str(e)}")
