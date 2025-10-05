import React, { useState } from 'react';
import { FileText, Download, Calendar, MapPin, Filter, TrendingUp } from 'lucide-react';
import useNotifications from '../hooks/useNotifications';

function Reports() {
  const [selectedReport, setSelectedReport] = useState('environmental');
  const [dateRange, setDateRange] = useState('30d');
  const [region, setRegion] = useState('sf-bay');
  const [isGenerating, setIsGenerating] = useState(false);
  const { showSuccess, showInfo } = useNotifications();

  const reportTypes = [
    {
      id: 'environmental',
      name: 'Environmental Impact Report',
      description: 'Comprehensive analysis of air quality and environmental factors',
      icon: TrendingUp,
      estimatedTime: '2-3 minutes'
    },
    {
      id: 'sensor',
      name: 'Sensor Network Status',
      description: 'Overview of sensor network health and data quality',
      icon: MapPin,
      estimatedTime: '1-2 minutes'
    },
    {
      id: 'trends',
      name: 'Trend Analysis Report',
      description: 'Long-term trends and seasonal patterns in environmental data',
      icon: TrendingUp,
      estimatedTime: '3-4 minutes'
    }
  ];

  const handleGenerateReport = async () => {
    setIsGenerating(true);
    
    showInfo('Generating comprehensive environmental report...', {
      title: 'Report Generation Started',
      autoHide: true
    });
    
    // Simulate report generation
    setTimeout(() => {
      // Create mock report data
      const reportData = {
        timestamp: new Date().toISOString(),
        type: selectedReport,
        dateRange: dateRange,
        region: region,
        summary: {
          totalSensors: 156,
          dataPoints: 45678,
          avgAirQuality: 'Moderate',
          coverage: '94.2%'
        }
      };
      
      // Generate and download JSON report
      const blob = new Blob([JSON.stringify(reportData, null, 2)], { 
        type: 'application/json' 
      });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `seit-${selectedReport}-report-${new Date().toISOString().split('T')[0]}.json`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
      
      showSuccess(`${reportTypes.find(r => r.id === selectedReport)?.name} generated and downloaded successfully!`, {
        title: 'Report Ready',
        autoHide: false
      });
      
      setIsGenerating(false);
    }, 3000);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-neutral-900 dark:text-white">
            Reports & Exports
          </h1>
          <p className="text-neutral-600 dark:text-neutral-400 mt-2">
            Generate comprehensive environmental impact reports and data exports
          </p>
        </div>
      </div>

      {/* Report Configuration */}
      <div className="bg-white dark:bg-neutral-800 rounded-lg border border-neutral-200 dark:border-neutral-700 p-6">
        <h2 className="text-xl font-semibold text-neutral-900 dark:text-white mb-4">
          Report Configuration
        </h2>
        
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Report Type */}
          <div>
            <label className="block text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-2">
              Report Type
            </label>
            <select
              value={selectedReport}
              onChange={(e) => setSelectedReport(e.target.value)}
              className="w-full px-3 py-2 border border-neutral-300 dark:border-neutral-600 rounded-lg bg-white dark:bg-neutral-700 text-neutral-900 dark:text-white"
            >
              {reportTypes.map(type => (
                <option key={type.id} value={type.id}>
                  {type.name}
                </option>
              ))}
            </select>
          </div>

          {/* Date Range */}
          <div>
            <label className="block text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-2">
              Date Range
            </label>
            <select
              value={dateRange}
              onChange={(e) => setDateRange(e.target.value)}
              className="w-full px-3 py-2 border border-neutral-300 dark:border-neutral-600 rounded-lg bg-white dark:bg-neutral-700 text-neutral-900 dark:text-white"
            >
              <option value="7d">Last 7 Days</option>
              <option value="30d">Last 30 Days</option>
              <option value="90d">Last 3 Months</option>
              <option value="1y">Last Year</option>
            </select>
          </div>

          {/* Region */}
          <div>
            <label className="block text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-2">
              Region
            </label>
            <select
              value={region}
              onChange={(e) => setRegion(e.target.value)}
              className="w-full px-3 py-2 border border-neutral-300 dark:border-neutral-600 rounded-lg bg-white dark:bg-neutral-700 text-neutral-900 dark:text-white"
            >
              <option value="sf-bay">San Francisco Bay Area</option>
              <option value="los-angeles">Los Angeles</option>
              <option value="new-york">New York City</option>
              <option value="custom">Custom Region</option>
            </select>
          </div>
        </div>
      </div>

      {/* Report Types */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {reportTypes.map((report) => (
          <div
            key={report.id}
            className={`p-6 rounded-lg border-2 cursor-pointer transition-all ${
              selectedReport === report.id
                ? 'border-primary-600 bg-primary-50 dark:bg-primary-900/20'
                : 'border-neutral-200 dark:border-neutral-700 hover:border-neutral-300'
            }`}
            onClick={() => setSelectedReport(report.id)}
          >
            <div className="flex items-center space-x-3 mb-3">
              <div className="p-2 rounded-lg bg-primary-100 text-primary-600">
                <report.icon className="w-6 h-6" />
              </div>
              <h3 className="font-semibold text-neutral-900 dark:text-white">
                {report.name}
              </h3>
            </div>
            <p className="text-sm text-neutral-600 dark:text-neutral-400 mb-4">
              {report.description}
            </p>
            <div className="flex items-center justify-between text-xs text-neutral-500">
              <span>Est. Time: {report.estimatedTime}</span>
              <FileText className="w-4 h-4" />
            </div>
          </div>
        ))}
      </div>

      {/* Generate Button */}
      <div className="flex justify-center">
        <button
          onClick={handleGenerateReport}
          disabled={isGenerating}
          className="flex items-center space-x-2 px-8 py-3 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {isGenerating ? (
            <>
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
              <span>Generating Report...</span>
            </>
          ) : (
            <>
              <Download className="w-5 h-5" />
              <span>Generate Report</span>
            </>
          )}
        </button>
      </div>

      {/* Recent Reports */}
      <div className="bg-white dark:bg-neutral-800 rounded-lg border border-neutral-200 dark:border-neutral-700 p-6">
        <h2 className="text-xl font-semibold text-neutral-900 dark:text-white mb-4">
          Recent Reports
        </h2>
        
        <div className="space-y-4">
          {[
            { name: 'Environmental Impact Report - December 2024', date: '2024-12-15', size: '2.4 MB', type: 'PDF' },
            { name: 'Sensor Network Status - November 2024', date: '2024-11-30', size: '1.1 MB', type: 'PDF' },
            { name: 'Trend Analysis Report - Q4 2024', date: '2024-11-15', size: '3.2 MB', type: 'PDF' }
          ].map((report, index) => (
            <div key={index} className="flex items-center justify-between p-4 bg-neutral-50 dark:bg-neutral-900 rounded-lg">
              <div className="flex items-center space-x-3">
                <FileText className="w-5 h-5 text-neutral-500" />
                <div>
                  <p className="font-medium text-neutral-900 dark:text-white">
                    {report.name}
                  </p>
                  <p className="text-sm text-neutral-500">
                    {report.date} • {report.size} • {report.type}
                  </p>
                </div>
              </div>
              <button className="text-primary-600 hover:text-primary-700 transition-colors">
                <Download className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default Reports;
