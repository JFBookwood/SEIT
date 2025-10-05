import React, { useState, useEffect, useRef } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import { LatLngBounds } from 'leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import { Calendar, Play, Pause, SkipForward } from 'lucide-react';

// Fix for default markers
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
});

import gibsService from '../../services/gibsService';
function GIBSTileLayer({ layerId, date, opacity = 0.8 }) {
  const map = useMap();
  
  useEffect(() => {
    if (!layerId || !date) return;
    
    // Generate GIBS tile URL
    const gibsUrl = `https://gibs.earthdata.nasa.gov/wmts/epsg4326/best/${layerId}/default/${date}/250m/{z}/{y}/{x}.jpg`;
    
    const tileLayer = L.tileLayer(gibsUrl, {
      opacity: opacity,
      attribution: '© NASA GIBS',
      bounds: [[-85, -180], [85, 180]]
    });
    
    tileLayer.addTo(map);
    
    return () => {
      map.removeLayer(tileLayer);
    };
  }, [map, layerId, date, opacity]);
  
  return null;
}

function TimeSlider({ currentDate, onDateChange, dateRange, isPlaying, onPlayToggle }) {
  const [localDate, setLocalDate] = useState(currentDate);
  
  const formatDateForInput = (date) => {
    return date.toISOString().split('T')[0];
  };
  
  const handleDateChange = (event) => {
    const newDate = new Date(event.target.value);
    setLocalDate(newDate);
    onDateChange(newDate);
  };
  
  return (
    <div className="bg-white dark:bg-space-900 rounded-lg shadow-lg p-4">
      <div className="flex items-center space-x-4">
        <button
          onClick={onPlayToggle}
          className="p-2 rounded-lg bg-primary-600 hover:bg-primary-700 text-white transition-colors shadow-md"
        >
          {isPlaying ? <Pause className="w-5 h-5" /> : <Play className="w-5 h-5" />}
        </button>
        
        <div className="flex-1">
          <label className="block text-xs text-neutral-600 dark:text-neutral-400 mb-1">
            Satellite Data Date
          </label>
          <input
            type="date"
            value={formatDateForInput(localDate)}
            onChange={handleDateChange}
            min={formatDateForInput(dateRange.start)}
            max={formatDateForInput(dateRange.end)}
            className="w-full px-3 py-2 border border-neutral-300 dark:border-neutral-600 rounded-lg bg-white dark:bg-neutral-800 text-neutral-900 dark:text-white focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
          />
        </div>
        
        <div className="text-right">
          <div className="text-xs text-neutral-500 dark:text-neutral-400">Selected</div>
          <div className="text-sm font-medium text-neutral-900 dark:text-white">
            {localDate.toLocaleDateString()}
          </div>
        </div>
      </div>
    </div>
  );
}

function InteractiveMap({ 
  sensorData = [], 
  selectedLayer = null, 
  currentDate = new Date(), 
  onMarkerClick,
  onDateChange,
  className = ""
}) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [dateRange] = useState({
    start: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000), // 30 days ago
    end: new Date()
  });
  
  // Animation effect
  useEffect(() => {
    if (!isPlaying) return;
    
    const interval = setInterval(() => {
      const nextDay = new Date(currentDate);
      nextDay.setDate(nextDay.getDate() + 1);
      
      if (nextDay <= dateRange.end) {
        onDateChange(nextDay);
      } else {
        setIsPlaying(false);
      }
    }, 1000); // Change every second for demo
    
    return () => clearInterval(interval);
  }, [isPlaying, currentDate, dateRange.end, onDateChange]);
  
  const handlePlayToggle = () => {
    setIsPlaying(!isPlaying);
  };
  
  // Create custom icons for different sensor types
  const createCustomIcon = (sensorType, severity = 'low') => {
    const colors = {
      low: '#10b981',
      moderate: '#f59e0b', 
      high: '#ef4444',
      critical: '#dc2626'
    };
    
    return L.divIcon({
      className: 'custom-sensor-marker',
      html: `
        <div style="
          background-color: ${colors[severity]};
          border: 2px solid white;
          border-radius: 50%;
          width: 20px;
          height: 20px;
          box-shadow: 0 2px 4px rgba(0,0,0,0.3);
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 10px;
          font-weight: bold;
          color: white;
          text-shadow: 0 1px 2px rgba(0,0,0,0.8);
        "></div>
      `,
      iconSize: [20, 20],
       iconAnchor: [10, 10],
      popupAnchor: [0, -10]
    });
  };
  
  const getSeverityLevel = (pm25Value) => {
    if (pm25Value > 55) return 'critical';
    if (pm25Value > 35) return 'high';
    if (pm25Value > 15) return 'moderate';
    return 'low';
  };
  
  return (
    <div className={`relative ${className}`}>
      <MapContainer
        center={[20, 0]} // Global center
        zoom={2}
        className="w-full h-full rounded-lg"
        zoomControl={true}
        preferCanvas={false}
        renderer={L.svg()}
        markerZoomAnimation={false}
        fadeAnimation={false}
        zoomAnimation={false}
        trackResize={false}
      >
        {/* Base layer */}
        <TileLayer
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        />
        
        {/* GIBS Satellite Layer */}
        {selectedLayer && (
          <GIBSTileLayer 
            layerId={selectedLayer.id}
            date={currentDate.toISOString().split('T')[0]}
            opacity={0.7}
          />
        )}
        
        {/* Sensor markers */}
        {sensorData.map((sensor, index) => (
          // Only render markers with valid coordinates
          sensor.latitude && sensor.longitude && 
          !isNaN(sensor.latitude) && !isNaN(sensor.longitude) &&
          sensor.latitude >= -90 && sensor.latitude <= 90 &&
          sensor.longitude >= -180 && sensor.longitude <= 180 ? (
          <Marker
            key={sensor.sensor_id || index}
            position={[parseFloat(sensor.latitude), parseFloat(sensor.longitude)]}
            icon={createCustomIcon(
              sensor.source, 
              getSeverityLevel(sensor.pm25 || 0)
            )}
            riseOnHover={false}
            riseOffset={0}
            bubblingMouseEvents={false}
            interactive={true}
            eventHandlers={{
              click: (e) => {
                e.originalEvent.stopPropagation();
                e.originalEvent.preventDefault();
                if (onMarkerClick) {
                  onMarkerClick(sensor);
                }
              }
            }}
          >
            <Popup>
              <div className="p-2">
                <h3 className="font-semibold text-sm">
                  Sensor {sensor.sensor_id}
                </h3>
                <div className="mt-2 space-y-1 text-xs">
                  <div>PM2.5: {sensor.pm25?.toFixed(1) || 'N/A'} μg/m³</div>
                  <div>PM10: {sensor.pm10?.toFixed(1) || 'N/A'} μg/m³</div>
                  {sensor.temperature && (
                    <div>Temp: {sensor.temperature.toFixed(1)}°C</div>
                  )}
                  {sensor.humidity && (
                    <div>Humidity: {sensor.humidity.toFixed(1)}%</div>
                  )}
                  <div className="text-neutral-500">
                    Source: {sensor.source}
                  </div>
                </div>
              </div>
            </Popup>
          </Marker>
          ) : null
        ))}
      </MapContainer>
      
      {/* Time controls */}
      {/* Time controls - Enhanced positioning */}
      <div className="absolute bottom-4 left-4 right-4 z-20">
        <TimeSlider
          currentDate={currentDate}
          onDateChange={onDateChange}
          dateRange={dateRange}
          isPlaying={isPlaying}
          onPlayToggle={handlePlayToggle}
        />
      </div>
      
      {/* Air Quality Legend */}
      <div className="absolute top-4 right-4 z-30 bg-white dark:bg-neutral-800 rounded-lg shadow-lg p-3">
        <h4 className="text-xs font-semibold mb-2 text-neutral-900 dark:text-white">Air Quality Scale</h4>
        <div className="space-y-1">
          <div className="flex items-center space-x-2">
            <div className="w-3 h-3 rounded-full bg-green-500"></div>
            <span className="text-xs text-neutral-700 dark:text-neutral-300">Good (0-15)</span>
          </div>
          <div className="flex items-center space-x-2">
            <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
            <span className="text-xs text-neutral-700 dark:text-neutral-300">Moderate (15-35)</span>
          </div>
          <div className="flex items-center space-x-2">
            <div className="w-3 h-3 rounded-full bg-red-500"></div>
            <span className="text-xs text-neutral-700 dark:text-neutral-300">Unhealthy (35+)</span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default InteractiveMap;