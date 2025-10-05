import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Menu, X, Satellite, Moon, Sun } from 'lucide-react';

function Navbar({ darkMode, toggleDarkMode }) {
  const [isOpen, setIsOpen] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  const navigation = [
    { name: 'Dashboard', href: '#dashboard' },
    { name: 'Maps', href: '#maps' },
    { name: 'Analytics', href: '#analytics' },
    { name: 'Reports', href: '#reports' },
    { name: 'Admin', href: '#admin' }
  ];

  const handleNavigation = (href) => {
    navigate(href);
    setIsOpen(false);
  };
  return (
    <nav className="bg-white dark:bg-space-900 border-b border-neutral-200 dark:border-neutral-700 sticky top-0 z-50">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          {/* Logo */}
          <div className="flex items-center space-x-2">
            <div className="relative">
              <Satellite className="w-8 h-8 text-primary-600" />
              <div className="absolute -top-1 -right-1 w-3 h-3 bg-environmental-green rounded-full border-2 border-white"></div>
            </div>
            <span className="text-xl font-bold text-neutral-900 dark:text-white">
              SEIT
            </span>
            <span className="text-xs bg-primary-100 text-primary-600 px-2 py-1 rounded-full font-medium">
              v1.0
            </span>
          </div>

          {/* Desktop Navigation */}
          <div className="hidden md:block">
            <div className="ml-10 flex items-baseline space-x-4">
              {navigation.map((item) => (
                <a
                  key={item.name}
                  onClick={(e) => {
                    e.preventDefault();
                    const section = item.href.replace('#', '');
                    if (section === 'dashboard') {
                      navigate('/dashboard');
                    } else if (section === 'maps') {
                      navigate('/maps');
                    } else if (section === 'analytics') {
                      navigate('/analytics');
                    } else if (section === 'reports') {
                      navigate('/reports');
                    } else if (section === 'admin') {
                      navigate('/admin');
                    } else {
                      navigate(`/${section}`);
                    }
                  }}
                  className={`cursor-pointer px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                    location.pathname === item.href.replace('#', '/')
                      ? 'text-primary-600 bg-primary-50 dark:bg-primary-900/20'
                      : 'text-neutral-600 dark:text-neutral-300 hover:text-primary-600 dark:hover:text-primary-400'
                  }`}
                >
                  {item.name}
                </a>
              ))}
            </div>
          </div>

          {/* Dark Mode Toggle */}
          <div className="flex items-center space-x-4">
            <button
              onClick={toggleDarkMode}
              className="p-2 rounded-lg bg-neutral-100 dark:bg-neutral-800 hover:bg-neutral-200 dark:hover:bg-neutral-700 transition-colors"
              aria-label="Toggle dark mode"
            >
              {darkMode ? (
                <Sun className="w-5 h-5 text-yellow-500" />
              ) : (
                <Moon className="w-5 h-5 text-neutral-600" />
              )}
            </button>

            {/* Mobile menu button */}
            <div className="md:hidden">
              <button
                onClick={() => setIsOpen(!isOpen)}
                className="inline-flex items-center justify-center p-2 rounded-md text-neutral-600 dark:text-neutral-300 hover:text-primary-600 dark:hover:text-primary-400 transition-colors"
              >
                {isOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
              </button>
            </div>
          </div>
        </div>

        {/* Mobile Navigation */}
        {isOpen && (
          <div className="md:hidden">
            <div className="px-2 pt-2 pb-3 space-y-1 sm:px-3 border-t border-neutral-200 dark:border-neutral-700">
              {navigation.map((item) => (
                <a
                  key={item.name}
                  onClick={(e) => {
                    e.preventDefault();
                    const section = item.href.replace('#', '');
                    navigate(`/${section}`);
                    setIsOpen(false);
                  }}
                  className={`cursor-pointer block px-3 py-2 rounded-md text-base font-medium transition-colors ${
                    location.pathname === item.href.replace('#', '/')
                      ? 'text-primary-600 bg-primary-50 dark:bg-primary-900/20'
                      : 'text-neutral-600 dark:text-neutral-300 hover:text-primary-600 dark:hover:text-primary-400'
                  }`}
                >
                  {item.name}
                </a>
              ))}
            </div>
          </div>
        )}
      </div>
    </nav>
  );
}

export default Navbar;
