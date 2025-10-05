import React, { useState, useEffect, useRef } from 'react';
import { useMap, useMapEvents } from 'react-leaflet';
import L from 'leaflet';
import { generateHeatmapGrid, getColorForValue } from '../../services/heatmapGenerator';
function HeatmapOverlay({ 
   sensorData = [],
 resolution = 250,
  method = 'idw',
  opacity = 0.7,
  showUncertainty = true,
   isVisible = true
}) {
  const map = useMap();
  const heatmapLayerRef = useRef(null);
  const uncertaintyLayerRef = useRef(null);
   const [currentBounds, setCurrentBounds] = useState(null);
  const [gridData, setGridData] = useState(null);
  const [loading, setLoading] = useState(false);
 
   // Track map bounds changes
  useMapEvents({
    moveend: () => {
      const bounds = map.getBounds();
      setCurrentBounds([
        bounds.getWest(),
        bounds.getSouth(),
        bounds.getEast(),
        bounds.getNorth()
      ]);
    }
  });
   // Initialize bounds
 useEffect(() => {
     if (map && !currentBounds) {
      const bounds = map.getBounds();
      setCurrentBounds([
        bounds.getWest(),
        bounds.getSouth(),
        bounds.getEast(),
        bounds.getNorth()
      ]);
   }
   }, [map, currentBounds]);
   // Generate heatmap when data or bounds change
 useEffect(() => {
     if (!map || !sensorData.length || !currentBounds || !isVisible) {
      // Clear existing layers
      if (heatmapLayerRef.current) {
        map.removeLayer(heatmapLayerRef.current);
        heatmapLayerRef.current = null;
      }
      if (uncertaintyLayerRef.current) {
        map.removeLayer(uncertaintyLayerRef.current);
        uncertaintyLayerRef.current = null;
      }
      return;
    }
     generateHeatmap();
  }, [map, sensorData, currentBounds, resolution, method, isVisible, opacity, showUncertainty]);

  const generateHeatmap = async () => {
    if (loading) return;
    
    setLoading(true);
    try {
      // Generate interpolation grid
      const interpolatedGrid = generateHeatmapGrid(sensorData, currentBounds, {
        resolution,
        method,
        searchRadius: 5000 // 5km search radius
      });
      
      setGridData(interpolatedGrid);
      renderHeatmapLayers(interpolatedGrid);
      
    } catch (error) {
      console.error('Heatmap generation failed:', error);
    } finally {
      setLoading(false);
    }
  };

  const renderHeatmapLayers = (interpolatedGrid) => {
   // Clear existing layers
    if (heatmapLayerRef.current) {
      map.removeLayer(heatmapLayerRef.current);
    }
    if (uncertaintyLayerRef.current) {
      map.removeLayer(uncertaintyLayerRef.current);
    }

     // Create feature groups
   const heatmapLayer = L.featureGroup();
    const uncertaintyLayer = L.featureGroup();

     // Process grid points
    interpolatedGrid.forEach(gridPoint => {
      const { lat, lon, value, uncertainty, neighbors } = gridPoint;
       if (value === null || isNaN(value)) return;
       // Create heatmap circle
     const circle = L.circleMarker([lat, lon], {
         radius: Math.max(4, Math.min(12, resolution / 30)),
        fillColor: getColorForValue(value),
       color: 'white',
        weight: 1,
        opacity: 1,
         fillOpacity: opacity
     });

       // Enhanced popup
     circle.bindPopup(`
        <div class="heatmap-popup">
           <h4 class="font-semibold text-sm mb-2">PM2.5 Heatmap</h4>
         <div class="space-y-1 text-xs">
             <div><strong>Value:</strong> ${value.toFixed(1)} μg/m³</div>
           <div><strong>Uncertainty:</strong> ±${uncertainty.toFixed(1)} μg/m³</div>
             <div><strong>Neighbors:</strong> ${neighbors} sensors</div>
           <div><strong>Method:</strong> ${method.toUpperCase()}</div>
            <div><strong>Resolution:</strong> ${resolution}m</div>
          </div>
        </div>
       `);
      heatmapLayer.addLayer(circle);

       // Add uncertainty visualization
      if (showUncertainty && uncertainty > 8) {
        const uncertaintyRadius = Math.min(20, 6 + (uncertainty / 8));
       
        const uncertaintyCircle = L.circleMarker([lat, lon], {
          radius: uncertaintyRadius,
           fillColor: '#ef4444',
          color: '#ef4444',
          weight: 1,
          opacity: 0.4,
          fillOpacity: 0.15,
         dashArray: '5, 5'
        });

         uncertaintyCircle.bindTooltip(`Uncertainty: ±${uncertainty.toFixed(1)} μg/m³`, {
         permanent: false,
          direction: 'top'
        });

        uncertaintyLayer.addLayer(uncertaintyCircle);
      }
    });

     // Add layers
    if (heatmapLayer.getLayers().length > 0) {
      heatmapLayer.addTo(map);
      heatmapLayerRef.current = heatmapLayer;
    }
    
   if (showUncertainty) {
      uncertaintyLayer.addTo(map);
       uncertaintyLayerRef.current = uncertaintyLayer;
   }

  };
   // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (heatmapLayerRef.current) {
        map.removeLayer(heatmapLayerRef.current);
      }
      if (uncertaintyLayerRef.current) {
        map.removeLayer(uncertaintyLayerRef.current);
      }
    };
  }, [map]);
 return null; // This component only manages map layers
}

export default HeatmapOverlay;