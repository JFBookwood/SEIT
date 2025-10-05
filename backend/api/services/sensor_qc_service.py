from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timezone, timedelta
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session
from decimal import Decimal
import logging

from ..models.harmonized_models import SensorHarmonized, DataQualityLog

logger = logging.getLogger(__name__)

class SensorQCService:
    """Service for applying comprehensive quality control to sensor data"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
        self.qc_rules = {
            'range_validation': True,
            'spike_detection': True,
            'temporal_consistency': True,
            'spatial_coherence': True,
            'meteorological_flagging': True
        }
        
        # QC thresholds
        self.qc_thresholds = {
            'pm25_max': 500.0,  # μg/m³
            'pm10_max': 1000.0,  # μg/m³
            'temperature_min': -50.0,  # °C
            'temperature_max': 60.0,   # °C
            'humidity_min': 0.0,    # %
            'humidity_max': 100.0,  # %
            'pressure_min': 800.0,  # hPa
            'pressure_max': 1200.0, # hPa
            'spike_threshold': 3.5,  # Modified Z-score threshold
            'high_humidity_threshold': 85.0  # % RH
        }
    
    def apply_qc_rules(self, sensor_data: Dict) -> Dict:
        """Apply comprehensive QC rules to sensor data"""
        qc_flags = []
        processed_data = sensor_data.copy()
        
        # Rule 1: Remove negative values
        if processed_data.get('raw_pm2_5', 0) is not None:
            pm25_value = float(processed_data['raw_pm2_5'])
            if pm25_value < 0:
                qc_flags.append('NEGATIVE_PM25')
                processed_data['raw_pm2_5'] = None
                logger.debug(f"Removed negative PM2.5 value: {pm25_value}")
        
        if processed_data.get('raw_pm10', 0) is not None:
            pm10_value = float(processed_data['raw_pm10'])
            if pm10_value < 0:
                qc_flags.append('NEGATIVE_PM10')
                processed_data['raw_pm10'] = None
                logger.debug(f"Removed negative PM10 value: {pm10_value}")
        
        # Rule 2: Flag extreme values
        if processed_data.get('raw_pm2_5') is not None:
            pm25_value = float(processed_data['raw_pm2_5'])
            if pm25_value > self.qc_thresholds['pm25_max']:
                qc_flags.append('EXTREME_PM25')
                logger.warning(f"Extreme PM2.5 value flagged: {pm25_value}")
        
        # Rule 3: High humidity uncertainty flag
        if processed_data.get('rh') is not None:
            rh_value = float(processed_data['rh'])
            if rh_value > self.qc_thresholds['high_humidity_threshold']:
                qc_flags.append('HIGH_HUMIDITY_UNCERTAINTY')
                logger.debug(f"High humidity uncertainty flagged: {rh_value}%")
        
        # Rule 4: Spike detection
        if processed_data.get('sensor_id') and processed_data.get('raw_pm2_5'):
            if self.detect_sudden_spike(processed_data):
                qc_flags.append('SUDDEN_SPIKE')
                logger.info(f"Sudden spike detected for sensor {processed_data['sensor_id']}")
        
        # Rule 5: Temperature range validation
        if processed_data.get('temperature') is not None:
            temp_value = float(processed_data['temperature'])
            if temp_value < self.qc_thresholds['temperature_min'] or temp_value > self.qc_thresholds['temperature_max']:
                qc_flags.append('EXTREME_TEMPERATURE')
                processed_data['temperature'] = None
                logger.debug(f"Removed extreme temperature: {temp_value}")
        
        # Rule 6: Humidity range validation
        if processed_data.get('rh') is not None:
            rh_value = float(processed_data['rh'])
            if rh_value < self.qc_thresholds['humidity_min'] or rh_value > self.qc_thresholds['humidity_max']:
                qc_flags.append('INVALID_HUMIDITY')
                processed_data['rh'] = None
                logger.debug(f"Removed invalid humidity: {rh_value}")
        
        # Rule 7: Pressure range validation
        if processed_data.get('pressure') is not None:
            pressure_value = float(processed_data['pressure'])
            if pressure_value < self.qc_thresholds['pressure_min'] or pressure_value > self.qc_thresholds['pressure_max']:
                qc_flags.append('INVALID_PRESSURE')
                processed_data['pressure'] = None
                logger.debug(f"Removed invalid pressure: {pressure_value}")
        
        # Rule 8: PM2.5/PM10 ratio validation
        if (processed_data.get('raw_pm2_5') is not None and 
            processed_data.get('raw_pm10') is not None):
            pm25 = float(processed_data['raw_pm2_5'])
            pm10 = float(processed_data['raw_pm10'])
            if pm10 > 0:
                ratio = pm25 / pm10
                if ratio > 1.2:  # PM2.5 should be subset of PM10
                    qc_flags.append('INVALID_PM_RATIO')
                    logger.warning(f"Invalid PM2.5/PM10 ratio: {ratio:.2f}")
        
        processed_data['qc_flags'] = qc_flags
        
        # Log QC results
        self._log_qc_results(processed_data, qc_flags)
        
        return processed_data
    
    def detect_sudden_spike(self, sensor_data: Dict) -> bool:
        """Detect sudden spikes in PM2.5 readings"""
        try:
            sensor_id = sensor_data['sensor_id']
            current_pm25 = float(sensor_data['raw_pm2_5'])
            
            # Get recent readings for this sensor (last 6 hours)
            recent_cutoff = datetime.now(timezone.utc) - timedelta(hours=6)
            
            recent_readings = self.db.query(SensorHarmonized).filter(
                SensorHarmonized.sensor_id == sensor_id,
                SensorHarmonized.timestamp_utc >= recent_cutoff,
                SensorHarmonized.raw_pm2_5.isnot(None)
            ).order_by(SensorHarmonized.timestamp_utc.desc()).limit(10).all()
            
            if len(recent_readings) < 3:
                return False  # Not enough history
            
            # Extract PM2.5 values
            recent_values = [float(r.raw_pm2_5) for r in recent_readings]
            
            # Calculate median and MAD (Median Absolute Deviation)
            recent_median = np.median(recent_values)
            recent_mad = np.median(np.abs(np.array(recent_values) - recent_median))
            
            if recent_mad > 0:
                # Modified Z-score for spike detection
                modified_z_score = 0.6745 * (current_pm25 - recent_median) / recent_mad
                
                if abs(modified_z_score) > self.qc_thresholds['spike_threshold']:
                    logger.info(f"Spike detected: sensor {sensor_id}, value {current_pm25}, z-score {modified_z_score:.2f}")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Spike detection failed for sensor {sensor_data.get('sensor_id')}: {e}")
            return False
    
    def _log_qc_results(self, sensor_data: Dict, qc_flags: List[str]) -> None:
        """Log quality control results for monitoring"""
        try:
            for flag in qc_flags:
                qc_log = DataQualityLog(
                    sensor_id=sensor_data.get('sensor_id'),
                    timestamp_utc=sensor_data.get('timestamp_utc', datetime.now(timezone.utc)),
                    qc_rule=flag,
                    rule_result='flag',
                    original_value=sensor_data.get('raw_pm2_5'),
                    flag_reason=f"QC rule triggered: {flag}"
                )
                self.db.add(qc_log)
            
            # Log successful QC if no flags
            if not qc_flags:
                qc_log = DataQualityLog(
                    sensor_id=sensor_data.get('sensor_id'),
                    timestamp_utc=sensor_data.get('timestamp_utc', datetime.now(timezone.utc)),
                    qc_rule='COMPREHENSIVE_QC',
                    rule_result='pass',
                    original_value=sensor_data.get('raw_pm2_5')
                )
                self.db.add(qc_log)
            
            self.db.commit()
            
        except Exception as e:
            logger.error(f"Failed to log QC results: {e}")
            self.db.rollback()
    
    def get_qc_summary(self, sensor_id: Optional[str] = None, hours_back: int = 24) -> Dict:
        """Get QC summary statistics"""
        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_back)
            
            query = self.db.query(DataQualityLog).filter(
                DataQualityLog.created_at >= cutoff_time
            )
            
            if sensor_id:
                query = query.filter(DataQualityLog.sensor_id == sensor_id)
            
            qc_logs = query.all()
            
            # Calculate statistics
            total_records = len(qc_logs)
            passed_records = len([log for log in qc_logs if log.rule_result == 'pass'])
            flagged_records = len([log for log in qc_logs if log.rule_result == 'flag'])
            
            # Count flag types
            flag_counts = {}
            for log in qc_logs:
                if log.rule_result == 'flag':
                    flag_counts[log.qc_rule] = flag_counts.get(log.qc_rule, 0) + 1
            
            return {
                'time_range_hours': hours_back,
                'total_records': total_records,
                'passed_records': passed_records,
                'flagged_records': flagged_records,
                'pass_rate': passed_records / total_records if total_records > 0 else 0,
                'flag_breakdown': flag_counts,
                'sensor_id': sensor_id
            }
            
        except Exception as e:
            logger.error(f"Error generating QC summary: {e}")
            return {'error': str(e)}
