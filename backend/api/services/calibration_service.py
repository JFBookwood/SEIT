from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score, mean_squared_error
import logging

from ..models.harmonized_models import SensorHarmonized, SensorCalibration

logger = logging.getLogger(__name__)

class SensorCalibrationService:
    """Service for sensor calibration and validation"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
        self.calibration_window_days = 30  # Default calibration window
        self.min_reference_points = 10     # Minimum points for calibration
    
    def fit_sensor_calibration(self, sensor_id: str, reference_data: List[Dict]) -> Dict:
        """Fit linear calibration model for a sensor"""
        try:
            if len(reference_data) < self.min_reference_points:
                raise ValueError(f"Insufficient reference data: {len(reference_data)} < {self.min_reference_points}")
            
            # Prepare calibration data
            calibration_df = pd.DataFrame(reference_data)
            
            # Validate required columns
            required_columns = ['raw_pm2_5', 'reference_pm2_5']
            for col in required_columns:
                if col not in calibration_df.columns:
                    raise ValueError(f"Missing required column: {col}")
            
            # Remove rows with missing critical data
            calibration_df = calibration_df.dropna(subset=required_columns)
            
            if len(calibration_df) < self.min_reference_points:
                raise ValueError(f"Insufficient valid data after cleaning: {len(calibration_df)}")
            
            # Prepare design matrix: [1, raw_pm2_5, rh, temperature]
            X = self._prepare_design_matrix(calibration_df)
            y = calibration_df['reference_pm2_5'].values
            
            # Fit linear regression
            model = LinearRegression()
            model.fit(X, y)
            
            # Calculate performance metrics
            y_pred = model.predict(X)
            r2 = r2_score(y, y_pred)
            rmse = np.sqrt(mean_squared_error(y, y_pred))
            bias = np.mean(y_pred - y)
            
            # Calculate residual standard error (sigma_i)
            residuals = y - y_pred
            degrees_freedom = len(y) - X.shape[1]
            sigma_i = np.sqrt(np.sum(residuals**2) / degrees_freedom) if degrees_freedom > 0 else rmse
            
            # Extract calibration coefficients
            coefficients = {
                'alpha': float(model.intercept_),  # Intercept
                'beta': float(model.coef_[1]),     # Raw PM2.5 coefficient
                'gamma': float(model.coef_[2]) if X.shape[1] > 2 else 0.0,  # Humidity coefficient
                'delta': float(model.coef_[3]) if X.shape[1] > 3 else 0.0,  # Temperature coefficient
                'sigma_i': float(sigma_i),
                'calibration_r2': float(r2),
                'validation_rmse': float(rmse),
                'validation_bias': float(bias),
                'reference_count': len(calibration_df),
                'last_calibrated': datetime.now(timezone.utc)
            }
            
            logger.info(f"Calibration fitted for sensor {sensor_id}: R²={r2:.3f}, RMSE={rmse:.2f}, σᵢ={sigma_i:.2f}")
            
            return coefficients
            
        except Exception as e:
            logger.error(f"Calibration fitting failed for sensor {sensor_id}: {e}")
            raise
    
    def _prepare_design_matrix(self, df: pd.DataFrame) -> np.ndarray:
        """Prepare design matrix for linear calibration"""
        # Start with intercept column
        X = np.ones((len(df), 1))
        
        # Add raw PM2.5 column
        if 'raw_pm2_5' in df.columns:
            X = np.column_stack([X, df['raw_pm2_5'].values])
        else:
            raise ValueError("Missing raw_pm2_5 column")
        
        # Add humidity column if available
        if 'rh' in df.columns and not df['rh'].isna().all():
            X = np.column_stack([X, df['rh'].fillna(50).values])  # Fill missing with typical value
        else:
            X = np.column_stack([X, np.full(len(df), 50)])  # Default humidity
        
        # Add temperature column if available
        if 'temperature' in df.columns and not df['temperature'].isna().all():
            X = np.column_stack([X, df['temperature'].fillna(20).values])  # Fill missing with typical value
        else:
            X = np.column_stack([X, np.full(len(df), 20)])  # Default temperature
        
        return X
    
    def apply_calibration(self, sensor_id: str, raw_data: Dict) -> Dict:
        """Apply calibration to raw sensor data"""
        try:
            # Get calibration parameters
            calibration = self.db.query(SensorCalibration).filter(
                SensorCalibration.sensor_id == sensor_id,
                SensorCalibration.is_active == True
            ).first()
            
            if not calibration:
                logger.warning(f"No calibration found for sensor {sensor_id}, using default")
                # Use default calibration (no correction)
                calibrated_data = raw_data.copy()
                calibrated_data['pm2_5_corrected'] = raw_data.get('raw_pm2_5')
                calibrated_data['calibration_applied'] = False
                calibrated_data['sigma_i'] = 10.0  # Default uncertainty
                return calibrated_data
            
            # Apply linear calibration: c_corr = alpha + beta*c_raw + gamma*rh + delta*t
            raw_pm25 = raw_data.get('raw_pm2_5')
            rh = raw_data.get('rh', 50)  # Default humidity
            temperature = raw_data.get('temperature', 20)  # Default temperature
            
            if raw_pm25 is None:
                calibrated_data = raw_data.copy()
                calibrated_data['pm2_5_corrected'] = None
                calibrated_data['calibration_applied'] = False
                return calibrated_data
            
            # Calculate corrected value
            c_corrected = (
                float(calibration.alpha) +
                float(calibration.beta) * float(raw_pm25) +
                float(calibration.gamma) * float(rh or 50) +
                float(calibration.delta) * float(temperature or 20)
            )
            
            # Ensure corrected value is non-negative
            c_corrected = max(0.0, c_corrected)
            
            # Prepare calibrated data
            calibrated_data = raw_data.copy()
            calibrated_data['pm2_5_corrected'] = round(c_corrected, 2)
            calibrated_data['calibration_applied'] = True
            calibrated_data['sigma_i'] = float(calibration.sigma_i)
            calibrated_data['calibration_method'] = calibration.calibration_method
            calibrated_data['last_calibrated'] = calibration.last_calibrated
            
            return calibrated_data
            
        except Exception as e:
            logger.error(f"Calibration application failed for sensor {sensor_id}: {e}")
            # Return uncalibrated data with error flag
            calibrated_data = raw_data.copy()
            calibrated_data['pm2_5_corrected'] = raw_data.get('raw_pm2_5')
            calibrated_data['calibration_applied'] = False
            calibrated_data['calibration_error'] = str(e)
            return calibrated_data
    
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
    
    def get_calibration_diagnostics(self, sensor_id: str) -> Dict:
        """Get calibration diagnostics for a sensor"""
        try:
            calibration = self.db.query(SensorCalibration).filter(
                SensorCalibration.sensor_id == sensor_id
            ).first()
            
            if not calibration:
                return {'error': 'No calibration found'}
            
            # Get recent QC performance
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
            
            return {
                'sensor_id': sensor_id,
                'calibration_parameters': {
                    'alpha': float(calibration.alpha),
                    'beta': float(calibration.beta),
                    'gamma': float(calibration.gamma),
                    'delta': float(calibration.delta),
                    'sigma_i': float(calibration.sigma_i)
                },
                'performance': {
                    'r2': float(calibration.calibration_r2) if calibration.calibration_r2 else None,
                    'rmse': float(calibration.validation_rmse) if calibration.validation_rmse else None,
                    'bias': float(calibration.validation_bias) if calibration.validation_bias else None,
                    'reference_count': calibration.reference_count
                },
                'status': {
                    'last_calibrated': calibration.last_calibrated.isoformat() if calibration.last_calibrated else None,
                    'is_active': calibration.is_active,
                    'method': calibration.calibration_method
                },
                'recent_data': recent_stats
            }
            
        except Exception as e:
            logger.error(f"Error getting calibration diagnostics for {sensor_id}: {e}")
            return {'error': str(e)}
    
    def validate_calibration_performance(self, sensor_id: str) -> Dict:
        """Validate calibration performance using recent data"""
        try:
            calibration = self.db.query(SensorCalibration).filter(
                SensorCalibration.sensor_id == sensor_id
            ).first()
            
            if not calibration:
                return {'error': 'No calibration found'}
            
            # Get recent sensor data
            recent_cutoff = datetime.now(timezone.utc) - timedelta(days=7)
            
            recent_data = self.db.query(SensorHarmonized).filter(
                SensorHarmonized.sensor_id == sensor_id,
                SensorHarmonized.timestamp_utc >= recent_cutoff,
                SensorHarmonized.raw_pm2_5.isnot(None)
            ).all()
            
            if len(recent_data) < 5:
                return {'warning': 'Insufficient recent data for validation'}
            
            # Apply current calibration to recent data
            validation_results = []
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
                
                validation_results.append({
                    'timestamp': record.timestamp_utc,
                    'raw_pm25': raw_pm25,
                    'corrected_pm25': max(0.0, corrected),
                    'rh': rh,
                    'temperature': temp
                })
            
            # Calculate validation statistics
            corrected_values = [r['corrected_pm25'] for r in validation_results]
            raw_values = [r['raw_pm25'] for r in validation_results]
            
            stats = {
                'sensor_id': sensor_id,
                'validation_period': {
                    'start': recent_cutoff.isoformat(),
                    'end': datetime.now(timezone.utc).isoformat(),
                    'data_points': len(validation_results)
                },
                'correction_stats': {
                    'mean_raw': float(np.mean(raw_values)),
                    'mean_corrected': float(np.mean(corrected_values)),
                    'correction_factor': float(np.mean(corrected_values) / np.mean(raw_values)) if np.mean(raw_values) > 0 else 1.0,
                    'std_raw': float(np.std(raw_values)),
                    'std_corrected': float(np.std(corrected_values))
                },
                'calibration_info': {
                    'alpha': float(calibration.alpha),
                    'beta': float(calibration.beta),
                    'gamma': float(calibration.gamma),
                    'delta': float(calibration.delta),
                    'sigma_i': float(calibration.sigma_i),
                    'last_calibrated': calibration.last_calibrated.isoformat() if calibration.last_calibrated else None
                }
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Calibration validation failed for sensor {sensor_id}: {e}")
            return {'error': str(e)}
    
    def auto_calibrate_sensors(self, source_filter: Optional[str] = None) -> Dict:
        """Automatically calibrate sensors that need recalibration"""
        try:
            # Find sensors that need recalibration
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.calibration_window_days)
            
            query = self.db.query(SensorCalibration).filter(
                (SensorCalibration.last_calibrated < cutoff_date) |
                (SensorCalibration.last_calibrated.is_(None))
            )
            
            if source_filter:
                # Get sensors from specific source
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
                    # Get reference data for this sensor (mock for now - would come from co-location studies)
                    reference_data = self._generate_mock_reference_data(sensor_calibration.sensor_id)
                    
                    if len(reference_data) >= self.min_reference_points:
                        # Fit new calibration
                        new_params = self.fit_sensor_calibration(sensor_calibration.sensor_id, reference_data)
                        
                        # Update calibration parameters
                        success = self.store_calibration_parameters(
                            sensor_calibration.sensor_id,
                            sensor_calibration.sensor_type,
                            new_params
                        )
                        
                        if success:
                            calibration_results['successful_calibrations'] += 1
                            calibration_results['results'].append({
                                'sensor_id': sensor_calibration.sensor_id,
                                'status': 'success',
                                'r2': new_params.get('calibration_r2'),
                                'rmse': new_params.get('validation_rmse'),
                                'sigma_i': new_params.get('sigma_i')
                            })
                        else:
                            calibration_results['failed_calibrations'] += 1
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
    
    def _generate_mock_reference_data(self, sensor_id: str) -> List[Dict]:
        """Generate mock reference data for calibration (replace with real co-location data)"""
        # In production, this would fetch co-location data from reference monitors
        # For now, generate synthetic but realistic reference data
        
        recent_cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        
        # Get recent sensor data
        sensor_data = self.db.query(SensorHarmonized).filter(
            SensorHarmonized.sensor_id == sensor_id,
            SensorHarmonized.timestamp_utc >= recent_cutoff,
            SensorHarmonized.raw_pm2_5.isnot(None)
        ).limit(50).all()
        
        reference_data = []
        for record in sensor_data:
            raw_pm25 = float(record.raw_pm2_5)
            
            # Simulate reference measurement with realistic bias and noise
            # Typical low-cost sensor bias patterns
            reference_pm25 = raw_pm25 * 0.85 + 2.0 + np.random.normal(0, 3.0)
            reference_pm25 = max(0, reference_pm25)  # Ensure non-negative
            
            reference_data.append({
                'timestamp': record.timestamp_utc,
                'raw_pm2_5': raw_pm25,
                'reference_pm2_5': reference_pm25,
                'rh': float(record.rh) if record.rh else 50,
                'temperature': float(record.temperature) if record.temperature else 20
            })
        
        return reference_data
    
    def store_calibration_parameters(self, sensor_id: str, sensor_type: str, 
                                   calibration_params: Dict) -> bool:
        """Store calibration parameters (reusing from quality_control_service.py)"""
        try:
            existing_calibration = self.db.query(SensorCalibration).filter(
                SensorCalibration.sensor_id == sensor_id
            ).first()
            
            if existing_calibration:
                # Update existing
                for key, value in calibration_params.items():
                    if hasattr(existing_calibration, key):
                        setattr(existing_calibration, key, value)
                existing_calibration.updated_at = datetime.now(timezone.utc)
            else:
                # Create new
                new_calibration = SensorCalibration(
                    sensor_id=sensor_id,
                    sensor_type=sensor_type,
                    **calibration_params
                )
                self.db.add(new_calibration)
            
            self.db.commit()
            return True
            
        except Exception as e:
            logger.error(f"Failed to store calibration for {sensor_id}: {e}")
            self.db.rollback()
            return False
