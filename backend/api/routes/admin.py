from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List
import os
import shutil
from datetime import datetime, timedelta
from ..database import get_db
from ..models import SensorData, SatelliteData, AnalysisJob
from ..auth import get_current_user
from ..services.nasa_auth_service import nasa_auth_service

router = APIRouter()

@router.get("/status")
async def get_system_status(db: Session = Depends(get_db)):
    """Get system status and statistics"""
    try:
        # Database statistics
        total_sensors = db.query(SensorData).count()
        total_satellite = db.query(SatelliteData).count()
        total_jobs = db.query(AnalysisJob).count()
        
        # Recent activity (last 24 hours)
        yesterday = datetime.utcnow() - timedelta(days=1)
        recent_sensors = db.query(SensorData).filter(SensorData.created_at >= yesterday).count()
        recent_jobs = db.query(AnalysisJob).filter(AnalysisJob.created_at >= yesterday).count()
        
        # Job status breakdown
        job_stats = db.query(AnalysisJob.status, db.func.count(AnalysisJob.id)).group_by(AnalysisJob.status).all()
        job_status_counts = {status: count for status, count in job_stats}
        
        # Data source breakdown
        source_stats = db.query(SensorData.source, db.func.count(SensorData.id)).group_by(SensorData.source).all()
        source_counts = {source: count for source, count in source_stats}
        
        # Disk usage (if applicable)
        cache_size = 0
        cache_dir = os.getenv("CACHE_DIR", "/tmp/seit_cache")
        if os.path.exists(cache_dir):
            for root, dirs, files in os.walk(cache_dir):
                cache_size += sum(os.path.getsize(os.path.join(root, file)) for file in files)
        
        return {
            "system": {
                "status": "operational",
                "timestamp": datetime.utcnow().isoformat(),
                "version": "1.0.0"
            },
            "database": {
                "sensor_records": total_sensors,
                "satellite_records": total_satellite,
                "analysis_jobs": total_jobs,
                "recent_activity": {
                    "sensors_24h": recent_sensors,
                    "jobs_24h": recent_jobs
                }
            },
            "jobs": {
                "status_breakdown": job_status_counts
            },
            "data_sources": source_counts,
            "storage": {
                "cache_size_bytes": cache_size,
                "cache_size_mb": round(cache_size / (1024 * 1024), 2)
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving system status: {str(e)}")

@router.get("/nasa/token-status")
async def get_nasa_token_status():
    """Get NASA Earthdata token status and information"""
    try:
        token_info = nasa_auth_service.get_token_info()
        
        return {
            "token_status": token_info,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving NASA token status: {str(e)}")

@router.post("/nasa/validate-token")
async def validate_nasa_token():
    """Validate NASA Earthdata token against NASA services"""
    try:
        validation_result = await nasa_auth_service.validate_token()
        
        return validation_result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"NASA token validation failed: {str(e)}")

@router.post("/nasa/test-api-access")
async def test_nasa_api_access():
    """Test access to NASA APIs with current token"""
    try:
        test_results = await nasa_auth_service.test_api_access()
        
        return test_results
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"NASA API access test failed: {str(e)}")

@router.get("/nasa/usage-statistics")
async def get_nasa_usage_statistics(days_back: int = 7):
    """Get NASA API usage statistics for monitoring"""
    try:
        usage_stats = await nasa_auth_service.get_usage_statistics(days_back)
        
        return usage_stats
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving NASA usage statistics: {str(e)}")

@router.post("/nasa/refresh-token")
async def refresh_nasa_token():
    """Attempt to refresh NASA token using stored credentials"""
    try:
        refresh_result = await nasa_auth_service.refresh_token_if_needed()
        
        return refresh_result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"NASA token refresh failed: {str(e)}")
@router.delete("/cache")
async def clear_cache():
    """Clear system cache"""
    try:
        cache_dir = os.getenv("CACHE_DIR", "/tmp/seit_cache")
        
        if os.path.exists(cache_dir):
            shutil.rmtree(cache_dir)
            os.makedirs(cache_dir, exist_ok=True)
        
        return {
            "message": "Cache cleared successfully",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error clearing cache: {str(e)}")

@router.delete("/data/sensors")
async def cleanup_old_sensor_data(
    days_old: int = 30,
    db: Session = Depends(get_db)
):
    """Clean up sensor data older than specified days"""
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        # Count records to be deleted
        old_records = db.query(SensorData).filter(SensorData.created_at < cutoff_date)
        count = old_records.count()
        
        # Delete old records
        old_records.delete()
        db.commit()
        
        return {
            "message": f"Deleted {count} sensor records older than {days_old} days",
            "deleted_count": count,
            "cutoff_date": cutoff_date.isoformat()
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error cleaning up sensor data: {str(e)}")

@router.delete("/jobs/failed")
async def cleanup_failed_jobs(db: Session = Depends(get_db)):
    """Clean up failed analysis jobs"""
    try:
        # Get failed jobs older than 7 days
        cutoff_date = datetime.utcnow() - timedelta(days=7)
        failed_jobs = db.query(AnalysisJob).filter(
            AnalysisJob.status == "failed",
            AnalysisJob.created_at < cutoff_date
        )
        
        count = failed_jobs.count()
        failed_jobs.delete()
        db.commit()
        
        return {
            "message": f"Deleted {count} failed jobs",
            "deleted_count": count,
            "cutoff_date": cutoff_date.isoformat()
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error cleaning up failed jobs: {str(e)}")

@router.post("/reprocess")
async def trigger_reprocessing(
    job_type: str,
    parameters: dict,
    db: Session = Depends(get_db)
):
    """Trigger reprocessing of data with specified parameters"""
    try:
        # Create new reprocessing job
        job_id = str(uuid.uuid4())
        job = AnalysisJob(
            job_id=job_id,
            job_type=f"reprocess_{job_type}",
            status="pending",
            parameters=parameters
        )
        db.add(job)
        db.commit()
        
        return {
            "job_id": job_id,
            "status": "submitted",
            "message": f"Reprocessing job for {job_type} submitted successfully"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error triggering reprocessing: {str(e)}")

@router.get("/logs")
async def get_system_logs(lines: int = 100):
    """Get recent system logs"""
    try:
        log_file = os.getenv("LOG_FILE", "/var/log/seit/application.log")
        
        if not os.path.exists(log_file):
            return {"message": "Log file not found", "logs": []}
        
        # Read last N lines
        with open(log_file, 'r') as f:
            all_lines = f.readlines()
            recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
        
        return {
            "total_lines": len(all_lines),
            "returned_lines": len(recent_lines),
            "logs": [line.strip() for line in recent_lines]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving logs: {str(e)}")
