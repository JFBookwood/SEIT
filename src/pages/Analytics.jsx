import React, { useState } from 'react';
import { BarChart3, TrendingUp, MapPin, AlertTriangle, Download, Play } from 'lucide-react';
import StatsCard from '../components/Dashboard/StatsCard';
import useNotifications from '../hooks/useNotifications';

function Analytics() {
  const [selectedAnalysis, setSelectedAnalysis] = useState('hotspots');
  const [isRunning, setIsRunning] = useState(false);
  const [results, setResults] = useState(null);
  const { showSuccess, showInfo, showError } = useNotifications();

  const analysisTypes = [
    {
      id: 'hotspots',
      name: 'Hotspot Detection',
      description: 'Identify pollution hotspots using DBSCAN clustering',
      icon: MapPin,
      color: 'red'
    },
    {
      id: 'anomalies',
      name: 'Anomaly Detection', 
      description: 'Find unusual patterns in sensor data using ML',
      icon: AlertTriangle,
      color: 'yellow'
    },
    {
      id: 'trends',
      name: 'Trend Analysis',
      description: 'Analyze temporal trends and seasonal patterns',
      icon: TrendingUp,
      color: 'green'
    }
  ];

  const handleRunAnalysis = async (analysisType) => {
    setIsRunning(true);
    setSelectedAnalysis(analysisType);
    
    showInfo(`Starting ${analysisType} analysis...`, {
      title: 'Analysis Starting',
      autoHide: true
    });
    
    // Simulate analysis running
    setTimeout(() => {
      setResults({
        type: analysisType,
        timestamp: new Date().toISOString(),
        summary: `${analysisType} analysis completed successfully`,
        details: generateMockResults(analysisType)
      });
      
      showSuccess(`${analysisType} analysis completed successfully!`, {
        title: 'Analysis Complete',
        autoHide: false
      });
      
      setIsRunning(false);
    }, 3000);
  };

  const generateMockResults = (type) => {
    switch (type) {
      case 'hotspots':
        return {
          hotspotsFound: 7,
          totalArea: '15.2 km²',
          avgPollutionLevel: '42.3 μg/m³',
          recommendation: 'Focus monitoring on downtown and industrial areas'
        };
      case 'anomalies':
        return {
          anomaliesDetected: 23,
          confidenceScore: '94%',
          timeRange: 'Last 30 days',
          recommendation: 'Investigate sensors showing unusual spikes'
        };
      case 'trends':
        return {
          trendDirection: 'Improving',
          changeRate: '-12% over 6 months',
          seasonalPattern: 'Higher in winter months',
          recommendation: 'Continue current environmental policies'
        };
      default:
        return {};
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-neutral-900 dark:text-white">
            Advanced Analytics
          </h1>
          <p className="text-neutral-600 dark:text-neutral-400 mt-2">
            Run sophisticated analysis on environmental sensor data
          </p>
        </div>
        
        <button
          onClick={() => window.open('/api/docs', '_blank')}
          className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
        >
          <Download className="w-4 h-4 inline mr-2" />
          Export Results
        </button>
      </div>

      {/* Analysis Type Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {analysisTypes.map((analysis) => (
          <div
            key={analysis.id}
            className={`p-6 rounded-lg border-2 cursor-pointer transition-all ${
              selectedAnalysis === analysis.id
                ? 'border-primary-600 bg-primary-50 dark:bg-primary-900/20'
                : 'border-neutral-200 dark:border-neutral-700 hover:border-neutral-300'
            }`}
            onClick={() => setSelectedAnalysis(analysis.id)}
          >
            <div className="flex items-center space-x-3 mb-3">
              <div className={`p-2 rounded-lg bg-${analysis.color}-100 text-${analysis.color}-600`}>
                <analysis.icon className="w-6 h-6" />
              </div>
              <h3 className="font-semibold text-neutral-900 dark:text-white">
                {analysis.name}
              </h3>
            </div>
            <p className="text-sm text-neutral-600 dark:text-neutral-400 mb-4">
              {analysis.description}
            </p>
            <button
              onClick={(e) => {
                e.stopPropagation();
                handleRunAnalysis(analysis.id);
              }}
              disabled={isRunning}
              className="w-full flex items-center justify-center space-x-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <Play className="w-4 h-4" />
              <span>{isRunning && selectedAnalysis === analysis.id ? 'Running...' : 'Run Analysis'}</span>
            </button>
          </div>
        ))}
      </div>

      {/* Results Section */}
      {results && (
        <div className="bg-white dark:bg-neutral-800 rounded-lg border border-neutral-200 dark:border-neutral-700 p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold text-neutral-900 dark:text-white">
              Analysis Results: {results.type.charAt(0).toUpperCase() + results.type.slice(1)}
            </h2>
            <span className="text-sm text-neutral-500">
              {new Date(results.timestamp).toLocaleString()}
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            {Object.entries(results.details).map(([key, value]) => (
              <StatsCard
                key={key}
                title={key.charAt(0).toUpperCase() + key.slice(1).replace(/([A-Z])/g, ' $1')}
                value={value}
                color="primary"
              />
            ))}
          </div>

          <div className="bg-neutral-50 dark:bg-neutral-900 rounded-lg p-4">
            <h3 className="font-semibold text-neutral-900 dark:text-white mb-2">
              Recommendation
            </h3>
            <p className="text-neutral-600 dark:text-neutral-400">
              {results.details.recommendation}
            </p>
          </div>
        </div>
      )}

      {/* Quick Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatsCard
          title="Total Analyses Run"
          value="127"
          icon={BarChart3}
          color="primary"
          trend="up"
          trendValue="+23"
        />
        <StatsCard
          title="Hotspots Identified"
          value="15"
          icon={MapPin}
          color="red"
          trend="down"
          trendValue="-3"
        />
        <StatsCard
          title="Anomalies Detected"
          value="89"
          icon={AlertTriangle}
          color="yellow"
          trend="up"
          trendValue="+12"
        />
        <StatsCard
          title="Trend Accuracy"
          value="94.2%"
          icon={TrendingUp}
          color="green"
          trend="up"
          trendValue="+2.1%"
        />
      </div>
    </div>
  );
}

export default Analytics;
