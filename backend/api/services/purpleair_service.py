import aiohttp
import asyncio
from typing import Dict, List, Optional
import os
from datetime import datetime, timedelta

class PurpleAirService:
    """Service for interacting with PurpleAir API"""
    
    def __init__(self):
        self.api_key = os.getenv("PURPLEAIR_API_KEY")
        self.base_url = "https://api.purpleair.com/v1"
        
        if not self.api_key:
            print("Warning: PURPLEAIR_API_KEY not found. Using mock data.")
    
    async def get_sensors(self, bbox: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """Get PurpleAir sensors, optionally filtered by bounding box"""
        try:
            if not self.api_key:
                return self._generate_mock_sensors(bbox, limit)
            
            headers = {"X-API-Key": self.api_key}
            params = {
                "fields": "sensor_index,name,latitude,longitude,altitude,location_type,pm2.5,temperature,humidity,pressure,last_seen"
            }
            
            if bbox:
                west, south, east, north = map(float, bbox.split(','))
                params["nwlat"] = north
                params["nwlng"] = west
                params["selat"] = south
                params["selng"] = east
            
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/sensors"
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        sensors = data.get("data", [])
                        
                        # Convert to standardized format
                        formatted_sensors = []
                        for sensor in sensors[:limit]:
                            formatted_sensor = {
                                "sensor_index": sensor[0],
                                "name": sensor[1],
                                "latitude": sensor[2],
                                "longitude": sensor[3],
                                "altitude": sensor[4] if len(sensor) > 4 else None,
                                "location_type": sensor[5] if len(sensor) > 5 else None,
                                "pm25": sensor[6] if len(sensor) > 6 else None,
                                "temperature": sensor[7] if len(sensor) > 7 else None,
                                "humidity": sensor[8] if len(sensor) > 8 else None,
                                "pressure": sensor[9] if len(sensor) > 9 else None,
                                "last_seen": sensor[10] if len(sensor) > 10 else None
                            }
                            formatted_sensors.append(formatted_sensor)
                        
                        return formatted_sensors
                    else:
                        print(f"PurpleAir API error: {response.status}")
                        return self._generate_mock_sensors(bbox, limit)
                        
        except Exception as e:
            print(f"PurpleAir API request failed: {e}")
            return self._generate_mock_sensors(bbox, limit)
    
    async def get_sensor_history(
        self, 
        sensor_id: int, 
        start_timestamp: int, 
        end_timestamp: int, 
        average: int = 60
    ) -> List[Dict]:
        """Get historical data for a specific sensor"""
        try:
            if not self.api_key:
                return self._generate_mock_history(sensor_id, start_timestamp, end_timestamp)
            
            headers = {"X-API-Key": self.api_key}
            params = {
                "start_timestamp": start_timestamp,
                "end_timestamp": end_timestamp,
                "average": average,
                "fields": "pm2.5_atm,pm10.0_atm,temperature,humidity,pressure"
            }
            
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/sensors/{sensor_id}/history"
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Convert to standardized format
                        history = []
                        for record in data.get("data", []):
                            formatted_record = {
                                "time_stamp": record[0],
                                "pm2.5_atm": record[1] if len(record) > 1 else None,
                                "pm10.0_atm": record[2] if len(record) > 2 else None,
                                "temperature": record[3] if len(record) > 3 else None,
                                "humidity": record[4] if len(record) > 4 else None,
                                "pressure": record[5] if len(record) > 5 else None
                            }
                            history.append(formatted_record)
                        
                        return history
                    else:
                        print(f"PurpleAir history API error: {response.status}")
                        return self._generate_mock_history(sensor_id, start_timestamp, end_timestamp)
                        
        except Exception as e:
            print(f"PurpleAir history request failed: {e}")
            return self._generate_mock_history(sensor_id, start_timestamp, end_timestamp)
    
    def _generate_mock_sensors(self, bbox: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """Generate mock sensor data for testing"""
        import random
        
        # Land-based coordinates in SF Bay Area - avoid water
        if bbox:
            west, south, east, north = map(float, bbox.split(','))
        else:
            west, south, east, north = -122.45, 37.35, -122.15, 37.75
        
        # Define land-based areas in SF Bay
        land_zones = [
            {"lat": 37.7849, "lng": -122.4094, "radius": 0.02},  # SF downtown
            {"lat": 37.8044, "lng": -122.2711, "radius": 0.015}, # Oakland
            {"lat": 37.6879, "lng": -122.4702, "radius": 0.01},  # Daly City
            {"lat": 37.4419, "lng": -122.1430, "radius": 0.02},  # Palo Alto
            {"lat": 37.3382, "lng": -121.8863, "radius": 0.025}  # San Jose
        ]
        
        sensors = []
        for i in range(min(limit, 25)):  # Limit mock data
            # Choose a land zone and place sensor within it
            zone = random.choice(land_zones)
            lat = zone["lat"] + (random.random() - 0.5) * zone["radius"]
            lng = zone["lng"] + (random.random() - 0.5) * zone["radius"]
            
            sensor = {
                "sensor_index": 100000 + i,
                "name": f"Mock Sensor {i + 1}",
                "latitude": round(lat, 6),
                "longitude": round(lng, 6),
                "altitude": random.randint(0, 500),
                "location_type": random.choice(["outside", "inside"]),
                "pm25": round(random.uniform(5, 50), 1),
                "temperature": round(random.uniform(15, 30), 1),
                "humidity": round(random.uniform(30, 80), 1),
                "pressure": round(random.uniform(1000, 1030), 1),
                "last_seen": int(datetime.utcnow().timestamp())
            }
            sensors.append(sensor)
        
        return sensors
    
    def _generate_mock_history(
        self, 
        sensor_id: int, 
        start_timestamp: int, 
        end_timestamp: int
    ) -> List[Dict]:
        """Generate mock historical data"""
        import random
        
        history = []
        current = start_timestamp
        
        # Generate hourly data points
        while current <= end_timestamp:
            record = {
                "time_stamp": current,
                "pm2.5_atm": round(random.uniform(8, 35), 1),
                "pm10.0_atm": round(random.uniform(15, 60), 1),
                "temperature": round(random.uniform(18, 28), 1),
                "humidity": round(random.uniform(40, 75), 1),
                "pressure": round(random.uniform(1005, 1025), 1)
            }
            history.append(record)
            current += 3600  # Add 1 hour
        
        return history[:100]  # Limit mock data points
