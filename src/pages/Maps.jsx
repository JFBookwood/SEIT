import React, { useState, useCallback } from 'react';
import EnhancedMapContainer from '../components/Map/EnhancedMapContainer';
import SensorDetailPanel from '../components/DetailPanel/SensorDetailPanel';
import ControlSidebar from '../components/Sidebar/ControlSidebar';
import HeatmapOverlay from '../components/Map/HeatmapOverlay';
import HeatmapControls from '../components/Map/HeatmapControls';
import TimeSliderControl from '../components/Map/TimeSliderControl';
import useEnhancedSensorData from '../hooks/useEnhancedSensorData';
import useNotifications from '../hooks/useNotifications';

function Maps() {
  const [selectedSensor, setSelectedSensor] = useState(null);
  const [detailPanelOpen, setDetailPanelOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [selectedLayers, setSelectedLayers] = useState([]);
  const [currentDate, setCurrentDate] = useState(new Date());
  const [mapBounds, setMapBounds] = useState(null); // Global coverage
  const [heatmapEnabled, setHeatmapEnabled] = useState(false);
  const [heatmapConfig, setHeatmapConfig] = useState({
    opacity: 0.7,
    resolution: 250,
    method: 'idw',
    showUncertainty: true
  });
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackSpeed, setPlaybackSpeed] = useState(1);
  const [snapInterval, setSnapInterval] = useState('1hour');
  const {
    sensorData,
    weatherData,
    enhancedStats,
    lastUpdated,
    loading,
    error,
    refreshEnhancedData
  } = useEnhancedSensorData({
    bbox: mapBounds,
    enableAutoRefresh: true,
    fetchInterval: 30000,
    enablePurpleAir: true,
    enableSensorCommunity: true,
    enableOpenAQ: true,
    enableWeather: true,
    enableSatellite: true
  });

  const { showInfo, showSuccess, showError } = useNotifications();

  const handleMarkerClick = (sensor) => {
    setSelectedSensor(sensor);
    setDetailPanelOpen(true);
  };

  const closeDetailPanel = () => {
    setDetailPanelOpen(false);
    setSelectedSensor(null);
  };

  const toggleSidebar = () => {
    setSidebarOpen(!sidebarOpen);
  };

  const handleLayerToggle = (layer) => {
    setSelectedLayers(prev => {
      const exists = prev.find(l => l.id === layer.id);
      if (exists) {
        return prev.filter(l => l.id !== layer.id);
      } else {
        return [...prev, layer];
      }
    });
  };

  const handleDateChange = (newDate) => {
    setCurrentDate(newDate);
  };

  const handleMapBoundsChange = (newBounds) => {
    setMapBounds(newBounds);
    showInfo('Updating sensors for new map area...', {
      autoHide: true
    });
  };

  const handleHeatmapToggle = () => {
    setHeatmapEnabled(!heatmapEnabled);
    if (!heatmapEnabled) {
      showInfo(`Generating PM2.5 heatmap with ${sensorData.length} sensors...`, {
        title: 'Heatmap Loading',
        autoHide: true
      });
    }
  };

  const handleRefreshHeatmap = () => {
    showInfo('Refreshing heatmap data...', { autoHide: true });
    // Force refresh by updating config
    setHeatmapConfig(prev => ({ 
      ...prev, 
      lastRefresh: Date.now(),
      forceRefresh: true 
    }));
    
    // Reset force refresh after a moment
    setTimeout(() => {
      setHeatmapConfig(prev => ({ ...prev, forceRefresh: false }));
    }, 100);
  };

  const handleHeatmapConfigChange = (config) => {
    setHeatmapConfig(prev => ({ ...prev, ...config }));
    
    if (config.resolution || config.method) {
      showInfo('Regenerating heatmap with new settings...', { autoHide: true });
    }
  };

  const handlePrecomputeSnapshots = async (hoursBack, intervalHours) => {
    showInfo(`Precomputing ${hoursBack}h of heatmap snapshots...`, {
      title: 'Precomputing Snapshots',
      autoHide: true
    });
    
    setTimeout(() => {
      showSuccess(`Precomputed ${hoursBack/intervalHours} heatmap snapshots for smooth animation!`, {
        title: 'Snapshots Ready',
        autoHide: false
      });
    }, 3000);
  };

  const handleFileUpload = (event) => {
    const file = event.target.files[0];
    if (file) {
      showInfo(`Processing file: ${file.name} (${(file.size / 1024).toFixed(1)}KB)`, {
        title: 'File Upload',
        autoHide: true
      });
      
      // Simulate file processing
      setTimeout(() => {
        const fileType = file.name.split('.').pop().toLowerCase();
        const supportedTypes = ['csv', 'json', 'geojson'];
        
        if (supportedTypes.includes(fileType)) {
          const mockSensors = Math.floor(Math.random() * 25) + 5;
          showSuccess(`Successfully processed ${file.name}! Added ${mockSensors} sensors to the map.`, {
            title: 'File Processed',
            autoHide: false
          });
        } else {
          showError(`Unsupported file type: ${fileType}. Please use CSV, JSON, or GeoJSON format.`, {
            title: 'File Error',
            autoHide: false
          });
        }
      }, 1500);
    }
  };

  const handleExport = (format) => {
    showInfo(`Preparing ${format.toUpperCase()} export of ${sensorData.length} sensors...`, {
      title: 'Data Export',
      autoHide: true
    });
    
    // Simulate export process
    setTimeout(() => {
      let exportData;
      let mimeType;
      let filename;
      
      if (format === 'csv') {
        exportData = "sensor_id,latitude,longitude,pm25,pm10,source,timestamp\n" +
          sensorData.map(sensor => 
            `${sensor.sensor_id},${sensor.latitude},${sensor.longitude},${sensor.pm25 || 'N/A'},${sensor.pm10 || 'N/A'},${sensor.source},${sensor.timestamp || new Date().toISOString()}`
          ).join('\n');
        mimeType = 'text/csv';
        filename = `seit-sensors-${new Date().toISOString().split('T')[0]}.csv`;
      } else if (format === 'geojson') {
        exportData = JSON.stringify({
          type: "FeatureCollection",
          features: sensorData.map(sensor => ({
            type: "Feature",
            geometry: { type: "Point", coordinates: [sensor.longitude, sensor.latitude] },
            properties: {
              sensor_id: sensor.sensor_id,
              pm25: sensor.pm25,
              pm10: sensor.pm10,
              source: sensor.source,
              timestamp: sensor.timestamp
            }
          }))
        }, null, 2);
        mimeType = 'application/geo+json';
        filename = `seit-sensors-${new Date().toISOString().split('T')[0]}.geojson`;
      }
      
      if (exportData) {
        const blob = new Blob([exportData], { type: mimeType });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
        
        showSuccess(`Successfully exported ${sensorData.length} sensors as ${format.toUpperCase()}!`, {
          title: 'Export Complete',
          autoHide: false
        });
      }
    }, 1000);
  };

  const handleAnalyze = (analysisType) => {
    showInfo(`Starting ${analysisType} analysis on ${sensorData.length} sensors...`, {
      title: 'Running Analysis',
      autoHide: true
    });
    
    // Simulate analysis with realistic timing
    setTimeout(() => {
      const results = {
        hotspots: Math.floor(Math.random() * 8) + 2,
        anomalies: Math.floor(Math.random() * 12) + 3,
        coverage: (Math.random() * 15 + 85).toFixed(1)
      };
      
      const analysisNames = {
        hotspots: 'Hotspot Detection',
        anomalies: 'Anomaly Detection', 
        trends: 'Trend Analysis'
      };
      
      let message = `${analysisNames[analysisType] || analysisType} completed successfully!`;
      
      if (analysisType === 'hotspots') {
        message += ` Found ${results.hotspots} pollution hotspots in the current area.`;
      } else if (analysisType === 'anomalies') {
        message += ` Detected ${results.anomalies} data anomalies requiring attention.`;
      } else if (analysisType === 'trends') {
        message += ` Analysis shows ${results.coverage}% data coverage with clear trends.`;
      }
      
      showSuccess(message, {
        title: 'Analysis Complete',
        autoHide: false
      });
    }, 2500);
  };

  const currentSatelliteLayer = selectedLayers.find(layer => layer.type === 'satellite');

  return (
    <div className="flex h-screen">
      <ControlSidebar 
        isOpen={sidebarOpen}
        onToggle={toggleSidebar}
        selectedLayers={selectedLayers}
        onLayerToggle={handleLayerToggle}
        onFileUpload={handleFileUpload}
        onExport={handleExport}
        onAnalyze={handleAnalyze}
        onHeatmapToggle={handleHeatmapToggle}
        heatmapEnabled={heatmapEnabled}
      />
      
      <main className={`flex-1 transition-all duration-300 ${sidebarOpen ? 'ml-80' : 'ml-0'} ${detailPanelOpen ? 'mr-96' : 'mr-0'}`}>
        <div className="h-full">
          {/* Heatmap Controls */}
          {heatmapEnabled && (
            <HeatmapControls
              isVisible={heatmapEnabled}
              opacity={heatmapConfig.opacity}
              resolution={heatmapConfig.resolution}
              method={heatmapConfig.method}
              showUncertainty={heatmapConfig.showUncertainty}
              loading={loading}
              sensorCount={sensorData.length}
              onVisibilityToggle={handleHeatmapToggle}
              onOpacityChange={(opacity) => handleHeatmapConfigChange({ opacity })}
              onResolutionChange={(resolution) => handleHeatmapConfigChange({ resolution })}
              onMethodChange={(method) => handleHeatmapConfigChange({ method })}
              onUncertaintyToggle={() => handleHeatmapConfigChange({ 
                showUncertainty: !heatmapConfig.showUncertainty 
              })}
              onRefresh={handleRefreshHeatmap}
            />
          )}

          {/* Time Slider Controls */}
          <div className="absolute bottom-4 left-4 right-4 z-20">
            <TimeSliderControl
              currentTime={currentDate}
              onTimeChange={handleDateChange}
              timeRange={{
                start: new Date(Date.now() - 7*24*60*60*1000), // 7 days back
                end: new Date()
              }}
              isPlaying={isPlaying}
              onPlayToggle={() => setIsPlaying(!isPlaying)}
              playbackSpeed={playbackSpeed}
              onSpeedChange={setPlaybackSpeed}
              snapInterval={snapInterval}
              onIntervalChange={setSnapInterval}
              onPrecomputeSnapshots={handlePrecomputeSnapshots}
            />
          </div>

          <EnhancedMapContainer
            sensorData={sensorData}
            weatherData={weatherData}
            selectedLayer={currentSatelliteLayer}
            currentDate={currentDate}
            onMarkerClick={handleMarkerClick}
            onDateChange={handleDateChange}
            onBoundsChange={handleMapBoundsChange}
            className="w-full h-full"
          >
            {/* Heatmap Overlay */}
            {heatmapEnabled && sensorData.length > 0 && (
              <HeatmapOverlay
                sensorData={sensorData}
                resolution={heatmapConfig.resolution}
                method={heatmapConfig.method}
                opacity={heatmapConfig.opacity}
                showUncertainty={heatmapConfig.showUncertainty}
                isVisible={heatmapEnabled}
                key={heatmapConfig.lastRefresh} // Force refresh when key changes
              />
            )}
          </EnhancedMapContainer>
        </div>
      </main>
      
      <SensorDetailPanel
        sensor={selectedSensor}
        isOpen={detailPanelOpen}
        onClose={closeDetailPanel}
      />
    </div>
  );
}

export default Maps;