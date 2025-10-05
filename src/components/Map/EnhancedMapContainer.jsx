import React, { useState } from 'react';
import { Map, Layers } from 'lucide-react';
import MapboxContainer from './MapboxContainer'; // Mapbox version
function EnhancedMapContainer({ 
  sensorData = [], 
  weatherData = [],
  selectedLayer = null, 
  currentDate = new Date(), 
  onMarkerClick,
  onDateChange,
  onBoundsChange,
  className = ""
}) {
  const [mapProvider, setMapProvider] = useState('leaflet'); // Only use leaflet
  const [show3D, setShow3D] = useState(false);

  const MapComponent = MapboxContainer; // Always use Mapbox
  const currentSatelliteLayer = selectedLayer;
  
  // Enhanced marker click handler to prevent position issues
  const handleMarkerClick = (sensor) => {
    // Validate sensor coordinates before processing
    if (!sensor || !sensor.latitude || !sensor.longitude) {
      console.warn('EnhancedMapContainer: Invalid sensor data:', sensor);
      return;
    }
    
    if (onMarkerClick) {
      onMarkerClick(sensor);
    }
  };

  return (
    <div className={`relative ${className}`}>
      {/* Map Provider Toggle */}
      <div className="absolute top-4 right-20 z-40 bg-white dark:bg-neutral-800 rounded-lg shadow-lg p-2">
        <div className="flex items-center space-x-2">
          <button
            className="p-2 rounded text-xs bg-primary-600 text-white"
            title="Mapbox (Vector)"
          >
            <Layers className="w-4 h-4" />
          </button>
        </div>
        
        {/* Layer Status Indicator */}
        {currentSatelliteLayer && (
          <div className="mt-2 pt-2 border-t border-neutral-200 dark:border-neutral-600">
            <div className="text-xs text-environmental-green font-medium">
              ✓ {currentSatelliteLayer.name}
            </div>
            <div className="text-xs text-neutral-500">
              Active Layer
            </div>
          </div>
        )}
      </div>

      {/* Enhanced Statistics Overlay */}
      <div className="absolute top-20 right-4 z-30 bg-white dark:bg-neutral-800 rounded-lg shadow-lg p-3 min-w-48">
        <h4 className="text-xs font-semibold mb-2 text-neutral-900 dark:text-white">
          Data Overview
        </h4>
        <div className="space-y-1 text-xs">
          <div className="flex justify-between">
            <span className="text-neutral-600 dark:text-neutral-400">Total Sensors:</span>
            <span className="font-medium text-neutral-900 dark:text-white">{sensorData.length}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-neutral-600 dark:text-neutral-400">Weather Points:</span>
            <span className="font-medium text-neutral-900 dark:text-white">{weatherData.length}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-neutral-600 dark:text-neutral-400">Map Provider:</span>
            <span className="font-medium text-neutral-900 dark:text-white">Mapbox</span>
          </div>
          {selectedLayer && (
            <div className="flex justify-between">
              <span className="text-neutral-600 dark:text-neutral-400">Satellite Layer:</span>
              <span className="font-medium text-environmental-green text-xs">Active</span>
            </div>
          )}
        </div>

        {/* Data Source Breakdown */}
        <div className="mt-3 pt-2 border-t border-neutral-200 dark:border-neutral-700">
          <div className="text-xs space-y-1">
            {['purpleair', 'sensor_community', 'openaq', 'mock_data'].map(source => {
              const count = sensorData.filter(s => s.source === source).length;
              if (count === 0) return null;
              return (
                <div key={source} className="flex justify-between">
                  <span className="text-neutral-600 dark:text-neutral-400 capitalize">
                    {source.replace('_', '.').replace('mock.data', 'Demo')}:
                  </span>
                  <span className="font-medium text-primary-600">{count}</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Map Component */}
      <MapComponent
        sensorData={sensorData}
        weatherData={weatherData}
        selectedLayer={selectedLayer}
        currentDate={currentDate}
        onMarkerClick={handleMarkerClick}
        onDateChange={onDateChange}
        onBoundsChange={onBoundsChange}
        className="w-full h-full relative"
      />
    </div>
  );
}

export default EnhancedMapContainer;