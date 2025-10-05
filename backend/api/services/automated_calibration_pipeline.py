import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session

from .calibration_engine_service import CalibrationEngineService
from .sensor_qc_service import SensorQCService
from .data_harmonization_service import DataHarmonizationService
from ..models.harmonized_models import SensorHarmonized, SensorCalibration
from ..database import get_db

logger = logging.getLogger(__name__)

class AutomatedCalibrationPipeline:
    """Automated pipeline for sensor calibration and quality control"""
    
    def __init__(self):
        self.pipeline_stats = {
            'total_sensors_processed': 0,
            'successful_calibrations': 0,
            'qc_flags_applied': 0,
            'harmonization_successes': 0,
            'pipeline_errors': []
        }
    
    async def run_daily_calibration_update(self, db: Session) -> Dict[str, Any]:
        """Run daily calibration updates for all sensors"""
        logger.info("Starting daily calibration update pipeline")
        
        try:
            calibration_service = CalibrationEngineService(db)
            
            # Get sensors that need recalibration
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=30)
            
            sensors_needing_calibration = db.query(SensorCalibration).filter(
                (SensorCalibration.last_calibrated < cutoff_date) |
                (SensorCalibration.last_calibrated.is_(None))
            ).all()
            
            pipeline_results = {
                'pipeline_start': datetime.now(timezone.utc).isoformat(),
                'sensors_identified': len(sensors_needing_calibration),
                'calibration_results': [],
                'summary': {}
            }
            
            # Process sensors in batches to avoid overwhelming the system
            batch_size = 10
            for i in range(0, len(sensors_needing_calibration), batch_size):
                batch = sensors_needing_calibration[i:i + batch_size]
                
                # Process batch
                batch_results = await self._process_calibration_batch(batch, calibration_service)
                pipeline_results['calibration_results'].extend(batch_results)
                
                # Add small delay between batches
                await asyncio.sleep(2)
            
            # Calculate summary statistics
            successful = len([r for r in pipeline_results['calibration_results'] if r.get('status') == 'success'])
            failed = len([r for r in pipeline_results['calibration_results'] if r.get('status') == 'failed'])
            
            pipeline_results['summary'] = {
                'total_processed': len(sensors_needing_calibration),
                'successful_calibrations': successful,
                'failed_calibrations': failed,
                'success_rate': successful / len(sensors_needing_calibration) if sensors_needing_calibration else 0,
                'pipeline_duration_minutes': (datetime.now(timezone.utc) - 
                                            datetime.fromisoformat(pipeline_results['pipeline_start'])).total_seconds() / 60
            }
            
            logger.info(f"Daily calibration update completed: {successful}/{len(sensors_needing_calibration)} successful")
            
            return pipeline_results
            
        except Exception as e:
            logger.error(f"Daily calibration pipeline failed: {e}")
            return {'error': str(e)}
    
    async def _process_calibration_batch(self, sensors: List, calibration_service: CalibrationEngineService) -> List[Dict]:
        """Process a batch of sensors for calibration"""
        batch_results = []
        
        for sensor in sensors:
            try:
                # Generate reference data (in production, query co-location database)
                reference_data = calibration_service._generate_mock_reference_data(sensor.sensor_id)
                
                if len(reference_data) >= calibration_service.min_reference_points:
                    # Fit calibration
                    calibration_params = calibration_service.fit_calibration_model(
                        sensor.sensor_id, reference_data
                    )
                    
                    # Store parameters
                    success = calibration_service.store_calibration_parameters(
                        sensor.sensor_id, sensor.sensor_type, calibration_params
                    )
                    
                    if success:
                        batch_results.append({
                            'sensor_id': sensor.sensor_id,
                            'status': 'success',
                            'r2': calibration_params.get('calibration_r2'),
                            'sigma_i': calibration_params.get('sigma_i'),
                            'reference_points': len(reference_data)
                        })
                        self.pipeline_stats['successful_calibrations'] += 1
                    else:
                        batch_results.append({
                            'sensor_id': sensor.sensor_id,
                            'status': 'failed',
                            'error': 'Failed to store calibration parameters'
                        })
                else:
                    batch_results.append({
                        'sensor_id': sensor.sensor_id,
                        'status': 'insufficient_data',
                        'data_points': len(reference_data),
                        'required_points': calibration_service.min_reference_points
                    })
                
                self.pipeline_stats['total_sensors_processed'] += 1
                
            except Exception as e:
                logger.error(f"Calibration failed for sensor {sensor.sensor_id}: {e}")
                batch_results.append({
                    'sensor_id': sensor.sensor_id,
                    'status': 'error',
                    'error': str(e)
                })
                self.pipeline_stats['pipeline_errors'].append(str(e))
        
        return batch_results
    
    async def run_qc_validation_sweep(self, db: Session, hours_back: int = 24) -> Dict[str, Any]:
        """Run quality control validation on recent sensor data"""
        logger.info(f"Starting QC validation sweep for last {hours_back} hours")
        
        try:
            qc_service = SensorQCService(db)
            harmonization_service = DataHarmonizationService()
            
            # Get recent sensor data that needs QC validation
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_back)
            
            recent_sensors = db.query(SensorHarmonized).filter(
                SensorHarmonized.created_at >= cutoff_time,
                SensorHarmonized.raw_pm2_5.isnot(None)
            ).all()
            
            qc_results = {
                'validation_start': datetime.now(timezone.utc).isoformat(),
                'sensors_processed': 0,
                'qc_flags_applied': 0,
                'sensors_with_issues': 0,
                'flag_summary': {},
                'processing_errors': []
            }
            
            # Process each sensor record
            for sensor_record in recent_sensors:
                try:
                    # Convert to dict format for QC processing
                    sensor_data = {
                        'sensor_id': sensor_record.sensor_id,
                        'raw_pm2_5': float(sensor_record.raw_pm2_5) if sensor_record.raw_pm2_5 else None,
                        'raw_pm10': float(sensor_record.raw_pm10) if sensor_record.raw_pm10 else None,
                        'temperature': float(sensor_record.temperature) if sensor_record.temperature else None,
                        'rh': float(sensor_record.rh) if sensor_record.rh else None,
                        'pressure': float(sensor_record.pressure) if sensor_record.pressure else None,
                        'timestamp_utc': sensor_record.timestamp_utc,
                        'source': sensor_record.source
                    }
                    
                    # Apply QC rules
                    processed_data = qc_service.apply_qc_rules(sensor_data)
                    
                    # Count flags
                    flags = processed_data.get('qc_flags', [])
                    qc_results['qc_flags_applied'] += len(flags)
                    
                    if flags:
                        qc_results['sensors_with_issues'] += 1
                        
                        # Count flag types
                        for flag in flags:
                            qc_results['flag_summary'][flag] = qc_results['flag_summary'].get(flag, 0) + 1
                    
                    qc_results['sensors_processed'] += 1
                    
                except Exception as e:
                    qc_results['processing_errors'].append(f"Sensor {sensor_record.sensor_id}: {str(e)}")
                    continue
            
            # Update pipeline stats
            self.pipeline_stats['qc_flags_applied'] += qc_results['qc_flags_applied']
            
            # Calculate completion metrics
            qc_results['summary'] = {
                'total_sensors': len(recent_sensors),
                'processed_sensors': qc_results['sensors_processed'],
                'sensors_with_issues': qc_results['sensors_with_issues'],
                'issue_rate': qc_results['sensors_with_issues'] / qc_results['sensors_processed'] if qc_results['sensors_processed'] > 0 else 0,
                'most_common_flags': sorted(qc_results['flag_summary'].items(), key=lambda x: x[1], reverse=True)[:5]
            }
            
            logger.info(f"QC validation sweep completed: {qc_results['sensors_processed']} sensors processed, {qc_results['qc_flags_applied']} flags applied")
            
            return qc_results
            
        except Exception as e:
            logger.error(f"QC validation sweep failed: {e}")
            return {'error': str(e)}
    
    def get_pipeline_statistics(self) -> Dict[str, Any]:
        """Get comprehensive pipeline statistics"""
        return {
            'pipeline_stats': self.pipeline_stats.copy(),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
    
    def reset_pipeline_statistics(self):
        """Reset pipeline statistics counters"""
        self.pipeline_stats = {
            'total_sensors_processed': 0,
            'successful_calibrations': 0,
            'qc_flags_applied': 0,
            'harmonization_successes': 0,
            'pipeline_errors': []
        }
        logger.info("Pipeline statistics reset")

# Singleton instance
automated_pipeline = AutomatedCalibrationPipeline()
