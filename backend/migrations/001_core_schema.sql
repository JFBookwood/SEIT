/*
# Core SEIT Database Schema
1. Purpose: Create canonical tables for sensor data harmonization and calibration
2. Schema: sensors_harmonized, sensor_calibration, artifact_cache
3. Security: RLS enabled with proper access policies
*/

-- Harmonized sensor data table
CREATE TABLE IF NOT EXISTS sensors_harmonized (
    id SERIAL PRIMARY KEY,
    sensor_id VARCHAR(255) NOT NULL,
    sensor_type VARCHAR(100) NOT NULL,
    lat DECIMAL(10,6) NOT NULL CHECK (lat >= -90 AND lat <= 90),
    lon DECIMAL(10,6) NOT NULL CHECK (lon >= -180 AND lon <= 180),
    timestamp_utc TIMESTAMPTZ NOT NULL,
    raw_pm2_5 DECIMAL(8,2) CHECK (raw_pm2_5 >= 0 AND raw_pm2_5 <= 1000),
    rh DECIMAL(5,2) CHECK (rh >= 0 AND rh <= 100),
    temperature DECIMAL(6,2) CHECK (temperature >= -50 AND temperature <= 60),
    pressure DECIMAL(7,2) CHECK (pressure >= 800 AND pressure <= 1200),
    raw_pm10 DECIMAL(8,2) CHECK (raw_pm10 >= 0 AND raw_pm10 <= 2000),
    no2 DECIMAL(8,2) CHECK (no2 >= 0),
    o3 DECIMAL(8,2) CHECK (o3 >= 0),
    source VARCHAR(50) NOT NULL,
    raw_blob JSONB,
    qc_flags TEXT[] DEFAULT '{}',
    data_quality_score DECIMAL(3,2) DEFAULT 1.0 CHECK (data_quality_score >= 0 AND data_quality_score <= 1),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Sensor calibration parameters table
CREATE TABLE IF NOT EXISTS sensor_calibration (
    sensor_id VARCHAR(255) PRIMARY KEY,
    sensor_type VARCHAR(100) NOT NULL,
    alpha DECIMAL(10,4) DEFAULT 0.0,
    beta DECIMAL(10,4) DEFAULT 1.0,
    gamma DECIMAL(10,4) DEFAULT 0.0,
    delta DECIMAL(10,4) DEFAULT 0.0,
    sigma_i DECIMAL(8,4) NOT NULL DEFAULT 5.0,
    last_calibrated TIMESTAMPTZ,
    calibration_r2 DECIMAL(5,4),
    reference_count INTEGER DEFAULT 0,
    calibration_method VARCHAR(50) DEFAULT 'linear',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Processed artifact cache table
CREATE TABLE IF NOT EXISTS artifact_cache (
    cache_key VARCHAR(255) PRIMARY KEY,
    bbox VARCHAR(100) NOT NULL,
    timestamp_utc TIMESTAMPTZ NOT NULL,
    resolution INTEGER NOT NULL DEFAULT 250,
    method VARCHAR(50) NOT NULL DEFAULT 'idw',
    grid_data JSONB NOT NULL,
    metadata JSONB,
    expires_at TIMESTAMPTZ NOT NULL,
    file_size_bytes INTEGER DEFAULT 0,
    processing_time_ms INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Quality control logs table  
CREATE TABLE IF NOT EXISTS data_quality_logs (
    id SERIAL PRIMARY KEY,
    sensor_id VARCHAR(255) NOT NULL,
    timestamp_utc TIMESTAMPTZ NOT NULL,
    qc_rule VARCHAR(100) NOT NULL,
    rule_result VARCHAR(20) NOT NULL,
    original_value DECIMAL(10,4),
    corrected_value DECIMAL(10,4),
    flag_reason TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_sensors_harmonized_spatial ON sensors_harmonized(lat, lon);
CREATE INDEX IF NOT EXISTS idx_sensors_harmonized_temporal ON sensors_harmonized(timestamp_utc);
CREATE INDEX IF NOT EXISTS idx_sensors_harmonized_source ON sensors_harmonized(source);
CREATE INDEX IF NOT EXISTS idx_sensors_harmonized_sensor_time ON sensors_harmonized(sensor_id, timestamp_utc);
CREATE INDEX IF NOT EXISTS idx_artifact_cache_bbox_time ON artifact_cache(bbox, timestamp_utc);
CREATE INDEX IF NOT EXISTS idx_artifact_cache_expires ON artifact_cache(expires_at);
CREATE INDEX IF NOT EXISTS idx_data_quality_sensor_time ON data_quality_logs(sensor_id, timestamp_utc);

-- Enable Row Level Security
ALTER TABLE sensors_harmonized ENABLE ROW LEVEL SECURITY;
ALTER TABLE sensor_calibration ENABLE ROW LEVEL SECURITY;
ALTER TABLE artifact_cache ENABLE ROW LEVEL SECURITY;
ALTER TABLE data_quality_logs ENABLE ROW LEVEL SECURITY;

-- Create RLS policies for authenticated access
CREATE POLICY "Authenticated users can view harmonized sensors"
    ON sensors_harmonized FOR SELECT 
    USING (auth.role() = 'authenticated');

CREATE POLICY "Authenticated users can insert harmonized sensors"
    ON sensors_harmonized FOR INSERT 
    WITH CHECK (auth.role() = 'authenticated');

CREATE POLICY "Authenticated users can view calibration data"
    ON sensor_calibration FOR SELECT 
    USING (auth.role() = 'authenticated');

CREATE POLICY "Admin users can modify calibration data"
    ON sensor_calibration FOR ALL 
    USING (auth.role() = 'authenticated');

CREATE POLICY "Authenticated users can view cached artifacts"
    ON artifact_cache FOR SELECT 
    USING (auth.role() = 'authenticated');

CREATE POLICY "Service role can manage artifacts"
    ON artifact_cache FOR ALL 
    USING (auth.role() = 'service_role');

CREATE POLICY "Authenticated users can view quality logs"
    ON data_quality_logs FOR SELECT 
    USING (auth.role() = 'authenticated');

CREATE POLICY "Service role can insert quality logs"
    ON data_quality_logs FOR INSERT 
    WITH CHECK (auth.role() = 'service_role');
