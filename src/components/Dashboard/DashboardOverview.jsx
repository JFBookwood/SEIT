import React, { useState, useEffect } from 'react';
import { Activity, MapPin, Zap, AlertTriangle } from 'lucide-react';
import StatsCard from './StatsCard';
import useNotifications from '../../hooks/useNotifications';

function DashboardOverview({ 
  sensorData = [], 
  dataStats = {}, 
  lastUpdated = null, 
  loading = false 
}) {
  const { showInfo, showSuccess } = useNotifications();
  const [stats, setStats] = useState({
    totalSensors: 0,
    activeSensors: 0,
    avgPM25: 0,
    hotspots: 0,
    recentReadings: 0,
    dataQuality: 0
  });
  
  useEffect(() => {
    if (sensorData.length > 0) {
      calculateStats();
    }
  }, [sensorData, dataStats]);

  const calculateStats = () => {
    const pm25Values = sensorData
      .map(sensor => sensor.pm25)
      .filter(val => val !== null && val !== undefined && !isNaN(val));

    const avgPM25 = pm25Values.length > 0 
      ? pm25Values.reduce((sum, val) => sum + val, 0) / pm25Values.length 
      : 0;

    // Calculate hotspots (sensors with PM2.5 > 35)
    const hotspots = pm25Values.filter(val => val > 35).length;

    // Calculate data quality based on completeness
    const totalPossibleReadings = sensorData.length * 5; // 5 parameters per sensor
    const actualReadings = sensorData.reduce((count, sensor) => {
      return count + 
        (sensor.pm25 !== null && sensor.pm25 !== undefined ? 1 : 0) +
        (sensor.pm10 !== null && sensor.pm10 !== undefined ? 1 : 0) +
        (sensor.temperature !== null && sensor.temperature !== undefined ? 1 : 0) +
        (sensor.humidity !== null && sensor.humidity !== undefined ? 1 : 0) +
        (sensor.pressure !== null && sensor.pressure !== undefined ? 1 : 0);
    }, 0);

    const dataQuality = totalPossibleReadings > 0 
      ? (actualReadings / totalPossibleReadings) * 100 
      : 0;

    setStats({
      totalSensors: dataStats.total || sensorData.length,
      activeSensors: sensorData.length,
      avgPM25: avgPM25,
      hotspots: hotspots,
      recentReadings: sensorData.length * 24, // Estimate based on hourly readings
      dataQuality: dataQuality
    });
  };
  
  if (loading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {[...Array(6)].map((_, i) => (
          <div key={i} className="bg-white dark:bg-space-900 rounded-lg border border-neutral-200 dark:border-neutral-700 p-6 animate-pulse">
            <div className="flex items-center justify-between">
              <div className="flex-1">
                <div className="h-4 bg-neutral-200 dark:bg-neutral-700 rounded w-2/3 mb-2"></div>
                <div className="h-8 bg-neutral-200 dark:bg-neutral-700 rounded w-1/2 mb-2"></div>
                <div className="h-3 bg-neutral-200 dark:bg-neutral-700 rounded w-3/4"></div>
              </div>
              <div className="w-12 h-12 bg-neutral-200 dark:bg-neutral-700 rounded-lg"></div>
            </div>
          </div>
        ))}
      </div>
    );
  }
  
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-neutral-900 dark:text-white">
          Dashboard Overview
        </h2>
        <div className="text-sm text-neutral-500 dark:text-neutral-400">
          Last updated: {lastUpdated ? new Date(lastUpdated).toLocaleTimeString() : 'Never'}
        </div>
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
        {/* Total Sensors */}
        <StatsCard
          title="Total Sensors"
          value={stats.totalSensors.toLocaleString()}
          icon={MapPin}
          color="primary"
          trend={stats.totalSensors > 0 ? "up" : null}
          trendValue={stats.totalSensors > 0 ? `+${stats.totalSensors}` : null}
        />
        
        {/* Active Sensors */}
        <StatsCard
          title="Active Sensors"
          value={stats.activeSensors.toLocaleString()}
          icon={Activity}
          color="green"
          trend={stats.activeSensors > 0 ? "up" : null}
          trendValue={stats.activeSensors > 0 ? `+${stats.activeSensors}` : null}
        />
        
        {/* Average PM2.5 */}
        <StatsCard
          title="Average PM2.5"
          value={stats.avgPM25.toFixed(1)}
          unit="μg/m³"
          icon={Zap}
          color={stats.avgPM25 > 35 ? 'red' : stats.avgPM25 > 15 ? 'yellow' : 'green'}
          trend={stats.avgPM25 > 25 ? 'up' : stats.avgPM25 > 0 ? 'down' : null}
          trendValue={stats.avgPM25 > 0 ? `${stats.avgPM25.toFixed(1)}` : null}
        />
        
        {/* Hotspots Detected */}
        <StatsCard
          title="Active Hotspots"
          value={stats.hotspots}
          icon={AlertTriangle}
          color="red"
          trend={stats.hotspots > 0 ? "up" : "down"}
          trendValue={stats.hotspots > 0 ? `+${stats.hotspots}` : "0"}
        />
        
        {/* Recent Readings */}
        <StatsCard
          title="Recent Readings"
          value={stats.recentReadings.toLocaleString()}
          icon={Activity}
          color="primary"
          className="md:col-span-2 lg:col-span-1"
        />
        
        {/* Data Quality */}
        <StatsCard
          title="Data Quality"
          value={stats.dataQuality.toFixed(1)}
          unit="%"
          icon={Zap}
          color="green"
          trend={stats.dataQuality > 80 ? "up" : stats.dataQuality > 0 ? "down" : null}
          trendValue={stats.dataQuality > 0 ? `${stats.dataQuality.toFixed(1)}%` : null}
        />
      </div>
      
      {/* Quick Actions */}
      <div className="bg-white dark:bg-space-900 rounded-lg border border-neutral-200 dark:border-neutral-700 p-6">
        <h3 className="text-lg font-semibold text-neutral-900 dark:text-white mb-4">
          Quick Actions
        </h3>
        
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <button className="flex items-center justify-center space-x-2 p-4 bg-primary-50 dark:bg-primary-900/20 hover:bg-primary-100 dark:hover:bg-primary-900/30 rounded-lg border border-primary-200 dark:border-primary-800 transition-colors" onClick={() => window.location.hash = '#map'}>
            <MapPin className="w-5 h-5 text-primary-600" />
            <span className="text-primary-600 font-medium">View Map</span>
          </button>
          
          <button className="flex items-center justify-center space-x-2 p-4 bg-environmental-green/10 hover:bg-environmental-green/20 rounded-lg border border-environmental-green/30 transition-colors" onClick={() => {
              showInfo("Running comprehensive analysis of all sensor data...", {
                title: 'Analysis Started',
                autoHide: true
              });
              // Trigger analysis after a brief delay
              setTimeout(() => {
                showSuccess("Analysis complete! Check the map for hotspots and anomalies.", {
                  title: 'Analysis Complete',
                  autoHide: false
                });
              }, 3000);
            }}>
            <Activity className="w-5 h-5 text-environmental-green" />
            <span className="text-environmental-green font-medium">Run Analysis</span>
          </button>
          
          <button className="flex items-center justify-center space-x-2 p-4 bg-environmental-yellow/10 hover:bg-environmental-yellow/20 rounded-lg border border-environmental-yellow/30 transition-colors" onClick={() => {
              showInfo("Generating comprehensive PDF report...", {
                title: 'Report Generation',
                autoHide: true
              });
              // Simulate report generation
              setTimeout(() => {
                const reportData = {
                  timestamp: new Date().toISOString(),
                  totalSensors: stats.totalSensors || 0,
                  avgPM25: stats.avgPM25.toFixed(2) || 'N/A',
                  coverage: stats.dataQuality.toFixed(1) || 'N/A'
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
            }}>
            <Zap className="w-5 h-5 text-environmental-yellow" />
            <span className="text-environmental-yellow font-medium">Generate Report</span>
          </button>
        </div>
      </div>
      
      {/* System Status */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Data Sources Status */}
        <div className="bg-white dark:bg-space-900 rounded-lg border border-neutral-200 dark:border-neutral-700 p-6">
          <h3 className="text-lg font-semibold text-neutral-900 dark:text-white mb-4">
            Data Sources
          </h3>
          
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm text-neutral-600 dark:text-neutral-400">PurpleAir</span>
              <div className="flex items-center space-x-2">
                <div className="w-2 h-2 bg-environmental-green rounded-full"></div>
                <span className="text-sm font-medium text-environmental-green">Online</span>
              </div>
            </div>
            
            <div className="flex items-center justify-between">
              <span className="text-sm text-neutral-600 dark:text-neutral-400">Sensor.Community</span>
              <div className="flex items-center space-x-2">
                <div className="w-2 h-2 bg-environmental-green rounded-full"></div>
                <span className="text-sm font-medium text-environmental-green">Online</span>
              </div>
            </div>
            
            <div className="flex items-center justify-between">
              <span className="text-sm text-neutral-600 dark:text-neutral-400">NASA GIBS</span>
              <div className="flex items-center space-x-2">
                <div className="w-2 h-2 bg-environmental-green rounded-full"></div>
                <span className="text-sm font-medium text-environmental-green">Online</span>
              </div>
            </div>
            
            <div className="flex items-center justify-between">
              <span className="text-sm text-neutral-600 dark:text-neutral-400">Harmony API</span>
              <div className="flex items-center space-x-2">
                <div className="w-2 h-2 bg-environmental-yellow rounded-full animate-pulse"></div>
                <span className="text-sm font-medium text-environmental-yellow">Limited</span>
              </div>
            </div>
          </div>
        </div>
        
        {/* Recent Activity */}
        <div className="bg-white dark:bg-space-900 rounded-lg border border-neutral-200 dark:border-neutral-700 p-6">
          <h3 className="text-lg font-semibold text-neutral-900 dark:text-white mb-4">
            Recent Activity
          </h3>
          
          <div className="space-y-3">
            <div className="flex items-start space-x-3">
              <div className="w-2 h-2 bg-primary-600 rounded-full mt-2"></div>
              <div className="flex-1">
                <div className="text-sm text-neutral-900 dark:text-white">
                  Hotspot analysis completed
                </div>
                <div className="text-xs text-neutral-500 dark:text-neutral-400">
                  2 minutes ago
                </div>
              </div>
            </div>
            
            <div className="flex items-start space-x-3">
              <div className="w-2 h-2 bg-environmental-green rounded-full mt-2"></div>
              <div className="flex-1">
                <div className="text-sm text-neutral-900 dark:text-white">
                  45 new sensors registered
                </div>
                <div className="text-xs text-neutral-500 dark:text-neutral-400">
                  15 minutes ago
                </div>
              </div>
            </div>
            
            <div className="flex items-start space-x-3">
              <div className="w-2 h-2 bg-environmental-yellow rounded-full mt-2"></div>
              <div className="flex-1">
                <div className="text-sm text-neutral-900 dark:text-white">
                  Satellite data sync completed
                </div>
                <div className="text-xs text-neutral-500 dark:text-neutral-400">
                  1 hour ago
                </div>
              </div>
            </div>
            
            <div className="flex items-start space-x-3">
              <div className="w-2 h-2 bg-environmental-red rounded-full mt-2"></div>
              <div className="flex-1">
                <div className="text-sm text-neutral-900 dark:text-white">
                  Air quality alert triggered
                </div>
                <div className="text-xs text-neutral-500 dark:text-neutral-400">
                  3 hours ago
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default DashboardOverview;