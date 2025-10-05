from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, JSON
from sqlalchemy.sql import func
from .database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class SensorData(Base):
    __tablename__ = "sensor_data"
    
    id = Column(Integer, primary_key=True, index=True)
    sensor_id = Column(String, index=True, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    pm25 = Column(Float)
    pm10 = Column(Float)
    temperature = Column(Float)
    humidity = Column(Float)
    pressure = Column(Float)
    source = Column(String, nullable=False)  # 'purpleair', 'sensor_community', 'upload'
    metadata = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class SatelliteData(Base):
    __tablename__ = "satellite_data"
    
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(String, nullable=False)
    granule_id = Column(String, unique=True, nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    bbox = Column(String, nullable=False)  # JSON string of bounding box
    file_path = Column(String, nullable=False)
    metadata = Column(JSON)
    processed = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String, unique=True, nullable=False)
    job_type = Column(String, nullable=False)  # 'hotspot', 'anomaly', 'trend'
    status = Column(String, default="pending")  # 'pending', 'running', 'completed', 'failed'
    parameters = Column(JSON)
    result_path = Column(String)
    error_message = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))
