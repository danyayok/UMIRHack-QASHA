import React, { useState, useEffect } from 'react';
import { projectsAPI } from '../../../services/api';

const AnalysisStatus = ({ analysisId, onComplete }) => {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const checkStatus = async () => {
      try {
        const statusData = await projectsAPI.getAnalysisStatus(analysisId);
        setStatus(statusData);

        if (statusData.status === 'completed' || statusData.status === 'failed') {
          onComplete?.(statusData);
        }
      } catch (error) {
        console.error('Error fetching analysis status:', error);
      } finally {
        setLoading(false);
      }
    };

    // Первая проверка
    checkStatus();

    // Периодическая проверка каждые 3 секунды
    const interval = setInterval(checkStatus, 3000);

    return () => clearInterval(interval);
  }, [analysisId, onComplete]);

  const getStatusColor = (status) => {
    const colors = {
      pending: 'bg-gray-100 text-gray-800',
      cloning: 'bg-blue-100 text-blue-800',
      extracting: 'bg-blue-100 text-blue-800',
      analyzing: 'bg-yellow-100 text-yellow-800',
      generating: 'bg-purple-100 text-purple-800',
      pushing: 'bg-indigo-100 text-indigo-800',
      completed: 'bg-green-100 text-green-800',
      failed: 'bg-red-100 text-red-800',
    };
    return colors[status] || colors.pending;
  };

  const getStatusText = (status) => {
    const texts = {
      pending: 'Ожидание',
      cloning: 'Клонирование репозитория',
      extracting: 'Извлечение архива',
      analyzing: 'Анализ кода',
      generating: 'Генерация тестов',
      pushing: 'Отправка в репозиторий',
      completed: 'Завершено',
      failed: 'Ошибка',
    };
    return texts[status] || status;
  };

  const getStatusIcon = (status) => {
    const icons = {
      pending: '⏳',
      cloning: '📥',
      extracting: '📦',
      analyzing: '🔍',
      generating: '⚡',
      pushing: '🚀',
      completed: '✅',
      failed: '❌',
    };
    return icons[status] || '⏳';
  };

  if (loading || !status) {
    return (
      <div className="p-4 bg-gray-50 rounded-lg border">
        <div className="animate-pulse flex items-center space-x-3">
          <div className="w-8 h-8 bg-gray-300 rounded-full"></div>
          <div className="flex-1 space-y-2">
            <div className="h-4 bg-gray-300 rounded w-3/4"></div>
            <div className="h-2 bg-gray-300 rounded w-1/2"></div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="p-4 bg-white border rounded-lg shadow-sm">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center space-x-3">
          <span className="text-2xl">{getStatusIcon(status.status)}</span>
          <div>
            <h4 className="font-medium text-gray-900">Статус анализа</h4>
            <p className="text-sm text-gray-500">ID: {status.id}</p>
          </div>
        </div>
        <span className={`px-3 py-1 text-sm font-medium rounded-full ${getStatusColor(status.status)}`}>
          {getStatusText(status.status)}
        </span>
      </div>

      {/* Progress bar */}
      <div className="w-full bg-gray-200 rounded-full h-3 mb-3">
        <div
          className="bg-blue-600 h-3 rounded-full transition-all duration-500 ease-out"
          style={{ width: `${status.progress || 0}%` }}
        ></div>
      </div>

      <div className="flex justify-between text-sm text-gray-600">
        <span>Прогресс: {status.progress || 0}%</span>
        <span>Запущен: {new Date(status.created_at).toLocaleTimeString()}</span>
      </div>

      {status.message && (
        <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded text-sm text-red-700">
          <strong>Ошибка:</strong> {status.message}
        </div>
      )}

      {status.status === 'completed' && (
        <div className="mt-3 p-3 bg-green-50 border border-green-200 rounded text-sm text-green-700">
          <strong>✅ Анализ завершен успешно!</strong> Тесты сгенерированы и готовы к использованию.
        </div>
      )}
    </div>
  );
};

export default AnalysisStatus;