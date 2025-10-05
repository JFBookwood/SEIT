import React, { useState, useEffect } from 'react';
import { Shield, Satellite, AlertTriangle, CheckCircle, RefreshCw, Key, Clock, Activity } from 'lucide-react';
import useNotifications from '../../hooks/useNotifications';

function NASATokenManager() {
  const [tokenStatus, setTokenStatus] = useState(null);
  const [usageStats, setUsageStats] = useState(null);
  const [apiTestResults, setApiTestResults] = useState(null);
  const [loading, setLoading] = useState(true);
  const [validating, setValidating] = useState(false);
  const [testing, setTesting] = useState(false);
  
  const { showSuccess, showError, showWarning, showInfo } = useNotifications();

  useEffect(() => {
    fetchTokenStatus();
    fetchUsageStats();
  }, []);

  const fetchTokenStatus = async () => {
    try {
      const response = await fetch('/api/admin/nasa/token-status');
      const data = await response.json();
      setTokenStatus(data.token_status);
    } catch (error) {
      console.error('Failed to fetch NASA token status:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchUsageStats = async () => {
    try {
      const response = await fetch('/api/admin/nasa/usage-statistics?days_back=7');
      const data = await response.json();
      setUsageStats(data);
    } catch (error) {
      console.error('Failed to fetch usage stats:', error);
    }
  };

  const handleValidateToken = async () => {
    setValidating(true);
    try {
      showInfo("Validating NASA Earthdata token...", {
        title: 'Token Validation',
        autoHide: true
      });
      
      const response = await fetch('/api/admin/nasa/validate-token', { method: 'POST' });
      const result = await response.json();
      
      if (result.valid) {
        showSuccess("NASA token is valid and authenticated!", {
          title: 'Token Valid',
          autoHide: false
        });
      } else {
        showWarning(`Token validation failed: ${result.errors?.join(', ') || 'Unknown error'}`, {
          title: 'Token Issues',
          autoHide: false
        });
      }
      
      fetchTokenStatus(); // Refresh status
    } catch (error) {
      showError("Token validation request failed", {
        title: 'Validation Error',
        autoHide: false
      });
    } finally {
      setValidating(false);
    }
  };

  const handleTestApiAccess = async () => {
    setTesting(true);
    try {
      showInfo("Testing NASA API endpoints...", {
        title: 'API Access Test',
        autoHide: true
      });
      
      const response = await fetch('/api/admin/nasa/test-api-access', { method: 'POST' });
      const result = await response.json();
      setApiTestResults(result);
      
      if (result.overall_status === 'all_accessible') {
        showSuccess("All NASA APIs are accessible and working!", {
          title: 'API Test Successful',
          autoHide: false
        });
      } else if (result.overall_status === 'partial_access') {
        showWarning("Some NASA APIs are accessible, check individual service status", {
          title: 'Partial API Access',
          autoHide: false
        });
      } else {
        showError("NASA API access failed - check token and network connectivity", {
          title: 'API Access Failed',
          autoHide: false
        });
      }
    } catch (error) {
      showError("API access test request failed", {
        title: 'Test Error',
        autoHide: false
      });
    } finally {
      setTesting(false);
    }
  };

  const handleRefreshUsageStats = async () => {
    showInfo("Refreshing usage statistics...", { autoHide: true });
    await fetchUsageStats();
    await fetchTokenStatus();
    showSuccess("Usage statistics updated", { autoHide: true });
  };

  const getStatusIcon = (configured, daysRemaining) => {
    if (!configured) return <AlertTriangle className="w-5 h-5 text-environmental-red" />;
    if (daysRemaining <= 7) return <AlertTriangle className="w-5 h-5 text-environmental-red" />;
    if (daysRemaining <= 30) return <Clock className="w-5 h-5 text-environmental-yellow" />;
    return <CheckCircle className="w-5 h-5 text-environmental-green" />;
  };

  const getStatusColor = (configured, daysRemaining) => {
    if (!configured) return 'text-environmental-red';
    if (daysRemaining <= 7) return 'text-environmental-red';
    if (daysRemaining <= 30) return 'text-environmental-yellow';
    return 'text-environmental-green';
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Token Status Overview */}
      <div className="bg-white dark:bg-neutral-800 rounded-lg border border-neutral-200 dark:border-neutral-700 p-6">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-semibold text-neutral-900 dark:text-white">
            NASA Earthdata Token Management
          </h2>
          <button
            onClick={handleRefreshUsageStats}
            className="p-2 rounded-lg bg-neutral-100 dark:bg-neutral-700 hover:bg-neutral-200 dark:hover:bg-neutral-600 transition-colors"
            title="Refresh statistics"
          >
            <RefreshCw className="w-4 h-4 text-neutral-600 dark:text-neutral-400" />
          </button>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Token Information */}
          <div className="space-y-4">
            <div className="flex items-center space-x-3">
              {getStatusIcon(tokenStatus?.configured, tokenStatus?.days_until_expiry)}
              <div>
                <h3 className="font-medium text-neutral-900 dark:text-white">Token Status</h3>
                <p className={`text-sm ${getStatusColor(tokenStatus?.configured, tokenStatus?.days_until_expiry)}`}>
                  {tokenStatus?.configured ? 'Configured and Active' : 'Not Configured'}
                </p>
              </div>
            </div>
            
            {tokenStatus?.metadata && (
              <div className="bg-neutral-50 dark:bg-neutral-900 rounded-lg p-4">
                <h4 className="font-medium text-neutral-900 dark:text-white mb-3">Token Details</h4>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-neutral-600 dark:text-neutral-400">User ID:</span>
                    <span className="font-medium text-neutral-900 dark:text-white">
                      {tokenStatus.metadata.user_id || 'Unknown'}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-neutral-600 dark:text-neutral-400">Issued:</span>
                    <span className="font-medium text-neutral-900 dark:text-white">
                      {tokenStatus.metadata.issued_at ? new Date(tokenStatus.metadata.issued_at).toLocaleDateString() : 'Unknown'}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-neutral-600 dark:text-neutral-400">Expires:</span>
                    <span className={`font-medium ${getStatusColor(true, tokenStatus.days_until_expiry)}`}>
                      {tokenStatus.expires_at ? new Date(tokenStatus.expires_at).toLocaleDateString() : 'Unknown'}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-neutral-600 dark:text-neutral-400">Days Remaining:</span>
                    <span className={`font-medium ${getStatusColor(true, tokenStatus.days_until_expiry)}`}>
                      {tokenStatus.days_until_expiry || 'Unknown'}
                    </span>
                  </div>
                </div>
              </div>
            )}
          </div>
          
          {/* Usage Statistics */}
          <div className="space-y-4">
            <h3 className="font-medium text-neutral-900 dark:text-white">API Usage (7 Days)</h3>
            
            {usageStats ? (
              <div className="bg-neutral-50 dark:bg-neutral-900 rounded-lg p-4">
                <div className="space-y-3 text-sm">
                  <div className="flex justify-between">
                    <span className="text-neutral-600 dark:text-neutral-400">Total Requests:</span>
                    <span className="font-medium text-neutral-900 dark:text-white">
                      {usageStats.total_requests || 0}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-neutral-600 dark:text-neutral-400">Success Rate:</span>
                    <span className="font-medium text-environmental-green">
                      {usageStats.success_rate ? `${(usageStats.success_rate * 100).toFixed(1)}%` : 'N/A'}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-neutral-600 dark:text-neutral-400">Data Transferred:</span>
                    <span className="font-medium text-neutral-900 dark:text-white">
                      {usageStats.total_data_transferred_mb ? `${usageStats.total_data_transferred_mb.toFixed(1)} MB` : 'N/A'}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-neutral-600 dark:text-neutral-400">Avg Response:</span>
                    <span className="font-medium text-neutral-900 dark:text-white">
                      {usageStats.average_response_time_ms ? `${usageStats.average_response_time_ms.toFixed(0)}ms` : 'N/A'}
                    </span>
                  </div>
                </div>
                
                {/* Service Breakdown */}
                {usageStats.service_breakdown && Object.keys(usageStats.service_breakdown).length > 0 && (
                  <div className="mt-4 pt-3 border-t border-neutral-200 dark:border-neutral-700">
                    <h5 className="font-medium text-neutral-900 dark:text-white mb-2">Service Usage</h5>
                    {Object.entries(usageStats.service_breakdown).map(([service, count]) => (
                      <div key={service} className="flex justify-between text-xs">
                        <span className="text-neutral-600 dark:text-neutral-400 capitalize">{service}:</span>
                        <span className="font-medium text-neutral-900 dark:text-white">{count}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <div className="text-sm text-neutral-500">Loading usage statistics...</div>
            )}
          </div>
        </div>
      </div>
      
      {/* NASA API Test Results */}
      {apiTestResults && (
        <div className="bg-white dark:bg-neutral-800 rounded-lg border border-neutral-200 dark:border-neutral-700 p-6">
          <h3 className="text-lg font-semibold text-neutral-900 dark:text-white mb-4">
            NASA API Access Test Results
          </h3>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {Object.entries(apiTestResults.services || {}).map(([service, result]) => (
              <div key={service} className="p-4 bg-neutral-50 dark:bg-neutral-900 rounded-lg">
                <div className="flex items-center justify-between mb-2">
                  <h4 className="font-medium text-neutral-900 dark:text-white capitalize">{service}</h4>
                  <div className={`flex items-center space-x-1 ${
                    result.status === 'accessible' ? 'text-environmental-green' : 'text-environmental-red'
                  }`}>
                    {result.status === 'accessible' ? 
                      <CheckCircle className="w-4 h-4" /> : 
                      <AlertTriangle className="w-4 h-4" />
                    }
                    <span className="text-sm font-medium capitalize">{result.status}</span>
                  </div>
                </div>
                <div className="text-xs space-y-1">
                  <div className="flex justify-between">
                    <span className="text-neutral-600 dark:text-neutral-400">Endpoint:</span>
                    <span className="text-neutral-900 dark:text-white">{result.endpoint}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-neutral-600 dark:text-neutral-400">Response Code:</span>
                    <span className="text-neutral-900 dark:text-white">{result.response_code || 'N/A'}</span>
                  </div>
                  {result.error && (
                    <div className="mt-2 text-environmental-red text-xs">
                      Error: {result.error}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
      
      {/* Token Management Actions */}
      <div className="bg-white dark:bg-neutral-800 rounded-lg border border-neutral-200 dark:border-neutral-700 p-6">
        <h3 className="text-lg font-semibold text-neutral-900 dark:text-white mb-4">
          Token Management Actions
        </h3>
        
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <button 
            onClick={handleValidateToken}
            disabled={validating}
            className="flex items-center justify-center space-x-2 p-4 bg-primary-50 dark:bg-primary-900/20 hover:bg-primary-100 dark:hover:bg-primary-900/30 rounded-lg border border-primary-200 dark:border-primary-800 transition-colors disabled:opacity-50"
          >
            {validating ? (
              <RefreshCw className="w-5 h-5 text-primary-600 animate-spin" />
            ) : (
              <Shield className="w-5 h-5 text-primary-600" />
            )}
            <span className="text-primary-600 font-medium">
              {validating ? 'Validating...' : 'Validate Token'}
            </span>
          </button>
          
          <button 
            onClick={handleTestApiAccess}
            disabled={testing}
            className="flex items-center justify-center space-x-2 p-4 bg-environmental-green/10 hover:bg-environmental-green/20 rounded-lg border border-environmental-green/30 transition-colors disabled:opacity-50"
          >
            {testing ? (
              <RefreshCw className="w-5 h-5 text-environmental-green animate-spin" />
            ) : (
              <Satellite className="w-5 h-5 text-environmental-green" />
            )}
            <span className="text-environmental-green font-medium">
              {testing ? 'Testing...' : 'Test API Access'}
            </span>
          </button>
          
          <button 
            onClick={() => {
              showInfo("Token rotation documentation available at /docs/nasa-token-rotation", {
                title: 'Token Rotation Guide',
                autoHide: false
              });
            }}
            className="flex items-center justify-center space-x-2 p-4 bg-environmental-yellow/10 hover:bg-environmental-yellow/20 rounded-lg border border-environmental-yellow/30 transition-colors"
          >
            <Key className="w-5 h-5 text-environmental-yellow" />
            <span className="text-environmental-yellow font-medium">Rotation Guide</span>
          </button>
        </div>
      </div>
      
      {/* Security Guidelines */}
      <div className="bg-white dark:bg-neutral-800 rounded-lg border border-neutral-200 dark:border-neutral-700 p-6">
        <h3 className="text-lg font-semibold text-neutral-900 dark:text-white mb-4">
          Security Guidelines
        </h3>
        
        <div className="space-y-3 text-sm">
          <div className="flex items-start space-x-3">
            <Shield className="w-4 h-4 text-primary-600 mt-0.5" />
            <div>
              <strong className="text-neutral-900 dark:text-white">Server-Side Only:</strong>
              <span className="text-neutral-600 dark:text-neutral-400"> NASA tokens are stored and used exclusively on the server. Never expose tokens in client-side code.</span>
            </div>
          </div>
          
          <div className="flex items-start space-x-3">
            <Clock className="w-4 h-4 text-environmental-yellow mt-0.5" />
            <div>
              <strong className="text-neutral-900 dark:text-white">Token Expiration:</strong>
              <span className="text-neutral-600 dark:text-neutral-400"> NASA tokens typically expire every 60 days. Monitor expiration and rotate proactively.</span>
            </div>
          </div>
          
          <div className="flex items-start space-x-3">
            <Activity className="w-4 h-4 text-environmental-green mt-0.5" />
            <div>
              <strong className="text-neutral-900 dark:text-white">Usage Monitoring:</strong>
              <span className="text-neutral-600 dark:text-neutral-400"> All NASA API calls are logged for compliance and performance monitoring.</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default NASATokenManager;
