# MILESTONE 3: Sensor Calibration & QC Pipeline

## 🎯 OBJECTIVE
Production-grade sensor data quality control and calibration system.

## 📋 IMPLEMENTATION TASKS

### Task 3.1: Data Quality Control System
**Time: 60 minutes**

#### QC Rules Implementation
```python
class SensorQCService:
    def apply_qc_rules(self, sensor_data: dict) -> dict:
        """Apply comprehensive QC rules to sensor data"""
        qc_flags = []
        
        # Rule 1: Remove negative values
        if sensor_data.get('raw_pm2_5', 0) < 0:
            qc_flags.append('NEGATIVE_PM25')
            sensor_data['raw_pm2_5'] = None
        
        # Rule 2: Flag extreme values
        if sensor_data.get('raw_pm2_5', 0) > 500:
            qc_flags.append('EXTREME_PM25')
        
        # Rule 3: High humidity uncertainty flag
        if sensor_data.get('rh', 0) > 85:
            qc_flags.append('HIGH_HUMIDITY_UNCERTAINTY')
        
        # Rule 4: Spike detection
        if self.detect_sudden_spike(sensor_data):
            qc_flags.append('SUDDEN_SPIKE')
        
        sensor_data['qc_flags'] = qc_flags
        return sensor_data
```

#### Data Harmonization Layer
```python
class DataHarmonizationService:
    FIELD_MAPPINGS = {
        'purpleair': {
            'sensor_id': 'sensor_index',
            'raw_pm2_5': 'pm2.5_atm',
            'lat': 'latitude',
            'lon': 'longitude',
            'timestamp_utc': 'last_seen'
        },
        'sensor_community': {
            'sensor_id': 'id',
            'raw_pm2_5': 'P2',
            'lat': 'location.latitude',
            'lon': 'location.longitude'
        }
    }
    
    def harmonize_data(self, raw_data: dict, source: str) -> dict:
        """Map source fields to canonical schema"""
```

### Task 3.2: Calibration Model Implementation
**Time: 90 minutes**

#### Linear Calibration Models
```python
class SensorCalibrationService:
    def fit_calibration_model(self, sensor_id: str, reference_data: List[dict]):
        """Fit linear calibration: c_corr = alpha + beta*c_raw + gamma*rh + delta*t"""
        
        # Prepare design matrix
        X = np.column_stack([
            np.ones(len(reference_data)),  # intercept
            [d['raw_pm2_5'] for d in reference_data],  # raw PM2.5
            [d['rh'] for d in reference_data],  # relative humidity
            [d['temperature'] for d in reference_data]  # temperature
        ])
        
        y = np.array([d['reference_pm2_5'] for d in reference_data])
        
        # Fit model with uncertainty quantification
        coeffs, residuals = np.linalg.lstsq(X, y, rcond=None)[:2]
        sigma_i = np.sqrt(residuals / (len(y) - 4))  # residual standard error
        
        return {
            'alpha': coeffs[0],
            'beta': coeffs[1], 
            'gamma': coeffs[2],
            'delta': coeffs[3],
            'sigma_i': sigma_i,
            'r2': self.calculate_r2(y, X @ coeffs)
        }
```

#### Automated Calibration Pipeline
- Scheduled calibration updates (daily/weekly)
- Cross-validation for model performance
- Drift detection and recalibration triggers
- Calibration uncertainty propagation

### Task 3.3: Reference Data Management
**Time: 45 minutes**

#### Co-location Data Integration
- Support for EPA/regulatory monitor data upload
- Automated sensor-reference pairing by proximity
- Temporal alignment and averaging windows
- Quality control for reference data

#### Admin Calibration Interface
- Manual calibration trigger controls
- Calibration diagnostics visualization
- Model performance monitoring
- Reference data upload and validation

## 🔬 SCIENTIFIC METHODOLOGY

### Calibration Approach
1. **Linear Model**: Start with proven linear correction approach
2. **Covariates**: Include humidity and temperature for optical sensor correction
3. **Uncertainty**: Propagate calibration uncertainty through spatial interpolation
4. **Validation**: Cross-validation to prevent overfitting

### QC Framework
1. **Range Checks**: Physical validity of measurements
2. **Temporal Consistency**: Spike and drift detection
3. **Meteorological Flagging**: High-uncertainty conditions
4. **Source Validation**: Data source reliability metrics

## ✅ ACCEPTANCE CRITERIA

### Calibration System
- [ ] Linear calibration models fitting correctly
- [ ] Per-sensor calibration parameters stored and applied
- [ ] Uncertainty estimates (sigma_i) calculated for each sensor
- [ ] Automated recalibration triggers working

### Data Quality
- [ ] QC rules removing invalid data
- [ ] Field harmonization producing consistent schema
- [ ] Raw data preserved for traceability
- [ ] Quality flags properly assigned and logged

### Admin Interface
- [ ] Calibration diagnostics displaying correctly
- [ ] Manual recalibration controls functional
- [ ] Reference data upload working
- [ ] Performance metrics visible and accurate
