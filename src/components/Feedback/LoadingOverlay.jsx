import React from 'react';
import { Loader2, Satellite, Database, Zap } from 'lucide-react';

function LoadingOverlay({ 
  isVisible = false, 
  message = "Loading data...", 
  progress = null,
  type = "default",
  children
}) {
  if (!isVisible) return children;

  const getLoadingIcon = () => {
    switch (type) {
      case 'satellite':
        return <Satellite className="w-8 h-8 text-primary-600 animate-pulse" />;
      case 'database':
        return <Database className="w-8 h-8 text-primary-600 animate-pulse" />;
      case 'analysis':
        return <Zap className="w-8 h-8 text-primary-600 animate-pulse" />;
      default:
        return <Loader2 className="w-8 h-8 text-primary-600 animate-spin" />;
    }
  };

  return (
    <div className="relative">
      {children}
      
      {/* Overlay */}
      <div className="absolute inset-0 bg-white/80 dark:bg-neutral-900/80 backdrop-blur-sm z-50 flex items-center justify-center">
        <div className="bg-white dark:bg-neutral-800 rounded-lg shadow-lg p-6 max-w-sm w-full mx-4">
          <div className="text-center">
            <div className="mb-4">
              {getLoadingIcon()}
            </div>
            
            <h3 className="text-lg font-semibold text-neutral-900 dark:text-white mb-2">
              {message}
            </h3>
            
            {progress !== null && (
              <div className="mb-4">
                <div className="w-full bg-neutral-200 dark:bg-neutral-700 rounded-full h-2">
                  <div 
                    className="bg-primary-600 h-2 rounded-full transition-all duration-300"
                    style={{ width: `${Math.min(100, Math.max(0, progress))}%` }}
                  />
                </div>
                <p className="text-sm text-neutral-600 dark:text-neutral-400 mt-2">
                  {Math.round(progress)}% complete
                </p>
              </div>
            )}
            
            <div className="flex justify-center">
              <div className="flex space-x-1">
                {[0, 1, 2].map((i) => (
                  <div
                    key={i}
                    className="w-2 h-2 bg-primary-600 rounded-full animate-pulse"
                    style={{
                      animationDelay: `${i * 0.2}s`,
                      animationDuration: '1s'
                    }}
                  />
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default LoadingOverlay;
