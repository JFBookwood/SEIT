import React, { useState, useEffect } from 'react';
import { X, CheckCircle, AlertTriangle, AlertCircle, Info } from 'lucide-react';

function NotificationToast({ 
  notifications = [], 
  onDismiss = () => {},
  maxVisible = 3,
  autoHideDuration = 5000 
}) {
  const [visibleNotifications, setVisibleNotifications] = useState([]);

  useEffect(() => {
    setVisibleNotifications(notifications.slice(0, maxVisible));
  }, [notifications, maxVisible]);

  useEffect(() => {
    const timers = visibleNotifications
      .filter(notification => notification.autoHide !== false)
      .map(notification => {
        return setTimeout(() => {
          onDismiss(notification.id);
        }, autoHideDuration);
      });

    return () => {
      timers.forEach(timer => clearTimeout(timer));
    };
  }, [visibleNotifications, autoHideDuration, onDismiss]);

  const getNotificationIcon = (type) => {
    switch (type) {
      case 'success':
        return <CheckCircle className="w-5 h-5 text-environmental-green" />;
      case 'warning':
        return <AlertTriangle className="w-5 h-5 text-environmental-yellow" />;
      case 'error':
        return <AlertCircle className="w-5 h-5 text-environmental-red" />;
      default:
        return <Info className="w-5 h-5 text-primary-600" />;
    }
  };

  const getNotificationStyles = (type) => {
    const baseStyles = "border-l-4 bg-white dark:bg-neutral-800 shadow-lg";
    
    switch (type) {
      case 'success':
        return `${baseStyles} border-environmental-green`;
      case 'warning':
        return `${baseStyles} border-environmental-yellow`;
      case 'error':
        return `${baseStyles} border-environmental-red`;
      default:
        return `${baseStyles} border-primary-600`;
    }
  };

  if (visibleNotifications.length === 0) return null;

  return (
    <div className="fixed top-4 right-4 z-50 space-y-2 max-w-sm w-full">
      {visibleNotifications.map((notification, index) => (
        <div
          key={notification.id}
          className={`${getNotificationStyles(notification.type)} rounded-lg p-4 transform transition-all duration-300 ease-in-out`}
          style={{
            transform: `translateY(${index * 4}px)`,
            zIndex: 50 - index
          }}
        >
          <div className="flex items-start space-x-3">
            {getNotificationIcon(notification.type)}
            
            <div className="flex-1 min-w-0">
              {notification.title && (
                <h4 className="text-sm font-semibold text-neutral-900 dark:text-white">
                  {notification.title}
                </h4>
              )}
              <p className="text-sm text-neutral-700 dark:text-neutral-300">
                {notification.message}
              </p>
              {notification.timestamp && (
                <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-1">
                  {new Date(notification.timestamp).toLocaleTimeString()}
                </p>
              )}
            </div>
            
            <button
              onClick={() => onDismiss(notification.id)}
              className="text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-300 transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
          
          {notification.actions && (
            <div className="mt-3 flex space-x-2">
              {notification.actions.map((action, actionIndex) => (
                <button
                  key={actionIndex}
                  onClick={() => {
                    action.handler();
                    if (action.dismissOnClick !== false) {
                      onDismiss(notification.id);
                    }
                  }}
                  className={`text-xs px-3 py-1 rounded transition-colors ${
                    action.primary
                      ? 'bg-primary-600 text-white hover:bg-primary-700'
                      : 'text-primary-600 hover:text-primary-700 border border-primary-600 hover:border-primary-700'
                  }`}
                >
                  {action.label}
                </button>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

export default NotificationToast;
