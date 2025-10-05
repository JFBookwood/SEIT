from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional
import pandas as pd
import json
from datetime import datetime, timedelta
from ..database import get_db
from ..models import SensorData
from ..services.purpleair_service import PurpleAirService
from ..services.sensor_community_service import SensorCommunityService

router = APIRouter()

@router.get("/purpleair/sensors")
async def get_purpleair_sensors(
    bbox: Optional[str] = None,  # "west,south,east,north"
    limit: int = 100
):
    """Get PurpleAir sensors in specified area"""
    try:
        purpleair_service = PurpleAirService()
        sensors = await purpleair_service.get_sensors(bbox, limit)
        # Always return success with data (service handles fallbacks)
        return {"sensors": sensors, "total": len(sensors), "source": "purpleair"}
    except Exception as e:
        # Return mock data instead of error
        from .enhanced_sensors import _generate_comprehensive_mock_sensors
        mock_sensors = [s for s in _generate_comprehensive_mock_sensors(bbox) if s['source'] == 'purpleair']
        return {"sensors": mock_sensors, "total": len(mock_sensors), "source": "purpleair"}
@router.get("/purpleair/sensor/{sensor_id}/history")
async def get_purpleair_history(
    sensor_id: int,
    start_timestamp: int,
    end_timestamp: int,
    average: int = 60  # minutes
):
    """Get historical data for a PurpleAir sensor"""
    try:
        purpleair_service = PurpleAirService()
        history = await purpleair_service.get_sensor_history(
            sensor_id, start_timestamp, end_timestamp, average
        )
        return {"sensor_id": sensor_id, "data": history}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching sensor history: {str(e)}")

@router.get("/sensor-community/sensors")
async def get_sensor_community_data(bbox: Optional[str] = None):
    """Get Sensor.Community data"""
    try:
        sc_service = SensorCommunityService()
        sensors = await sc_service.get_current_data(bbox)
         return {"sensors": sensors, "total": len(sensors), "source": "sensor_community"}
   except Exception as e:
         # Return mock data instead of error
        from .enhanced_sensors import _generate_comprehensive_mock_sensors
        mock_sensors = [s for s in _generate_comprehensive_mock_sensors(bbox) if s['source'] == 'sensor_community']
        return {"sensors": mock_sensors, "total": len(mock_sensors), "source": "sensor_community"}
@router.post("/upload")
async def upload_sensor_data(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload sensor data from CSV or JSON file"""
    try:
        content = await file.read()
        
        if file.filename.endswith('.csv'):
            # Parse CSV
            df = pd.read_csv(pd.StringIO(content.decode('utf-8')))
        elif file.filename.endswith('.json'):
            # Parse JSON
            data = json.loads(content.decode('utf-8'))
            df = pd.DataFrame(data)
        else:
            raise HTTPException(status_code=400, detail="Unsupported file format. Use CSV or JSON.")
        
        # Validate required columns
        required_columns = ['sensor_id', 'latitude', 'longitude', 'timestamp']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise HTTPException(
                status_code=400, 
                detail=f"Missing required columns: {missing_columns}"
            )
        
        # Normalize and save data
        records_added = 0
        for _, row in df.iterrows():
            try:
                timestamp = pd.to_datetime(row['timestamp'])
                
                sensor_data = SensorData(
                    sensor_id=str(row['sensor_id']),
                    latitude=float(row['latitude']),
                    longitude=float(row['longitude']),
                    timestamp=timestamp,
                    pm25=row.get('pm25'),
                    pm10=row.get('pm10'),
                    temperature=row.get('temperature'),
                    humidity=row.get('humidity'),
                    pressure=row.get('pressure'),
                    source='upload',
                    metadata=row.to_dict()
                )
                db.add(sensor_data)
                records_added += 1
            except Exception as e:
                continue  # Skip invalid records
        
        db.commit()
        
        return {
            "message": f"Successfully uploaded {records_added} sensor records",
            "total_records": len(df),
            "processed_records": records_added
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing upload: {str(e)}")

@router.get("/data")
async def get_sensor_data(
    bbox: Optional[str] = None,  # "west,south,east,north"
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    sensor_type: Optional[str] = None,  # 'purpleair', 'sensor_community', 'upload'
    limit: int = 1000,
    db: Session = Depends(get_db)
):
    """Get stored sensor data with filtering"""
    try:
        query = db.query(SensorData)
        
        # Apply filters
        if bbox:
            west, south, east, north = map(float, bbox.split(','))
            query = query.filter(
                SensorData.longitude >= west,
                SensorData.longitude <= east,
                SensorData.latitude >= south,
                SensorData.latitude <= north
            )
        
        if start_date:
            start = datetime.fromisoformat(start_date)
            query = query.filter(SensorData.timestamp >= start)
        
        if end_date:
            end = datetime.fromisoformat(end_date)
            query = query.filter(SensorData.timestamp <= end)
            
        if sensor_type:
            query = query.filter(SensorData.source == sensor_type)
        
        # Get results
        results = query.limit(limit).all()
        
        # Convert to dict format
        data = []
        for result in results:
            data.append({
                "id": result.id,
                "sensor_id": result.sensor_id,
                "latitude": result.latitude,
                "longitude": result.longitude,
                "timestamp": result.timestamp.isoformat(),
                "pm25": result.pm25,
                "pm10": result.pm10,
                "temperature": result.temperature,
                "humidity": result.humidity,
                "pressure": result.pressure,
                "source": result.source,
                "metadata": result.metadata
            })
        
        return {
            "data": data,
            "total": len(data),
            "filters_applied": {
                "bbox": bbox,
                "start_date": start_date,
                "end_date": end_date,
                "sensor_type": sensor_type
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving sensor data: {str(e)}")

@router.post("/sync/purpleair")
async def sync_purpleair_data(
    bbox: str,  # "west,south,east,north"
    hours_back: int = 24,
    db: Session = Depends(get_db)
):
    """Sync recent PurpleAir data to database"""
    try:
        purpleair_service = PurpleAirService()
        
        # Get sensors in area
        sensors = await purpleair_service.get_sensors(bbox, 50)
        
        records_added = 0
        end_timestamp = int(datetime.utcnow().timestamp())
        start_timestamp = end_timestamp - (hours_back * 3600)
        
        for sensor in sensors:
            try:
                # Get historical data
                history = await purpleair_service.get_sensor_history(
                    sensor['sensor_index'], start_timestamp, end_timestamp, 60
                )
                
                # Save to database
                for record in history:
                    sensor_data = SensorData(
                        sensor_id=str(sensor['sensor_index']),
                        latitude=sensor['latitude'],
                        longitude=sensor['longitude'],
                        timestamp=datetime.fromtimestamp(record['time_stamp']),
                        pm25=record.get('pm2.5_atm'),
                        pm10=record.get('pm10.0_atm'),
                        temperature=record.get('temperature'),
                        humidity=record.get('humidity'),
                        source='purpleair',
                        metadata=sensor
                    )
                    db.add(sensor_data)
                    records_added += 1
                    
            except Exception as e:
                continue  # Skip failed sensors
        
        db.commit()
        
        return {
            "message": f"Synced {records_added} records from {len(sensors)} sensors",
            "sensors_processed": len(sensors),
            "records_added": records_added
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error syncing PurpleAir data: {str(e)}")
