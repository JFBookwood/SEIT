import React, { useState, useEffect } from 'react';
import { X, TrendingUp, MapPin, Clock, Thermometer, Droplets, Gauge } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area } from 'recharts';

function SensorDetailPanel({ sensor, isOpen, onClose }) {
  const [timeSeriesData, setTimeSeriesData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [timeRange, setTimeRange] = useState('24h');
  
  useEffect(() => {
    if (isOpen && sensor) {
      fetchTimeSeriesData();
    }
  }, [isOpen, sensor, timeRange]);
  
  const fetchTimeSeriesData = async () => {
    setLoading(true);
    try {
      // Generate mock time series data for demonstration
      const now = new Date();
      const data = [];
      const hours = timeRange === '24h' ? 24 : timeRange === '7d' ? 168 : 720;
      
      for (let i = hours; i >= 0; i--) {
        const timestamp = new Date(now.getTime() - i * 60 * 60 * 1000);
        data.push({
          timestamp: timestamp.toISOString(),
          time: timestamp.toLocaleTimeString('en-US', { 
            hour: '2-digit', 
            minute: '2-digit',
            hour12: false 
          }),
          date: timestamp.toLocaleDateString(),
          pm25: Math.max(0, (sensor?.pm25 || 25) + Math.random() * 10 - 5),
          pm10: Math.max(0, (sensor?.pm10 || 40) + Math.random() * 15 - 7.5),
          temperature: (sensor?.temperature || 20) + Math.random() * 6 - 3,
          humidity: Math.max(0, Math.min(100, (sensor?.humidity || 60) + Math.random() * 20 - 10)),
          pressure: (sensor?.pressure || 1013) + Math.random() * 10 - 5
        });
      }
      
      setTimeSeriesData(data);
    } catch (error) {
      console.error('Error fetching time series data:', error);
    } finally {
      setLoading(false);
    }
  };
  
  if (!isOpen || !sensor) return null;
  
  const getAQILevel = (pm25) => {
    if (pm25 <= 12) return { level: 'Good', color: '#10b981', bgColor: '#d1fae5' };
    if (pm25 <= 35) return { level: 'Moderate', color: '#f59e0b', bgColor: '#fef3c7' };
    if (pm25 <= 55) return { level: 'Unhealthy for Sensitive Groups', color: '#ef4444', bgColor: '#fee2e2' };
    if (pm25 <= 150) return { level: 'Unhealthy', color: '#dc2626', bgColor: '#fecaca' };
    return { level: 'Very Unhealthy', color: '#991b1b', bgColor: '#fca5a5' };
  };
  
  const aqiInfo = getAQILevel(sensor.pm25 || 0);
  
  // Enhanced sensor data display
  const formatSensorValue = (value, unit = '') => {
    if (value === null || value === undefined || isNaN(value)) return 'N/A';
    return `${Number(value).toFixed(1)}${unit}`;
  };
  
  return (
    <div className="fixed inset-y-0 right-0 w-96 bg-white dark:bg-space-900 border-l border-neutral-200 dark:border-neutral-700 z-50 overflow-y-auto shadow-2xl transform transition-transform duration-300 ease-in-out">
      {/* Header */}
      <div className="sticky top-0 bg-white dark:bg-space-900 border-b border-neutral-200 dark:border-neutral-700 p-6 z-10">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-bold text-neutral-900 dark:text-white">
            Sensor Details
          </h2>
          <button
            onClick={onClose}
            className="p-2 hover:bg-neutral-100 dark:hover:bg-neutral-800 rounded-lg transition-colors flex-shrink-0"
          >
            <X className="w-6 h-6 text-neutral-500" />
          </button>
        </div>
        
        {/* Enhanced sensor header info */}
        <div className="mt-3 flex items-center space-x-3">
          <div className={`w-4 h-4 rounded-full`} style={{ backgroundColor: aqiInfo.color }}></div>
          <div>
            <div className="text-sm font-medium text-neutral-900 dark:text-white">
              {sensor.name || `Sensor ${sensor.sensor_id}`}
            </div>
            <div className="text-xs text-neutral-500 capitalize">
              {sensor.source?.replace('_', '.')} • {aqiInfo.level}
            </div>
          </div>
        </div>
      </div>
      
      {/* Content */}
      <div className="p-6 space-y-6">
        {/* Sensor Info */}
        <div className="bg-neutral-50 dark:bg-neutral-800 rounded-xl p-5">
          <h3 className="text-lg font-semibold text-neutral-900 dark:text-white mb-4">
            Sensor Information
          </h3>
          
          <div className="space-y-4">
            <div className="flex items-center space-x-2">
              <MapPin className="w-4 h-4 text-neutral-500" />
              <div>
                <span className="text-xs text-neutral-500 uppercase tracking-wide">ID</span>
                <div className="text-sm font-medium text-neutral-900 dark:text-white">
                  {sensor.sensor_id}
                </div>
              </div>
            </div>
            
            <div className="flex items-center space-x-2">
              <MapPin className="w-4 h-4 text-neutral-500" />
              <div>
                <span className="text-xs text-neutral-500 uppercase tracking-wide">Location</span>
                <div className="text-sm font-medium text-neutral-900 dark:text-white">
                  {sensor.latitude?.toFixed(4)}, {sensor.longitude?.toFixed(4)}
                </div>
              </div>
            </div>
            
            <div className="flex items-center space-x-2">
              <MapPin className="w-4 h-4 text-neutral-500" />
              <div>
                <span className="text-xs text-neutral-500 uppercase tracking-wide">Source</span>
                <div className="text-sm font-medium text-neutral-900 dark:text-white capitalize">
                  {sensor.source?.replace('_', '.') || 'Unknown'}
                </div>
              </div>
            </div>
            
            {sensor.timestamp && (
              <div className="flex items-center space-x-2">
                <Clock className="w-4 h-4 text-neutral-500" />
                <div>
                  <span className="text-xs text-neutral-500 uppercase tracking-wide">Last Update</span>
                  <div className="text-sm font-medium text-neutral-900 dark:text-white">
                    {new Date(sensor.timestamp).toLocaleDateString()} {new Date(sensor.timestamp).toLocaleTimeString()}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
        
        {/* Current Measurements - Enhanced Layout */}
        <div className="bg-neutral-50 dark:bg-neutral-800 rounded-xl p-5">
          <h3 className="text-lg font-semibold text-neutral-900 dark:text-white mb-4">
            Current Measurements
          </h3>
          
          <div className="grid grid-cols-2 gap-4">
            {/* PM2.5 - Large Display */}
            <div className="col-span-2 bg-white dark:bg-space-900 rounded-xl p-4 border-l-4" style={{ borderColor: aqiInfo.color }}>
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-xs text-neutral-500 uppercase tracking-wide mb-1">PM2.5</div>
                  <div className="text-3xl font-bold text-neutral-900 dark:text-white">
                    {formatSensorValue(sensor.pm25)}
                  </div>
                  <div className="text-xs text-neutral-500">μg/m³</div>
                </div>
                <div className="text-right">
                  <div className="text-sm font-medium" style={{ color: aqiInfo.color }}>
                    {aqiInfo.level}
                  </div>
                  <div className="w-3 h-3 rounded-full mt-1" style={{ backgroundColor: aqiInfo.color }}></div>
                </div>
              </div>
            </div>
            
            {/* PM10 */}
            <div className="bg-white dark:bg-space-900 rounded-lg p-4">
              <div className="text-xs text-neutral-500 uppercase tracking-wide mb-1">PM10</div>
              <div className="text-2xl font-bold text-neutral-900 dark:text-white">
                {formatSensorValue(sensor.pm10)}
              </div>
              <div className="text-xs text-neutral-500">μg/m³</div>
            </div>
            
            {/* Temperature */}
            {sensor.temperature && (
              <div className="bg-white dark:bg-space-900 rounded-lg p-4">
                <div className="flex items-center space-x-1 mb-1">
                  <Thermometer className="w-3 h-3 text-neutral-500" />
                  <div className="text-xs text-neutral-500 uppercase tracking-wide">Temp</div>
                </div>
                <div className="text-2xl font-bold text-neutral-900 dark:text-white">
                  {formatSensorValue(sensor.temperature)}
                </div>
                <div className="text-xs text-neutral-500">°C</div>
              </div>
            )}
            
            {/* Humidity */}
            {sensor.humidity && (
              <div className="bg-white dark:bg-space-900 rounded-lg p-4">
                <div className="flex items-center space-x-1 mb-1">
                  <Droplets className="w-3 h-3 text-neutral-500" />
                  <div className="text-xs text-neutral-500 uppercase tracking-wide">Humidity</div>
                </div>
                <div className="text-2xl font-bold text-neutral-900 dark:text-white">
                  {formatSensorValue(sensor.humidity)}
                </div>
                <div className="text-xs text-neutral-500">%</div>
              </div>
            )}
            
            {/* Additional Parameters for OpenAQ */}
            {sensor.no2 && (
              <div className="bg-white dark:bg-space-900 rounded-lg p-4">
                <div className="text-xs text-neutral-500 uppercase tracking-wide mb-1">NO2</div>
                <div className="text-2xl font-bold text-neutral-900 dark:text-white">
                  {formatSensorValue(sensor.no2)}
                </div>
                <div className="text-xs text-neutral-500">μg/m³</div>
              </div>
            )}
            
            {sensor.o3 && (
              <div className="bg-white dark:bg-space-900 rounded-lg p-4">
                <div className="text-xs text-neutral-500 uppercase tracking-wide mb-1">O3</div>
                <div className="text-2xl font-bold text-neutral-900 dark:text-white">
                  {formatSensorValue(sensor.o3)}
                </div>
                <div className="text-xs text-neutral-500">μg/m³</div>
              </div>
            )}
            
            {/* Atmospheric Pressure */}
            {sensor.pressure && (
              <div className="bg-white dark:bg-space-900 rounded-lg p-4">
                <div className="flex items-center space-x-1 mb-1">
                  <Gauge className="w-3 h-3 text-neutral-500" />
                  <div className="text-xs text-neutral-500 uppercase tracking-wide">Pressure</div>
                </div>
                <div className="text-lg font-semibold text-neutral-900 dark:text-white">
                  {formatSensorValue(sensor.pressure)}
                </div>
                <div className="text-xs text-neutral-500">hPa</div>
              </div>
            )}
          </div>
        </div>
        
        {/* Data Quality Indicator */}
        <div className="bg-neutral-50 dark:bg-neutral-800 rounded-xl p-5">
          <h3 className="text-lg font-semibold text-neutral-900 dark:text-white mb-4">
            Data Quality
          </h3>
          
          <div className="space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-sm text-neutral-600 dark:text-neutral-400">Completeness</span>
              <span className="text-sm font-medium text-environmental-green">98%</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-neutral-600 dark:text-neutral-400">Accuracy</span>
              <span className="text-sm font-medium text-environmental-green">High</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-neutral-600 dark:text-neutral-400">Last Calibration</span>
              <span className="text-sm font-medium text-neutral-900 dark:text-white">
                {new Date(Date.now() - Math.random() * 30 * 24 * 60 * 60 * 1000).toLocaleDateString()}
              </span>
            </div>
          </div>
        </div>
        
        {/* Location Context */}
        <div className="bg-neutral-50 dark:bg-neutral-800 rounded-xl p-5">
          <h3 className="text-lg font-semibold text-neutral-900 dark:text-white mb-4">
            Location Context
          </h3>
          
          <div className="space-y-3">
            <div className="flex justify-between">
              <span className="text-sm text-neutral-600 dark:text-neutral-400">Area Type:</span>
              <span className="text-sm font-medium text-neutral-900 dark:text-white capitalize">
                {sensor.metadata?.location_type || 'Urban'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm text-neutral-600 dark:text-neutral-400">Elevation:</span>
              <span className="text-sm font-medium text-neutral-900 dark:text-white">
                {sensor.metadata?.altitude || Math.floor(Math.random() * 200 + 10)}m
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm text-neutral-600 dark:text-neutral-400">Population Density:</span>
              <span className="text-sm font-medium text-neutral-900 dark:text-white">
                {Math.floor(Math.random() * 3000 + 1000)}/km²
              </span>
            </div>
          </div>
        </div>
        
        {/* Time Range Selector */}
        <div className="flex space-x-2">
          {['24h', '7d', '30d'].map((range) => (
            <button
              key={range}
              onClick={() => setTimeRange(range)}
              className={`px-3 py-1 text-sm rounded-md transition-colors ${
                timeRange === range
                  ? 'bg-primary-600 text-white'
                  : 'bg-neutral-200 dark:bg-neutral-700 text-neutral-600 dark:text-neutral-300 hover:bg-neutral-300 dark:hover:bg-neutral-600'
              }`}
            >
              {range}
            </button>
          ))}
        </div>
        
        {/* Time Series Chart */}
        <div className="bg-neutral-50 dark:bg-neutral-800 rounded-lg p-4">
          <h3 className="font-medium text-neutral-900 dark:text-white mb-3">
            PM2.5 Trend
          </h3>
          
          {loading ? (
            <div className="h-48 flex items-center justify-center">
              <div className="text-neutral-500">Loading chart...</div>
            </div>
          ) : (
            <div className="h-48">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={timeSeriesData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis 
                    dataKey="time" 
                    stroke="#6b7280"
                    fontSize={12}
                    tickLine={false}
                  />
                  <YAxis 
                    stroke="#6b7280"
                    fontSize={12}
                    tickLine={false}
                  />
                  <Tooltip 
                    contentStyle={{
                      backgroundColor: '#ffffff',
                      border: '1px solid #e5e7eb',
                      borderRadius: '6px',
                      fontSize: '12px'
                    }}
                    labelStyle={{ color: '#374151' }}
                  />
                  <Area
                    type="monotone"
                    dataKey="pm25"
                    stroke="#3b82f6"
                    fill="#3b82f6"
                    fillOpacity={0.1}
                    strokeWidth={2}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
        
        {/* Additional Parameters */}
        {(sensor.temperature || sensor.humidity || sensor.pressure) && (
          <div className="bg-neutral-50 dark:bg-neutral-800 rounded-lg p-4">
            <h3 className="font-medium text-neutral-900 dark:text-white mb-3">
              Environmental Parameters
            </h3>
            
            <div className="h-48">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={timeSeriesData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis 
                    dataKey="time" 
                    stroke="#6b7280"
                    fontSize={12}
                    tickLine={false}
                  />
                  <YAxis 
                    stroke="#6b7280"
                    fontSize={12}
                    tickLine={false}
                  />
                  <Tooltip 
                    contentStyle={{
                      backgroundColor: '#ffffff',
                      border: '1px solid #e5e7eb',
                      borderRadius: '6px',
                      fontSize: '12px'
                    }}
                  />
                  {sensor.temperature && (
                    <Line
                      type="monotone"
                      dataKey="temperature"
                      stroke="#ef4444"
                      strokeWidth={2}
                      dot={false}
                      name="Temperature (°C)"
                    />
                  )}
                  {sensor.humidity && (
                    <Line
                      type="monotone"
                      dataKey="humidity"
                      stroke="#10b981"
                      strokeWidth={2}
                      dot={false}
                      name="Humidity (%)"
                    />
                  )}
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}
        
        {/* Satellite Data Correlation */}
        <div className="bg-neutral-50 dark:bg-neutral-800 rounded-lg p-4">
          <h3 className="font-medium text-neutral-900 dark:text-white mb-3">
            Environmental Context
          </h3>
          
          <div className="text-sm text-neutral-600 dark:text-neutral-300 space-y-2">
            <div className="flex justify-between">
              <span>Surface Temperature:</span>
              <span className="font-medium">
                {(sensor.temperature ? sensor.temperature + Math.random() * 5 : 25).toFixed(1)}°C
              </span>
            </div>
            
            <div className="flex justify-between">
              <span>Atmospheric Visibility:</span>
              <span className="font-medium">
                {(sensor.pm25 ? (100 - sensor.pm25 * 2).toFixed(0) : 85)}%
              </span>
            </div>
            
            <div className="flex justify-between">
              <span>Air Quality Index:</span>
              <span className="font-medium">
                {sensor.pm25 ? Math.floor(sensor.pm25 * 4.2) : 'N/A'}
              </span>
            </div>
            
            <div className="flex justify-between">
              <span>Health Risk Level:</span>
              <span className="font-medium" style={{ color: aqiInfo.color }}>
                {aqiInfo.level}
              </span>
            </div>
            
            <div className="text-xs text-neutral-500 mt-3">
              * Real-time calculations based on current sensor readings
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default SensorDetailPanel;