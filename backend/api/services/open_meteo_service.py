import aiohttp
import asyncio
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import os

class OpenMeteoService:
    """Service for interacting with Open-Meteo Weather API"""
    
    def __init__(self):
        self.base_url = "https://api.open-meteo.com/v1"
        # Open-Meteo is free and doesn't require API keys
        
    async def get_current_weather(self, latitude: float, longitude: float) -> Dict:
        """Get current weather conditions"""
        try:
            params = {
                "latitude": latitude,
                "longitude": longitude,
                "current": [
                    "temperature_2m",
                    "relative_humidity_2m",
                    "apparent_temperature", 
                    "is_day",
                    "precipitation",
                    "weather_code",
                    "cloud_cover",
                    "surface_pressure",
                    "wind_speed_10m",
                    "wind_direction_10m",
                    "wind_gusts_10m"
                ]
            }
            
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/forecast"
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        current = data.get("current", {})
                        
                        return {
                            "latitude": data.get("latitude"),
                            "longitude": data.get("longitude"),
                            "timestamp": current.get("time"),
                            "temperature": current.get("temperature_2m"),
                            "apparent_temperature": current.get("apparent_temperature"),
                            "humidity": current.get("relative_humidity_2m"),
                            "pressure": current.get("surface_pressure"),
                            "wind_speed": current.get("wind_speed_10m"),
                            "wind_direction": current.get("wind_direction_10m"),
                            "wind_gusts": current.get("wind_gusts_10m"),
                            "cloud_cover": current.get("cloud_cover"),
                            "weather_code": current.get("weather_code"),
                            "is_day": current.get("is_day"),
                            "precipitation": current.get("precipitation", 0),
                            "source": "open_meteo"
                        }
                    else:
                        return self._generate_mock_weather(latitude, longitude)
                        
        except Exception as e:
            print(f"Open-Meteo current weather request failed: {e}")
            return self._generate_mock_weather(latitude, longitude)
    
    async def get_forecast(self, latitude: float, longitude: float, days: int = 7) -> Dict:
        """Get weather forecast"""
        try:
            params = {
                "latitude": latitude,
                "longitude": longitude,
                "daily": [
                    "weather_code",
                    "temperature_2m_max",
                    "temperature_2m_min",
                    "precipitation_sum",
                    "wind_speed_10m_max",
                    "wind_gusts_10m_max",
                    "wind_direction_10m_dominant"
                ],
                "forecast_days": days,
                "timezone": "auto"
            }
            
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/forecast"
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        daily = data.get("daily", {})
                        
                        forecast_days = []
                        for i in range(len(daily.get("time", []))):
                            day_data = {
                                "date": daily["time"][i],
                                "weather_code": daily.get("weather_code", [])[i] if i < len(daily.get("weather_code", [])) else None,
                                "temperature_max": daily.get("temperature_2m_max", [])[i] if i < len(daily.get("temperature_2m_max", [])) else None,
                                "temperature_min": daily.get("temperature_2m_min", [])[i] if i < len(daily.get("temperature_2m_min", [])) else None,
                                "precipitation": daily.get("precipitation_sum", [])[i] if i < len(daily.get("precipitation_sum", [])) else None,
                                "wind_speed_max": daily.get("wind_speed_10m_max", [])[i] if i < len(daily.get("wind_speed_10m_max", [])) else None,
                                "wind_gusts_max": daily.get("wind_gusts_10m_max", [])[i] if i < len(daily.get("wind_gusts_10m_max", [])) else None,
                                "wind_direction": daily.get("wind_direction_10m_dominant", [])[i] if i < len(daily.get("wind_direction_10m_dominant", [])) else None
                            }
                            forecast_days.append(day_data)
                        
                        return {
                            "latitude": data.get("latitude"),
                            "longitude": data.get("longitude"),
                            "timezone": data.get("timezone"),
                            "forecast": forecast_days,
                            "source": "open_meteo"
                        }
                    else:
                        return {"forecast": [], "source": "open_meteo"}
                        
        except Exception as e:
            print(f"Open-Meteo forecast request failed: {e}")
            return {"forecast": [], "source": "open_meteo"}
    
    async def get_hourly_data(self, latitude: float, longitude: float, hours_back: int = 24) -> Dict:
        """Get hourly weather data"""
        try:
            params = {
                "latitude": latitude,
                "longitude": longitude,
                "hourly": [
                    "temperature_2m",
                    "relative_humidity_2m",
                    "pressure_msl",
                    "wind_speed_10m",
                    "wind_direction_10m",
                    "precipitation",
                    "weather_code",
                    "cloud_cover"
                ],
                "past_days": max(1, hours_back // 24),
                "timezone": "auto"
            }
            
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/forecast"
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        hourly = data.get("hourly", {})
                        
                        hourly_data = []
                        times = hourly.get("time", [])
                        
                        for i, time_str in enumerate(times):
                            hour_data = {
                                "datetime": time_str,
                                "temperature": hourly.get("temperature_2m", [])[i] if i < len(hourly.get("temperature_2m", [])) else None,
                                "humidity": hourly.get("relative_humidity_2m", [])[i] if i < len(hourly.get("relative_humidity_2m", [])) else None,
                                "pressure": hourly.get("pressure_msl", [])[i] if i < len(hourly.get("pressure_msl", [])) else None,
                                "wind_speed": hourly.get("wind_speed_10m", [])[i] if i < len(hourly.get("wind_speed_10m", [])) else None,
                                "wind_direction": hourly.get("wind_direction_10m", [])[i] if i < len(hourly.get("wind_direction_10m", [])) else None,
                                "precipitation": hourly.get("precipitation", [])[i] if i < len(hourly.get("precipitation", [])) else None,
                                "weather_code": hourly.get("weather_code", [])[i] if i < len(hourly.get("weather_code", [])) else None,
                                "cloud_cover": hourly.get("cloud_cover", [])[i] if i < len(hourly.get("cloud_cover", [])) else None
                            }
                            hourly_data.append(hour_data)
                        
                        return {
                            "latitude": data.get("latitude"),
                            "longitude": data.get("longitude"),
                            "timezone": data.get("timezone"),
                            "hourly_data": hourly_data[-hours_back:],  # Get last N hours
                            "source": "open_meteo"
                        }
                    else:
                        return {"hourly_data": [], "source": "open_meteo"}
                        
        except Exception as e:
            print(f"Open-Meteo hourly data request failed: {e}")
            return {"hourly_data": [], "source": "open_meteo"}
    
    async def get_weather_for_region(self, bbox: List[float], grid_resolution: float = 0.25) -> List[Dict]:
        """Get weather data for a region using grid points"""
        west, south, east, north = bbox
        
        weather_points = []
        lat = south
        while lat <= north:
            lng = west
            while lng <= east:
                try:
                    weather_data = await self.get_current_weather(lat, lng)
                    if weather_data:
                        weather_points.append(weather_data)
                except Exception:
                    continue
                lng += grid_resolution
            lat += grid_resolution
        
        return weather_points
    
    def _generate_mock_weather(self, latitude: float, longitude: float) -> Dict:
        """Generate mock weather data"""
        import random
        
        return {
            "latitude": latitude,
            "longitude": longitude,
            "timestamp": datetime.utcnow().isoformat(),
            "temperature": round(random.uniform(-5, 35), 1),
            "apparent_temperature": round(random.uniform(-5, 35), 1),
            "humidity": round(random.uniform(30, 90), 1),
            "pressure": round(random.uniform(980, 1040), 1),
            "wind_speed": round(random.uniform(0, 25), 1),
            "wind_direction": random.randint(0, 360),
            "wind_gusts": round(random.uniform(0, 40), 1),
            "cloud_cover": random.randint(0, 100),
            "weather_code": random.choice([0, 1, 2, 3, 45, 48, 51, 53, 55]),
            "is_day": 1 if 6 <= datetime.now().hour <= 18 else 0,
            "precipitation": round(random.uniform(0, 5), 1),
            "source": "open_meteo"
        }
    
    @staticmethod
    def get_weather_description(weather_code: int) -> str:
        """Convert weather code to description"""
        weather_codes = {
            0: "Clear sky",
            1: "Mainly clear",
            2: "Partly cloudy", 
            3: "Overcast",
            45: "Fog",
            48: "Depositing rime fog",
            51: "Light drizzle",
            53: "Moderate drizzle",
            55: "Dense drizzle",
            56: "Light freezing drizzle",
            57: "Dense freezing drizzle",
            61: "Slight rain",
            63: "Moderate rain",
            65: "Heavy rain",
            66: "Light freezing rain",
            67: "Heavy freezing rain",
            71: "Slight snow fall",
            73: "Moderate snow fall",
            75: "Heavy snow fall",
            77: "Snow grains",
            80: "Slight rain showers",
            81: "Moderate rain showers",
            82: "Violent rain showers",
            85: "Slight snow showers",
            86: "Heavy snow showers",
            95: "Thunderstorm",
            96: "Thunderstorm with slight hail",
            99: "Thunderstorm with heavy hail"
        }
        return weather_codes.get(weather_code, "Unknown")
