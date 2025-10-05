from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score, mean_squared_error
from sklearn.model_selection import LeaveOneOut
import logging

from ..models.harmonized_models import SensorHarmonized, SensorCalibration

logger = logging.getLogger(__name__)

class CalibrationEngineService:
    """Service for sensor calibration model implementation"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
        self.calibration_window_days = 30  # Default calibration window
        self.min_reference_points = 10     # Minimum points for calibration
        self.max_calibration_age_days = 90  # Recalibrate if older than this
    
    def fit_calibration_model(self, sensor_id: str, reference_data: List[Dict]) -> Dict:
        """Fit linear calibration: c_corr = alpha + beta*c_raw + gamma*rh + delta*t"""
        try:
            if len(reference_data) < self.min_reference_points:
                raise ValueError(f"Insufficient reference data: {len(reference_data)} < {self.min_reference_points}")
            
            # Prepare design matrix
            X = []
            y = []
            
            for data_point in reference_data:
                # Design matrix: [1, c_raw, rh, temperature]
                row = [
                    1.0,  # intercept
                    float(data_point.get('raw_pm2_5', 0)),
                    float(data_point.get('rh', 50)),  # Default RH if missing
                    float(data_point.get('temperature', 20))  # Default temp if missing
                ]
                X.append(row)
                y.append(float(data_point['reference_pm2_5']))
            
            X = np.array(X)
            y = np.array(y)
            
            # Fit linear model using least squares
            coeffs, residuals, rank, singular_values = np.linalg.lstsq(X, y, rcond=None)
            
            # Calculate uncertainty (residual standard error)
            degrees_freedom = len(y) - X.shape[1]
            if degrees_freedom > 0 and len(residuals) > 0:
                sigma_i = np.sqrt(residuals[0] / degrees_freedom)
            else:
                # Fallback calculation
                y_pred = X @ coeffs
                sigma_i = np.sqrt(np.mean((y - y_pred) ** 2))
            
            # Calculate R-squared
            y_pred = X @ coeffs
            r2 = r2_score(y, y_pred)
            
            # Calculate validation metrics
            rmse = np.sqrt(mean_squared_error(y, y_pred))
            bias = np.mean(y_pred - y)
            
            calibration_params = {
                'alpha': float(coeffs[0]),  # intercept
                'beta': float(coeffs[1]),   # raw PM2.5 coefficient
                'gamma': float(coeffs[2]),  # humidity coefficient
                'delta': float(coeffs[3]),  # temperature coefficient
                'sigma_i': float(sigma_i),  # uncertainty estimate
                'calibration_r2': float(r2),
                'validation_rmse': float(rmse),
                'validation_bias': float(bias),
                'reference_count': len(reference_data),
                'last_calibrated': datetime.now(timezone.utc),
                'calibration_method': 'linear'
            }
            
            logger.info(f"Calibration fitted for sensor {sensor_id}: "
                       f"R²={r2:.3f}, RMSE={rmse:.2f}, σᵢ={sigma_i:.2f}")
            
            return calibration_params
            
        except Exception as e:
            logger.error(f"Calibration fitting failed for sensor {sensor_id}: {e}")
            raise
    
    def apply_calibration_correction(self, sensor_id: str, raw_data: Dict) -> Dict:
        """Apply calibration correction to raw sensor data"""
        try:
            # Get calibration parameters
            calibration = self.db.query(SensorCalibration).filter(
                SensorCalibration.sensor_id == sensor_id,
                SensorCalibration.is_active == True
            ).first()
            
            corrected_data = raw_data.copy()
            
            if not calibration:
                # No calibration available, use raw values
                corrected_data['pm2_5_corrected'] = raw_data.get('raw_pm2_5')
                corrected_data['calibration_applied'] = False
                corrected_data['sigma_i'] = 10.0  # Default uncertainty
                corrected_data['calibration_status'] = 'no_calibration'
                return corrected_data
            
            # Check if calibration is recent enough
            if calibration.last_calibrated:
                age_days = (datetime.now(timezone.utc) - calibration.last_calibrated).days
                if age_days > self.max_calibration_age_days:
                    logger.warning(f"Calibration for sensor {sensor_id} is {age_days} days old")
            
            # Apply linear calibration
            raw_pm25 = raw_data.get('raw_pm2_5')
            if raw_pm25 is not None:
                rh = raw_data.get('rh', 50)  # Default humidity
                temperature = raw_data.get('temperature', 20)  # Default temperature
                
                # c_corr = alpha + beta*c_raw + gamma*rh + delta*t
                c_corrected = (
                    float(calibration.alpha) +
                    float(calibration.beta) * float(raw_pm25) +
                    float(calibration.gamma) * float(rh) +
                    float(calibration.delta) * float(temperature)
                )
                
                # Ensure corrected value is non-negative
                c_corrected = max(0.0, c_corrected)
                
                corrected_data['pm2_5_corrected'] = round(c_corrected, 2)
                corrected_data['calibration_applied'] = True
                corrected_data['sigma_i'] = float(calibration.sigma_i)
                corrected_data['calibration_r2'] = float(calibration.calibration_r2) if calibration.calibration_r2 else None
                corrected_data['calibration_status'] = 'active'
                corrected_data['last_calibrated'] = calibration.last_calibrated.isoformat() if calibration.last_calibrated else None
            else:
                corrected_data['pm2_5_corrected'] = None
                corrected_data['calibration_applied'] = False
                corrected_data['calibration_status'] = 'no_raw_data'
            
            return corrected_data
            
        except Exception as e:
            logger.error(f"Calibration application failed for sensor {sensor_id}: {e}")
            # Return uncalibrated data with error status
            corrected_data = raw_data.copy()
            corrected_data['pm2_5_corrected'] = raw_data.get('raw_pm2_5')
            corrected_data['calibration_applied'] = False
            corrected_data['calibration_error'] = str(e)
            corrected_data['calibration_status'] = 'error'
            return corrected_data
    
    def store_calibration_parameters(self, sensor_id: str, sensor_type: str, 
                                   calibration_params: Dict) -> bool:
        """Store or update calibration parameters in database"""
        try:
            # Check if calibration exists
            existing_calibration = self.db.query(SensorCalibration).filter(
                SensorCalibration.sensor_id == sensor_id
            ).first()
            
            if existing_calibration:
                # Update existing calibration
                for key, value in calibration_params.items():
                    if hasattr(existing_calibration, key):
                        setattr(existing_calibration, key, value)
                existing_calibration.updated_at = datetime.now(timezone.utc)
                
                logger.info(f"Updated calibration for sensor {sensor_id}")
            else:
                # Create new calibration
                new_calibration = SensorCalibration(
                    sensor_id=sensor_id,
                    sensor_type=sensor_type,
                    **calibration_params
                )
                self.db.add(new_calibration)
                
                logger.info(f"Created new calibration for sensor {sensor_id}")
            
            self.db.commit()
            return True
            
        except Exception as e:
            logger.error(f"Failed to store calibration for sensor {sensor_id}: {e}")
            self.db.rollback()
            return False
    
    def perform_cross_validation(self, sensor_id: str, reference_data: List[Dict]) -> Dict:
        """Perform leave-one-out cross-validation for calibration"""
        try:
            if len(reference_data) < 5:
                return {'error': 'Insufficient data for cross-validation'}
            
            # Prepare data
            X = []
            y = []
            for data_point in reference_data:
                row = [
                    1.0,
                    float(data_point.get('raw_pm2_5', 0)),
                    float(data_point.get('rh', 50)),
                    float(data_point.get('temperature', 20))
                ]
                X.append(row)
                y.append(float(data_point['reference_pm2_5']))
            
            X = np.array(X)
            y = np.array(y)
            
            # Leave-one-out cross-validation
            loo = LeaveOneOut()
            predictions = []
            observations = []
            
            for train_idx, test_idx in loo.split(X):
                X_train, X_test = X[train_idx], X[test_idx]
                y_train, y_test = y[train_idx], y[test_idx]
                
                # Fit model on training data
                coeffs = np.linalg.lstsq(X_train, y_train, rcond=None)[0]
                
                # Predict on test data
                y_pred = X_test @ coeffs
                
                predictions.extend(y_pred)
                observations.extend(y_test)
            
            predictions = np.array(predictions)
            observations = np.array(observations)
            
            # Calculate cross-validation metrics
            cv_rmse = np.sqrt(mean_squared_error(observations, predictions))
            cv_r2 = r2_score(observations, predictions)
            cv_bias = np.mean(predictions - observations)
            cv_mae = np.mean(np.abs(predictions - observations))
            
            return {
                'sensor_id': sensor_id,
                'cv_rmse': float(cv_rmse),
                'cv_r2': float(cv_r2),
                'cv_bias': float(cv_bias),
                'cv_mae': float(cv_mae),
                'n_folds': len(predictions),
                'validation_type': 'leave_one_out'
            }
            
        except Exception as e:
            logger.error(f"Cross-validation failed for sensor {sensor_id}: {e}")
            return {'error': str(e)}
    
    def auto_calibrate_sensors(self, source_filter: Optional[str] = None) -> Dict:
        """Automatically calibrate sensors that need recalibration"""
        try:
            # Find sensors that need calibration
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.max_calibration_age_days)
            
            query = self.db.query(SensorCalibration).filter(
                (SensorCalibration.last_calibrated < cutoff_date) |
                (SensorCalibration.last_calibrated.is_(None))
            )
            
            if source_filter:
                # Filter by source
                sensor_ids = self.db.query(SensorHarmonized.sensor_id).filter(
                    SensorHarmonized.source == source_filter
                ).distinct().all()
                sensor_id_list = [sid[0] for sid in sensor_ids]
                query = query.filter(SensorCalibration.sensor_id.in_(sensor_id_list))
            
            sensors_to_calibrate = query.all()
            
            calibration_results = {
                'sensors_processed': 0,
                'successful_calibrations': 0,
                'failed_calibrations': 0,
                'results': []
            }
            
            for sensor_calibration in sensors_to_calibrate:
                try:
                    # Generate reference data (in production, this would come from co-location studies)
                    reference_data = self._generate_mock_reference_data(sensor_calibration.sensor_id)
                    
                    if len(reference_data) >= self.min_reference_points:
                        # Fit calibration model
                        calibration_params = self.fit_calibration_model(
                            sensor_calibration.sensor_id, 
                            reference_data
                        )
                        
                        # Store calibration parameters
                        success = self.store_calibration_parameters(
                            sensor_calibration.sensor_id,
                            sensor_calibration.sensor_type,
                            calibration_params
                        )
                        
                        if success:
                            # Perform cross-validation
                            cv_results = self.perform_cross_validation(
                                sensor_calibration.sensor_id,
                                reference_data
                            )
                            
                            calibration_results['successful_calibrations'] += 1
                            calibration_results['results'].append({
                                'sensor_id': sensor_calibration.sensor_id,
                                'status': 'success',
                                'calibration': calibration_params,
                                'validation': cv_results
                            })
                        else:
                            calibration_results['failed_calibrations'] += 1
                            calibration_results['results'].append({
                                'sensor_id': sensor_calibration.sensor_id,
                                'status': 'storage_failed'
                            })
                    else:
                        calibration_results['results'].append({
                            'sensor_id': sensor_calibration.sensor_id,
                            'status': 'insufficient_data',
                            'data_points': len(reference_data)
                        })
                        
                except Exception as e:
                    logger.error(f"Auto-calibration failed for sensor {sensor_calibration.sensor_id}: {e}")
                    calibration_results['failed_calibrations'] += 1
                    calibration_results['results'].append({
                        'sensor_id': sensor_calibration.sensor_id,
                        'status': 'error',
                        'error': str(e)
                    })
                
                calibration_results['sensors_processed'] += 1
            
            logger.info(f"Auto-calibration completed: {calibration_results['successful_calibrations']}/{calibration_results['sensors_processed']} successful")
            
            return calibration_results
            
        except Exception as e:
            logger.error(f"Auto-calibration process failed: {e}")
            return {'error': str(e)}
    
    def get_calibration_diagnostics(self, sensor_id: str) -> Dict:
        """Get calibration diagnostics for admin interface"""
        try:
            calibration = self.db.query(SensorCalibration).filter(
                SensorCalibration.sensor_id == sensor_id
            ).first()
            
            if not calibration:
                return {'error': 'No calibration found'}
            
            # Get recent sensor data for analysis
            recent_cutoff = datetime.now(timezone.utc) - timedelta(days=7)
            
            recent_data = self.db.query(SensorHarmonized).filter(
                SensorHarmonized.sensor_id == sensor_id,
                SensorHarmonized.timestamp_utc >= recent_cutoff,
                SensorHarmonized.raw_pm2_5.isnot(None)
            ).all()
            
            # Calculate recent statistics
            if recent_data:
                pm25_values = [float(r.raw_pm2_5) for r in recent_data]
                recent_stats = {
                    'mean_pm25': np.mean(pm25_values),
                    'std_pm25': np.std(pm25_values),
                    'min_pm25': np.min(pm25_values),
                    'max_pm25': np.max(pm25_values),
                    'data_points': len(pm25_values)
                }
            else:
                recent_stats = {'data_points': 0}
            
            # Calculate calibration age
            age_days = None
            if calibration.last_calibrated:
                age_days = (datetime.now(timezone.utc) - calibration.last_calibrated).days
            
            return {
                'sensor_id': sensor_id,
                'calibration_parameters': {
                    'alpha': float(calibration.alpha),
                    'beta': float(calibration.beta),
                    'gamma': float(calibration.gamma),
                    'delta': float(calibration.delta),
                    'sigma_i': float(calibration.sigma_i)
                },
                'performance_metrics': {
                    'r2': float(calibration.calibration_r2) if calibration.calibration_r2 else None,
                    'rmse': float(calibration.validation_rmse) if calibration.validation_rmse else None,
                    'bias': float(calibration.validation_bias) if calibration.validation_bias else None,
                    'reference_count': calibration.reference_count
                },
                'status': {
                    'last_calibrated': calibration.last_calibrated.isoformat() if calibration.last_calibrated else None,
                    'age_days': age_days,
                    'is_active': calibration.is_active,
                    'method': calibration.calibration_method,
                    'needs_recalibration': age_days > self.max_calibration_age_days if age_days else True
                },
                'recent_data_stats': recent_stats
            }
            
        except Exception as e:
            logger.error(f"Error getting calibration diagnostics for {sensor_id}: {e}")
            return {'error': str(e)}
    
    def _generate_mock_reference_data(self, sensor_id: str) -> List[Dict]:
        """Generate mock reference data for calibration (replace with real co-location data)"""
        # In production, this would query co-location data from reference monitors
        # For now, generate synthetic but realistic reference data
        
        recent_cutoff = datetime.now(timezone.utc) - timedelta(days=self.calibration_window_days)
        
        # Get recent sensor data
        sensor_data = self.db.query(SensorHarmonized).filter(
            SensorHarmonized.sensor_id == sensor_id,
            SensorHarmonized.timestamp_utc >= recent_cutoff,
            SensorHarmonized.raw_pm2_5.isnot(None)
        ).limit(50).all()
        
        reference_data = []
        for record in sensor_data:
            raw_pm25 = float(record.raw_pm2_5)
            
            # Simulate reference measurement with realistic bias patterns
            # Low-cost sensors typically read high, especially at high concentrations
            if raw_pm25 > 35:
                bias_factor = 0.75  # High bias at high concentrations
                noise_std = 3.0
            elif raw_pm25 > 15:
                bias_factor = 0.85  # Moderate bias
                noise_std = 2.0
            else:
                bias_factor = 0.95  # Low bias at low concentrations
                noise_std = 1.5
            
            # Add realistic noise and bias
            reference_pm25 = raw_pm25 * bias_factor + np.random.normal(0, noise_std)
            reference_pm25 = max(0, reference_pm25)  # Ensure non-negative
            
            reference_data.append({
                'timestamp': record.timestamp_utc,
                'raw_pm2_5': raw_pm25,
                'reference_pm2_5': reference_pm25,
                'rh': float(record.rh) if record.rh else 50,
                'temperature': float(record.temperature) if record.temperature else 20
            })
        
        return reference_data
    
    def detect_calibration_drift(self, sensor_id: str, days_back: int = 30) -> Dict:
        """Detect if sensor calibration has drifted"""
        try:
            # Get calibration parameters
            calibration = self.db.query(SensorCalibration).filter(
                SensorCalibration.sensor_id == sensor_id
            ).first()
            
            if not calibration:
                return {'error': 'No calibration found'}
            
            # Get recent data
            recent_cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
            recent_data = self.db.query(SensorHarmonized).filter(
                SensorHarmonized.sensor_id == sensor_id,
                SensorHarmonized.timestamp_utc >= recent_cutoff,
                SensorHarmonized.raw_pm2_5.isnot(None)
            ).all()
            
            if len(recent_data) < 10:
                return {'warning': 'Insufficient recent data for drift detection'}
            
            # Apply current calibration
            corrected_values = []
            raw_values = []
            
            for record in recent_data:
                raw_pm25 = float(record.raw_pm2_5)
                rh = float(record.rh) if record.rh else 50
                temp = float(record.temperature) if record.temperature else 20
                
                corrected = (
                    float(calibration.alpha) +
                    float(calibration.beta) * raw_pm25 +
                    float(calibration.gamma) * rh +
                    float(calibration.delta) * temp
                )
                
                corrected_values.append(max(0, corrected))
                raw_values.append(raw_pm25)
            
            # Calculate drift metrics
            correction_factors = np.array(corrected_values) / np.array(raw_values)
            correction_factors = correction_factors[~np.isnan(correction_factors)]
            
            if len(correction_factors) > 0:
                mean_correction = np.mean(correction_factors)
                std_correction = np.std(correction_factors)
                
                # Flag if correction factor is drifting significantly
                drift_detected = (
                    abs(mean_correction - 1.0) > 0.3 or  # Large systematic bias
                    std_correction > 0.2  # High variability in corrections
                )
                
                return {
                    'sensor_id': sensor_id,
                    'drift_detected': drift_detected,
                    'mean_correction_factor': float(mean_correction),
                    'correction_variability': float(std_correction),
                    'data_points_analyzed': len(correction_factors),
                    'recommendation': 'Recalibration recommended' if drift_detected else 'Calibration stable'
                }
            else:
                return {'error': 'No valid correction factors calculated'}
            
        except Exception as e:
            logger.error(f"Drift detection failed for sensor {sensor_id}: {e}")
            return {'error': str(e)}
