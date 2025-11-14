// src/components/features/tests/TestHistory.jsx
import React, { useState, useEffect } from 'react';
import { testsAPI } from '../../../services/api';
import { Button } from '../../ui';

const TestHistory = ({ project, onRunTestFromHistory }) => {
  const [testHistory, setTestHistory] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedRun, setSelectedRun] = useState(null);
  const [expandedRun, setExpandedRun] = useState(null);

  // Загружаем историю тестов
  useEffect(() => {
    loadTestHistory();
  }, [project.id]);

  const loadTestHistory = async () => {
    try {
      setLoading(true);
      const history = await testsAPI.getTestResults(project.id);
      // Преобразуем данные в формат истории
      const formattedHistory = Array.isArray(history)
        ? history.map(run => ({
            id: run.id || `run-${Date.now()}-${Math.random()}`,
            timestamp: run.created_at || new Date().toISOString(),
            status: run.status || 'completed',
            coverage: run.coverage || 0,
            duration: run.duration || 0,
            totalTests: run.results?.summary?.total || 0,
            passedTests: run.results?.summary?.passed || 0,
            failedTests: run.results?.summary?.failed || 0,
            tests: run.results?.tests || [],
            analysis_id: run.analysis_id,
            project_id: run.project_id
          }))
        : [];
      setTestHistory(formattedHistory);
    } catch (error) {
      console.error('Ошибка загрузки истории тестов:', error);
    } finally {
      setLoading(false);
    }
  };

  const formatDateTime = (timestamp) => {
    return new Date(timestamp).toLocaleString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const formatDuration = (ms) => {
    if (!ms) return 'N/A';
    const seconds = Math.floor(ms / 1000);
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;

    if (minutes > 0) {
      return `${minutes}m ${remainingSeconds}s`;
    }
    return `${remainingSeconds}s`;
  };

  const getStatusBadge = (status) => {
    const statusConfig = {
      completed: { color: 'bg-green-100 text-green-800', text: 'Завершено' },
      running: { color: 'bg-blue-100 text-blue-800', text: 'Запущено' },
      failed: { color: 'bg-red-100 text-red-800', text: 'Ошибка' },
      pending: { color: 'bg-yellow-100 text-yellow-800', text: 'Ожидание' }
    };

    const config = statusConfig[status] || statusConfig.pending;
    return (
      <span className={`px-2 py-1 rounded-full text-xs font-medium ${config.color}`}>
        {config.text}
      </span>
    );
  };

  const getCoverageColor = (coverage) => {
    if (coverage >= 80) return 'text-green-600';
    if (coverage >= 60) return 'text-yellow-600';
    return 'text-red-600';
  };

  const toggleRunDetails = (runId) => {
    setExpandedRun(expandedRun === runId ? null : runId);
  };

  const rerunTest = async (run) => {
    if (onRunTestFromHistory) {
      onRunTestFromHistory(run);
    }
  };

  const downloadResults = (run) => {
    const data = {
      project: project.name,
      timestamp: run.timestamp,
      results: run
    };

    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `test-results-${project.name}-${run.timestamp.split('T')[0]}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  if (loading) {
    return (
      <div className="bg-white rounded-lg border shadow-sm p-6">
        <div className="flex justify-center items-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          <span className="ml-3 text-gray-600">Загрузка истории тестов...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg border shadow-sm p-6">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h3 className="text-xl font-semibold">📊 История запусков тестов</h3>
          <p className="text-gray-600 text-sm mt-1">
            Всего запусков: {testHistory.length}
          </p>
        </div>
        <Button
          onClick={loadTestHistory}
          variant="secondary"
          size="small"
        >
          🔄 Обновить
        </Button>
      </div>

      {testHistory.length === 0 ? (
        <div className="text-center py-8 text-gray-500">
          <div className="text-4xl mb-2">📝</div>
          <p>История тестов пуста</p>
          <p className="text-sm mt-1">Запустите тесты, чтобы увидеть их здесь</p>
        </div>
      ) : (
        <div className="space-y-4">
          {testHistory.map((run) => (
            <div
              key={run.id}
              className="border rounded-lg hover:border-gray-400 transition-colors"
            >
              {/* Заголовок запуска */}
              <div
                className="p-4 cursor-pointer"
                onClick={() => toggleRunDetails(run.id)}
              >
                <div className="flex justify-between items-start">
                  <div className="flex items-center space-x-3">
                    <div className={`w-3 h-3 rounded-full ${
                      run.status === 'completed' ? 'bg-green-500' :
                      run.status === 'running' ? 'bg-blue-500' :
                      run.status === 'failed' ? 'bg-red-500' : 'bg-yellow-500'
                    }`}></div>
                    <div>
                      <div className="font-medium">
                        Запуск от {formatDateTime(run.timestamp)}
                      </div>
                      <div className="text-sm text-gray-500 flex items-center space-x-4 mt-1">
                        <span>{getStatusBadge(run.status)}</span>
                        <span>⏱️ {formatDuration(run.duration)}</span>
                        <span className={getCoverageColor(run.coverage)}>
                          📊 {run.coverage}% покрытия
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center space-x-2">
                    <Button
                      size="small"
                      variant="secondary"
                      onClick={(e) => {
                        e.stopPropagation();
                        rerunTest(run);
                      }}
                    >
                      🔁 Повторить
                    </Button>
                    <Button
                      size="small"
                      variant="secondary"
                      onClick={(e) => {
                        e.stopPropagation();
                        downloadResults(run);
                      }}
                    >
                      📥 Скачать
                    </Button>
                    <svg
                      className={`w-5 h-5 text-gray-400 transform transition-transform ${
                        expandedRun === run.id ? 'rotate-180' : ''
                      }`}
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                  </div>
                </div>

                {/* Краткая статистика */}
                <div className="grid grid-cols-4 gap-4 mt-3 text-center">
                  <div className="bg-blue-50 rounded p-2">
                    <div className="text-lg font-bold text-blue-700">{run.totalTests}</div>
                    <div className="text-xs text-blue-600">Всего тестов</div>
                  </div>
                  <div className="bg-green-50 rounded p-2">
                    <div className="text-lg font-bold text-green-700">{run.passedTests}</div>
                    <div className="text-xs text-green-600">Пройдено</div>
                  </div>
                  <div className="bg-red-50 rounded p-2">
                    <div className="text-lg font-bold text-red-700">{run.failedTests}</div>
                    <div className="text-xs text-red-600">Провалено</div>
                  </div>
                  <div className="bg-purple-50 rounded p-2">
                    <div className="text-lg font-bold text-purple-700">{run.coverage}%</div>
                    <div className="text-xs text-purple-600">Покрытие</div>
                  </div>
                </div>
              </div>

              {/* Детали запуска */}
              {expandedRun === run.id && (
                <div className="border-t p-4 bg-gray-50">
                  <div className="mb-4">
                    <h4 className="font-medium mb-2">📋 Детали тестов</h4>
                    <div className="space-y-2 max-h-60 overflow-y-auto">
                      {run.tests && run.tests.length > 0 ? (
                        run.tests.map((test, index) => (
                          <div
                            key={index}
                            className="flex justify-between items-center p-2 bg-white rounded border"
                          >
                            <div className="flex items-center space-x-3">
                              <span className={
                                test.status === 'passed' ? 'text-green-600' :
                                test.status === 'failed' ? 'text-red-600' : 'text-yellow-600'
                              }>
                                {test.status === 'passed' ? '✅' :
                                 test.status === 'failed' ? '❌' : '⏳'}
                              </span>
                              <div>
                                <div className="font-medium text-sm">{test.name}</div>
                                <div className="text-xs text-gray-500">{test.file}</div>
                              </div>
                            </div>
                            <div className="text-sm text-gray-600">
                              {test.duration ? `${test.duration}ms` : 'N/A'}
                            </div>
                          </div>
                        ))
                      ) : (
                        <div className="text-center py-4 text-gray-500">
                          Нет детальной информации о тестах
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="flex justify-between items-center">
                    <div className="text-sm text-gray-600">
                      ID запуска: {run.id}
                    </div>
                    <div className="flex space-x-2">
                      <Button
                        size="small"
                        variant="primary"
                        onClick={() => rerunTest(run)}
                      >
                        🔁 Запустить снова
                      </Button>
                      <Button
                        size="small"
                        variant="secondary"
                        onClick={() => downloadResults(run)}
                      >
                        📥 Скачать JSON
                      </Button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default TestHistory;