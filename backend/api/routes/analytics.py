from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import StandardScaler
import json
import uuid
from ..database import get_db
from ..models import SensorData, AnalysisJob
from ..services.hotspot_service import HotspotService
from ..services.anomaly_service import AnomalyService

router = APIRouter()

@router.post("/hotspots")
async def analyze_hotspots(
    bbox: List[float],  # [west, south, east, north]
    start_date: str,
    end_date: str,
    grid_size: float = 0.01,  # ~1km resolution
    eps: float = 0.01,
    min_samples: int = 3,
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db)
):
    """Detect environmental hotspots using DBSCAN clustering"""
    try:
        hotspot_service = HotspotService(db)
        
        # Create analysis job
        job_id = str(uuid.uuid4())
        job = AnalysisJob(
            job_id=job_id,
            job_type="hotspot",
            status="running",
            parameters={
                "bbox": bbox,
                "start_date": start_date,
                "end_date": end_date,
                "grid_size": grid_size,
                "eps": eps,
                "min_samples": min_samples
            }
        )
        db.add(job)
        db.commit()
        
        # Run analysis
        result = await hotspot_service.detect_hotspots(
            bbox, start_date, end_date, grid_size, eps, min_samples
        )
        
        # Update job status
        job.status = "completed"
        job.result_path = f"results/hotspots/{job_id}.geojson"
        db.commit()
        
        return {
            "job_id": job_id,
            "status": "completed",
            "hotspots": result["hotspots"],
            "summary": result["summary"]
        }
        
    except Exception as e:
        # Update job status on error
        if 'job' in locals():
            job.status = "failed"
            job.error_message = str(e)
            db.commit()
        raise HTTPException(status_code=500, detail=f"Error analyzing hotspots: {str(e)}")

@router.post("/anomalies")
async def detect_anomalies(
    bbox: List[float],
    start_date: str,
    end_date: str,
    method: str = "isolation_forest",  # or "autoencoder"
    threshold: float = 0.1,
    db: Session = Depends(get_db)
):
    """Detect anomalies in sensor data"""
    try:
        anomaly_service = AnomalyService(db)
        
        # Create analysis job
        job_id = str(uuid.uuid4())
        job = AnalysisJob(
            job_id=job_id,
            job_type="anomaly",
            status="running",
            parameters={
                "bbox": bbox,
                "start_date": start_date,
                "end_date": end_date,
                "method": method,
                "threshold": threshold
            }
        )
        db.add(job)
        db.commit()
        
        # Run analysis
        result = await anomaly_service.detect_anomalies(
            bbox, start_date, end_date, method, threshold
        )
        
        # Update job status
        job.status = "completed"
        job.result_path = f"results/anomalies/{job_id}.json"
        db.commit()
        
        return {
            "job_id": job_id,
            "status": "completed",
            "anomalies": result["anomalies"],
            "summary": result["summary"]
        }
        
    except Exception as e:
        if 'job' in locals():
            job.status = "failed"
            job.error_message = str(e)
            db.commit()
        raise HTTPException(status_code=500, detail=f"Error detecting anomalies: {str(e)}")

@router.get("/trends")
async def analyze_trends(
    bbox: List[float],
    start_date: str,
    end_date: str,
    parameter: str = "pm25",
    temporal_resolution: str = "daily",  # daily, weekly, monthly
    db: Session = Depends(get_db)
):
    """Analyze temporal trends in environmental data"""
    try:
        # Get sensor data
        west, south, east, north = bbox
        start = datetime.fromisoformat(start_date)
        end = datetime.fromisoformat(end_date)
        
        query = db.query(SensorData).filter(
            SensorData.longitude >= west,
            SensorData.longitude <= east,
            SensorData.latitude >= south,
            SensorData.latitude <= north,
            SensorData.timestamp >= start,
            SensorData.timestamp <= end
        )
        
        results = query.all()
        
        if not results:
            return {"message": "No data found for the specified area and time range", "trends": []}
        
        # Convert to DataFrame
        data = []
        for result in results:
            value = getattr(result, parameter, None)
            if value is not None:
                data.append({
                    'timestamp': result.timestamp,
                    'value': value,
                    'latitude': result.latitude,
                    'longitude': result.longitude
                })
        
        if not data:
            return {"message": f"No {parameter} data found", "trends": []}
        
        df = pd.DataFrame(data)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Resample based on temporal resolution
        freq_map = {
            'daily': 'D',
            'weekly': 'W',
            'monthly': 'M'
        }
        
        # Group by time period and calculate statistics
        df.set_index('timestamp', inplace=True)
        resampled = df.groupby(pd.Grouper(freq=freq_map[temporal_resolution])).agg({
            'value': ['mean', 'min', 'max', 'std', 'count']
        }).reset_index()
        
        resampled.columns = ['timestamp', 'mean', 'min', 'max', 'std', 'count']
        
        # Calculate trend (linear regression slope)
        from scipy import stats
        if len(resampled) > 1:
            x = np.arange(len(resampled))
            y = resampled['mean'].values
            slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
        else:
            slope = 0
            r_value = 0
            p_value = 1
        
        trends = []
        for _, row in resampled.iterrows():
            trends.append({
                'timestamp': row['timestamp'].isoformat(),
                'mean': float(row['mean']) if not pd.isna(row['mean']) else None,
                'min': float(row['min']) if not pd.isna(row['min']) else None,
                'max': float(row['max']) if not pd.isna(row['max']) else None,
                'std': float(row['std']) if not pd.isna(row['std']) else None,
                'count': int(row['count'])
            })
        
        return {
            "parameter": parameter,
            "temporal_resolution": temporal_resolution,
            "time_range": {"start": start_date, "end": end_date},
            "trends": trends,
            "statistics": {
                "total_records": len(data),
                "trend_slope": float(slope),
                "correlation": float(r_value),
                "p_value": float(p_value),
                "significance": "significant" if p_value < 0.05 else "not_significant"
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analyzing trends: {str(e)}")

@router.get("/jobs/{job_id}")
async def get_analysis_job(job_id: str, db: Session = Depends(get_db)):
    """Get analysis job status and results"""
    try:
        job = db.query(AnalysisJob).filter(AnalysisJob.job_id == job_id).first()
        
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        result = {
            "job_id": job.job_id,
            "job_type": job.job_type,
            "status": job.status,
            "parameters": job.parameters,
            "created_at": job.created_at.isoformat(),
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "error_message": job.error_message
        }
        
        # If completed, try to load results
        if job.status == "completed" and job.result_path:
            try:
                # In a real implementation, you'd load from file system or S3
                result["result_available"] = True
                result["result_path"] = job.result_path
            except Exception:
                result["result_available"] = False
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving job: {str(e)}")

@router.get("/summary")
async def get_analytics_summary(
    bbox: List[float],
    start_date: str,
    end_date: str,
    db: Session = Depends(get_db)
):
    """Get summary analytics for a region and time period"""
    try:
        west, south, east, north = bbox
        start = datetime.fromisoformat(start_date)
        end = datetime.fromisoformat(end_date)
        
        query = db.query(SensorData).filter(
            SensorData.longitude >= west,
            SensorData.longitude <= east,
            SensorData.latitude >= south,
            SensorData.latitude <= north,
            SensorData.timestamp >= start,
            SensorData.timestamp <= end
        )
        
        results = query.all()
        
        if not results:
            return {"message": "No data found for the specified area and time range"}
        
        # Calculate statistics
        pm25_values = [r.pm25 for r in results if r.pm25 is not None]
        pm10_values = [r.pm10 for r in results if r.pm10 is not None]
        temp_values = [r.temperature for r in results if r.temperature is not None]
        
        summary = {
            "total_records": len(results),
            "unique_sensors": len(set(r.sensor_id for r in results)),
            "time_range": {"start": start_date, "end": end_date},
            "spatial_bounds": {"west": west, "south": south, "east": east, "north": north},
            "data_sources": list(set(r.source for r in results)),
            "parameters": {}
        }
        
        if pm25_values:
            summary["parameters"]["pm25"] = {
                "mean": float(np.mean(pm25_values)),
                "median": float(np.median(pm25_values)),
                "min": float(np.min(pm25_values)),
                "max": float(np.max(pm25_values)),
                "std": float(np.std(pm25_values)),
                "count": len(pm25_values)
            }
        
        if pm10_values:
            summary["parameters"]["pm10"] = {
                "mean": float(np.mean(pm10_values)),
                "median": float(np.median(pm10_values)),
                "min": float(np.min(pm10_values)),
                "max": float(np.max(pm10_values)),
                "std": float(np.std(pm10_values)),
                "count": len(pm10_values)
            }
        
        if temp_values:
            summary["parameters"]["temperature"] = {
                "mean": float(np.mean(temp_values)),
                "median": float(np.median(temp_values)),
                "min": float(np.min(temp_values)),
                "max": float(np.max(temp_values)),
                "std": float(np.std(temp_values)),
                "count": len(temp_values)
            }
        
        return summary
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating summary: {str(e)}")
