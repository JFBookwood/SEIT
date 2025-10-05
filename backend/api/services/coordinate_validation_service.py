import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timezone
import math
import numpy as np

logger = logging.getLogger(__name__)

class CoordinateValidationService:
    """Service for comprehensive coordinate validation and normalization"""
    
    def __init__(self):
        # Validation thresholds and ranges
        self.validation_config = {
            'latitude_range': (-90.0, 90.0),
            'longitude_range': (-180.0, 180.0),
            'precision_decimal_places': 6,
            'min_coordinate_precision': 0.000001,  # ~10cm resolution
            'suspicious_coordinate_patterns': [
                (0.0, 0.0),    # Null Island
                (90.0, 0.0),   # North Pole
                (-90.0, 0.0),  # South Pole
                (0.0, 180.0),  # Date line
                (0.0, -180.0)  # Date line
            ],
            'ocean_exclusion_zones': [
                # Major ocean areas where sensors are unlikely
                {'bounds': [-180, -60, 180, 60], 'name': 'Open Ocean'},
                {'bounds': [-160, 15, -120, 50], 'name': 'North Pacific'},
                {'bounds': [-50, -30, 20, 20], 'name': 'South Atlantic'}
            ]
        }
        
        # Land/water validation (simplified - in production use detailed coastline data)
        self.known_land_areas = [
            # Major continental areas for validation
            {'bounds': [-125, 25, -65, 50], 'name': 'North America'},
            {'bounds': [-10, 35, 30, 70], 'name': 'Europe'},
            {'bounds': [95, -45, 155, -10], 'name': 'Australia'},
            {'bounds': [70, 5, 145, 55], 'name': 'Asia'},
            {'bounds': [-85, -25, -35, 15], 'name': 'South America'},
            {'bounds': [10, -35, 50, 35], 'name': 'Africa'}
        ]
    
    def validate_coordinates(self, latitude: float, longitude: float, 
                           sensor_metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """Comprehensive coordinate validation with detailed feedback"""
        validation_result = {
            'is_valid': True,
            'latitude': latitude,
            'longitude': longitude,
            'normalized_lat': None,
            'normalized_lon': None,
            'validation_flags': [],
            'confidence_score': 1.0,
            'metadata': sensor_metadata or {}
        }
        
        try:
            # Step 1: Basic range validation
            range_validation = self._validate_coordinate_ranges(latitude, longitude)
            if not range_validation['valid']:
                validation_result['is_valid'] = False
                validation_result['validation_flags'].extend(range_validation['flags'])
                return validation_result
            
            # Step 2: Precision and format validation
            precision_validation = self._validate_coordinate_precision(latitude, longitude)
            validation_result['validation_flags'].extend(precision_validation['flags'])
            validation_result['confidence_score'] *= precision_validation['confidence_factor']
            
            # Step 3: Suspicious pattern detection
            pattern_validation = self._detect_suspicious_patterns(latitude, longitude)
            validation_result['validation_flags'].extend(pattern_validation['flags'])
            validation_result['confidence_score'] *= pattern_validation['confidence_factor']
            
            # Step 4: Land/water validation for sensors
            location_validation = self._validate_sensor_location(latitude, longitude, sensor_metadata)
            validation_result['validation_flags'].extend(location_validation['flags'])
            validation_result['confidence_score'] *= location_validation['confidence_factor']
            
            # Step 5: Normalize coordinates
            validation_result['normalized_lat'] = self._normalize_latitude(latitude)
            validation_result['normalized_lon'] = self._normalize_longitude(longitude)
            
            # Step 6: Calculate final validity
            critical_flags = [flag for flag in validation_result['validation_flags'] 
                            if flag.startswith('CRITICAL_')]
            if critical_flags or validation_result['confidence_score'] < 0.3:
                validation_result['is_valid'] = False
            
            logger.debug(f"Coordinate validation: ({latitude}, {longitude}) -> "
                        f"Valid: {validation_result['is_valid']}, "
                        f"Confidence: {validation_result['confidence_score']:.2f}")
            
            return validation_result
            
        except Exception as e:
            logger.error(f"Coordinate validation failed: {e}")
            validation_result['is_valid'] = False
            validation_result['validation_flags'].append('CRITICAL_VALIDATION_ERROR')
            return validation_result
    
    def _validate_coordinate_ranges(self, lat: float, lon: float) -> Dict:
        """Validate coordinates are within valid Earth ranges"""
        flags = []
        valid = True
        
        # Latitude validation
        if not isinstance(lat, (int, float)) or math.isnan(lat) or math.isinf(lat):
            flags.append('CRITICAL_INVALID_LATITUDE_FORMAT')
            valid = False
        elif not (self.validation_config['latitude_range'][0] <= lat <= self.validation_config['latitude_range'][1]):
            flags.append('CRITICAL_LATITUDE_OUT_OF_RANGE')
            valid = False
        
        # Longitude validation
        if not isinstance(lon, (int, float)) or math.isnan(lon) or math.isinf(lon):
            flags.append('CRITICAL_INVALID_LONGITUDE_FORMAT')
            valid = False
        elif not (self.validation_config['longitude_range'][0] <= lon <= self.validation_config['longitude_range'][1]):
            flags.append('CRITICAL_LONGITUDE_OUT_OF_RANGE')
            valid = False
        
        return {'valid': valid, 'flags': flags}
    
    def _validate_coordinate_precision(self, lat: float, lon: float) -> Dict:
        """Validate coordinate precision and detect truncation"""
        flags = []
        confidence_factor = 1.0
        
        # Check decimal precision
        lat_str = str(lat)
        lon_str = str(lon)
        
        lat_decimal_places = len(lat_str.split('.')[-1]) if '.' in lat_str else 0
        lon_decimal_places = len(lon_str.split('.')[-1]) if '.' in lon_str else 0
        
        # Flag low precision coordinates
        if lat_decimal_places < 4 or lon_decimal_places < 4:
            flags.append('LOW_PRECISION_COORDINATES')
            confidence_factor *= 0.8
        
        # Flag suspiciously rounded coordinates
        if lat % 0.001 == 0 and lon % 0.001 == 0:
            flags.append('SUSPICIOUSLY_ROUNDED_COORDINATES')
            confidence_factor *= 0.7
        
        # Flag identical coordinates (potential duplication)
        if lat == lon:
            flags.append('IDENTICAL_LAT_LON_VALUES')
            confidence_factor *= 0.5
        
        return {'flags': flags, 'confidence_factor': confidence_factor}
    
    def _detect_suspicious_patterns(self, lat: float, lon: float) -> Dict:
        """Detect suspicious coordinate patterns"""
        flags = []
        confidence_factor = 1.0
        
        # Check for exact suspicious coordinate pairs
        for suspicious_lat, suspicious_lon in self.validation_config['suspicious_coordinate_patterns']:
            if abs(lat - suspicious_lat) < 0.0001 and abs(lon - suspicious_lon) < 0.0001:
                flags.append(f'SUSPICIOUS_LOCATION_{suspicious_lat}_{suspicious_lon}')
                confidence_factor *= 0.2
        
        # Check for coordinates at country/administrative boundaries (often default values)
        administrative_boundaries = [
            (37.0902, -95.7129),  # Geographic center of US
            (51.5074, -0.1278),   # London (common default)
            (40.7128, -74.0060),  # NYC (common default)
            (0.0, 0.0)            # Origin point
        ]
        
        for boundary_lat, boundary_lon in administrative_boundaries:
            distance = self._calculate_distance(lat, lon, boundary_lat, boundary_lon)
            if distance < 0.01:  # Within ~1km
                flags.append('NEAR_ADMINISTRATIVE_BOUNDARY')
                confidence_factor *= 0.8
        
        return {'flags': flags, 'confidence_factor': confidence_factor}
    
    def _validate_sensor_location(self, lat: float, lon: float, metadata: Optional[Dict]) -> Dict:
        """Validate sensor location against expected deployment areas"""
        flags = []
        confidence_factor = 1.0
        
        # Check if coordinates are in major ocean areas (unlikely for land-based sensors)
        is_likely_ocean = self._is_likely_ocean_location(lat, lon)
        if is_likely_ocean and not self._is_marine_sensor(metadata):
            flags.append('POTENTIAL_OCEAN_LOCATION')
            confidence_factor *= 0.3
        
        # Check if coordinates are on known land areas
        is_on_land = self._is_on_known_land(lat, lon)
        if not is_on_land:
            flags.append('UNCERTAIN_LAND_LOCATION')
            confidence_factor *= 0.6
        
        # Validate against sensor type expectations
        if metadata:
            sensor_type = metadata.get('sensor_type', '').lower()
            location_type = metadata.get('location_type', '').lower()
            
            # Indoor sensors with precise coordinates are more suspicious
            if 'indoor' in location_type and self._has_high_precision(lat, lon):
                flags.append('INDOOR_HIGH_PRECISION')
                confidence_factor *= 0.9
            
            # Mobile sensors should have more variable coordinates
            if 'mobile' in sensor_type and self._appears_stationary(lat, lon, metadata):
                flags.append('MOBILE_SENSOR_STATIONARY')
                confidence_factor *= 0.7
        
        return {'flags': flags, 'confidence_factor': confidence_factor}
    
    def _calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two coordinates using Haversine formula"""
        R = 6371  # Earth's radius in kilometers
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        
        a = (math.sin(delta_lat / 2) ** 2 + 
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c
    
    def _is_likely_ocean_location(self, lat: float, lon: float) -> bool:
        """Check if coordinates are likely in ocean areas"""
        # Simple ocean detection - in production use detailed coastline data
        for ocean_zone in self.validation_config['ocean_exclusion_zones']:
            bounds = ocean_zone['bounds']
            if (bounds[0] <= lon <= bounds[2] and bounds[1] <= lat <= bounds[3]):
                return True
        
        # Additional ocean checks
        # Pacific Ocean
        if -180 <= lon <= -120 and -60 <= lat <= 60:
            return True
        # Atlantic Ocean (mid-ocean)
        if -40 <= lon <= -20 and -40 <= lat <= 60:
            return True
        
        return False
    
    def _is_on_known_land(self, lat: float, lon: float) -> bool:
        """Check if coordinates are on known land areas"""
        for land_area in self.known_land_areas:
            bounds = land_area['bounds']
            if (bounds[0] <= lon <= bounds[2] and bounds[1] <= lat <= bounds[3]):
                return True
        return False
    
    def _is_marine_sensor(self, metadata: Optional[Dict]) -> bool:
        """Check if sensor is intended for marine/water deployment"""
        if not metadata:
            return False
        
        marine_indicators = ['marine', 'ocean', 'ship', 'buoy', 'boat', 'vessel', 'water']
        sensor_type = metadata.get('sensor_type', '').lower()
        location_type = metadata.get('location_type', '').lower()
        description = metadata.get('description', '').lower()
        
        return any(indicator in text for indicator in marine_indicators 
                  for text in [sensor_type, location_type, description])
    
    def _has_high_precision(self, lat: float, lon: float) -> bool:
        """Check if coordinates have unusually high precision"""
        lat_precision = len(str(lat).split('.')[-1]) if '.' in str(lat) else 0
        lon_precision = len(str(lon).split('.')[-1]) if '.' in str(lon) else 0
        
        return lat_precision > 6 or lon_precision > 6
    
    def _appears_stationary(self, lat: float, lon: float, metadata: Dict) -> bool:
        """Check if mobile sensor appears to be stationary"""
        # In production, this would check historical positions
        # For now, flag if coordinates are too precise for mobile sensor
        return self._has_high_precision(lat, lon)
    
    def _normalize_latitude(self, lat: float) -> float:
        """Normalize latitude to standard precision"""
        # Clamp to valid range
        normalized = max(self.validation_config['latitude_range'][0], 
                        min(self.validation_config['latitude_range'][1], lat))
        
        # Round to specified precision
        return round(normalized, self.validation_config['precision_decimal_places'])
    
    def _normalize_longitude(self, lon: float) -> float:
        """Normalize longitude to standard precision and handle wrapping"""
        # Handle longitude wrapping (e.g., 185° -> -175°)
        if lon > 180:
            lon = lon - 360
        elif lon < -180:
            lon = lon + 360
        
        # Clamp to valid range
        normalized = max(self.validation_config['longitude_range'][0], 
                        min(self.validation_config['longitude_range'][1], lon))
        
        # Round to specified precision
        return round(normalized, self.validation_config['precision_decimal_places'])
    
    def batch_validate_coordinates(self, sensors: List[Dict]) -> Dict[str, Any]:
        """Validate coordinates for a batch of sensors"""
        validation_summary = {
            'total_sensors': len(sensors),
            'valid_sensors': 0,
            'invalid_sensors': 0,
            'suspicious_sensors': 0,
            'validation_results': [],
            'flag_summary': {},
            'processing_time': datetime.now(timezone.utc)
        }
        
        start_time = datetime.now(timezone.utc)
        
        for i, sensor in enumerate(sensors):
            try:
                lat = float(sensor.get('latitude', 0))
                lon = float(sensor.get('longitude', 0))
                metadata = sensor.get('metadata', {})
                
                result = self.validate_coordinates(lat, lon, metadata)
                result['sensor_index'] = i
                result['sensor_id'] = sensor.get('sensor_id', f'unknown_{i}')
                
                validation_summary['validation_results'].append(result)
                
                if result['is_valid']:
                    validation_summary['valid_sensors'] += 1
                else:
                    validation_summary['invalid_sensors'] += 1
                
                if result['confidence_score'] < 0.7:
                    validation_summary['suspicious_sensors'] += 1
                
                # Aggregate flags for summary
                for flag in result['validation_flags']:
                    validation_summary['flag_summary'][flag] = validation_summary['flag_summary'].get(flag, 0) + 1
                
            except Exception as e:
                logger.error(f"Validation failed for sensor {i}: {e}")
                validation_summary['invalid_sensors'] += 1
        
        # Calculate processing metrics
        processing_time = (datetime.now(timezone.utc) - start_time).total_seconds()
        validation_summary['processing_time_seconds'] = processing_time
        validation_summary['sensors_per_second'] = len(sensors) / max(processing_time, 0.001)
        
        logger.info(f"Batch validation completed: {validation_summary['valid_sensors']}/{validation_summary['total_sensors']} valid sensors")
        
        return validation_summary
    
    def filter_valid_sensors(self, sensors: List[Dict], 
                           min_confidence: float = 0.5) -> Tuple[List[Dict], List[Dict]]:
        """Filter sensors into valid and invalid groups"""
        valid_sensors = []
        invalid_sensors = []
        
        for sensor in sensors:
            try:
                lat = float(sensor.get('latitude', 0))
                lon = float(sensor.get('longitude', 0))
                metadata = sensor.get('metadata', {})
                
                validation_result = self.validate_coordinates(lat, lon, metadata)
                
                if validation_result['is_valid'] and validation_result['confidence_score'] >= min_confidence:
                    # Use normalized coordinates
                    sensor_copy = sensor.copy()
                    sensor_copy['latitude'] = validation_result['normalized_lat']
                    sensor_copy['longitude'] = validation_result['normalized_lon']
                    sensor_copy['coordinate_validation'] = validation_result
                    valid_sensors.append(sensor_copy)
                else:
                    sensor_copy = sensor.copy()
                    sensor_copy['coordinate_validation'] = validation_result
                    invalid_sensors.append(sensor_copy)
                    
            except Exception as e:
                logger.warning(f"Failed to validate sensor {sensor.get('sensor_id')}: {e}")
                invalid_sensors.append(sensor)
        
        logger.info(f"Filtered {len(valid_sensors)} valid sensors from {len(sensors)} total")
        
        return valid_sensors, invalid_sensors
    
    def generate_validation_report(self, validation_results: List[Dict]) -> Dict:
        """Generate comprehensive validation report"""
        total_sensors = len(validation_results)
        valid_count = sum(1 for r in validation_results if r['is_valid'])
        
        # Flag frequency analysis
        all_flags = []
        for result in validation_results:
            all_flags.extend(result.get('validation_flags', []))
        
        flag_counts = {}
        for flag in all_flags:
            flag_counts[flag] = flag_counts.get(flag, 0) + 1
        
        # Confidence score distribution
        confidence_scores = [r.get('confidence_score', 0) for r in validation_results]
        
        report = {
            'summary': {
                'total_sensors': total_sensors,
                'valid_sensors': valid_count,
                'invalid_sensors': total_sensors - valid_count,
                'validation_rate': valid_count / total_sensors if total_sensors > 0 else 0
            },
            'confidence_distribution': {
                'mean': np.mean(confidence_scores),
                'median': np.median(confidence_scores),
                'min': np.min(confidence_scores),
                'max': np.max(confidence_scores),
                'std': np.std(confidence_scores)
            },
            'flag_frequency': dict(sorted(flag_counts.items(), key=lambda x: x[1], reverse=True)),
            'most_common_issues': list(sorted(flag_counts.items(), key=lambda x: x[1], reverse=True)[:5]),
            'generated_at': datetime.now(timezone.utc).isoformat()
        }
        
        return report
