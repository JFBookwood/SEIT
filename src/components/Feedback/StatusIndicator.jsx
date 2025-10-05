import React from 'react';
import { 
  Wifi, 
  WifiOff, 
  AlertTriangle, 
  CheckCircle, 
  Clock, 
  RefreshCw,
  X 
} from 'lucide-react';

function StatusIndicator({ 
  isConnected = true, 
  error = null, 
  loading = false, 
  lastUpdated = null,
  onRetry = null,
  onDismiss = null,
  className = ""
}) {
  const getStatusColor = () => {
    if (error?.type === 'error') return 'text-environmental-red';
    if (error?.type === 'warning') return 'text-environmental-yellow';
    if (loading) return 'text-primary-600';
    if (isConnected) return 'text-environmental-green';
    return 'text-neutral-500';
  };

  const getStatusIcon = () => {
    if (error?.type === 'error') return <WifiOff className="w-4 h-4" />;
    if (error?.type === 'warning') return <AlertTriangle className="w-4 h-4" />;
    if (loading) return <RefreshCw className="w-4 h-4 animate-spin" />;
    if (isConnected) return <CheckCircle className="w-4 h-4" />;
    return <Wifi className="w-4 h-4" />;
  };

  const getStatusMessage = () => {
    if (error) return error.message;
    if (loading) return 'Updating data...';
    if (isConnected && lastUpdated) {
      const timeAgo = Math.floor((new Date() - new Date(lastUpdated)) / 1000);
      if (timeAgo < 60) return `Updated ${timeAgo}s ago`;
      if (timeAgo < 3600) return `Updated ${Math.floor(timeAgo / 60)}m ago`;
      return `Updated ${Math.floor(timeAgo / 3600)}h ago`;
    }
    return 'Connected';
  };

  // Don't render if no status to show
  if (!error && !loading && isConnected) {
    return null;
  }

  return (
    <div className={`flex items-center space-x-2 px-3 py-2 rounded-lg bg-white dark:bg-neutral-800 border border-neutral-200 dark:border-neutral-700 shadow-sm ${className}`}>
      <div className={getStatusColor()}>
        {getStatusIcon()}
      </div>
      
      <span className="text-sm text-neutral-700 dark:text-neutral-300 flex-1">
        {getStatusMessage()}
      </span>
      
      {lastUpdated && !loading && (
        <div className="flex items-center space-x-1 text-xs text-neutral-500">
          <Clock className="w-3 h-3" />
          <span>{new Date(lastUpdated).toLocaleTimeString()}</span>
        </div>
      )}
      
      {error && onRetry && (
        <button
          onClick={onRetry}
          className="text-primary-600 hover:text-primary-700 transition-colors"
          title="Retry failed operation"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      )}
      
      {error && onDismiss && (
        <button
          onClick={onDismiss}
          className="text-neutral-500 hover:text-neutral-700 transition-colors"
          title="Dismiss notification"
        >
          <X className="w-3 h-3" />
        </button>
      )}
    </div>
  );
}

export default StatusIndicator;
