import mapboxgl from 'mapbox-gl';

class MapboxService {
  constructor() {
    this.accessToken = import.meta.env.VITE_MAPBOX_ACCESS_TOKEN;
    mapboxgl.accessToken = this.accessToken;
  }

  // Map styles available
  getMapStyles() {
    return {
      satellite: 'mapbox://styles/mapbox/satellite-streets-v12',
      streets: 'mapbox://styles/mapbox/streets-v12',
      outdoors: 'mapbox://styles/mapbox/outdoors-v12',
      light: 'mapbox://styles/mapbox/light-v11',
      dark: 'mapbox://styles/mapbox/dark-v11',
      navigation: 'mapbox://styles/mapbox/navigation-day-v1',
      navigation_night: 'mapbox://styles/mapbox/navigation-night-v1'
    };
  }

  // Create custom marker for sensor data
  createSensorMarker(sensor, onClick) {
    const severity = this.getSeverityLevel(sensor.pm25 || 0);
    const color = this.getSeverityColor(severity);
    
    const el = document.createElement('div');
    el.className = 'sensor-marker';
    el.style.cssText = `
      width: 20px;
      height: 20px;
      border-radius: 50%;
      background-color: ${color};
      border: 2px solid white;
      box-shadow: 0 2px 4px rgba(0,0,0,0.3);
      cursor: pointer;
      transition: transform 0.2s ease;
      transform-origin: center center;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 10px;
      font-weight: bold;
      color: white;
      text-shadow: 0 1px 2px rgba(0,0,0,0.5);
    `;

    // Add sensor source indicator
    const sourceIndicator = {
      purpleair: 'P',
      sensor_community: 'S',
      openaq: 'O'
    };
    el.textContent = sourceIndicator[sensor.source] || '•';

    // Hover effects
    el.addEventListener('mouseenter', () => {
      el.style.transform = 'scale(1.3)';
      el.style.transformOrigin = 'center center';
      el.style.zIndex = '1000';
    });
    
    el.addEventListener('mouseleave', () => {
      el.style.transform = 'scale(1)';
      el.style.transformOrigin = 'center center';
      el.style.zIndex = '1';
    });

    // Click handler
    el.addEventListener('click', () => {
      if (onClick) onClick(sensor);
    });

    return el;
  }

  // Create weather marker
  createWeatherMarker(weather) {
    const el = document.createElement('div');
    el.className = 'weather-marker';
    
    const tempColor = this.getTemperatureColor(weather.temperature);
    
    el.style.cssText = `
      width: 16px;
      height: 16px;
      border-radius: 50%;
      background: linear-gradient(135deg, ${tempColor}, ${tempColor}aa);
      border: 2px solid white;
      box-shadow: 0 1px 3px rgba(0,0,0,0.3);
      opacity: 0.9;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 8px;
      font-weight: bold;
      color: white;
    `;

    // Add temperature indicator
    if (weather.temperature) {
      el.textContent = Math.round(weather.temperature) + '°';
    }

    return el;
  }

  // Create popup content for sensors
  createSensorPopup(sensor) {
    const severityLevel = this.getSeverityLevel(sensor.pm25 || 0);
    const severityColor = this.getSeverityColor(severityLevel);
    
    return `
      <div class="sensor-popup max-w-xs">
        <div class="flex items-center justify-between mb-2">
          <h3 class="font-semibold text-sm">${sensor.name || `Sensor ${sensor.sensor_id}`}</h3>
          <span class="px-2 py-1 text-xs rounded" style="background-color: ${severityColor}20; color: ${severityColor}">
            ${severityLevel.toUpperCase()}
          </span>
        </div>
        
        <div class="grid grid-cols-2 gap-2 text-xs">
          <div class="space-y-1">
            <div><strong>PM2.5:</strong> ${sensor.pm25?.toFixed(1) || 'N/A'} μg/m³</div>
            <div><strong>PM10:</strong> ${sensor.pm10?.toFixed(1) || 'N/A'} μg/m³</div>
            ${sensor.temperature ? `<div><strong>Temp:</strong> ${sensor.temperature.toFixed(1)}°C</div>` : ''}
            ${sensor.humidity ? `<div><strong>Humidity:</strong> ${sensor.humidity.toFixed(1)}%</div>` : ''}
          </div>
          
          <div class="space-y-1">
            ${sensor.no2 ? `<div><strong>NO2:</strong> ${sensor.no2.toFixed(1)} μg/m³</div>` : ''}
            ${sensor.o3 ? `<div><strong>O3:</strong> ${sensor.o3.toFixed(1)} μg/m³</div>` : ''}
            ${sensor.so2 ? `<div><strong>SO2:</strong> ${sensor.so2.toFixed(1)} μg/m³</div>` : ''}
            ${sensor.co ? `<div><strong>CO:</strong> ${sensor.co.toFixed(2)} mg/m³</div>` : ''}
          </div>
        </div>
        
        <div class="mt-3 pt-2 border-t text-xs text-neutral-500">
          <div><strong>Source:</strong> ${this.getSourceName(sensor.source)}</div>
          <div><strong>Location:</strong> ${sensor.latitude?.toFixed(4)}, ${sensor.longitude?.toFixed(4)}</div>
          ${sensor.timestamp ? `<div><strong>Updated:</strong> ${new Date(sensor.timestamp).toLocaleString()}</div>` : ''}
        </div>
      </div>
    `;
  }

  // Create popup content for weather
  createWeatherPopup(weather) {
    return `
      <div class="weather-popup max-w-xs">
        <h4 class="font-semibold text-sm mb-2">Weather Conditions</h4>
        
        <div class="grid grid-cols-2 gap-2 text-xs">
          <div class="space-y-1">
            <div><strong>Temperature:</strong> ${weather.temperature?.toFixed(1) || 'N/A'}°C</div>
            <div><strong>Feels like:</strong> ${weather.apparent_temperature?.toFixed(1) || 'N/A'}°C</div>
            <div><strong>Humidity:</strong> ${weather.humidity?.toFixed(0) || 'N/A'}%</div>
            <div><strong>Pressure:</strong> ${weather.pressure?.toFixed(0) || 'N/A'} hPa</div>
          </div>
          
          <div class="space-y-1">
            <div><strong>Wind Speed:</strong> ${weather.wind_speed?.toFixed(1) || 'N/A'} m/s</div>
            <div><strong>Wind Dir:</strong> ${weather.wind_direction || 'N/A'}°</div>
            <div><strong>Cloud Cover:</strong> ${weather.cloud_cover || 'N/A'}%</div>
            <div><strong>Precipitation:</strong> ${weather.precipitation?.toFixed(1) || '0'} mm</div>
          </div>
        </div>
        
        <div class="mt-3 pt-2 border-t text-xs text-neutral-500">
          <div><strong>Location:</strong> ${weather.latitude?.toFixed(4)}, ${weather.longitude?.toFixed(4)}</div>
          <div><strong>Source:</strong> Open-Meteo</div>
        </div>
      </div>
    `;
  }

  // Add NASA GIBS layer to map
  addGIBSLayer(map, layerId, date) {
    const sourceId = `gibs-${layerId}`;
    const dateStr = date.toISOString().split('T')[0];
    
    // Remove existing layer if present
    if (map.getLayer(sourceId)) {
      map.removeLayer(sourceId);
    }
    if (map.getSource(sourceId)) {
      map.removeSource(sourceId);
    }

    // Construct GIBS tile URL
    const gibsUrl = `https://gibs.earthdata.nasa.gov/wmts/epsg4326/best/${layerId}/default/${dateStr}/250m/{z}/{y}/{x}.jpg`;

    // Add source and layer
    map.addSource(sourceId, {
      type: 'raster',
      tiles: [gibsUrl],
      tileSize: 256,
      attribution: '© NASA GIBS'
    });

    map.addLayer({
      id: sourceId,
      type: 'raster',
      source: sourceId,
      paint: {
        'raster-opacity': 0.7,
        'raster-fade-duration': 300
      }
    });

    return sourceId;
  }

  // Helper methods
  getSeverityLevel(pm25Value) {
    if (pm25Value > 150) return 'hazardous';
    if (pm25Value > 55) return 'very_unhealthy';
    if (pm25Value > 35) return 'unhealthy';
    if (pm25Value > 15) return 'moderate';
    return 'good';
  }

  getSeverityColor(severity) {
    const colors = {
      good: '#10b981',
      moderate: '#f59e0b',
      unhealthy: '#ef4444',
      very_unhealthy: '#dc2626',
      hazardous: '#991b1b'
    };
    return colors[severity] || colors.good;
  }

  getTemperatureColor(temp) {
    if (temp >= 35) return '#dc2626'; // Very hot - red
    if (temp >= 25) return '#f59e0b'; // Warm - orange  
    if (temp >= 15) return '#10b981'; // Mild - green
    if (temp >= 5) return '#3b82f6';  // Cool - blue
    return '#6366f1'; // Cold - indigo
  }

  getSourceName(source) {
    const names = {
      purpleair: 'PurpleAir',
      sensor_community: 'Sensor.Community',
      openaq: 'OpenAQ',
      weather: 'Open-Meteo Weather'
    };
    return names[source] || source;
  }

  // Calculate bounds for sensor data
  calculateBounds(sensors) {
    if (!sensors.length) return null;

    let minLat = Infinity, maxLat = -Infinity;
    let minLng = Infinity, maxLng = -Infinity;

    sensors.forEach(sensor => {
      if (sensor.latitude && sensor.longitude) {
        minLat = Math.min(minLat, sensor.latitude);
        maxLat = Math.max(maxLat, sensor.latitude);
        minLng = Math.min(minLng, sensor.longitude);
        maxLng = Math.max(maxLng, sensor.longitude);
      }
    });

    return [[minLng, minLat], [maxLng, maxLat]];
  }

  // Fit map to bounds
  fitToBounds(map, sensors, padding = 50) {
    const bounds = this.calculateBounds(sensors);
    if (bounds) {
      map.fitBounds(bounds, { padding });
    }
  }
}

export default new MapboxService();
