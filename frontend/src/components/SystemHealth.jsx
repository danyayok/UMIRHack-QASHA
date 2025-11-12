import React, { useState, useEffect } from 'react';
import { healthAPI } from '../services/api';

const SystemHealth = () => {
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    checkHealth();
    const interval = setInterval(checkHealth, 30000); // Проверка каждые 30 сек
    return () => clearInterval(interval);
  }, []);

  const checkHealth = async () => {
    try {
      const data = await healthAPI.check();
      setHealth(data);
    } catch (error) {
      setHealth({ status: 'unhealthy', error: error.message });
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="p-4 bg-gray-100 rounded-lg">
        <div className="animate-pulse">Checking system health...</div>
      </div>
    );
  }

  return (
    <div className="p-4 bg-white border rounded-lg shadow-sm">
      <h3 className="text-lg font-semibold mb-3">System Health</h3>
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <span>Overall Status:</span>
          <span className={`px-2 py-1 rounded text-sm ${
            health.status === 'healthy' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
          }`}>
            {health.status || 'unknown'}
          </span>
        </div>
        {health.database && (
          <div className="flex items-center justify-between">
            <span>Database:</span>
            <span className="text-green-600">✅ Connected</span>
          </div>
        )}
        {health.redis && (
          <div className="flex items-center justify-between">
            <span>Redis:</span>
            <span className="text-green-600">✅ Connected</span>
          </div>
        )}
        {health.error && (
          <div className="p-2 bg-red-50 border border-red-200 rounded text-sm text-red-700">
            Error: {health.error}
          </div>
        )}
      </div>
    </div>
  );
};

export default SystemHealth;