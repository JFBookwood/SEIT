from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone
import logging
from decimal import Decimal, InvalidOperation

from .coordinate_validation_service import CoordinateValidationService

logger = logging.getLogger(__name__)

class DataHarmonizationService:
    """Service for harmonizing diverse sensor data sources to canonical schema"""
    
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
    
    def harmonize_data(self, raw_data: Dict, source: str) -> Dict:
        """Map source fields to canonical schema"""
        if source not in self.FIELD_MAPPINGS:
            logger.error(f"Unknown data source: {source}")
            return {}
        
        mapping = self.FIELD_MAPPINGS[source]
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
        
        # Validate coordinates if present
        if harmonized.get('lat') and harmonized.get('lon'):
            coord_validation = self.coordinate_validator.validate_coordinates(
                float(harmonized['lat']), 
                float(harmonized['lon']), 
                raw_data.get('metadata', {})
            )
            
            if coord_validation['is_valid']:
                harmonized['lat'] = coord_validation['normalized_lat']
                harmonized['lon'] = coord_validation['normalized_lon']
                harmonized['coordinate_validation'] = coord_validation
            else:
                logger.debug(f"Invalid coordinates skipped: {harmonized.get('lat')}, {harmonized.get('lon')}")
                return {}  # Skip record with invalid coordinates
        
        # Add processing metadata
        harmonized['raw_blob'] = raw_data
        harmonized['created_at'] = datetime.now(timezone.utc)
        
        self.validation_stats['total_processed'] += 1
        
        return harmonized
    
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
                
                # Validate timestamp is reasonable
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
