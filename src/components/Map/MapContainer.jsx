import SensorMarkerLayer from './SensorMarkerLayer';
import React, { useState, useEffect, useRef } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import { LatLngBounds } from 'leaflet';
import 'leaflet/dist/leaflet.css';
import 'leaflet.markercluster/dist/MarkerCluster.css';
import 'leaflet.markercluster/dist/MarkerCluster.Default.css';
import L from 'leaflet';
import 'leaflet.markercluster/dist/MarkerCluster.css';
import 'leaflet.markercluster/dist/MarkerCluster.Default.css';
import 'leaflet.markercluster';
import 'leaflet.markercluster';
import { Calendar, Play, Pause, SkipForward } from 'lucide-react';

import canvasMarkerService from '../../services/canvasMarkerService';
import markerClusteringService from '../../services/markerClusteringService';
// import canvasMarkerService from '../../services/canvasMarkerService';
// import markerClusteringService from '../../services/markerClusteringService';
// Fix for default markers
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
});

function GIBSTileLayer({ layerId, date, opacity = 0.8 }) {
  const map = useMap();
  
  // Marker cluster group reference
  const clusterGroupRef = useRef(null);
  const [currentZoom, setCurrentZoom] = useState(2);
  const [mapBounds, setMapBounds] = useState(null);
  
  useEffect(() => {
    if (!layerId || !date) return;
    
    // Initialize clustering for sensor data
    const clusteringResult = markerClusteringService.initializeClustering(
      sensorData, 
      mapBounds,
      sensorData.length > 100 ? 'dense' : 'default'
    );
    
    // Get clusters and points for current view
    const { clusters, points } = markerClusteringService.getClustersForBounds(
      mapBounds || [-180, -90, 180, 90],
      currentZoom
    );
    
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

function SensorMarkerLayer({ sensorData, clusterGroup, currentZoom, mapBounds, onMarkerClick }) {
  const map = useMap();
  const markersRef = useRef({});
  const clusterGroupRef = useRef(null); // Ensure clusterGroupRef is defined here

  useEffect(() => {
    if (!map || !sensorData || sensorData.length === 0) return;

    // Clear existing markers and clusters
    if (clusterGroupRef.current) {
      clusterGroupRef.current.clearLayers();
    } else {
      // Initialize clusterGroupRef if it's not already initialized
      clusterGroupRef.current = L.markerClusterGroup({
        spiderfyOnMaxZoom: false,
        showCoverageOnHover: false,
        zoomToBoundsOnClick: true,
        maxClusterRadius: 80,
        iconCreateFunction: (cluster) => {
          const childCount = cluster.getChildCount();
          const markers = cluster.getAllChildMarkers();
          
          const pm25Values = markers.map(m => m.options.sensor?.pm25 || 0);
          const maxPm25 = Math.max(...pm25Values);
          const avgPm25 = pm25Values.reduce((a, b) => a + b, 0) / pm25Values.length;
          
          const clusterData = {
            count: childCount,
            maxPollution: maxPm25,
            avgPollution: avgPm25,
            source: 'cluster'
          };
          
          const iconUrl = canvasMarkerService.createCanvasMarker(clusterData, 'clustered');
          
          return L.icon({
            iconUrl,
            iconSize: [32, 32],
            iconAnchor: [16, 16],
            popupAnchor: [0, -16],
            className: 'cluster-icon'
          });
        }
      });
      map.addLayer(clusterGroupRef.current);
    }

    const { clusters, points } = markerClusteringService.getClustersForBounds(
      mapBounds || [-180, -90, 180, 90],
      currentZoom
    );

    // Add cluster markers
    clusters.forEach(cluster => {
      const clusterElement = canvasMarkerService.createMapboxElement(
        {
          count: cluster.count,
          maxPollution: cluster.maxPollution,
          source: 'cluster'
        },
        'clustered'
      );
      
      clusterElement.addEventListener('click', () => {
        const expansionZoom = markerClusteringService.getClusterExpansionZoom(cluster.id);
        if (expansionZoom) {
          map.flyTo({
            center: cluster.coordinates,
            zoom: expansionZoom
          });
        }
      });
      
      const clusterPopup = new L.Popup({
        offset: 25,
        closeButton: true
      }).setHTML(`
        <div class="cluster-popup">
          <h3 class="font-semibold text-sm mb-2">${cluster.count} Sensors</h3>
          <div class="space-y-1 text-xs">
            <div><strong>Max PM2.5:</strong> ${cluster.maxPollution.toFixed(1)} μg/m³</div>
            <div><strong>Avg PM2.5:</strong> ${cluster.avgPollution.toFixed(1)} μg/m³</div>
            <div><strong>Sources:</strong> ${Object.keys(cluster.sourceBreakdown).join(', ')}</div>
          </div>
          <div class="text-xs text-neutral-500 mt-2">Click to expand cluster</div>
        </div>
      `);
      
      const clusterMarker = L.marker(cluster.coordinates, {
        icon: L.divIcon({
          className: 'cluster-marker-icon',
          html: clusterElement.outerHTML,
          iconSize: [32, 32],
          iconAnchor: [16, 16]
        }),
        sensor: { id: `cluster_${cluster.id}` } // Add a unique identifier
      })
        .bindPopup(clusterPopup)
        .addTo(clusterGroupRef.current);
      
      markersRef.current[`cluster_${cluster.id}`] = clusterMarker;
    });
    
    points.forEach(({ sensor, coordinates }) => {
      const getSeverityLevel = (pm25Value) => {
        if (pm25Value > 55) return 'critical';
        if (pm25Value > 35) return 'high';
        if (pm25Value > 15) return 'moderate';
        return 'low';
      };

      const markerElement = canvasMarkerService.createMapboxElement(sensor, 'default');
      const severity = getSeverityLevel(sensor.pm25);
      const customIcon = L.divIcon({
        className: 'custom-sensor-marker',
        html: `
          <div style="
            background-color: ${severity === 'low' ? '#10b981' : severity === 'moderate' ? '#f59e0b' : severity === 'high' ? '#ef4444' : '#dc2626'};
            border: 2px solid white;
            border-radius: 50%;
          "></div>
        `,
        iconSize: [20, 20],
        iconAnchor: [10, 10],
        popupAnchor: [0, -10]
      });

      const sensorPopup = new L.Popup({
        offset: 25,
        closeButton: false
      }).setHTML(`
        <div class="sensor-popup">
          <h3 class="font-semibold text-sm mb-2">${sensor.name}</h3>
          <div class="space-y-1 text-xs">
            <div><strong>PM2.5:</strong> ${sensor.pm25.toFixed(1)} μg/m³</div>
            <div><strong>Source:</strong> ${sensor.source}</div>
          </div>
        </div>
      `);

      const sensorMarker = L.marker(coordinates, {
        icon: customIcon,
        sensor: sensor
      })
        .bindPopup(sensorPopup)
        .addTo(clusterGroupRef.current);

      sensorMarker.on('click', () => {
        onMarkerClick(sensor);
      });

      markersRef.current[sensor.id] = sensorMarker;
    });

    return () => {
      if (clusterGroupRef.current) {
        clusterGroupRef.current.clearLayers();
        map.removeLayer(clusterGroupRef.current);
      }
    };
  }, [map, sensorData, currentZoom, mapBounds, onMarkerClick]);

  return null;
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
  const [currentZoom, setCurrentZoom] = useState(2);
  const [mapBounds, setMapBounds] = useState(null);
  const clusterGroupRef = useRef(null);
  const mapRef = useRef(null);
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
        ref={mapRef}
        className="w-full h-full rounded-lg"
        zoomControl={true}
        preferCanvas={false}
        renderer={L.canvas({
          padding: 0.5,
          tolerance: 0
        })}
        markerZoomAnimation={false}
        fadeAnimation={false}
        zoomAnimation={false}
        trackResize={false}
        whenCreated={(map) => {
          mapRef.current = map;
          
          // Initialize marker cluster group with custom settings
          clusterGroupRef.current = L.markerClusterGroup({
            spiderfyOnMaxZoom: false,
            showCoverageOnHover: false,
            zoomToBoundsOnClick: true,
            maxClusterRadius: 80,
            iconCreateFunction: (cluster) => {
              const childCount = cluster.getChildCount();
              const markers = cluster.getAllChildMarkers();
              
              // Calculate cluster statistics
              const pm25Values = markers.map(m => m.options.sensor?.pm25 || 0);
              const maxPm25 = Math.max(...pm25Values);
              const avgPm25 = pm25Values.reduce((a, b) => a + b, 0) / pm25Values.length;
              
              // Create cluster data for canvas rendering
              const clusterData = {
                count: childCount,
                maxPollution: maxPm25,
                avgPollution: avgPm25,
                source: 'cluster'
              };
              
              // Generate canvas icon
              const iconUrl = canvasMarkerService.createCanvasMarker(clusterData, 'clustered');
              
              return L.icon({
                iconUrl,
                iconSize: [32, 32],
                iconAnchor: [16, 16],
                popupAnchor: [0, -16],
                className: 'cluster-icon'
              });
            }
          });
          
          map.addLayer(clusterGroupRef.current);
          
          // Track zoom and bounds for clustering optimization
          map.on('zoomend', () => {
            setCurrentZoom(map.getZoom());
          });
          
          map.on('moveend', () => {
            const bounds = map.getBounds();
            setMapBounds([
              bounds.getWest(),
              bounds.getSouth(),
              bounds.getEast(), 
              bounds.getNorth()
            ]);
          });
        }}
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
        <SensorMarkerLayer 
          sensorData={sensorData}
          clusterGroup={clusterGroupRef.current}
          currentZoom={currentZoom}
          mapBounds={mapBounds}
          onMarkerClick={onMarkerClick}
        />
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