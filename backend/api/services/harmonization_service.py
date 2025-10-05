from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone
import logging
from decimal import Decimal, InvalidOperation
import json

from .coordinate_validation_service import CoordinateValidationService
logger = logging.getLogger(__name__)

class DataHarmonizationService:
    """Service for mapping diverse sensor data sources to canonical schema"""
    
    # Field mapping configurations for different sources
    FIELD_MAPPINGS = {
        'purpleair': {
            'sensor_id': 'sensor_index',
            'lat': 'latitude',
            'lon': 'longitude',
            'timestamp_utc': 'last_seen',
            'raw_pm2_5': 'pm2.5_atm',
            'raw_pm10': 'pm10.0_atm',
            'temperature': 'temperature',
            'rh': 'humidity',
            'pressure': 'pressure',
            'sensor_type': lambda data: 'PurpleAir',
            'source': lambda data: 'purpleair'
        },
        'sensor_community': {
            'sensor_id': 'id',
            'lat': 'location.latitude',
            'lon': 'location.longitude',
            'timestamp_utc': 'timestamp',
            'raw_pm2_5': 'P2',  # PM2.5 in Sensor.Community format
            'raw_pm10': 'P1',   # PM10 in Sensor.Community format
            'temperature': 'temperature',
            'rh': 'humidity',
            'pressure': 'pressure',
            'sensor_type': 'sensor.sensor_type.name',
            'source': lambda data: 'sensor_community'
        },
        'openaq': {
            'sensor_id': 'locationId',
            'lat': 'coordinates.latitude',
            'lon': 'coordinates.longitude',
            'timestamp_utc': 'date.utc',
            'raw_pm2_5': 'pm25',
            'raw_pm10': 'pm10',
            'no2': 'no2',
            'o3': 'o3',
            'sensor_type': lambda data: 'OpenAQ',
            'source': lambda data: 'openaq'
        }
    }
    
    def __init__(self):
        self.validation_stats = {
            'total_processed': 0,
            'validation_errors': 0,
            'coordinate_errors': 0,
            'timestamp_errors': 0,
            'value_range_errors': 0
        }
        
        # Initialize coordinate validation service
        self.coordinate_validator = CoordinateValidationService()
    
    def harmonize_sensor_batch(self, raw_data_list: List[Dict], source: str) -> List[Dict]:
        """Harmonize a batch of sensor records from a specific source"""
        harmonized_records = []
        
        if source not in self.FIELD_MAPPINGS:
            logger.error(f"Unknown data source: {source}")
            return []
        
        # Step 1: Pre-validate coordinates for the entire batch
        coordinate_validation_summary = self.coordinate_validator.batch_validate_coordinates(raw_data_list)
        logger.info(f"Coordinate validation: {coordinate_validation_summary['valid_sensors']}/{coordinate_validation_summary['total_sensors']} valid")
        
        mapping = self.FIELD_MAPPINGS[source]
        
        for raw_record in raw_data_list:
            try:
                # Apply coordinate validation during harmonization
                lat = self._extract_nested_value(raw_record, mapping.get('lat', 'latitude'))
                lon = self._extract_nested_value(raw_record, mapping.get('lon', 'longitude'))
                
                if lat is not None and lon is not None:
                    coord_validation = self.coordinate_validator.validate_coordinates(
                        float(lat), float(lon), raw_record.get('metadata', {})
                    )
                    
                    # Skip sensors with invalid coordinates
                    if not coord_validation['is_valid']:
                        logger.debug(f"Skipping sensor with invalid coordinates: {lat}, {lon}")
                        self.validation_stats['coordinate_errors'] += 1
                        continue
                    
                    # Use normalized coordinates
                    raw_record = raw_record.copy()
                    raw_record['latitude'] = coord_validation['normalized_lat']
                    raw_record['longitude'] = coord_validation['normalized_lon']
                    raw_record['coordinate_validation'] = coord_validation
                
                harmonized = self.harmonize_single_record(raw_record, mapping, source)
                if harmonized:
                    harmonized_records.append(harmonized)
                    self.validation_stats['total_processed'] += 1
            except Exception as e:
                logger.warning(f"Failed to harmonize record from {source}: {e}")
                self.validation_stats['validation_errors'] += 1
                continue
        
        logger.info(f"Harmonized {len(harmonized_records)}/{len(raw_data_list)} records from {source}")
        return harmonized_records
    
    def harmonize_single_record(self, raw_data: Dict, mapping: Dict, source: str) -> Optional[Dict]:
        """Harmonize a single sensor record to canonical schema"""
        try:
            harmonized = {}
            
            # Map each field using the source-specific mapping
            for canonical_field, source_field in mapping.items():
                try:
                    if callable(source_field):
                        # Lambda function for computed fields
                        value = source_field(raw_data)
                    else:
                        # Extract value using dot notation for nested fields
                        value = self._extract_nested_value(raw_data, source_field)
                    
                    # Apply field-specific validation and normalization
                    normalized_value = self._normalize_field(canonical_field, value, source)
                    
                    if normalized_value is not None:
                        harmonized[canonical_field] = normalized_value
                        
                except Exception as e:
                    logger.debug(f"Failed to map field {canonical_field} from {source_field}: {e}")
                    continue
            
            # Validate essential fields are present
            if not self._validate_essential_fields(harmonized):
                self.validation_stats['validation_errors'] += 1
                return None
            
            # Add processing metadata
            harmonized['raw_blob'] = raw_data
            harmonized['created_at'] = datetime.now(timezone.utc)
            
            # Apply quality control rules
            qc_flags = self._apply_qc_rules(harmonized)
            harmonized['qc_flags'] = qc_flags
            harmonized['data_quality_score'] = self._calculate_quality_score(harmonized, qc_flags)
            
            return harmonized
            
        except Exception as e:
            logger.error(f"Error harmonizing record: {e}")
            return None
    
    def _extract_nested_value(self, data: Dict, field_path: str) -> Any:
        """Extract value from nested dictionary using dot notation"""
        try:
            current = data
            for key in field_path.split('.'):
                if isinstance(current, dict) and key in current:
                    current = current[key]
                else:
                    return None
            return current
        except Exception:
            return None
    
    def _normalize_field(self, field_name: str, value: Any, source: str) -> Any:
        """Normalize field value based on field type and source"""
        if value is None:
            return None
        
        try:
            # Coordinate normalization
            if field_name in ['lat', 'lon']:
                numeric_value = float(value)
                if field_name == 'lat' and not (-90 <= numeric_value <= 90):
                    self.validation_stats['coordinate_errors'] += 1
                    return None
                elif field_name == 'lon' and not (-180 <= numeric_value <= 180):
                    self.validation_stats['coordinate_errors'] += 1
                    return None
                return round(Decimal(str(numeric_value)), 6)
            
            # Timestamp normalization
            elif field_name == 'timestamp_utc':
                if isinstance(value, (int, float)):
                    # Unix timestamp
                    timestamp = datetime.fromtimestamp(value, tz=timezone.utc)
                elif isinstance(value, str):
                    # ISO string
                    timestamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
                elif isinstance(value, datetime):
                    timestamp = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
                else:
                    self.validation_stats['timestamp_errors'] += 1
                    return None
                
                # Validate timestamp is reasonable (not too far in past/future)
                now = datetime.now(timezone.utc)
                if timestamp < now - timedelta(days=30) or timestamp > now + timedelta(hours=1):
                    self.validation_stats['timestamp_errors'] += 1
                    logger.warning(f"Timestamp out of range: {timestamp}")
                
                return timestamp
            
            # Numeric value normalization
            elif field_name in ['raw_pm2_5', 'raw_pm10', 'temperature', 'rh', 'pressure', 'no2', 'o3']:
                try:
                    numeric_value = float(value)
                    
                    # Apply range validation
                    if field_name == 'raw_pm2_5' and not (0 <= numeric_value <= 1000):
                        self.validation_stats['value_range_errors'] += 1
                        return None
                    elif field_name == 'raw_pm10' and not (0 <= numeric_value <= 2000):
                        self.validation_stats['value_range_errors'] += 1
                        return None
                    elif field_name == 'temperature' and not (-50 <= numeric_value <= 60):
                        self.validation_stats['value_range_errors'] += 1
                        return None
                    elif field_name == 'rh' and not (0 <= numeric_value <= 100):
                        self.validation_stats['value_range_errors'] += 1
                        return None
                    elif field_name == 'pressure' and not (800 <= numeric_value <= 1200):
                        self.validation_stats['value_range_errors'] += 1
                        return None
                    
                    return round(Decimal(str(numeric_value)), 2)
                    
                except (ValueError, InvalidOperation):
                    return None
            
            # String field normalization
            elif field_name in ['sensor_id', 'sensor_type', 'source']:
                return str(value).strip() if value else None
            
            else:
                return value
                
        except Exception as e:
            logger.debug(f"Error normalizing field {field_name}: {e}")
            return None
    
    def _validate_essential_fields(self, harmonized: Dict) -> bool:
        """Validate that essential fields are present and valid"""
        essential_fields = ['sensor_id', 'lat', 'lon', 'timestamp_utc', 'source']
        
        for field in essential_fields:
            if field not in harmonized or harmonized[field] is None:
                logger.debug(f"Missing essential field: {field}")
                return False
        
        # Additional validation
        if not isinstance(harmonized['lat'], (int, float, Decimal)):
            return False
        if not isinstance(harmonized['lon'], (int, float, Decimal)):
            return False
        if not isinstance(harmonized['timestamp_utc'], datetime):
            return False
            
        return True
    
    def _apply_qc_rules(self, harmonized: Dict) -> List[str]:
        """Apply quality control rules and return list of flags"""
        qc_flags = []
        
        # Rule 1: Negative values flag
        for field in ['raw_pm2_5', 'raw_pm10']:
            if harmonized.get(field) is not None and float(harmonized[field]) < 0:
                qc_flags.append(f'NEGATIVE_{field.upper()}')
                harmonized[field] = None  # Set to null
        
        # Rule 2: Extreme values flag
        pm25_value = harmonized.get('raw_pm2_5')
        if pm25_value is not None and float(pm25_value) > 500:
            qc_flags.append('EXTREME_PM25')
        
        # Rule 3: High humidity uncertainty flag (optical sensors)
        rh_value = harmonized.get('rh')
        if rh_value is not None and float(rh_value) > 85:
            qc_flags.append('HIGH_HUMIDITY_UNCERTAINTY')
        
        # Rule 4: Temperature range validation
        temp_value = harmonized.get('temperature')
        if temp_value is not None:
            temp_float = float(temp_value)
            if temp_float < -40 or temp_float > 50:
                qc_flags.append('EXTREME_TEMPERATURE')
        
        # Rule 5: Missing critical measurements
        if harmonized.get('raw_pm2_5') is None:
            qc_flags.append('MISSING_PM25')
        
        return qc_flags
    
    def _calculate_quality_score(self, harmonized: Dict, qc_flags: List[str]) -> float:
        """Calculate data quality score (0-1)"""
        base_score = 1.0
        
        # Deduct for missing data
        critical_fields = ['raw_pm2_5', 'raw_pm10', 'temperature', 'rh']
        missing_count = sum(1 for field in critical_fields if harmonized.get(field) is None)
        base_score -= (missing_count / len(critical_fields)) * 0.3
        
        # Deduct for QC flags
        flag_penalties = {
            'NEGATIVE_': 0.2,
            'EXTREME_': 0.15,
            'HIGH_HUMIDITY_': 0.1,
            'MISSING_': 0.25
        }
        
        for flag in qc_flags:
            for pattern, penalty in flag_penalties.items():
                if flag.startswith(pattern):
                    base_score -= penalty
                    break
        
        return max(0.0, min(1.0, base_score))
    
    def get_harmonization_stats(self) -> Dict:
        """Get statistics about the harmonization process"""
        total = self.validation_stats['total_processed']
        if total == 0:
            return self.validation_stats
        
        return {
            **self.validation_stats,
            'success_rate': (total - self.validation_stats['validation_errors']) / total,
            'coordinate_error_rate': self.validation_stats['coordinate_errors'] / total,
            'timestamp_error_rate': self.validation_stats['timestamp_errors'] / total,
            'value_range_error_rate': self.validation_stats['value_range_errors'] / total
        }
