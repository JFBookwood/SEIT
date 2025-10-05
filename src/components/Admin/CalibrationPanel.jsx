import React, { useState, useEffect } from 'react';
import { 
  Settings, 
  CheckCircle, 
  AlertTriangle, 
  RefreshCw, 
  TrendingUp, 
  Database,
  Target,
  BarChart3
} from 'lucide-react';
import useNotifications from '../../hooks/useNotifications';

function CalibrationPanel() {
  const [calibrationStatus, setCalibrationStatus] = useState(null);
  const [selectedSensor, setSelectedSensor] = useState('');
  const [diagnostics, setDiagnostics] = useState(null);
  const [qcSummary, setQcSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [processing, setProcessing] = useState(false);
  
  const { showSuccess, showError, showInfo, showWarning } = useNotifications();

  useEffect(() => {
    fetchCalibrationStatus();
    fetchQCSummary();
  }, []);

  const fetchCalibrationStatus = async () => {
    try {
      const response = await fetch('/api/calibration/status');
      const data = await response.json();
      setCalibrationStatus(data);
    } catch (error) {
      console.error('Failed to fetch calibration status:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchQCSummary = async () => {
    try {
      const response = await fetch('/api/data/qc-summary?hours_back=24');
      const data = await response.json();
      setQcSummary(data);
    } catch (error) {
      console.error('Failed to fetch QC summary:', error);
    }
  };

  const fetchSensorDiagnostics = async (sensorId) => {
    if (!sensorId) return;
    
    try {
      setLoading(true);
      const response = await fetch(`/api/sensors/calibration/diagnostics/${sensorId}`);
      const data = await response.json();
      setDiagnostics(data);
    } catch (error) {
      showError(`Failed to fetch diagnostics for sensor ${sensorId}`, {
        title: 'Diagnostic Error',
        autoHide: false
      });
    } finally {
      setLoading(false);
    }
  };

  const handleAutoCalibration = async () => {
    setProcessing(true);
    try {
      showInfo("Starting automatic calibration for sensors...", {
        title: 'Auto-Calibration Started',
        autoHide: true
      });
      
      const response = await fetch('/api/sensors/auto-calibrate', { method: 'POST' });
      const result = await response.json();
      
      if (result.status === 'completed') {
        const successCount = result.result.successful_calibrations;
        const totalCount = result.result.sensors_processed;
        
        showSuccess(`Auto-calibration completed: ${successCount}/${totalCount} sensors calibrated successfully!`, {
          title: 'Calibration Complete',
          autoHide: false
        });
        
        // Refresh status
        fetchCalibrationStatus();
      } else {
        showWarning("Auto-calibration completed with issues - check individual sensor results", {
          title: 'Calibration Warning',
          autoHide: false
        });
      }
      
    } catch (error) {
      showError("Auto-calibration process failed", {
        title: 'Calibration Error',
        autoHide: false
      });
    } finally {
      setProcessing(false);
    }
  };

  const handleTestQualityControl = async () => {
    try {
      showInfo("Testing quality control rules on sample data...", {
        title: 'QC Test Started',
        autoHide: true
      });
      
      // Generate test sensor data
      const testSensorData = {
        sensor_id: 'test_sensor_qc',
        raw_pm2_5: 25.4,
        raw_pm10: 35.2,
        temperature: 22.1,
        rh: 65.5,
        pressure: 1013.2,
        timestamp_utc: new Date().toISOString()
      };
      
      const response = await fetch('/api/data/quality-control', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(testSensorData)
      });
      
      const result = await response.json();
      
      const flagCount = result.qc_flags?.length || 0;
      if (flagCount === 0) {
        showSuccess("Quality control test passed - no flags raised on test data", {
          title: 'QC Test Successful',
          autoHide: false
        });
      } else {
        showWarning(`Quality control detected ${flagCount} issues in test data: ${result.qc_flags.join(', ')}`, {
          title: 'QC Test Results',
          autoHide: false
        });
      }
      
      // Refresh QC summary
      fetchQCSummary();
      
    } catch (error) {
      showError("Quality control test failed", {
        title: 'QC Test Error',
        autoHide: false
      });
    }
  };

  if (loading && !calibrationStatus) {
    return (
      <div className="flex items-center justify-center p-8">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Calibration Status Overview */}
      <div className="bg-white dark:bg-neutral-800 rounded-lg border border-neutral-200 dark:border-neutral-700 p-6">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-semibold text-neutral-900 dark:text-white">
            Sensor Calibration Status
          </h2>
          <button
            onClick={fetchCalibrationStatus}
            className="p-2 rounded-lg bg-neutral-100 dark:bg-neutral-700 hover:bg-neutral-200 dark:hover:bg-neutral-600 transition-colors"
          >
            <RefreshCw className="w-4 h-4 text-neutral-600 dark:text-neutral-400" />
          </button>
        </div>
        
        {calibrationStatus && (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="bg-neutral-50 dark:bg-neutral-900 rounded-lg p-4">
              <div className="flex items-center space-x-2 mb-2">
                <Database className="w-5 h-5 text-primary-600" />
                <span className="font-medium text-neutral-900 dark:text-white">Total Sensors</span>
              </div>
              <div className="text-2xl font-bold text-neutral-900 dark:text-white">
                {calibrationStatus.total_sensors}
              </div>
            </div>
            
            <div className="bg-neutral-50 dark:bg-neutral-900 rounded-lg p-4">
              <div className="flex items-center space-x-2 mb-2">
                <CheckCircle className="w-5 h-5 text-environmental-green" />
                <span className="font-medium text-neutral-900 dark:text-white">Calibrated</span>
              </div>
              <div className="text-2xl font-bold text-environmental-green">
                {calibrationStatus.active_calibrations}
              </div>
              <div className="text-xs text-neutral-500">
                {(calibrationStatus.calibration_rate * 100).toFixed(1)}% coverage
              </div>
            </div>
            
            <div className="bg-neutral-50 dark:bg-neutral-900 rounded-lg p-4">
              <div className="flex items-center space-x-2 mb-2">
                <TrendingUp className="w-5 h-5 text-primary-600" />
                <span className="font-medium text-neutral-900 dark:text-white">Avg R²</span>
              </div>
              <div className="text-2xl font-bold text-neutral-900 dark:text-white">
                {calibrationStatus.performance_stats?.mean_r2?.toFixed(3) || 'N/A'}
              </div>
            </div>
            
            <div className="bg-neutral-50 dark:bg-neutral-900 rounded-lg p-4">
              <div className="flex items-center space-x-2 mb-2">
                <Target className="w-5 h-5 text-environmental-yellow" />
                <span className="font-medium text-neutral-900 dark:text-white">Avg σᵢ</span>
              </div>
              <div className="text-2xl font-bold text-neutral-900 dark:text-white">
                {calibrationStatus.performance_stats?.mean_sigma_i?.toFixed(1) || 'N/A'}
              </div>
              <div className="text-xs text-neutral-500">μg/m³</div>
            </div>
          </div>
        )}
      </div>
      
      {/* Quality Control Summary */}
      {qcSummary && (
        <div className="bg-white dark:bg-neutral-800 rounded-lg border border-neutral-200 dark:border-neutral-700 p-6">
          <h3 className="text-lg font-semibold text-neutral-900 dark:text-white mb-4">
            Quality Control Summary (24h)
          </h3>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
            <div className="text-center">
              <div className="text-2xl font-bold text-environmental-green">
                {qcSummary.passed_records || 0}
              </div>
              <div className="text-sm text-neutral-600 dark:text-neutral-400">Passed QC</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-environmental-red">
                {qcSummary.flagged_records || 0}
              </div>
              <div className="text-sm text-neutral-600 dark:text-neutral-400">Flagged</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-primary-600">
                {qcSummary.pass_rate ? (qcSummary.pass_rate * 100).toFixed(1) : 0}%
              </div>
              <div className="text-sm text-neutral-600 dark:text-neutral-400">Pass Rate</div>
            </div>
          </div>
          
          {/* QC Flags Breakdown */}
          {qcSummary.flag_breakdown && Object.keys(qcSummary.flag_breakdown).length > 0 && (
            <div className="mt-4">
              <h4 className="font-medium text-neutral-900 dark:text-white mb-2">Common QC Flags</h4>
              <div className="space-y-2">
                {Object.entries(qcSummary.flag_breakdown).map(([flag, count]) => (
                  <div key={flag} className="flex justify-between text-sm">
                    <span className="text-neutral-600 dark:text-neutral-400">{flag}:</span>
                    <span className="font-medium text-neutral-900 dark:text-white">{count}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
      
      {/* Sensor Diagnostics */}
      <div className="bg-white dark:bg-neutral-800 rounded-lg border border-neutral-200 dark:border-neutral-700 p-6">
        <h3 className="text-lg font-semibold text-neutral-900 dark:text-white mb-4">
          Individual Sensor Diagnostics
        </h3>
        
        <div className="flex items-center space-x-4 mb-4">
          <input
            type="text"
            placeholder="Enter sensor ID..."
            value={selectedSensor}
            onChange={(e) => setSelectedSensor(e.target.value)}
            className="flex-1 px-3 py-2 border border-neutral-300 dark:border-neutral-600 rounded-lg bg-white dark:bg-neutral-700 text-neutral-900 dark:text-white"
          />
          <button
            onClick={() => fetchSensorDiagnostics(selectedSensor)}
            disabled={!selectedSensor || loading}
            className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 transition-colors"
          >
            Get Diagnostics
          </button>
        </div>
        
        {diagnostics && (
          <div className="space-y-4">
            {diagnostics.error ? (
              <div className="p-4 bg-environmental-red/10 border border-environmental-red/30 rounded-lg">
                <div className="flex items-center space-x-2">
                  <AlertTriangle className="w-4 h-4 text-environmental-red" />
                  <span className="font-medium text-environmental-red">Error</span>
                </div>
                <p className="text-sm text-neutral-700 dark:text-neutral-300 mt-1">
                  {diagnostics.error}
                </p>
              </div>
            ) : (
              <>
                {/* Calibration Parameters */}
                <div className="bg-neutral-50 dark:bg-neutral-900 rounded-lg p-4">
                  <h4 className="font-medium text-neutral-900 dark:text-white mb-3">
                    Calibration Parameters
                  </h4>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                    <div>
                      <span className="text-neutral-600 dark:text-neutral-400">α (Intercept):</span>
                      <div className="font-medium text-neutral-900 dark:text-white">
                        {diagnostics.calibration_parameters?.alpha?.toFixed(3) || 'N/A'}
                      </div>
                    </div>
                    <div>
                      <span className="text-neutral-600 dark:text-neutral-400">β (PM2.5):</span>
                      <div className="font-medium text-neutral-900 dark:text-white">
                        {diagnostics.calibration_parameters?.beta?.toFixed(3) || 'N/A'}
                      </div>
                    </div>
                    <div>
                      <span className="text-neutral-600 dark:text-neutral-400">γ (Humidity):</span>
                      <div className="font-medium text-neutral-900 dark:text-white">
                        {diagnostics.calibration_parameters?.gamma?.toFixed(3) || 'N/A'}
                      </div>
                    </div>
                    <div>
                      <span className="text-neutral-600 dark:text-neutral-400">δ (Temperature):</span>
                      <div className="font-medium text-neutral-900 dark:text-white">
                        {diagnostics.calibration_parameters?.delta?.toFixed(3) || 'N/A'}
                      </div>
                    </div>
                  </div>
                </div>
                
                {/* Performance Metrics */}
                <div className="bg-neutral-50 dark:bg-neutral-900 rounded-lg p-4">
                  <h4 className="font-medium text-neutral-900 dark:text-white mb-3">
                    Performance Metrics
                  </h4>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div className="text-center">
                      <div className="text-lg font-bold text-primary-600">
                        {diagnostics.performance_metrics?.r2?.toFixed(3) || 'N/A'}
                      </div>
                      <div className="text-xs text-neutral-600 dark:text-neutral-400">R² Score</div>
                    </div>
                    <div className="text-center">
                      <div className="text-lg font-bold text-environmental-yellow">
                        {diagnostics.performance_metrics?.rmse?.toFixed(2) || 'N/A'}
                      </div>
                      <div className="text-xs text-neutral-600 dark:text-neutral-400">RMSE (μg/m³)</div>
                    </div>
                    <div className="text-center">
                      <div className="text-lg font-bold text-neutral-900 dark:text-white">
                        {diagnostics.performance_metrics?.bias?.toFixed(2) || 'N/A'}
                      </div>
                      <div className="text-xs text-neutral-600 dark:text-neutral-400">Bias (μg/m³)</div>
                    </div>
                  </div>
                </div>
                
                {/* Status Information */}
                <div className="bg-neutral-50 dark:bg-neutral-900 rounded-lg p-4">
                  <h4 className="font-medium text-neutral-900 dark:text-white mb-3">
                    Calibration Status
                  </h4>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-neutral-600 dark:text-neutral-400">Last Calibrated:</span>
                      <span className="font-medium text-neutral-900 dark:text-white">
                        {diagnostics.status?.last_calibrated ? 
                          new Date(diagnostics.status.last_calibrated).toLocaleDateString() : 
                          'Never'
                        }
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-neutral-600 dark:text-neutral-400">Age (Days):</span>
                      <span className={`font-medium ${
                        diagnostics.status?.age_days > 90 ? 'text-environmental-red' :
                        diagnostics.status?.age_days > 30 ? 'text-environmental-yellow' :
                        'text-environmental-green'
                      }`}>
                        {diagnostics.status?.age_days || 'Unknown'}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-neutral-600 dark:text-neutral-400">Status:</span>
                      <span className={`font-medium ${
                        diagnostics.status?.is_active ? 'text-environmental-green' : 'text-environmental-red'
                      }`}>
                        {diagnostics.status?.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-neutral-600 dark:text-neutral-400">Reference Points:</span>
                      <span className="font-medium text-neutral-900 dark:text-white">
                        {diagnostics.performance_metrics?.reference_count || 0}
                      </span>
                    </div>
                  </div>
                  
                  {diagnostics.status?.needs_recalibration && (
                    <div className="mt-3 p-3 bg-environmental-yellow/10 border border-environmental-yellow/30 rounded-lg">
                      <div className="flex items-center space-x-2">
                        <AlertTriangle className="w-4 h-4 text-environmental-yellow" />
                        <span className="text-sm font-medium text-environmental-yellow">
                          Recalibration Recommended
                        </span>
                      </div>
                      <p className="text-sm text-neutral-700 dark:text-neutral-300 mt-1">
                        This sensor's calibration is older than recommended. Consider recalibrating for optimal accuracy.
                      </p>
                    </div>
                  )}
                </div>
              </>
            )}
          </div>
        )}
      </div>
      
      {/*Management Actions */}
      <div className="bg-white dark:bg-neutral-800 rounded-lg border border-neutral-200 dark:border-neutral-700 p-6">
        <h3 className="text-lg font-semibold text-neutral-900 dark:text-white mb-4">
          Calibration Management
        </h3>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <button 
            onClick={handleAutoCalibration}
            disabled={processing}
            className="flex items-center justify-center space-x-2 p-4 bg-primary-50 dark:bg-primary-900/20 hover:bg-primary-100 dark:hover:bg-primary-900/30 rounded-lg border border-primary-200 dark:border-primary-800 transition-colors disabled:opacity-50"
          >
            {processing ? (
              <RefreshCw className="w-5 h-5 text-primary-600 animate-spin" />
            ) : (
              <Settings className="w-5 h-5 text-primary-600" />
            )}
            <span className="text-primary-600 font-medium">
              {processing ? 'Processing...' : 'Auto-Calibrate All'}
            </span>
          </button>
          
          <button 
            onClick={handleTestQualityControl}
            className="flex items-center justify-center space-x-2 p-4 bg-environmental-green/10 hover:bg-environmental-green/20 rounded-lg border border-environmental-green/30 transition-colors"
          >
            <BarChart3 className="w-5 h-5 text-environmental-green" />
            <span className="text-environmental-green font-medium">Test Quality Control</span>
          </button>
        </div>
      </div>
      
      {/* Recent Data Quality Trends */}
      <div className="bg-white dark:bg-neutral-800 rounded-lg border border-neutral-200 dark:border-neutral-700 p-6">
        <h3 className="text-lg font-semibold text-neutral-900 dark:text-white mb-4">
          Data Quality Guidelines
        </h3>
        
        <div className="space-y-3 text-sm">
          <div className="flex items-start space-x-3">
            <CheckCircle className="w-4 h-4 text-environmental-green mt-0.5" />
            <div>
              <strong className="text-neutral-900 dark:text-white">Range Validation:</strong>
              <span className="text-neutral-600 dark:text-neutral-400"> PM2.5: 0-500 μg/m³, Temperature: -50-60°C, Humidity: 0-100%</span>
            </div>
          </div>
          
          <div className="flex items-start space-x-3">
            <AlertTriangle className="w-4 h-4 text-environmental-yellow mt-0.5" />
            <div>
              <strong className="text-neutral-900 dark:text-white">Spike Detection:</strong>
              <span className="text-neutral-600 dark:text-neutral-400"> Modified Z-score > 3.5 triggers sudden spike flags for anomalous readings</span>
            </div>
          </div>
          
          <div className="flex items-start space-x-3">
            <Database className="w-4 h-4 text-primary-600 mt-0.5" />
            <div>
              <strong className="text-neutral-900 dark:text-white">Humidity Flagging:</strong>
              <span className="text-neutral-600 dark:text-neutral-400"> Relative humidity > 85% flags optical sensor uncertainty</span>
            </div>
          </div>
          
          <div className="flex items-start space-x-3">
            <TrendingUp className="w-4 h-4 text-environmental-green mt-0.5" />
            <div>
              <strong className="text-neutral-900 dark:text-white">Calibration Model:</strong>
              <span className="text-neutral-600 dark:text-neutral-400"> Linear correction: c_corr = α + β·c_raw + γ·rh + δ·t</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default CalibrationPanel;
