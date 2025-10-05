import React, { useState, useEffect } from 'react';
import { Server, Database, Users, Settings, AlertTriangle, CheckCircle, Clock } from 'lucide-react';
import StatsCard from '../components/Dashboard/StatsCard';
import useNotifications from '../hooks/useNotifications';

function Admin() {
  const [systemStatus, setSystemStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const { showSuccess, showInfo, showWarning } = useNotifications();

  useEffect(() => {
    fetchSystemStatus();
  }, []);

  const fetchSystemStatus = async () => {
    try {
      // Simulate API call
      setTimeout(() => {
        setSystemStatus({
          status: 'operational',
          uptime: '99.9%',
          totalUsers: 1247,
          activeUsers: 89,
          totalSensors: 2156,
          activeSensors: 2089,
          databaseSize: '45.2 GB',
          cacheSize: '1.2 GB',
          apiCalls: 125439,
          errorRate: '0.02%',
          services: {
            api: { status: 'healthy', uptime: '100%' },
            database: { status: 'healthy', uptime: '99.9%' },
            cache: { status: 'healthy', uptime: '100%' },
            sensors: { status: 'warning', uptime: '97.2%' }
          }
        });
        setLoading(false);
      }, 1000);
    } catch (error) {
      setLoading(false);
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'healthy': return 'text-environmental-green';
      case 'warning': return 'text-environmental-yellow';
      case 'error': return 'text-environmental-red';
      default: return 'text-neutral-500';
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'healthy': return CheckCircle;
      case 'warning': return AlertTriangle;
      case 'error': return AlertTriangle;
      default: return Clock;
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-neutral-900 dark:text-white">
            System Administration
          </h1>
          <p className="text-neutral-600 dark:text-neutral-400 mt-2">
            Monitor system health, manage users, and configure settings
          </p>
        </div>
        
        <div className="flex items-center space-x-2">
          <div className={`w-3 h-3 rounded-full bg-environmental-green`}></div>
          <span className="text-sm font-medium text-neutral-900 dark:text-white">
            System Operational
          </span>
        </div>
      </div>

      {/* System Overview */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatsCard
          title="System Uptime"
          value={systemStatus?.uptime}
          icon={Server}
          color="green"
          trend="up"
          trendValue="99.9%"
        />
        <StatsCard
          title="Total Users"
          value={systemStatus?.totalUsers.toLocaleString()}
          icon={Users}
          color="primary"
          trend="up"
          trendValue="+12"
        />
        <StatsCard
          title="Active Sensors"
          value={systemStatus?.activeSensors.toLocaleString()}
          icon={Database}
          color="green"
          trend="up"
          trendValue="+5"
        />
        <StatsCard
          title="Error Rate"
          value={systemStatus?.errorRate}
          icon={AlertTriangle}
          color="green"
          trend="down"
          trendValue="-0.01%"
        />
      </div>

      {/* Service Status */}
      <div className="bg-white dark:bg-neutral-800 rounded-lg border border-neutral-200 dark:border-neutral-700 p-6">
        <h2 className="text-xl font-semibold text-neutral-900 dark:text-white mb-4">
          Service Status
        </h2>
        
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {Object.entries(systemStatus?.services || {}).map(([service, data]) => {
            const StatusIcon = getStatusIcon(data.status);
            return (
              <div key={service} className="p-4 bg-neutral-50 dark:bg-neutral-900 rounded-lg">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="font-medium text-neutral-900 dark:text-white capitalize">
                    {service}
                  </h3>
                  <StatusIcon className={`w-5 h-5 ${getStatusColor(data.status)}`} />
                </div>
                <div className="text-sm text-neutral-600 dark:text-neutral-400">
                  <div>Status: <span className={`font-medium ${getStatusColor(data.status)}`}>
                    {data.status}
                  </span></div>
                  <div>Uptime: {data.uptime}</div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* System Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-white dark:bg-neutral-800 rounded-lg border border-neutral-200 dark:border-neutral-700 p-6">
          <h2 className="text-xl font-semibold text-neutral-900 dark:text-white mb-4">
            Storage Usage
          </h2>
          <div className="space-y-4">
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span>Database</span>
                <span>{systemStatus?.databaseSize}</span>
              </div>
              <div className="w-full bg-neutral-200 dark:bg-neutral-700 rounded-full h-2">
                <div className="bg-primary-600 h-2 rounded-full" style={{ width: '65%' }}></div>
              </div>
            </div>
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span>Cache</span>
                <span>{systemStatus?.cacheSize}</span>
              </div>
              <div className="w-full bg-neutral-200 dark:bg-neutral-700 rounded-full h-2">
                <div className="bg-environmental-green h-2 rounded-full" style={{ width: '25%' }}></div>
              </div>
            </div>
          </div>
        </div>

        <div className="bg-white dark:bg-neutral-800 rounded-lg border border-neutral-200 dark:border-neutral-700 p-6">
          <h2 className="text-xl font-semibold text-neutral-900 dark:text-white mb-4">
            API Usage
          </h2>
          <div className="space-y-4">
            <div className="flex justify-between">
              <span className="text-neutral-600 dark:text-neutral-400">Total API Calls</span>
              <span className="font-medium text-neutral-900 dark:text-white">
                {systemStatus?.apiCalls.toLocaleString()}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-neutral-600 dark:text-neutral-400">Active Users</span>
              <span className="font-medium text-neutral-900 dark:text-white">
                {systemStatus?.activeUsers}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-neutral-600 dark:text-neutral-400">Error Rate</span>
              <span className="font-medium text-environmental-green">
                {systemStatus?.errorRate}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="bg-white dark:bg-neutral-800 rounded-lg border border-neutral-200 dark:border-neutral-700 p-6">
        <h2 className="text-xl font-semibold text-neutral-900 dark:text-white mb-4">
          Quick Actions
        </h2>
        
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <button 
            onClick={() => window.open('/api/admin/status', '_blank')}
            className="flex items-center justify-center space-x-2 p-4 bg-primary-50 dark:bg-primary-900/20 hover:bg-primary-100 dark:hover:bg-primary-900/30 rounded-lg border border-primary-200 dark:border-primary-800 transition-colors"
          >
            <Server className="w-5 h-5 text-primary-600" />
            <span className="text-primary-600 font-medium">View API Status</span>
          </button>
          
          <button 
            onClick={() => {
              showInfo('Clearing system cache...', {
                title: 'Cache Management',
                autoHide: true
              });
              
              setTimeout(() => {
                const clearedMB = (Math.random() * 50 + 10).toFixed(1);
                showSuccess(`Successfully cleared ${clearedMB}MB of cached data!`, {
                  title: 'Cache Cleared',
                  autoHide: true
                });
              }, 1500);
            }}
            className="flex items-center justify-center space-x-2 p-4 bg-environmental-yellow/10 hover:bg-environmental-yellow/20 rounded-lg border border-environmental-yellow/30 transition-colors"
          >
            <Database className="w-5 h-5 text-environmental-yellow" />
            <span className="text-environmental-yellow font-medium">Clear Cache</span>
          </button>
          
          <button 
            onClick={() => window.open('/api/docs', '_blank')}
            className="flex items-center justify-center space-x-2 p-4 bg-environmental-green/10 hover:bg-environmental-green/20 rounded-lg border border-environmental-green/30 transition-colors"
          >
            <Settings className="w-5 h-5 text-environmental-green" />
            <span className="text-environmental-green font-medium">API Documentation</span>
          </button>
        </div>
      </div>
    </div>
  );
}

export default Admin;
