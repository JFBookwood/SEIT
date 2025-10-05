import gibsService from '../../services/gibsService';
import React, { useState, useEffect, useRef, useCallback } from 'react';
import mapboxgl from 'mapbox-gl';
import 'mapbox-gl/dist/mapbox-gl.css';
import { Calendar, Play, Pause, Layers, RotateCcw, ZoomIn, ZoomOut } from 'lucide-react';

// Set Mapbox access token
mapboxgl.accessToken = import.meta.env.VITE_MAPBOX_ACCESS_TOKEN;

function MapboxContainer({ 
  sensorData = [], 
  weatherData = [],
  selectedLayer = null, 
  currentDate = new Date(), 
  onMarkerClick,
  onDateChange,
  onBoundsChange,
  className = ""
}) {
  const mapContainer = useRef(null);
  const map = useRef(null);
  const markersRef = useRef({});
  const [isPlaying, setIsPlaying] = useState(false);
  const [mapStyle, setMapStyle] = useState('mapbox://styles/mapbox/satellite-streets-v12');
  const [showWeatherLayer, setShowWeatherLayer] = useState(false);
  const [dateRange] = useState({
    start: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000), // 30 days ago
    end: new Date()
  });

  // Initialize map
  useEffect(() => {
    if (map.current) return; // Initialize map only once

    map.current = new mapboxgl.Map({
      container: mapContainer.current,
      style: mapStyle,
      center: [0, 20], // Global center
      zoom: 2,
      pitch: 0,
      bearing: 0,
      antialias: true
    });

    // Add navigation controls
    map.current.addControl(new mapboxgl.NavigationControl(), 'top-right');
    map.current.addControl(new mapboxgl.FullscreenControl(), 'top-right');

    // Add scale control
    map.current.addControl(new mapboxgl.ScaleControl({
      maxWidth: 80,
      unit: 'metric'
    }), 'bottom-left');

    // Handle bounds change
    map.current.on('moveend', () => {
      if (onBoundsChange) {
        const bounds = map.current.getBounds();
        onBoundsChange([
          bounds.getWest(),
          bounds.getSouth(),
          bounds.getEast(),
          bounds.getNorth()
        ]);
      }
    });

    return () => {
      if (map.current) {
        map.current.remove();
        map.current = null;
      }
    };
  }, []);

  // Update map style
  useEffect(() => {
    if (map.current) {
      map.current.setStyle(mapStyle);
    }
  }, [mapStyle]);

  // Add NASA GIBS layer
  useEffect(() => {
    if (!map.current || !selectedLayer) return;

    const layerId = 'nasa-gibs-layer';
    
    // Remove existing layer
    if (map.current.getLayer(layerId)) {
      map.current.removeLayer(layerId);
    }
    if (map.current.getSource(layerId)) {
      map.current.removeSource(layerId);
    }

    // Validate layer and generate proper GIBS URL
    const dateStr = gibsService.formatDate(currentDate);
    const validation = gibsService.validateLayer(selectedLayer.id, dateStr);
    
    if (!validation.valid) {
      console.error('Invalid GIBS layer:', validation.error);
      return;
    }

    // Generate proper GIBS tile URL template
    const gibsUrlTemplate = gibsService.generateTileUrl(
      selectedLayer.id, 
      dateStr, 
      '{z}', 
      '{x}', 
      '{y}', 
      validation.layer.format === 'jpeg' ? 'jpg' : 'png'
    );

    // Wait for style to load, then add layer
    const addGIBSLayer = () => {
      try {
        if (!map.current.getSource(layerId)) {
          map.current.addSource(layerId, {
            type: 'raster',
            tiles: [gibsUrlTemplate],
            tileSize: 256,
            attribution: '© NASA GIBS WMTS',
            minzoom: 0,
            maxzoom: 9
          });
        }

        if (!map.current.getLayer(layerId)) {
          map.current.addLayer({
            id: layerId,
            type: 'raster',
            source: layerId,
            paint: {
              'raster-opacity': 0.7,
              'raster-fade-duration': 300
            }
          }, 'waterway-label'); // Add before labels to prevent overlap
        }
      } catch (error) {
        console.error('Error adding GIBS layer:', error);
      }
    };

    if (map.current.isStyleLoaded()) {
      addGIBSLayer();
    } else {
      map.current.once('style.load', addGIBSLayer);
    }
  }, [selectedLayer, currentDate]);

  // Update sensor markers
  useEffect(() => {
    if (!map.current) return;
    
    // Clear existing markers
    Object.values(markersRef.current).forEach(marker => marker.remove());
    markersRef.current = {};

    if (!sensorData.length) {
      console.log('MapboxContainer: No sensor data to display');
      return;
    }

    // Add new markers
    sensorData.forEach(sensor => {
      console.log('Processing sensor:', sensor.sensor_id, sensor.latitude, sensor.longitude, sensor.source);
      
      // Validate coordinates before creating markers
      const lat = Number(sensor.latitude);
      const lng = Number(sensor.longitude);
      
      // Skip sensors with invalid or zero coordinates
      if (!lat || !lng || isNaN(lat) || isNaN(lng) || 
          lat < -85 || lat > 85 || lng < -180 || lng > 180) {
        console.warn('Skipping sensor with invalid coordinates:', sensor.sensor_id, lat, lng);
        return;
      }
      
      console.log('Creating marker for sensor:', sensor.sensor_id, 'at', lat, lng);
      
      const pm25Value = parseFloat(sensor.pm25) || 0;
      const severity = getSeverityLevel(pm25Value);
      const color = getSeverityColor(severity);

      // Create custom marker element
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
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 10px;
        font-weight: bold;
        color: white;
        text-shadow: 0 1px 2px rgba(0,0,0,0.8);
      `;

      // Add source indicator
      const sourceIndicators = {
        purpleair: 'P',
        sensor_community: 'S', 
        openaq: 'O'
      };
      el.textContent = sourceIndicators[sensor.source] || '•';
      
      // Create popup
      const popup = new mapboxgl.Popup({
        offset: 25,
        closeButton: true,
        closeOnClick: true
      }).setHTML(`
        <div class="sensor-popup">
          <h3 class="font-semibold text-sm mb-2">Sensor ${sensor.sensor_id}</h3>
          <div class="space-y-1 text-xs">
            <div><strong>PM2.5:</strong> ${sensor.pm25?.toFixed(1) || 'N/A'} μg/m³</div>
            <div><strong>PM10:</strong> ${sensor.pm10?.toFixed(1) || 'N/A'} μg/m³</div>
            ${sensor.temperature ? `<div><strong>Temp:</strong> ${sensor.temperature.toFixed(1)}°C</div>` : ''}
            ${sensor.humidity ? `<div><strong>Humidity:</strong> ${sensor.humidity.toFixed(1)}%</div>` : ''}
            <div class="text-neutral-500 mt-2"><strong>Source:</strong> ${sensor.source}</div>
            ${sensor.no2 ? `<div><strong>NO2:</strong> ${sensor.no2.toFixed(1)} μg/m³</div>` : ''}
            ${sensor.o3 ? `<div><strong>O3:</strong> ${sensor.o3.toFixed(1)} μg/m³</div>` : ''}
          </div>
        </div>
      `);

      // Create marker
      const marker = new mapboxgl.Marker({
        element: el,
        anchor: 'center'
      })
        .setLngLat([lng, lat])  // Mapbox uses [longitude, latitude] order
        .setPopup(popup)
        .addTo(map.current);

      // Add click handler
      el.addEventListener('click', () => {
        if (onMarkerClick) {
          onMarkerClick(sensor);
        }
      });
      
      markersRef.current[sensor.uniqueId || `${sensor.source}_${sensor.sensor_id}`] = marker;
    });
  }, [sensorData, onMarkerClick]);

  // Add weather data markers
  useEffect(() => {
    if (!map.current || !showWeatherLayer || !weatherData.length) return;
    
    // Add weather data as heat map or points
    weatherData.forEach(weather => {
      if (!weather.latitude || !weather.longitude) return;

      // Create custom marker element
      const el = document.createElement('div');
      el.className = 'weather-marker';
      el.style.cssText = `
        width: 12px;
        height: 12px;
        border-radius: 50%;
        background-color: ${getTemperatureColor(weather.temperature)};
        border: 1px solid white;
        opacity: 0.8;
      `;

      const popup = new mapboxgl.Popup({
        closeOnClick: true,
        anchor: 'bottom',
        offset: 15
      }).setHTML(`
        <div class="weather-popup">
          <h4 class="font-semibold text-xs mb-1">Weather Data</h4>
          <div class="text-xs space-y-0.5">
            <div><strong>Temperature:</strong> ${weather.temperature?.toFixed(1) || 'N/A'}°C</div>
            <div><strong>Humidity:</strong> ${weather.humidity?.toFixed(0) || 'N/A'}%</div>
            <div><strong>Pressure:</strong> ${weather.pressure?.toFixed(0) || 'N/A'} hPa</div>
            <div><strong>Wind:</strong> ${weather.wind_speed?.toFixed(1) || 'N/A'} m/s</div>
          </div>
        </div>
      `);

      new mapboxgl.Marker(el)
        .setLngLat([weather.longitude, weather.latitude])
        .setPopup(popup)
        .addTo(map.current);
    });
  }, [weatherData, showWeatherLayer]);

  // Helper functions
  const getSeverityLevel = (pm25Value) => {
    if (pm25Value > 55) return 'critical';
    if (pm25Value > 35) return 'high';
    if (pm25Value > 15) return 'moderate';
    return 'low';
  };
  
  const getSeverityColor = (severity) => {
    const colors = {
      low: '#10b981',
      moderate: '#f59e0b', 
      high: '#ef4444',
      critical: '#dc2626'
    };
    return colors[severity] || colors.low;
  };
  
  const getTemperatureColor = (temp) => {
    if (temp > 30) return '#ef4444';
    if (temp > 20) return '#f59e0b';
    if (temp > 10) return '#10b981';
    return '#3b82f6';
  };
  
  const handlePlayToggle = () => {
    setIsPlaying(!isPlaying);
  };
  
  const handleStyleChange = (newStyle) => {
    setMapStyle(newStyle);
  };

  const resetView = () => {
    if (map.current) {
      map.current.flyTo({
        center: [0, 20],
        zoom: 2,
        pitch: 0,
        bearing: 0
      });
    }
  };

  return (
    <div className={`relative ${className}`}>
      <div ref={mapContainer} className="w-full h-full" />
      
      {/* Map Controls */}
      <div className="absolute top-4 left-4 bg-white dark:bg-neutral-800 rounded-lg shadow-lg p-2 space-y-2">
        <div className="flex flex-col space-y-1">
          <button
            onClick={() => handleStyleChange('mapbox://styles/mapbox/satellite-streets-v12')}
            className={`px-3 py-1 text-xs rounded ${mapStyle.includes('satellite') ? 'bg-primary-600 text-white' : 'bg-neutral-100 text-neutral-700'}`}
            title="Switch to satellite view"
          >
            Satellite
          </button>
          <button
            onClick={() => handleStyleChange('mapbox://styles/mapbox/streets-v12')}
            className={`px-3 py-1 text-xs rounded ${mapStyle.includes('streets') ? 'bg-primary-600 text-white' : 'bg-neutral-100 text-neutral-700'}`}
            title="Switch to street map view"
          >
            Streets
          </button>
          <button
            onClick={() => handleStyleChange('mapbox://styles/mapbox/outdoors-v12')}
            className={`px-3 py-1 text-xs rounded ${mapStyle.includes('outdoors') ? 'bg-primary-600 text-white' : 'bg-neutral-100 text-neutral-700'}`}
            title="Switch to terrain view"
          >
            Terrain
          </button>
        </div>
        
        <div className="border-t pt-2">
          <button
            onClick={() => setShowWeatherLayer(!showWeatherLayer)}
            className={`w-full px-3 py-1 text-xs rounded ${showWeatherLayer ? 'bg-blue-600 text-white' : 'bg-neutral-100 text-neutral-700'}`}
            title={showWeatherLayer ? 'Hide weather layer' : 'Show weather layer'}
          >
            Weather Layer
          </button>
        </div>
        
        <div className="border-t pt-2">
          <button
            onClick={resetView}
            className="w-full px-3 py-1 text-xs rounded bg-neutral-100 hover:bg-neutral-200 text-neutral-700"
            title="Reset map view to default position"
          >
            <RotateCcw className="w-3 h-3 inline mr-1" />
            Reset View
          </button>
        </div>
      </div>
      
      {/* Time Controls */}
      <div className="absolute bottom-4 left-4 right-4 bg-white dark:bg-neutral-800 rounded-lg shadow-lg p-4">
        <div className="flex items-center space-x-4">
          <button
            onClick={handlePlayToggle}
            className="p-2 rounded-lg bg-primary-600 hover:bg-primary-700 text-white transition-colors"
          >
            {isPlaying ? <Pause className="w-5 h-5" /> : <Play className="w-5 h-5" />}
          </button>
          
          <div className="flex-1">
            <input
              type="date"
              value={currentDate.toISOString().split('T')[0]}
              onChange={(e) => onDateChange(new Date(e.target.value))}
              min={dateRange.start.toISOString().split('T')[0]}
              max={dateRange.end.toISOString().split('T')[0]}
              className="w-full px-3 py-2 border border-neutral-300 dark:border-neutral-600 rounded-lg bg-white dark:bg-neutral-800 text-neutral-900 dark:text-white"
            />
          </div>
          
          <span className="text-sm text-neutral-600 dark:text-neutral-300 min-w-max">
            {currentDate.toLocaleDateString()}
          </span>
        </div>
      </div>

      {/* Legend */}
      <div className="absolute bottom-20 right-4 z-30 bg-white dark:bg-neutral-800 rounded-lg shadow-lg p-3">
        <h4 className="text-xs font-semibold mb-2">Air Quality</h4>
        <div className="space-y-1">
          <div className="flex items-center space-x-2">
            <div className="w-3 h-3 rounded-full bg-green-500"></div>
            <span className="text-xs">Good (0-15)</span>
          </div>
          <div className="flex items-center space-x-2">
            <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
            <span className="text-xs">Moderate (15-35)</span>
          </div>
          <div className="flex items-center space-x-2">
            <div className="w-3 h-3 rounded-full bg-red-500"></div>
            <span className="text-xs">Unhealthy (35+)</span>
          </div>
          <div className="flex items-center space-x-2">
            <div className="w-3 h-3 rounded-full bg-red-800"></div>
            <span className="text-xs">Critical (55+)</span>
          </div>
        </div>
        
        {/* Source Legend */}
        <div className="mt-3 pt-2 border-t border-neutral-200 dark:border-neutral-600">
          <h5 className="text-xs font-semibold mb-1">Data Sources</h5>
          <div className="space-y-1">
            <div className="flex items-center space-x-2">
              <div className="w-3 h-3 rounded-full bg-blue-500 text-white text-xs flex items-center justify-center font-bold" style={{fontSize: '8px'}}>P</div>
              <span className="text-xs">PurpleAir</span>
            </div>
            <div className="flex items-center space-x-2">
              <div className="w-3 h-3 rounded-full bg-green-600 text-white text-xs flex items-center justify-center font-bold" style={{fontSize: '8px'}}>S</div>
              <span className="text-xs">Sensor.Community</span>
            </div>
            <div className="flex items-center space-x-2">
              <div className="w-3 h-3 rounded-full bg-purple-600 text-white text-xs flex items-center justify-center font-bold" style={{fontSize: '8px'}}>O</div>
              <span className="text-xs">OpenAQ</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default MapboxContainer;