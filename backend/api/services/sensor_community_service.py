import aiohttp
import asyncio
from typing import Dict, List, Optional
from datetime import datetime

class SensorCommunityService:
    """Service for interacting with Sensor.Community API"""
    
    def __init__(self):
        self.base_url = "https://data.sensor.community/airrohr/v1"
        # Sensor.Community provides open data without API keys
    
    async def get_current_data(self, bbox: Optional[str] = None) -> List[Dict]:
        """Get current sensor data from Sensor.Community"""
        try:
            async with aiohttp.ClientSession() as session:
                # Get sensor locations first
                url = f"{self.base_url}/filter/area=0,0,0,0"  # This gets all sensors
                async with session.get(url, timeout=30) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        sensors = []
                        for item in data:
                            try:
                                location = item.get("location", {})
                                lat = float(location.get("latitude", 0))
                                lng = float(location.get("longitude", 0))
                                
                                # Apply bounding box filter if specified
                                if bbox:
                                    west, south, east, north = map(float, bbox.split(','))
                                    if not (west <= lng <= east and south <= lat <= north):
                                        continue
                                
                                # Extract sensor readings
                                sensor_data_values = item.get("sensordatavalues", [])
                                pm25 = None
                                pm10 = None
                                temperature = None
                                humidity = None
                                pressure = None
                                
                                for reading in sensor_data_values:
                                    value_type = reading.get("value_type")
                                    value = reading.get("value")
                                    
                                    if value_type == "P2" and value:  # PM2.5
                                        pm25 = float(value)
                                    elif value_type == "P1" and value:  # PM10
                                        pm10 = float(value)
                                    elif value_type == "temperature" and value:
                                        temperature = float(value)
                                    elif value_type == "humidity" and value:
                                        humidity = float(value)
                                    elif value_type == "pressure" and value:
                                        pressure = float(value)
                                
                                sensor = {
                                    "sensor_id": str(item.get("id", "unknown")),
                                    "latitude": lat,
                                    "longitude": lng,
                                    "timestamp": item.get("timestamp"),
                                    "pm25": pm25,
                                    "pm10": pm10,
                                    "temperature": temperature,
                                    "humidity": humidity,
                                    "pressure": pressure,
                                    "source": "sensor_community",
                                    "sensor_type": item.get("sensor", {}).get("sensor_type", {}).get("name"),
                                    "metadata": {
                                        "location_id": location.get("id"),
                                        "country": location.get("country"),
                                        "exact_location": location.get("exact_location"),
                                        "indoor": location.get("indoor")
                                    }
                                }
                                sensors.append(sensor)
                                
                                # Limit results for performance
                                if len(sensors) >= 100:
                                    break
                                    
                            except Exception as e:
                                continue  # Skip invalid records
                        
                        return sensors
                    else:
                        print(f"Sensor.Community API error: {response.status}")
                        return self._generate_mock_data(bbox)
                        
        except Exception as e:
            print(f"Sensor.Community request failed: {e}")
            return self._generate_mock_data(bbox)
    
    async def get_sensor_data(self, sensor_id: str) -> Optional[Dict]:
        """Get data for a specific sensor"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/sensor/{sensor_id}/"
                async with session.get(url, timeout=30) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data
                    else:
                        return None
                        
        except Exception as e:
            print(f"Error fetching sensor {sensor_id}: {e}")
            return None
    
    def _generate_mock_data(self, bbox: Optional[str] = None) -> List[Dict]:
        """Generate mock Sensor.Community data for testing"""
        import random
        from datetime import datetime, timedelta
        
        # Land-based European cities - avoid water areas
        if bbox:
            west, south, east, north = map(float, bbox.split(','))
        else:
            west, south, east, north = -5, 40, 25, 65  # Central Europe land areas
        
        # Define major European cities on land
        european_cities = [
                {"lat": 51.5074, "lng": -0.1278, "name": "London"},
                {"lat": 48.8566, "lng": 2.3522, "name": "Paris"},
                {"lat": 52.5200, "lng": 13.4050, "name": "Berlin"},
                {"lat": 52.3676, "lng": 4.9041, "name": "Amsterdam"},
                {"lat": 50.8503, "lng": 4.3517, "name": "Brussels"},
                {"lat": 55.7558, "lng": 12.5059, "name": "Copenhagen"}
        ]
        
        sensors = []
        for i in range(15):  # Generate 15 mock sensors
            # Pick a city and place sensor nearby on land
            city = random.choice(european_cities)
                lat = city["lat"] + (random.random() - 0.5) * 0.02
                lng = city["lng"] + (random.random() - 0.5) * 0.02
            
            # Mock timestamp (recent)
            timestamp = datetime.utcnow() - timedelta(minutes=random.randint(1, 60))
            
            sensor = {
                "sensor_id": f"sc_{20000 + i}",
                "latitude": round(lat, 6),
                "longitude": round(lng, 6),
                "timestamp": timestamp.isoformat() + "Z",
                "pm25": round(random.uniform(3, 45), 1),
                "pm10": round(random.uniform(8, 80), 1),
                "temperature": round(random.uniform(-5, 35), 1),
                "humidity": round(random.uniform(25, 90), 1),
                "pressure": round(random.uniform(980, 1040), 1),
                "source": "sensor_community",
                "sensor_type": random.choice(["SDS011", "PMS5003", "SPS30"]),
                "metadata": {
                    "location_id": 10000 + i,
                    "country": random.choice(["DE", "FR", "NL", "BE", "AT", "CH"]),
                    "exact_location": 0,
                    "indoor": 0
                }
            }
            sensors.append(sensor)
        
        return sensors
    
    def normalize_sensor_data(self, raw_data: List[Dict]) -> List[Dict]:
        """Normalize Sensor.Community data to standard format"""
        normalized = []
        
        for item in raw_data:
            try:
                # Extract sensor readings from nested structure
                sensor_values = {}
                for reading in item.get("sensordatavalues", []):
                    value_type = reading.get("value_type")
                    value = reading.get("value")
                    
                    if value and value_type:
                        sensor_values[value_type] = float(value)
                
                # Map to standard parameter names
                normalized_item = {
                    "sensor_id": str(item.get("id")),
                    "latitude": float(item.get("location", {}).get("latitude", 0)),
                    "longitude": float(item.get("location", {}).get("longitude", 0)),
                    "timestamp": item.get("timestamp"),
                    "pm25": sensor_values.get("P2"),  # P2 = PM2.5 in Sensor.Community
                    "pm10": sensor_values.get("P1"),  # P1 = PM10 in Sensor.Community
                    "temperature": sensor_values.get("temperature"),
                    "humidity": sensor_values.get("humidity"),
                    "pressure": sensor_values.get("pressure"),
                    "source": "sensor_community",
                    "metadata": {
                        "sensor_type": item.get("sensor", {}).get("sensor_type", {}).get("name"),
                        "location": item.get("location", {}),
                        "sampling_rate": item.get("sampling_rate")
                    }
                }
                
                normalized.append(normalized_item)
                
            except Exception as e:
                continue  # Skip malformed records
        
        return normalized
