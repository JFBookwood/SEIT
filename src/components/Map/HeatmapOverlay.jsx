import React, { useState, useEffect, useRef } from 'react';
import { useMap } from 'react-leaflet';
import L from 'leaflet';
import useHeatmapData from '../../hooks/useHeatmapData';

function HeatmapOverlay({ 
  bbox = null,
  resolution = 250,
  method = 'idw',
  timestamp = null,
  opacity = 0.7,
  showUncertainty = true,
  onDataUpdate = null
}) {
  const map = useMap();
  const heatmapLayerRef = useRef(null);
  const uncertaintyLayerRef = useRef(null);
  
  const {
    heatmapData,
    loading,
    error,
    metadata,
    refreshHeatmapData,
    getColorScale
  } = useHeatmapData({
    bbox,
    resolution,
    method,
    timestamp,
    enableAutoRefresh: false // Manual control for map overlay
  });

  // Update parent component when data changes
  useEffect(() => {
    if (onDataUpdate && heatmapData) {
      onDataUpdate({
        features: heatmapData.features || [],
        metadata: metadata,
        loading,
        error
      });
    }
  }, [heatmapData, metadata, loading, error, onDataUpdate]);

  // Render heatmap layer
  useEffect(() => {
    if (!map || !heatmapData?.features) return;

    // Clear existing layers
    if (heatmapLayerRef.current) {
      map.removeLayer(heatmapLayerRef.current);
    }
    if (uncertaintyLayerRef.current) {
      map.removeLayer(uncertaintyLayerRef.current);
    }

    // Create feature group for heatmap
    const heatmapLayer = L.featureGroup();
    const uncertaintyLayer = L.featureGroup();

    // Process features and create visual elements
    heatmapData.features.forEach(feature => {
      const coords = feature.geometry.coordinates;
      const props = feature.properties;
      
      if (!coords || coords.length < 2) return;

      const lat = coords[1];
      const lon = coords[0];
      const pm25 = props.c_hat || 0;
      const uncertainty = props.uncertainty || 0;

      // Create colored circle for PM2.5 value
      const circle = L.circleMarker([lat, lon], {
        radius: 8,
        fillColor: props.color || '#10b981',
        color: 'white',
        weight: 1,
        opacity: 1,
        fillOpacity: (props.opacity || 1.0) * opacity
      });

      // Add popup with detailed information
      circle.bindPopup(`
        <div class="heatmap-popup">
          <h4 class="font-semibold text-sm mb-2">Interpolated PM2.5</h4>
          <div class="space-y-1 text-xs">
            <div><strong>Value:</strong> ${pm25.toFixed(1)} μg/m³</div>
            <div><strong>Uncertainty:</strong> ±${uncertainty.toFixed(1)} μg/m³</div>
            <div><strong>Neighbors:</strong> ${props.n_eff || 'N/A'} sensors</div>
            <div><strong>Method:</strong> ${method.toUpperCase()}</div>
            <div><strong>Resolution:</strong> ${resolution}m</div>
          </div>
          ${timestamp ? `<div class="text-xs text-gray-500 mt-2">Time: ${new Date(timestamp).toLocaleString()}</div>` : ''}
        </div>
      `, {
        className: 'custom-popup'
      });

      heatmapLayer.addLayer(circle);

      // Add uncertainty visualization if enabled
      if (showUncertainty && uncertainty > 10) {
        const uncertaintyRadius = Math.min(15, 8 + (uncertainty / 10));
        
        const uncertaintyCircle = L.circleMarker([lat, lon], {
          radius: uncertaintyRadius,
          fillColor: '#ff6b6b',
          color: '#ff6b6b',
          weight: 2,
          opacity: 0.3,
          fillOpacity: 0.1,
          dashArray: '5, 5'
        });

        uncertaintyCircle.bindTooltip(`High Uncertainty: ±${uncertainty.toFixed(1)} μg/m³`, {
          permanent: false,
          direction: 'top'
        });

        uncertaintyLayer.addLayer(uncertaintyCircle);
      }
    });

    // Add layers to map
    heatmapLayer.addTo(map);
    if (showUncertainty) {
      uncertaintyLayer.addTo(map);
    }

    // Store references for cleanup
    heatmapLayerRef.current = heatmapLayer;
    uncertaintyLayerRef.current = uncertaintyLayer;

    // Cleanup function
    return () => {
      if (heatmapLayerRef.current && map.hasLayer(heatmapLayerRef.current)) {
        map.removeLayer(heatmapLayerRef.current);
      }
      if (uncertaintyLayerRef.current && map.hasLayer(uncertaintyLayerRef.current)) {
        map.removeLayer(uncertaintyLayerRef.current);
      }
    };
  }, [map, heatmapData, opacity, showUncertainty, method, resolution, timestamp]);

  // Trigger refresh when parameters change
  useEffect(() => {
    if (bbox) {
      refreshHeatmapData();
    }
  }, [bbox, resolution, method, timestamp, refreshHeatmapData]);

  return null; // This component only manages map layers
}

export default HeatmapOverlay;
