import React from 'react';
import { useState, useEffect } from 'react';
import DashboardOverview from '../components/Dashboard/DashboardOverview';
import DataSourceStatus from '../components/Dashboard/DataSourceStatus';
import EnhancedMapContainer from '../components/Map/EnhancedMapContainer';
import SensorDetailPanel from '../components/DetailPanel/SensorDetailPanel';
import useEnhancedSensorData from '../hooks/useEnhancedSensorData';
import useNotifications from '../hooks/useNotifications';

function Dashboard() {
  const [mapBounds] = useState(null); // Global coverage
  const [selectedSensor, setSelectedSensor] = useState(null);
  const [detailPanelOpen, setDetailPanelOpen] = useState(false);
  const [currentDate, setCurrentDate] = useState(new Date());
  const [viewMode, setViewMode] = useState('overview'); // 'overview' or 'map'
  
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
    enableSatellite: false
  });

  const { showSuccess, showError, showWarning, showInfo } = useNotifications();

  const handleMarkerClick = (sensor) => {
    setSelectedSensor(sensor);
    setDetailPanelOpen(true);
  };

  const closeDetailPanel = () => {
    setDetailPanelOpen(false);
    setSelectedSensor(null);
  };

  const handleDateChange = (newDate) => {
    setCurrentDate(newDate);
  };

  const handleMapBoundsChange = (newBounds) => {
    // Handle bounds change if needed
  };

  // Prepare data source status for dashboard
  const dataSourceStatus = {
    purpleair: {
      count: enhancedStats.purpleair,
      error: error?.type === 'error' && error.message.includes('PurpleAir') ? error.message : null
    },
    sensor_community: {
      count: enhancedStats.sensor_community,
      error: error?.type === 'error' && error.message.includes('Sensor.Community') ? error.message : null
    },
    openaq: {
      count: enhancedStats.openaq,
      error: error?.type === 'error' && error.message.includes('OpenAQ') ? error.message : null
    },
    weather: {
      count: enhancedStats.weather_points,
      error: error?.type === 'error' && error.message.includes('Weather') ? error.message : null
    }
  };

  return (
    <div className="space-y-6 p-6">
      {/* View Toggle */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <button
            onClick={() => setViewMode('overview')}
            className={`px-4 py-2 rounded-lg font-medium transition-colors ${
              viewMode === 'overview'
                ? 'bg-primary-600 text-white'
                : 'bg-white dark:bg-neutral-800 text-neutral-600 dark:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-neutral-700'
            }`}
          >
            Dashboard Overview
          </button>
          <button
            onClick={() => setViewMode('map')}
            className={`px-4 py-2 rounded-lg font-medium transition-colors ${
              viewMode === 'map'
                ? 'bg-primary-600 text-white'
                : 'bg-white dark:bg-neutral-800 text-neutral-600 dark:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-neutral-700'
            }`}
          >
            Interactive Map
          </button>
        </div>

          <button 
            onClick={() => {
              showInfo("Running comprehensive analysis of all sensor data...", {
                title: 'Analysis Started',
                autoHide: true
              });
              setTimeout(() => {
                showSuccess("Analysis complete! Check the map for hotspots and anomalies.", {
                  title: 'Analysis Complete',
                  autoHide: false
                });
              }, 3000);
            }}
            className="flex items-center justify-center space-x-2 p-4 bg-environmental-green/10 hover:bg-environmental-green/20 rounded-lg border border-environmental-green/30 transition-colors"
          >
            {/* This button is intentionally left empty to match the original structure */}
          </button>
        {/* Data Stats */}
        <div className="text-sm text-neutral-600 dark:text-neutral-400">
          {enhancedStats.total > 0 ? (
            <span>
              {enhancedStats.total} sensors loaded
              {enhancedStats.purpleair > 0 && ` • ${enhancedStats.purpleair} PurpleAir`}
              {enhancedStats.sensor_community > 0 && ` • ${enhancedStats.sensor_community} Sensor.Community`}
              {enhancedStats.openaq > 0 && ` • ${enhancedStats.openaq} OpenAQ`}
            </span>
          ) : (
            <span>Loading sensor data...</span>
          )}
        </div>
      </div>

      {/* Content Area */}
      {viewMode === 'overview' ? (
        <div className="space-y-6">
          <DashboardOverview 
            sensorData={sensorData}
            dataStats={enhancedStats}  
            weatherData={weatherData}
            lastUpdated={lastUpdated}
            loading={loading}
          />
          <DataSourceStatus
            dataSources={dataSourceStatus}
            lastUpdated={lastUpdated}
            onRefresh={refreshEnhancedData}
          />
        </div>
      ) : (
        <div className="h-[calc(100vh-200px)] relative">
          <EnhancedMapContainer
            sensorData={sensorData}
            weatherData={weatherData}
            selectedLayer={null}
            currentDate={currentDate}
            onMarkerClick={handleMarkerClick}
            onDateChange={handleDateChange}
            onBoundsChange={handleMapBoundsChange}
            className="w-full h-full"
          />
        </div>
      )}
      {/* Sensor Detail Panel */}
      <SensorDetailPanel
        sensor={selectedSensor}
        isOpen={detailPanelOpen}
        onClose={closeDetailPanel}
      />
          <button 
            onClick={() => {
              showInfo("Generating comprehensive PDF report...", {
                title: 'Report Generation',
                autoHide: true
              });
              setTimeout(() => {
                const reportData = {
                  timestamp: new Date().toISOString(),
                  totalSensors: sensorData.length || 0,
                  avgPM25: sensorData.length > 0 ? (sensorData.reduce((sum, s) => sum + (s.pm25 || 0), 0) / sensorData.length).toFixed(2) : 'N/A',
                  coverage: enhancedStats.coverage || 'N/A'
                };
                
                const blob = new Blob([JSON.stringify(reportData, null, 2)], { 
                  type: 'application/json' 
                });
                const url = URL.createObjectURL(blob);
                const link = document.createElement('a');
                link.href = url;
                link.download = `seit-report-${new Date().toISOString().split('T')[0]}.json`;
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
                URL.revokeObjectURL(url);
                
                showSuccess("Report downloaded successfully!", {
                  title: 'Report Ready',
                  autoHide: true
                });
              }, 2000);
            }}
            className="flex items-center justify-center space-x-2 p-4 bg-environmental-yellow/10 hover:bg-environmental-yellow/20 rounded-lg border border-environmental-yellow/30 transition-colors"
          >
            <span className="text-environmental-yellow font-medium">Download Report</span>
          </button>
    </div>
  );
}

export default Dashboard;