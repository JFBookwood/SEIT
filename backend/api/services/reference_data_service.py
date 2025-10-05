from typing import Dict, List, Optional, Any
from datetime import datetime, timezone, timedelta
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session
import logging

from ..models.harmonized_models import SensorHarmonized

logger = logging.getLogger(__name__)

class ReferenceDataService:
    """Service for managing reference monitor data and co-location studies"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
        
        # Reference data quality thresholds
        self.quality_thresholds = {
            'min_colocation_days': 7,      # Minimum co-location period
            'max_distance_meters': 100,    # Maximum distance for co-location
            'min_temporal_overlap': 0.7,   # Minimum temporal data overlap
            'max_time_difference_minutes': 30  # Maximum time difference for paired measurements
        }
    
    def find_colocation_opportunities(self, bbox: List[float], 
                                    reference_monitors: List[Dict]) -> List[Dict]:
        """Find sensors that could be co-located with reference monitors"""
        try:
            west, south, east, north = bbox
            
            # Get sensors in the area
            sensors_in_area = self.db.query(SensorHarmonized).filter(
                SensorHarmonized.lon >= west,
                SensorHarmonized.lon <= east,
                SensorHarmonized.lat >= south,
                SensorHarmonized.lat <= north
            ).distinct(SensorHarmonized.sensor_id).all()
            
            colocation_opportunities = []
            
            for sensor in sensors_in_area:
                for ref_monitor in reference_monitors:
                    # Calculate distance
                    distance_m = self._calculate_distance(
                        float(sensor.lat), float(sensor.lon),
                        ref_monitor['latitude'], ref_monitor['longitude']
                    )
                    
                    if distance_m <= self.quality_thresholds['max_distance_meters']:
                        # Check temporal overlap
                        overlap_score = self._calculate_temporal_overlap(
                            sensor.sensor_id, ref_monitor['monitor_id']
                        )
                        
                        if overlap_score >= self.quality_thresholds['min_temporal_overlap']:
                            colocation_opportunities.append({
                                'sensor_id': sensor.sensor_id,
                                'reference_monitor_id': ref_monitor['monitor_id'],
                                'distance_meters': round(distance_m, 1),
                                'temporal_overlap': round(overlap_score, 2),
                                'sensor_location': {'lat': float(sensor.lat), 'lon': float(sensor.lon)},
                                'reference_location': {
                                    'lat': ref_monitor['latitude'], 
                                    'lon': ref_monitor['longitude']
                                },
                                'quality_score': self._calculate_colocation_quality(distance_m, overlap_score)
                            })
            
            # Sort by quality score (best opportunities first)
            colocation_opportunities.sort(key=lambda x: x['quality_score'], reverse=True)
            
            return colocation_opportunities
            
        except Exception as e:
            logger.error(f"Error finding co-location opportunities: {e}")
            return []
    
    def generate_reference_dataset(self, sensor_id: str, reference_monitor_id: str,
                                 days_back: int = 30) -> List[Dict]:
        """Generate paired sensor-reference dataset for calibration"""
        try:
            # Get sensor data
            cutoff_time = datetime.now(timezone.utc) - timedelta(days=days_back)
            
            sensor_data = self.db.query(SensorHarmonized).filter(
                SensorHarmonized.sensor_id == sensor_id,
                SensorHarmonized.timestamp_utc >= cutoff_time,
                SensorHarmonized.raw_pm2_5.isnot(None)
            ).order_by(SensorHarmonized.timestamp_utc).all()
            
            # For demonstration, generate paired reference data
            # In production, this would query actual reference monitor database
            reference_dataset = []
            
            for sensor_record in sensor_data:
                # Generate realistic reference measurement
                raw_pm25 = float(sensor_record.raw_pm2_5)
                
                # Simulate reference monitor with known bias patterns
                reference_pm25 = self._simulate_reference_measurement(
                    raw_pm25,
                    float(sensor_record.rh) if sensor_record.rh else 50,
                    float(sensor_record.temperature) if sensor_record.temperature else 20
                )
                
                reference_dataset.append({
                    'timestamp': sensor_record.timestamp_utc,
                    'sensor_id': sensor_id,
                    'reference_monitor_id': reference_monitor_id,
                    'raw_pm2_5': raw_pm25,
                    'reference_pm2_5': reference_pm25,
                    'rh': float(sensor_record.rh) if sensor_record.rh else 50,
                    'temperature': float(sensor_record.temperature) if sensor_record.temperature else 20,
                    'temporal_difference_minutes': 0,  # Perfectly aligned for simulation
                    'spatial_distance_meters': 50  # Simulated co-location distance
                })
            
            logger.info(f"Generated {len(reference_dataset)} reference data points for sensor {sensor_id}")
            
            return reference_dataset
            
        except Exception as e:
            logger.error(f"Error generating reference dataset for sensor {sensor_id}: {e}")
            return []
    
    def validate_reference_data_quality(self, reference_dataset: List[Dict]) -> Dict[str, Any]:
        """Validate the quality of reference data for calibration"""
        try:
            if not reference_dataset:
                return {'valid': False, 'errors': ['No reference data provided']}
            
            validation_result = {
                'valid': True,
                'warnings': [],
                'errors': [],
                'quality_metrics': {}
            }
            
            df = pd.DataFrame(reference_dataset)
            
            # Check minimum data requirements
            if len(df) < 10:
                validation_result['errors'].append(f'Insufficient data points: {len(df)} < 10')
                validation_result['valid'] = False
            
            # Check for missing critical fields
            required_fields = ['raw_pm2_5', 'reference_pm2_5', 'rh', 'temperature']
            for field in required_fields:
                if field not in df.columns:
                    validation_result['errors'].append(f'Missing required field: {field}')
                    validation_result['valid'] = False
                elif df[field].isna().sum() > len(df) * 0.2:  # More than 20% missing
                    validation_result['warnings'].append(f'High missing data rate for {field}: {df[field].isna().sum()}/{len(df)}')
            
            # Check value ranges
            if 'raw_pm2_5' in df.columns:
                raw_pm25 = df['raw_pm2_5'].dropna()
                if (raw_pm25 < 0).any():
                    validation_result['errors'].append('Negative raw PM2.5 values detected')
                    validation_result['valid'] = False
                if (raw_pm25 > 500).any():
                    validation_result['warnings'].append('Extremely high raw PM2.5 values detected')
            
            if 'reference_pm2_5' in df.columns:
                ref_pm25 = df['reference_pm2_5'].dropna()
                if (ref_pm25 < 0).any():
                    validation_result['errors'].append('Negative reference PM2.5 values detected')
                    validation_result['valid'] = False
            
            # Calculate quality metrics
            if validation_result['valid'] and len(df) > 0:
                validation_result['quality_metrics'] = {
                    'data_points': len(df),
                    'temporal_span_days': (df['timestamp'].max() - df['timestamp'].min()).days if 'timestamp' in df.columns else None,
                    'raw_pm25_range': {
                        'min': float(df['raw_pm2_5'].min()) if 'raw_pm2_5' in df.columns else None,
                        'max': float(df['raw_pm2_5'].max()) if 'raw_pm2_5' in df.columns else None,
                        'mean': float(df['raw_pm2_5'].mean()) if 'raw_pm2_5' in df.columns else None
                    },
                    'reference_pm25_range': {
                        'min': float(df['reference_pm2_5'].min()) if 'reference_pm2_5' in df.columns else None,
                        'max': float(df['reference_pm2_5'].max()) if 'reference_pm2_5' in df.columns else None,
                        'mean': float(df['reference_pm2_5'].mean()) if 'reference_pm2_5' in df.columns else None
                    },
                    'completeness': {
                        'raw_pm25': 1 - (df['raw_pm2_5'].isna().sum() / len(df)) if 'raw_pm2_5' in df.columns else 0,
                        'reference_pm25': 1 - (df['reference_pm2_5'].isna().sum() / len(df)) if 'reference_pm2_5' in df.columns else 0,
                        'meteorology': 1 - ((df['rh'].isna().sum() + df['temperature'].isna().sum()) / (2 * len(df))) if all(col in df.columns for col in ['rh', 'temperature']) else 0
                    }
                }
            
            return validation_result
            
        except Exception as e:
            logger.error(f"Reference data validation failed: {e}")
            return {'valid': False, 'errors': [str(e)]}
    
    def _calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two points using Haversine formula"""
        R = 6371000  # Earth's radius in meters
        
        lat1_rad = np.radians(lat1)
        lat2_rad = np.radians(lat2)
        delta_lat = np.radians(lat2 - lat1)
        delta_lon = np.radians(lon2 - lon1)
        
        a = (np.sin(delta_lat / 2) ** 2 + 
             np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(delta_lon / 2) ** 2)
        c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
        
        return R * c
    
    def _calculate_temporal_overlap(self, sensor_id: str, reference_monitor_id: str) -> float:
        """Calculate temporal data overlap between sensor and reference monitor"""
        # For simulation, return a realistic overlap score
        # In production, this would analyze actual temporal alignment
        return np.random.uniform(0.7, 0.95)  # 70-95% overlap
    
    def _calculate_colocation_quality(self, distance_m: float, temporal_overlap: float) -> float:
        """Calculate overall co-location quality score"""
        # Distance factor (closer is better)
        distance_factor = max(0, 1 - (distance_m / self.quality_thresholds['max_distance_meters']))
        
        # Temporal factor
        temporal_factor = temporal_overlap
        
        # Combined quality score (0-1)
        quality_score = (distance_factor * 0.4) + (temporal_factor * 0.6)
        
        return round(quality_score, 3)
    
    def _simulate_reference_measurement(self, raw_pm25: float, rh: float, temperature: float) -> float:
        """Simulate reference monitor measurement with realistic bias patterns"""
        # Simulate typical low-cost sensor biases
        # High concentrations: sensors read high
        # High humidity: optical interference
        # Temperature effects: minimal for most sensors
        
        # Base bias factor
        if raw_pm25 > 50:
            bias_factor = 0.75  # High bias at very high concentrations
        elif raw_pm25 > 25:
            bias_factor = 0.85  # Moderate bias
        else:
            bias_factor = 0.92  # Small bias at low concentrations
        
        # Humidity correction (optical sensors affected by high RH)
        if rh > 85:
            humidity_factor = 0.95
        elif rh > 70:
            humidity_factor = 0.98
        else:
            humidity_factor = 1.0
        
        # Apply corrections and add realistic noise
        reference_value = raw_pm25 * bias_factor * humidity_factor
        reference_value += np.random.normal(0, 2.0)  # ±2 μg/m³ measurement noise
        
        return max(0, reference_value)  # Ensure non-negative
