from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta, timezone
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session
from decimal import Decimal
import logging

from ..models.harmonized_models import SensorHarmonized, DataQualityLog

logger = logging.getLogger(__name__)

class SensorQualityControlService:
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
    
    def apply_comprehensive_qc(self, sensor_data: Dict) -> Tuple[Dict, List[str]]:
        """Apply all QC rules to sensor data"""
        qc_flags = []
        processed_data = sensor_data.copy()
        
        # Rule 1: Range validation
        qc_flags.extend(self._validate_ranges(processed_data))
        
        # Rule 2: Spike detection
        if sensor_data.get('sensor_id'):
            spike_flags = self._detect_spikes(sensor_data['sensor_id'], processed_data)
            qc_flags.extend(spike_flags)
        
        # Rule 3: Meteorological flagging
        met_flags = self._meteorological_flagging(processed_data)
        qc_flags.extend(met_flags)
        
        # Rule 4: Temporal consistency
        if sensor_data.get('sensor_id'):
            temporal_flags = self._check_temporal_consistency(sensor_data['sensor_id'], processed_data)
            qc_flags.extend(temporal_flags)
        
        # Log QC results
        self._log_qc_results(sensor_data, qc_flags)
        
        return processed_data, qc_flags
    
    def _validate_ranges(self, data: Dict) -> List[str]:
        """Validate measurement ranges and remove invalid values"""
        flags = []
        
        # PM2.5 range validation
        pm25_value = data.get('raw_pm2_5')
        if pm25_value is not None:
            pm25_float = float(pm25_value)
            if pm25_float < 0:
                flags.append('NEGATIVE_PM25')
                data['raw_pm2_5'] = None
            elif pm25_float > 500:
                flags.append('EXTREME_PM25_HIGH')
                # Don't remove, but flag for uncertainty
        
        # PM10 range validation
        pm10_value = data.get('raw_pm10')
        if pm10_value is not None:
            pm10_float = float(pm10_value)
            if pm10_float < 0:
                flags.append('NEGATIVE_PM10')
                data['raw_pm10'] = None
            elif pm10_float > 1000:
                flags.append('EXTREME_PM10_HIGH')
        
        # Temperature range validation
        temp_value = data.get('temperature')
        if temp_value is not None:
            temp_float = float(temp_value)
            if temp_float < -50 or temp_float > 60:
                flags.append('EXTREME_TEMPERATURE')
                data['temperature'] = None
        
        # Humidity range validation
        rh_value = data.get('rh')
        if rh_value is not None:
            rh_float = float(rh_value)
            if rh_float < 0 or rh_float > 100:
                flags.append('INVALID_HUMIDITY')
                data['rh'] = None
        
        return flags
    
    def _detect_spikes(self, sensor_id: str, current_data: Dict) -> List[str]:
        """Detect sudden spikes in sensor readings"""
        flags = []
        
        try:
            # Get recent readings for this sensor
            recent_cutoff = datetime.now(timezone.utc) - timedelta(hours=6)
            
            recent_readings = self.db.query(SensorHarmonized).filter(
                SensorHarmonized.sensor_id == sensor_id,
                SensorHarmonized.timestamp_utc >= recent_cutoff,
                SensorHarmonized.raw_pm2_5.isnot(None)
            ).order_by(SensorHarmonized.timestamp_utc.desc()).limit(10).all()
            
            if len(recent_readings) < 3:
                return flags  # Not enough history for spike detection
            
            # Extract recent PM2.5 values
            recent_values = [float(r.raw_pm2_5) for r in recent_readings]
            current_pm25 = current_data.get('raw_pm2_5')
            
            if current_pm25 is not None:
                current_pm25_float = float(current_pm25)
                
                # Calculate recent statistics
                recent_median = np.median(recent_values)
                recent_mad = np.median(np.abs(np.array(recent_values) - recent_median))
                
                # Spike detection using modified Z-score
                if recent_mad > 0:
                    modified_z_score = 0.6745 * (current_pm25_float - recent_median) / recent_mad
                    
                    if abs(modified_z_score) > 3.5:  # Threshold for spike detection
                        flags.append('SUDDEN_SPIKE')
                        logger.info(f"Spike detected for sensor {sensor_id}: {current_pm25_float} vs median {recent_median}")
                
        except Exception as e:
            logger.warning(f"Spike detection failed for sensor {sensor_id}: {e}")
        
        return flags
    
    def _meteorological_flagging(self, data: Dict) -> List[str]:
        """Apply meteorological-based quality flags"""
        flags = []
        
        # High humidity flag for optical sensors (affects PM measurements)
        rh_value = data.get('rh')
        if rh_value is not None and float(rh_value) > 85:
            flags.append('HIGH_HUMIDITY_UNCERTAINTY')
        
        # Extreme weather conditions
        temp_value = data.get('temperature')
        if temp_value is not None:
            temp_float = float(temp_value)
            if temp_float > 45:
                flags.append('EXTREME_HEAT_CONDITIONS')
            elif temp_float < -20:
                flags.append('EXTREME_COLD_CONDITIONS')
        
        # Check for unrealistic PM2.5/PM10 ratio
        pm25_value = data.get('raw_pm2_5')
        pm10_value = data.get('raw_pm10')
        
        if pm25_value is not None and pm10_value is not None:
            pm25_float = float(pm25_value)
            pm10_float = float(pm10_value)
            
            if pm10_float > 0:
                ratio = pm25_float / pm10_float
                if ratio > 1.2:  # PM2.5 should typically be less than PM10
                    flags.append('INVALID_PM_RATIO')
                elif ratio < 0.1:  # Unusually low ratio
                    flags.append('SUSPICIOUS_PM_RATIO')
        
        return flags
    
    def _check_temporal_consistency(self, sensor_id: str, current_data: Dict) -> List[str]:
        """Check temporal consistency with recent measurements"""
        flags = []
        
        try:
            # Get most recent reading
            last_reading = self.db.query(SensorHarmonized).filter(
                SensorHarmonized.sensor_id == sensor_id
            ).order_by(SensorHarmonized.timestamp_utc.desc()).first()
            
            if not last_reading:
                return flags  # First reading for this sensor
            
            current_timestamp = current_data.get('timestamp_utc')
            if not isinstance(current_timestamp, datetime):
                return flags
            
            # Check time gap
            time_diff = current_timestamp - last_reading.timestamp_utc
            
            if time_diff.total_seconds() < 300:  # Less than 5 minutes
                flags.append('RAPID_UPDATE')
            elif time_diff.total_seconds() > 86400:  # More than 24 hours
                flags.append('STALE_DATA')
            
            # Check for duplicate timestamps
            if abs(time_diff.total_seconds()) < 60:  # Within 1 minute
                flags.append('DUPLICATE_TIMESTAMP')
            
        except Exception as e:
            logger.warning(f"Temporal consistency check failed for sensor {sensor_id}: {e}")
        
        return flags
    
    def _log_qc_results(self, sensor_data: Dict, qc_flags: List[str]) -> None:
        """Log quality control results for monitoring"""
        try:
            for flag in qc_flags:
                qc_log = DataQualityLog(
                    sensor_id=sensor_data.get('sensor_id'),
                    timestamp_utc=sensor_data.get('timestamp_utc'),
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
                    timestamp_utc=sensor_data.get('timestamp_utc'),
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
