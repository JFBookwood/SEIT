from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, JSON, ARRAY, DECIMAL, CheckConstraint
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import TIMESTAMPTZ, JSONB
from ..database import Base

class SensorHarmonized(Base):
    __tablename__ = "sensors_harmonized"
    
    id = Column(Integer, primary_key=True, index=True)
    sensor_id = Column(String(255), nullable=False, index=True)
    sensor_type = Column(String(100), nullable=False)
    lat = Column(DECIMAL(10,6), nullable=False, index=True)
    lon = Column(DECIMAL(10,6), nullable=False, index=True)
    timestamp_utc = Column(TIMESTAMPTZ, nullable=False, index=True)
    raw_pm2_5 = Column(DECIMAL(8,2))
    rh = Column(DECIMAL(5,2))  # Relative humidity
    temperature = Column(DECIMAL(6,2))
    pressure = Column(DECIMAL(7,2))
    raw_pm10 = Column(DECIMAL(8,2))
    no2 = Column(DECIMAL(8,2))
    o3 = Column(DECIMAL(8,2))
    source = Column(String(50), nullable=False, index=True)
    raw_blob = Column(JSONB)  # Original data for traceability
    qc_flags = Column(ARRAY(Text), default=list)
    data_quality_score = Column(DECIMAL(3,2), default=1.0)
    created_at = Column(TIMESTAMPTZ, server_default=func.now())
    updated_at = Column(TIMESTAMPTZ, server_default=func.now(), onupdate=func.now())
    
    # Constraints
    __table_args__ = (
        CheckConstraint('lat >= -90 AND lat <= 90', name='check_valid_latitude'),
        CheckConstraint('lon >= -180 AND lon <= 180', name='check_valid_longitude'),
        CheckConstraint('raw_pm2_5 >= 0 AND raw_pm2_5 <= 1000', name='check_pm25_range'),
        CheckConstraint('rh >= 0 AND rh <= 100', name='check_humidity_range'),
        CheckConstraint('temperature >= -50 AND temperature <= 60', name='check_temperature_range'),
        CheckConstraint('data_quality_score >= 0 AND data_quality_score <= 1', name='check_quality_score'),
    )

class SensorCalibration(Base):
    __tablename__ = "sensor_calibration"
    
    sensor_id = Column(String(255), primary_key=True)
    sensor_type = Column(String(100), nullable=False)
    alpha = Column(DECIMAL(10,4), default=0.0)  # Intercept
    beta = Column(DECIMAL(10,4), default=1.0)   # Raw PM2.5 coefficient
    gamma = Column(DECIMAL(10,4), default=0.0)  # Humidity coefficient
    delta = Column(DECIMAL(10,4), default=0.0)  # Temperature coefficient
    sigma_i = Column(DECIMAL(8,4), nullable=False, default=5.0)  # Residual uncertainty
    last_calibrated = Column(TIMESTAMPTZ)
    calibration_r2 = Column(DECIMAL(5,4))
    reference_count = Column(Integer, default=0)
    calibration_method = Column(String(50), default='linear')
    is_active = Column(Boolean, default=True)
    validation_rmse = Column(DECIMAL(8,4))
    validation_bias = Column(DECIMAL(8,4))
    created_at = Column(TIMESTAMPTZ, server_default=func.now())
    updated_at = Column(TIMESTAMPTZ, server_default=func.now(), onupdate=func.now())

class ArtifactCache(Base):
    __tablename__ = "artifact_cache"
    
    cache_key = Column(String(255), primary_key=True)
    bbox = Column(String(100), nullable=False, index=True)
    timestamp_utc = Column(TIMESTAMPTZ, nullable=False, index=True)
    resolution = Column(Integer, nullable=False, default=250)
    method = Column(String(50), nullable=False, default='idw')
    grid_data = Column(JSONB, nullable=False)
    metadata = Column(JSONB)
    expires_at = Column(TIMESTAMPTZ, nullable=False, index=True)
    file_size_bytes = Column(Integer, default=0)
    processing_time_ms = Column(Integer, default=0)
    created_at = Column(TIMESTAMPTZ, server_default=func.now())

class DataQualityLog(Base):
    __tablename__ = "data_quality_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    sensor_id = Column(String(255), nullable=False, index=True)
    timestamp_utc = Column(TIMESTAMPTZ, nullable=False, index=True)
    qc_rule = Column(String(100), nullable=False)
    rule_result = Column(String(20), nullable=False)  # 'pass', 'fail', 'flag'
    original_value = Column(DECIMAL(10,4))
    corrected_value = Column(DECIMAL(10,4))
    flag_reason = Column(Text)
    created_at = Column(TIMESTAMPTZ, server_default=func.now())
