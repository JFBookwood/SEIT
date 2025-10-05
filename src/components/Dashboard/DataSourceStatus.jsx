import React from 'react';
import { 
  Wifi, 
  WifiOff, 
  CheckCircle, 
  AlertTriangle, 
  Clock,
  Database,
  Satellite,
  Activity
} from 'lucide-react';

function DataSourceStatus({ 
  dataSources = {},
  lastUpdated = null,
  onRefresh = null,
  className = ""
}) {
  const getStatusInfo = (source) => {
    const data = dataSources[source];
    if (!data) {
      return {
        status: 'unknown',
        icon: WifiOff,
        color: 'text-neutral-400',
        bgColor: 'bg-neutral-100 dark:bg-neutral-700',
        message: 'No data'
      };
    }

    if (data.error) {
      return {
        status: 'error',
        icon: AlertTriangle,
        color: 'text-environmental-red',
        bgColor: 'bg-environmental-red/10',
        message: data.error
      };
    }

    if (data.count > 0) {
      return {
        status: 'success',
        icon: CheckCircle,
        color: 'text-environmental-green',
        bgColor: 'bg-environmental-green/10',
        message: `${data.count} sensors`
      };
    }

    return {
      status: 'warning',
      icon: Clock,
      color: 'text-environmental-yellow',
      bgColor: 'bg-environmental-yellow/10',
      message: 'No sensors found'
    };
  };

  const sources = [
    {
      key: 'purpleair',
      name: 'PurpleAir',
      description: 'Real-time air quality sensors',
      icon: Activity
    },
    {
      key: 'sensor_community',
      name: 'Sensor.Community',
      description: 'Open sensor network',
      icon: Database
    },
    {
      key: 'satellite',
      name: 'NASA GIBS',
      description: 'Satellite imagery layers',
      icon: Satellite
    }
  ];

  return (
    <div className={`bg-white dark:bg-space-900 rounded-lg border border-neutral-200 dark:border-neutral-700 p-6 ${className}`}>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-neutral-900 dark:text-white">
          Data Sources
        </h3>
        {onRefresh && (
          <button
            onClick={onRefresh}
            className="text-primary-600 hover:text-primary-700 transition-colors"
            title="Refresh data sources"
          >
            <Activity className="w-4 h-4" />
          </button>
        )}
      </div>

      <div className="space-y-4">
        {sources.map(source => {
          const statusInfo = getStatusInfo(source.key);
          const StatusIcon = statusInfo.icon;
          const SourceIcon = source.icon;

          return (
            <div
              key={source.key}
              className="flex items-center space-x-3 p-3 rounded-lg border border-neutral-200 dark:border-neutral-700 hover:bg-neutral-50 dark:hover:bg-neutral-800 transition-colors"
            >
              <div className={`p-2 rounded-lg ${statusInfo.bgColor}`}>
                <SourceIcon className="w-5 h-5 text-neutral-600 dark:text-neutral-400" />
              </div>

              <div className="flex-1 min-w-0">
                <div className="flex items-center space-x-2">
                  <h4 className="font-medium text-neutral-900 dark:text-white">
                    {source.name}
                  </h4>
                  <StatusIcon className={`w-4 h-4 ${statusInfo.color}`} />
                </div>
                <p className="text-sm text-neutral-600 dark:text-neutral-400">
                  {source.description}
                </p>
              </div>

              <div className="text-right">
                <p className={`text-sm font-medium ${statusInfo.color}`}>
                  {statusInfo.status.charAt(0).toUpperCase() + statusInfo.status.slice(1)}
                </p>
                <p className="text-xs text-neutral-500 dark:text-neutral-400">
                  {statusInfo.message}
                </p>
              </div>
            </div>
          );
        })}
      </div>

      {lastUpdated && (
        <div className="mt-4 pt-4 border-t border-neutral-200 dark:border-neutral-700">
          <div className="flex items-center justify-between text-sm text-neutral-500 dark:text-neutral-400">
            <span>Last updated:</span>
            <span>{new Date(lastUpdated).toLocaleString()}</span>
          </div>
        </div>
      )}
    </div>
  );
}

export default DataSourceStatus;
