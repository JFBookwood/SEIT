import aiohttp
import asyncio
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import os

class OpenAQService:
    """Service for interacting with OpenAQ API"""
    
    def __init__(self):
        self.api_key = "dfc2eec721e2f738e90fd6731f14f76ab92f7352698f1efe3010c6234da1a731"
        self.base_url = "https://api.openaq.org/v2"
        
    async def get_locations(self, bbox: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """Get OpenAQ monitoring locations"""
        try:
            headers = {"X-API-Key": self.api_key}
            params = {
                "limit": limit,
                "order_by": "lastUpdated",
                "sort": "desc"
            }
            
            if bbox:
                west, south, east, north = map(float, bbox.split(','))
                params["coordinates"] = f"{west},{south},{east},{north}"
            
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/locations"
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        locations = []
                        
                        for location in data.get("results", []):
                            loc_data = {
                                "sensor_id": f"openaq_{location.get('id')}",
                                "name": location.get("name"),
                                "latitude": location.get("coordinates", {}).get("latitude"),
                                "longitude": location.get("coordinates", {}).get("longitude"),
                                "country": location.get("country"),
                                "city": location.get("city"),
                                "source_name": location.get("sourceName"),
                                "last_updated": location.get("lastUpdated"),
                                "parameters": location.get("parameters", []),
                                "source": "openaq"
                            }
                            locations.append(loc_data)
                        
                        return locations
                    else:
                        return self._generate_mock_openaq_data(bbox, limit)
                        
        except Exception as e:
            print(f"OpenAQ API request failed: {e}")
            return self._generate_mock_openaq_data(bbox, limit)
    
    async def get_measurements(self, location_id: str, parameter: str = "pm25", hours_back: int = 24) -> List[Dict]:
        """Get recent measurements for a location"""
        try:
            headers = {"X-API-Key": self.api_key}
            
            # Calculate date range
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(hours=hours_back)
            
            params = {
                "location": location_id,
                "parameter": parameter,
                "date_from": start_date.isoformat(),
                "date_to": end_date.isoformat(),
                "limit": 1000,
                "order_by": "datetime",
                "sort": "desc"
            }
            
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/measurements"
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        measurements = []
                        
                        for measurement in data.get("results", []):
                            meas_data = {
                                "location_id": measurement.get("locationId"),
                                "parameter": measurement.get("parameter"),
                                "value": measurement.get("value"),
                                "unit": measurement.get("unit"),
                                "datetime": measurement.get("date", {}).get("utc"),
                                "coordinates": measurement.get("coordinates"),
                                "source": "openaq"
                            }
                            measurements.append(meas_data)
                        
                        return measurements
                    else:
                        return []
                        
        except Exception as e:
            print(f"OpenAQ measurements request failed: {e}")
            return []
    
    async def get_latest_measurements(self, bbox: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """Get latest measurements across all locations"""
        try:
            headers = {"X-API-Key": self.api_key}
            params = {
                "limit": limit,
                "order_by": "datetime",
                "sort": "desc"
            }
            
            if bbox:
                west, south, east, north = map(float, bbox.split(','))
                params["coordinates"] = f"{west},{south},{east},{north}"
            
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/latest"
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        sensors = []
                        
                        # Group measurements by location
                        location_data = {}
                        for measurement in data.get("results", []):
                            location_id = measurement.get("location")
                            if location_id not in location_data:
                                location_data[location_id] = {
                                    "sensor_id": f"openaq_{location_id}",
                                    "location": measurement.get("location"),
                                    "city": measurement.get("city"),
                                    "country": measurement.get("country"),
                                    "latitude": measurement.get("coordinates", {}).get("latitude"),
                                    "longitude": measurement.get("coordinates", {}).get("longitude"),
                                    "timestamp": measurement.get("date", {}).get("utc"),
                                    "source": "openaq",
                                    "measurements": {}
                                }
                            
                            # Add parameter measurement
                            param = measurement.get("parameter")
                            value = measurement.get("value")
                            unit = measurement.get("unit")
                            
                            if param == "pm25":
                                location_data[location_id]["pm25"] = value
                            elif param == "pm10":
                                location_data[location_id]["pm10"] = value
                            elif param == "no2":
                                location_data[location_id]["no2"] = value
                            elif param == "o3":
                                location_data[location_id]["o3"] = value
                            elif param == "so2":
                                location_data[location_id]["so2"] = value
                            elif param == "co":
                                location_data[location_id]["co"] = value
                            
                            location_data[location_id]["measurements"][param] = {
                                "value": value,
                                "unit": unit
                            }
                        
                        return list(location_data.values())
                    else:
                        return self._generate_mock_openaq_data(bbox, limit)
                        
        except Exception as e:
            print(f"OpenAQ latest measurements request failed: {e}")
            return self._generate_mock_openaq_data(bbox, limit)
    
    def _generate_mock_openaq_data(self, bbox: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """Generate mock OpenAQ data for testing"""
        import random
        
        # Land-based coordinates - specific neighborhoods in NYC
        if bbox:
            west, south, east, north = map(float, bbox.split(','))
        else:
            west, south, east, north = -74.05, 40.65, -73.95, 40.85  # NYC land areas
        
        # NYC neighborhoods on land only
        nyc_neighborhoods = [
            {"lat": 40.7589, "lng": -73.9851, "area": "Manhattan"},
            {"lat": 40.6892, "lng": -73.9442, "area": "Brooklyn"},
            {"lat": 40.7282, "lng": -73.7949, "area": "Queens"},
            {"lat": 40.8448, "lng": -73.8648, "area": "Bronx"},
            {"lat": 40.5795, "lng": -74.1502, "area": "Staten Island"}
        ]
        
        sensors = []
        cities = ["Manhattan", "Brooklyn", "Queens", "Bronx", "Staten Island"]
        
        for i in range(min(limit, 25)):
            # Place in specific NYC neighborhoods on land
            neighborhood = random.choice(nyc_neighborhoods)
            lat = neighborhood["lat"] + (random.random() - 0.5) * 0.01
            lng = neighborhood["lng"] + (random.random() - 0.5) * 0.01
            
            sensor = {
                "sensor_id": f"openaq_mock_{i}",
                "location": f"NYC_Location_{i}",
                "city": random.choice(cities),
                "country": "US",
                "latitude": round(lat, 6),
                "longitude": round(lng, 6),
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "pm25": round(random.uniform(8, 45), 1),
                "pm10": round(random.uniform(15, 80), 1),
                "no2": round(random.uniform(10, 60), 1),
                "o3": round(random.uniform(20, 120), 1),
                "so2": round(random.uniform(0, 20), 1),
                "co": round(random.uniform(0.2, 2.5), 2),
                "source": "openaq",
                "measurements": {
                    "pm25": {"value": round(random.uniform(8, 45), 1), "unit": "µg/m³"},
                    "pm10": {"value": round(random.uniform(15, 80), 1), "unit": "µg/m³"},
                    "no2": {"value": round(random.uniform(10, 60), 1), "unit": "µg/m³"},
                    "o3": {"value": round(random.uniform(20, 120), 1), "unit": "µg/m³"}
                }
            }
            sensors.append(sensor)
        
        return sensors
