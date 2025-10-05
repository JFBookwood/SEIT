import React, { useEffect, useRef } from 'react';
import { useMap } from 'react-leaflet';
import L from 'leaflet';
import canvasMarkerService from '../../services/canvasMarkerService';
import markerClusteringService from '../../services/markerClusteringService';

function SensorMarkerLayer({ 
  sensorData = [], 
  clusterGroup = null, 
  currentZoom = 2, 
  mapBounds = null,
  onMarkerClick 
}) {
  const map = useMap();
  const markersRef = useRef({});
  const clusteringDataRef = useRef(null);
  
  useEffect(() => {
    if (!map || !clusterGroup) return;
    
    // Clear existing markers from cluster group
    clusterGroup.clearLayers();
    
    // Clear individual marker references
    Object.values(markersRef.current).forEach(marker => {
      if (marker && map.hasLayer(marker)) {
        map.removeLayer(marker);
      }
    });
    markersRef.current = {};
    
    if (!sensorData.length) {
      console.log('SensorMarkerLayer: No sensor data to display');
      return;
    }
    
    // Validate and filter sensor data
    const validSensors = sensorData.filter(sensor => {
      const lat = parseFloat(sensor.latitude);
      const lng = parseFloat(sensor.longitude);
      
      // Strict coordinate validation
      return (
        !isNaN(lat) && !isNaN(lng) &&
        lat >= -90 && lat <= 90 &&
        lng >= -180 && lng <= 180 &&
        sensor.sensor_id
      );
    });
    
    if (validSensors.length === 0) {
      console.warn('No valid sensors after coordinate validation');
      return;
    }
    
    console.log(`Creating markers for ${validSensors.length} valid sensors (zoom: ${currentZoom})`);
    
    // Determine if clustering should be used based on zoom and density
    const shouldCluster = currentZoom < 12 && validSensors.length > 10;
    
    if (shouldCluster) {
      // Use clustering for high-density/low-zoom scenarios
      const clusteringResult = markerClusteringService.initializeClustering(
        validSensors,
        mapBounds,
        validSensors.length > 100 ? 'dense' : 'default'
      );
      
      clusteringDataRef.current = clusteringResult;
      
      // Add markers to cluster group
      validSensors.forEach(sensor => {
        const marker = createStableMarker(sensor, false);
        if (marker) {
          clusterGroup.addLayer(marker);
        }
      });
    } else {
      // Add individual markers for low-density/high-zoom scenarios
      validSensors.forEach(sensor => {
        const marker = createStableMarker(sensor, false);
        if (marker) {
          map.addLayer(marker);
          markersRef.current[sensor.sensor_id] = marker;
        }
      });
    }
    
  }, [sensorData, currentZoom, mapBounds, clusterGroup, map, onMarkerClick]);
  
  /**
   * Create stable canvas-based marker
   */
  const createStableMarker = (sensor, isSelected = false) => {
    try {
      const lat = parseFloat(sensor.latitude);
      const lng = parseFloat(sensor.longitude);
      
      // Create canvas-based icon
      const icon = canvasMarkerService.createLeafletIcon(sensor, 'default', isSelected);
      
      // Create marker with stable positioning
      const marker = L.marker([lat, lng], {
        icon,
        riseOnHover: false,
        riseOffset: 0,
        bubblingMouseEvents: false,
        interactive: true,
        sensor: sensor  // Store sensor data for cluster calculations
      });
      
      // Add popup
      const popupContent = createEnhancedPopupContent(sensor);
      marker.bindPopup(popupContent, {
        maxWidth: 300,
        closeButton: true,
        closeOnClick: true
      });
      
      // Add click handler
      marker.on('click', (e) => {
        e.originalEvent?.stopPropagation();
        if (onMarkerClick) {
          onMarkerClick(sensor);
        }
      });
      
      return marker;
      
    } catch (error) {
      console.error(`Failed to create marker for sensor ${sensor.sensor_id}:`, error);
      return null;
    }
  };
  
  /**
   * Create enhanced popup content with validation info
   */
  const createEnhancedPopupContent = (sensor) => {
    const validation = sensor.coordinate_validation;
    const hasValidation = validation && validation.confidence_score < 1.0;
    
    return `
      <div class="sensor-popup">
        <div class="flex items-center justify-between mb-2">
          <h3 class="font-semibold text-sm">Sensor ${sensor.sensor_id}</h3>
          ${hasValidation ? `
            <span class="text-xs px-2 py-1 rounded" style="background-color: ${validation.confidence_score > 0.7 ? '#fef3c7' : '#fee2e2'}">
              ${validation.confidence_score > 0.7 ? 'Verified' : 'Unverified'}
            </span>
          ` : ''}
        </div>
        
        <div class="space-y-1 text-xs">
          <div><strong>PM2.5:</strong> ${sensor.pm25?.toFixed(1) || 'N/A'} μg/m³</div>
          <div><strong>PM10:</strong> ${sensor.pm10?.toFixed(1) || 'N/A'} μg/m³</div>
          ${sensor.temperature ? `<div><strong>Temp:</strong> ${sensor.temperature.toFixed(1)}°C</div>` : ''}
          ${sensor.humidity ? `<div><strong>Humidity:</strong> ${sensor.humidity.toFixed(1)}%</div>` : ''}
          ${sensor.no2 ? `<div><strong>NO2:</strong> ${sensor.no2.toFixed(1)} μg/m³</div>` : ''}
          ${sensor.o3 ? `<div><strong>O3:</strong> ${sensor.o3.toFixed(1)} μg/m³</div>` : ''}
        </div>
        
        <div class="mt-3 pt-2 border-t text-xs text-neutral-500">
          <div><strong>Source:</strong> ${sensor.source}</div>
          <div><strong>Location:</strong> ${sensor.latitude?.toFixed(4)}, ${sensor.longitude?.toFixed(4)}</div>
          ${validation ? `
            <div><strong>Confidence:</strong> ${(validation.confidence_score * 100).toFixed(0)}%</div>
            ${validation.validation_flags.length > 0 ? `
              <div class="text-orange-600 mt-1">
                <strong>Flags:</strong> ${validation.validation_flags.join(', ')}
              </div>
            ` : ''}
          ` : ''}
        </div>
      </div>
    `;
  };
  
  // Component cleanup
  useEffect(() => {
    return () => {
      // Clean up markers
      Object.values(markersRef.current).forEach(marker => {
        if (marker && map.hasLayer(marker)) {
          map.removeLayer(marker);
        }
      });
      
      // Clean up clustering cache
      markerClusteringService.cleanup();
    };
  }, []);
  
  return null; // This component only manages markers, no visual output
}

export default SensorMarkerLayer;
