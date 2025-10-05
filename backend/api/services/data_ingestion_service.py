from typing import Dict, List, Optional, Any
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session

from .harmonization_service import DataHarmonizationService
from .quality_control_service import SensorQualityControlService
from .calibration_service import SensorCalibrationService
from .purpleair_service import PurpleAirService
from .sensor_community_service import SensorCommunityService
from .openaq_service import OpenAQService
from ..models.harmonized_models import SensorHarmonized
from ..database import get_db

logger = logging.getLogger(__name__)

class DataIngestionService:
    """Centralized service for ingesting and processing sensor data from multiple sources"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
        self.harmonization_service = DataHarmonizationService()
        self.qc_service = SensorQualityControlService(db_session)
        self.calibration_service = SensorCalibrationService(db_session)
        
        # External service clients
        self.purpleair_service = PurpleAirService()
        self.sensor_community_service = SensorCommunityService()
        self.openaq_service = OpenAQService()
        
        self.ingestion_stats = {
            'total_fetched': 0,
            'total_harmonized': 0,
            'total_stored': 0,
            'qc_flags_applied': 0,
            'calibrations_applied': 0,
            'errors': []
        }
    
    async def ingest_all_sources(self, bbox: Optional[str] = None, 
                               sources: List[str] = None) -> Dict:
        """Ingest data from all enabled sources"""
        if sources is None:
            sources = ['purpleair', 'sensor_community', 'openaq']
        
        ingestion_results = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'bbox': bbox,
            'sources_processed': [],
            'total_sensors_ingested': 0,
            'processing_summary': {}
        }
        
        # Process each source
        for source in sources:
            try:
                logger.info(f"Starting ingestion for source: {source}")
                result = await self._ingest_single_source(source, bbox)
                
                ingestion_results['sources_processed'].append(source)
                ingestion_results['total_sensors_ingested'] += result.get('sensors_stored', 0)
                ingestion_results['processing_summary'][source] = result
                
            except Exception as e:
                logger.error(f"Ingestion failed for source {source}: {e}")
                ingestion_results['processing_summary'][source] = {'error': str(e)}
                self.ingestion_stats['errors'].append(f"{source}: {str(e)}")
        
        # Update global stats
        ingestion_results['global_stats'] = self.ingestion_stats.copy()
        
        logger.info(f"Ingestion completed. Total sensors: {ingestion_results['total_sensors_ingested']}")
        
        return ingestion_results
    
    async def _ingest_single_source(self, source: str, bbox: Optional[str] = None) -> Dict:
        """Ingest data from a single source with full processing pipeline"""
        source_result = {
            'source': source,
            'raw_data_fetched': 0,
            'harmonized_records': 0,
            'qc_processed': 0,
            'calibrations_applied': 0,
            'sensors_stored': 0,
            'processing_errors': []
        }
        
        try:
            # Step 1: Fetch raw data from external API
            raw_data = await self._fetch_raw_data(source, bbox)
            source_result['raw_data_fetched'] = len(raw_data)
            self.ingestion_stats['total_fetched'] += len(raw_data)
            
            if not raw_data:
                source_result['processing_errors'].append('No data returned from API')
                return source_result
            
            # Step 2: Harmonize data to canonical schema
            harmonized_data = self.harmonization_service.harmonize_sensor_batch(raw_data, source)
            source_result['harmonized_records'] = len(harmonized_data)
            self.ingestion_stats['total_harmonized'] += len(harmonized_data)
            
            # Step 3: Apply quality control and calibration
            processed_sensors = []
            for harmonized_record in harmonized_data:
                try:
                    # Apply QC rules
                    qc_processed_data, qc_flags = self.qc_service.apply_comprehensive_qc(harmonized_record)
                    source_result['qc_processed'] += 1
                    self.ingestion_stats['qc_flags_applied'] += len(qc_flags)
                    
                    # Apply calibration
                    calibrated_data = self.calibration_service.apply_calibration(
                        qc_processed_data['sensor_id'], 
                        qc_processed_data
                    )
                    
                    if calibrated_data.get('calibration_applied'):
                        source_result['calibrations_applied'] += 1
                        self.ingestion_stats['calibrations_applied'] += 1
                    
                    processed_sensors.append(calibrated_data)
                    
                except Exception as e:
                    source_result['processing_errors'].append(f"Processing error: {str(e)}")
                    continue
            
            # Step 4: Store in database
            stored_count = self._store_harmonized_sensors(processed_sensors)
            source_result['sensors_stored'] = stored_count
            self.ingestion_stats['total_stored'] += stored_count
            
            logger.info(f"Source {source} ingestion completed: {stored_count} sensors stored")
            
        except Exception as e:
            logger.error(f"Source ingestion failed for {source}: {e}")
            source_result['processing_errors'].append(str(e))
        
        return source_result
    
    async def _fetch_raw_data(self, source: str, bbox: Optional[str] = None) -> List[Dict]:
        """Fetch raw data from external APIs"""
        try:
            if source == 'purpleair':
                return await self.purpleair_service.get_sensors(bbox, 100)
            elif source == 'sensor_community':
                return await self.sensor_community_service.get_current_data(bbox)
            elif source == 'openaq':
                return await self.openaq_service.get_latest_measurements(bbox, 100)
            else:
                logger.warning(f"Unknown source: {source}")
                return []
                
        except Exception as e:
            logger.error(f"Failed to fetch data from {source}: {e}")
            return []
    
    def _store_harmonized_sensors(self, processed_sensors: List[Dict]) -> int:
        """Store harmonized and processed sensor data in database"""
        stored_count = 0
        
        try:
            for sensor_data in processed_sensors:
                try:
                    # Check if record already exists (avoid duplicates)
                    existing = self.db.query(SensorHarmonized).filter(
                        SensorHarmonized.sensor_id == sensor_data['sensor_id'],
                        SensorHarmonized.timestamp_utc == sensor_data['timestamp_utc']
                    ).first()
                    
                    if existing:
                        # Update existing record
                        for key, value in sensor_data.items():
                            if hasattr(existing, key) and key not in ['id', 'created_at']:
                                setattr(existing, key, value)
                        existing.updated_at = datetime.now(timezone.utc)
                    else:
                        # Create new record
                        harmonized_sensor = SensorHarmonized(**sensor_data)
                        self.db.add(harmonized_sensor)
                    
                    stored_count += 1
                    
                except Exception as e:
                    logger.warning(f"Failed to store sensor {sensor_data.get('sensor_id')}: {e}")
                    continue
            
            self.db.commit()
            logger.info(f"Successfully stored {stored_count} harmonized sensor records")
            
        except Exception as e:
            logger.error(f"Database storage failed: {e}")
            self.db.rollback()
            stored_count = 0
        
        return stored_count
    
    def _generate_mock_reference_data(self, sensor_id: str) -> List[Dict]:
        """Generate mock reference data for calibration (temporary)"""
        # In production, this would query co-location reference monitor data
        # For now, generate realistic synthetic reference data
        
        recent_cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        
        # Get recent sensor readings
        sensor_readings = self.db.query(SensorHarmonized).filter(
            SensorHarmonized.sensor_id == sensor_id,
            SensorHarmonized.timestamp_utc >= recent_cutoff,
            SensorHarmonized.raw_pm2_5.isnot(None)
        ).limit(20).all()
        
        reference_data = []
        for reading in sensor_readings:
            if reading.raw_pm2_5:
                raw_pm25 = float(reading.raw_pm2_5)
                
                # Simulate reference monitor with typical low-cost sensor biases
                # Low-cost sensors typically read high, especially at high concentrations
                if raw_pm25 > 35:
                    bias_factor = 0.75  # High bias at high concentrations
                elif raw_pm25 > 15:
                    bias_factor = 0.85  # Moderate bias at moderate concentrations
                else:
                    bias_factor = 0.95  # Low bias at low concentrations
                
                reference_pm25 = raw_pm25 * bias_factor + np.random.normal(0, 2.0)
                reference_pm25 = max(0, reference_pm25)
                
                reference_data.append({
                    'timestamp': reading.timestamp_utc,
                    'raw_pm2_5': raw_pm25,
                    'reference_pm2_5': reference_pm25,
                    'rh': float(reading.rh) if reading.rh else 50,
                    'temperature': float(reading.temperature) if reading.temperature else 20
                })
        
        return reference_data
    
    def get_ingestion_summary(self, hours_back: int = 24) -> Dict:
        """Get summary of recent ingestion activity"""
        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_back)
            
            # Count recent records by source
            recent_counts = self.db.query(
                SensorHarmonized.source,
                self.db.func.count(SensorHarmonized.id).label('count')
            ).filter(
                SensorHarmonized.created_at >= cutoff_time
            ).group_by(SensorHarmonized.source).all()
            
            source_counts = {source: count for source, count in recent_counts}
            
            # Get QC flag summary
            qc_summary = self.qc_service.get_qc_summary(hours_back=hours_back)
            
            # Get harmonization stats
            harmonization_stats = self.harmonization_service.get_harmonization_stats()
            
            return {
                'time_range_hours': hours_back,
                'sensors_by_source': source_counts,
                'total_sensors': sum(source_counts.values()),
                'qc_summary': qc_summary,
                'harmonization_stats': harmonization_stats,
                'global_ingestion_stats': self.ingestion_stats.copy()
            }
            
        except Exception as e:
            logger.error(f"Error generating ingestion summary: {e}")
            return {'error': str(e)}
