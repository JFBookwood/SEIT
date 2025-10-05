# MILESTONE 1: Data Architecture & Bug Fixes

## 🎯 OBJECTIVE
Fix immediate reliability issues and establish robust data foundation for production air quality monitoring.

## 📋 TASKS BREAKDOWN

### Task 1.1: Enhanced Database Schema
**Time: 45 minutes**

#### Database Schema Updates
- **sensors_harmonized** table with canonical field schema
- **sensor_calibration** table for per-sensor calibration parameters
- **artifact_cache** table for processed data storage
- **data_quality_logs** table for QC tracking

#### Schema Design:
```sql
CREATE TABLE sensors_harmonized (
    id SERIAL PRIMARY KEY,
    sensor_id VARCHAR NOT NULL,
    sensor_type VARCHAR NOT NULL,
    lat DECIMAL(10,6) NOT NULL,
    lon DECIMAL(10,6) NOT NULL,
    timestamp_utc TIMESTAMP NOT NULL,
    raw_pm2_5 DECIMAL(8,2),
    rh DECIMAL(5,2),
    temperature DECIMAL(6,2),
    source VARCHAR NOT NULL,
    raw_blob JSONB,
    qc_flags TEXT[],
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE sensor_calibration (
    sensor_id VARCHAR PRIMARY KEY,
    sensor_type VARCHAR NOT NULL,
    alpha DECIMAL(10,4) DEFAULT 0,
    beta DECIMAL(10,4) DEFAULT 1,
    gamma DECIMAL(10,4) DEFAULT 0,
    delta DECIMAL(10,4) DEFAULT 0,
    sigma_i DECIMAL(8,4),
    last_calibrated TIMESTAMP,
    calibration_r2 DECIMAL(5,4),
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Task 1.2: Server-Side API Consolidation
**Time: 60 minutes**

#### Backend API Refactoring
- Move PurpleAir, Open-Meteo, NASA calls to background tasks
- Implement Redis caching with TTL controls
- Add rate limiting with exponential backoff
- Create unified data ingestion endpoints

#### Key Services:
- **IngestService**: Coordinate multi-source data collection
- **CacheService**: Manage artifact storage and retrieval
- **QCService**: Apply data quality validation rules
- **HarmonizationService**: Map fields to canonical schema

### Task 1.3: Frontend Marker Stabilization
**Time: 45 minutes**

#### Marker Rendering Fixes
- Validate coordinates at ingestion (lat: -90 to 90, lon: -180 to 180)
- Implement canvas-based marker rendering for stability
- Remove CSS transitions causing wobble effects
- Add proper marker clustering for high-density areas

#### Map Layer Improvements
- Replace fragile external tile services with stable base maps
- Implement server-side tile proxy for reliability
- Add proper loading states and error boundaries
- Ensure CORS compliance for all map resources

## 🔧 IMPLEMENTATION DETAILS

### Data Validation Pipeline
```python
def validate_sensor_coordinates(lat: float, lon: float) -> bool:
    """Validate sensor coordinates are within valid ranges"""
    return (-90 <= lat <= 90) and (-180 <= lon <= 180)

def harmonize_sensor_data(raw_data: dict, source: str) -> dict:
    """Map source-specific fields to canonical schema"""
    harmonized = {
        'sensor_id': extract_sensor_id(raw_data, source),
        'sensor_type': extract_sensor_type(raw_data, source),
        'lat': float(raw_data.get('latitude', 0)),
        'lon': float(raw_data.get('longitude', 0)),
        'timestamp_utc': parse_timestamp(raw_data, source),
        'raw_pm2_5': extract_pm25(raw_data, source),
        'source': source,
        'raw_blob': raw_data
    }
    return harmonized
```

### Caching Strategy
- **L1 Cache**: In-memory Redis for frequently accessed data (TTL: 5 minutes)
- **L2 Cache**: Artifact storage for processed grids (TTL: 1 hour)
- **L3 Cache**: Long-term storage for historical snapshots (TTL: 30 days)

### Frontend Marker Implementation
```javascript
// Stable marker rendering without wobble
const createStableMarker = (sensor) => {
  return L.circleMarker([sensor.lat, sensor.lon], {
    radius: 8,
    fillColor: getSeverityColor(sensor.pm25_corrected),
    color: 'white',
    weight: 2,
    opacity: 1,
    fillOpacity: 0.8
  });
};
```

## ✅ ACCEPTANCE CRITERIA

### Technical Validation
- [ ] Marker stability: No wobbling during pan/zoom operations
- [ ] Coordinate validation: All sensors have valid lat/lon ranges
- [ ] Server-side caching: External API calls moved to background tasks
- [ ] Data harmonization: Consistent field naming across sources

### Performance Validation
- [ ] Frontend loading: Map renders in <3 seconds
- [ ] Data freshness: Cache invalidation working properly
- [ ] Error handling: Graceful degradation with meaningful messages
- [ ] Memory usage: No memory leaks during extended usage

### Data Quality Validation
- [ ] Field mapping: All sources correctly harmonized to canonical schema
- [ ] QC rules: Invalid/suspicious data properly flagged
- [ ] Traceability: Original data preserved in raw_blob
- [ ] Logging: Comprehensive QC and error logging

## 🚀 NEXT STEPS

After Milestone 1 completion:
1. Validate data loading and marker stability
2. Test server-side caching performance
3. Verify harmonized data quality
4. Prepare for NASA Earthdata integration (Milestone 2)

This milestone establishes the foundation for advanced features while fixing current reliability issues.
