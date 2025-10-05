# MILESTONE 6: Monitoring & Validation

## 🎯 OBJECTIVE
Operational monitoring and scientific validation system for production deployment.

## 📋 IMPLEMENTATION TASKS

### Task 6.1: Spatial Cross-Validation System
**Time: 60 minutes**

#### Leave-One-Site-Out Validation
```python
class SpatialValidationService:
    def __init__(self, db_session: Session):
        self.db = db_session
    
    async def run_cross_validation(self, bbox: List[float], timestamp: str, 
                                 method: str = 'idw') -> dict:
        """Perform leave-one-site-out spatial cross-validation"""
        
        sensors = await self.get_sensors_for_validation(bbox, timestamp)
        
        predictions = []
        observations = []
        uncertainties = []
        
        for i, holdout_sensor in enumerate(sensors):
            # Create training set (all sensors except holdout)
            training_sensors = sensors[:i] + sensors[i+1:]
            
            # Generate prediction at holdout location
            if method == 'idw':
                result = self.idw_service.interpolate_point(
                    holdout_sensor['lon'], 
                    holdout_sensor['lat'], 
                    training_sensors
                )
            elif method == 'kriging':
                result = await self.kriging_service.predict_point(
                    holdout_sensor['lon'],
                    holdout_sensor['lat'],
                    training_sensors
                )
            
            if result:
                predictions.append(result[0])  # c_hat
                observations.append(holdout_sensor['pm25_corrected'])
                uncertainties.append(result[1])  # uncertainty
        
        # Calculate validation metrics
        metrics = self.calculate_validation_metrics(
            observations, predictions, uncertainties
        )
        
        return {
            'method': method,
            'bbox': bbox,
            'timestamp': timestamp,
            'n_sensors': len(sensors),
            'metrics': metrics,
            'validation_timestamp': datetime.utcnow().isoformat()
        }
    
    def calculate_validation_metrics(self, obs: List[float], pred: List[float], 
                                   unc: List[float]) -> dict:
        """Calculate comprehensive validation metrics"""
        obs = np.array(obs)
        pred = np.array(pred)
        unc = np.array(unc)
        
        # Basic metrics
        rmse = np.sqrt(np.mean((obs - pred) ** 2))
        mae = np.mean(np.abs(obs - pred))
        bias = np.mean(pred - obs)
        r2 = np.corrcoef(obs, pred)[0, 1] ** 2
        
        # Uncertainty-based metrics
        coverage_80 = np.mean(np.abs(obs - pred) <= 1.28 * unc)  # 80% coverage
        coverage_95 = np.mean(np.abs(obs - pred) <= 1.96 * unc)  # 95% coverage
        
        # Reliability metrics
        chi_squared = np.mean(((obs - pred) / unc) ** 2)
        
        return {
            'rmse': float(rmse),
            'mae': float(mae),
            'bias': float(bias),
            'r2': float(r2),
            'coverage_80': float(coverage_80),
            'coverage_95': float(coverage_95),
            'chi_squared': float(chi_squared),
            'n_pairs': len(obs)
        }
```

### Task 6.2: Automated Monitoring Dashboard
**Time: 45 minutes**

#### Validation Metrics Dashboard
```javascript
const ValidationDashboard = ({ validationResults, onTriggerValidation }) => {
  return (
    <div className="validation-dashboard">
      <div className="metrics-grid">
        <MetricCard
          title="RMSE"
          value={validationResults?.rmse?.toFixed(2)}
          unit="μg/m³"
          target={5.0}
          color={validationResults?.rmse < 5 ? 'green' : 'red'}
        />
        <MetricCard
          title="Coverage (95%)"
          value={`${(validationResults?.coverage_95 * 100)?.toFixed(1)}%`}
          target={95}
          color={validationResults?.coverage_95 > 0.90 ? 'green' : 'yellow'}
        />
        <MetricCard
          title="Bias"
          value={validationResults?.bias?.toFixed(2)}
          unit="μg/m³"
          target={0}
          color={Math.abs(validationResults?.bias || 0) < 2 ? 'green' : 'red'}
        />
      </div>
      
      <ValidationHistory 
        results={validationResults}
        onTriggerValidation={onTriggerValidation}
      />
    </div>
  );
};
```

#### Alert System
```python
class ValidationAlertService:
    def __init__(self):
        self.alert_thresholds = {
            'rmse': 8.0,  # μg/m³
            'bias': 5.0,  # μg/m³
            'coverage_95': 0.85,  # 85% minimum
            'chi_squared': 2.0  # reliability threshold
        }
    
    def check_validation_alerts(self, metrics: dict) -> List[dict]:
        """Check if validation metrics exceed thresholds"""
        alerts = []
        
        for metric, threshold in self.alert_thresholds.items():
            value = metrics.get(metric)
            if value is not None:
                if metric == 'coverage_95' and value < threshold:
                    alerts.append({
                        'type': 'warning',
                        'metric': metric,
                        'value': value,
                        'threshold': threshold,
                        'message': f'Coverage below target: {value:.1%} < {threshold:.1%}'
                    })
                elif metric != 'coverage_95' and value > threshold:
                    alerts.append({
                        'type': 'error' if value > threshold * 1.5 else 'warning',
                        'metric': metric,
                        'value': value,
                        'threshold': threshold,
                        'message': f'{metric.upper()} exceeds threshold: {value:.2f} > {threshold:.2f}'
                    })
        
        return alerts
```

### Task 6.3: Admin Controls & Documentation
**Time: 45 minutes**

#### Admin Interface Components
```javascript
const AdminCalibrationPanel = ({ sensors, onRecalibrate, onForceRebuild }) => {
  const [selectedSensors, setSelectedSensors] = useState([]);
  const [calibrationStatus, setCalibrationStatus] = useState({});
  
  return (
    <div className="admin-calibration-panel">
      <SensorCalibrationTable 
        sensors={sensors}
        calibrationStatus={calibrationStatus}
        onSelectSensors={setSelectedSensors}
      />
      
      <CalibrationControls
        selectedSensors={selectedSensors}
        onRecalibrate={onRecalibrate}
        onForceRebuild={onForceRebuild}
      />
      
      <CalibrationDiagnostics 
        sensors={selectedSensors}
        showAdvancedMetrics={true}
      />
    </div>
  );
};
```

#### Operations Documentation
```markdown
# SEIT Operations Manual

## NASA Token Management
1. **Token Rotation**: Update NASA_EARTHDATA_TOKEN in environment
2. **Validation**: Test token with `/api/admin/nasa/validate-token`
3. **Monitoring**: Check usage logs in `/api/admin/nasa/usage`

## Calibration Management
1. **Auto-Calibration**: Runs daily at 02:00 UTC
2. **Manual Trigger**: Use admin interface or API endpoint
3. **Quality Monitoring**: Check RMSE trends in validation dashboard
4. **Reference Data**: Upload co-location data via admin interface

## Grid Rebuilding
1. **Automatic**: Triggered on new calibrations or QC threshold breaches
2. **Manual**: Admin controls for specific bbox/time combinations
3. **Validation**: Cross-validation runs after each rebuild
4. **Performance**: Monitor processing time and cache hit rates
```

## 🔧 TECHNICAL IMPLEMENTATION

### Scheduled Validation Jobs
```python
@celery.task
def run_scheduled_validation():
    """Daily validation job for monitoring system performance"""
    
    # Key metropolitan areas for validation
    validation_bboxes = [
        [-122.5, 37.3, -122.0, 37.8],  # San Francisco Bay
        [-118.7, 33.7, -118.0, 34.3],  # Los Angeles
        [-74.3, 40.5, -73.7, 40.9]     # New York City
    ]
    
    for bbox in validation_bboxes:
        for method in ['idw', 'kriging']:
            try:
                result = await validation_service.run_cross_validation(
                    bbox, datetime.utcnow().isoformat(), method
                )
                
                # Store results and check alerts
                store_validation_result(result)
                alerts = alert_service.check_validation_alerts(result['metrics'])
                
                if alerts:
                    send_admin_notifications(alerts, bbox, method)
                    
            except Exception as e:
                logger.error(f"Validation failed for {bbox}, {method}: {e}")
```

### Performance Monitoring
```python
class PerformanceMonitor:
    def monitor_grid_generation(self, bbox: List[float], resolution: float):
        """Monitor heatmap generation performance"""
        start_time = time.time()
        
        # Track key metrics
        metrics = {
            'bbox_area_km2': self.calculate_bbox_area(bbox),
            'grid_cells': self.calculate_grid_cells(bbox, resolution),
            'n_sensors': self.count_sensors_in_bbox(bbox),
            'start_time': start_time
        }
        
        return metrics
    
    def log_completion(self, metrics: dict, success: bool):
        """Log completion metrics for analysis"""
        metrics['duration_seconds'] = time.time() - metrics['start_time']
        metrics['success'] = success
        metrics['timestamp'] = datetime.utcnow().isoformat()
        
        # Store performance metrics for trending
        self.performance_db.insert(metrics)
```

## ✅ ACCEPTANCE CRITERIA

### Monitoring System
- [ ] Spatial cross-validation running automatically
- [ ] Performance metrics tracked and visualized
- [ ] Alert system triggering on quality degradation
- [ ] Admin dashboard showing system health

### Validation Quality
- [ ] RMSE < 8 μg/m³ for urban areas
- [ ] 95% coverage > 85% across validation sites
- [ ] Bias < 5 μg/m³ on average
- [ ] Chi-squared statistic indicating reliable uncertainty

### Operational Controls
- [ ] Manual calibration triggers working
- [ ] Grid rebuild controls functional
- [ ] NASA token validation and rotation procedures documented
- [ ] Performance monitoring providing actionable insights

### Documentation
- [ ] Complete operations manual
- [ ] API documentation with examples
- [ ] Deployment guide for production
- [ ] Sample validation datasets provided

## 🔄 CONTINUOUS IMPROVEMENT

### Automated Quality Assurance
- Daily validation runs with alert notifications
- Weekly calibration performance reviews
- Monthly model retraining and optimization
- Quarterly scientific validation with external datasets

### Monitoring Dashboards
- Real-time system performance metrics
- Historical validation trends
- Calibration drift detection
- NASA API usage and health monitoring

This comprehensive monitoring and validation system ensures the air quality platform maintains scientific accuracy and operational reliability in production deployment.
