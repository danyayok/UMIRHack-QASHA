// src/components/features/tests/TestRunner.jsx (обновленная версия)
import React, { useState, useEffect } from 'react';
import { testsAPI } from '../../../services/api';
import { Button } from '../../ui';
import TestHistory from './TestHistory';

const TestRunner = ({ project, onTestResultsUpdate }) => {
  const [testResults, setTestResults] = useState(null);
  const [isRunning, setIsRunning] = useState(false);
  const [progress, setProgress] = useState(0);
  const [logs, setLogs] = useState([]);
  const [selectedTest, setSelectedTest] = useState(null);
  const [activeTab, setActiveTab] = useState('current'); // 'current' или 'history'

  // Загружаем последние результаты тестов
  useEffect(() => {
    loadTestResults();
  }, [project.id]);

  const loadTestResults = async () => {
    try {
      const results = await testsAPI.getTestResults(project.id);
      // Если API возвращает массив, берем последний результат
      const latestResult = Array.isArray(results) ? results[0] : results;
      setTestResults(latestResult);
    } catch (error) {
      console.error('Ошибка загрузки результатов тестов:', error);
    }
  };

  const runAllTests = async () => {
    setIsRunning(true);
    setProgress(0);
    setLogs(prev => [...prev, '🚀 Запуск всех тестов...']);

    try {
      // Имитация прогресса
      const progressInterval = setInterval(() => {
        setProgress(prev => {
          if (prev >= 90) {
            clearInterval(progressInterval);
            return 90;
          }
          return prev + 10;
        });
      }, 500);

      const results = await testsAPI.runTests(project.id);

      clearInterval(progressInterval);
      setProgress(100);
      setTestResults(results);
      onTestResultsUpdate?.(results);

      setLogs(prev => [...prev, '✅ Все тесты завершены!']);

      // Автоматически скрываем прогресс через 2 секунды
      setTimeout(() => {
        setIsRunning(false);
        setProgress(0);
      }, 2000);

    } catch (error) {
      setIsRunning(false);
      setProgress(0);
      setLogs(prev => [...prev, `❌ Ошибка: ${error.message}`]);
    }
  };

  const runSpecificTest = async (testFile) => {
    setIsRunning(true);
    setSelectedTest(testFile);
    setLogs(prev => [...prev, `🎯 Запуск теста: ${testFile}`]);

    try {
      const results = await testsAPI.runSpecificTest(project.id, testFile);
      setTestResults(results);
      onTestResultsUpdate?.(results);
      setLogs(prev => [...prev, `✅ Тест ${testFile} завершен`]);
    } catch (error) {
      setLogs(prev => [...prev, `❌ Ошибка в тесте ${testFile}: ${error.message}`]);
    } finally {
      setIsRunning(false);
      setSelectedTest(null);
    }
  };

  const handleRunFromHistory = async (historicalRun) => {
    setLogs(prev => [...prev, `🔁 Повторный запуск из истории: ${historicalRun.timestamp}`]);
    await runAllTests();
  };

  const clearLogs = () => {
    setLogs([]);
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'passed': return 'text-green-600 bg-green-100';
      case 'failed': return 'text-red-600 bg-red-100';
      case 'running': return 'text-blue-600 bg-blue-100';
      default: return 'text-gray-600 bg-gray-100';
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'passed': return '✅';
      case 'failed': return '❌';
      case 'running': return '🔄';
      default: return '⏸️';
    }
  };

  return (
    <div className="space-y-6">
      {/* Переключатель вкладок */}
      <div className="bg-white rounded-lg border shadow-sm p-4">
        <div className="flex border-b">
          <button
            onClick={() => setActiveTab('current')}
            className={`px-4 py-2 font-medium border-b-2 transition-colors ${
              activeTab === 'current'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            🧪 Текущие тесты
          </button>
          <button
            onClick={() => setActiveTab('history')}
            className={`px-4 py-2 font-medium border-b-2 transition-colors ${
              activeTab === 'history'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            📊 История запусков
          </button>
        </div>
      </div>

      {activeTab === 'current' ? (
        /* Вкладка текущих тестов */
        <>
          {/* Статистика и быстрые действия */}
          <div className="bg-white rounded-lg border shadow-sm p-6">
            <div className="flex justify-between items-center mb-6">
              <h3 className="text-xl font-semibold">Запуск тестов</h3>
              <div className="flex gap-3">
                <Button
                  onClick={runAllTests}
                  loading={isRunning && !selectedTest}
                  disabled={isRunning}
                  variant="primary"
                >
                  ▶️ Запустить все тесты
                </Button>
                <Button
                  onClick={loadTestResults}
                  variant="secondary"
                >
                  🔄 Обновить результаты
                </Button>
              </div>
            </div>

            {/* Прогресс бар */}
            {isRunning && (
              <div className="mb-6">
                <div className="flex justify-between text-sm text-gray-600 mb-2">
                  <span>
                    {selectedTest ? `Запуск теста: ${selectedTest}` : 'Запуск всех тестов...'}
                  </span>
                  <span>{progress}%</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-3">
                  <div
                    className="bg-blue-600 h-3 rounded-full transition-all duration-300"
                    style={{ width: `${progress}%` }}
                  ></div>
                </div>
              </div>
            )}

            {/* Статистика тестов */}
            {testResults && (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                <div className={`p-4 rounded-lg text-center ${
                  testResults.passed > 0 ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                }`}>
                  <div className="text-2xl font-bold">{testResults.passed || 0}</div>
                  <div className="text-sm">Пройдено</div>
                </div>
                <div className={`p-4 rounded-lg text-center ${
                  testResults.failed > 0 ? 'bg-red-100 text-red-800' : 'bg-gray-100 text-gray-800'
                }`}>
                  <div className="text-2xl font-bold">{testResults.failed || 0}</div>
                  <div className="text-sm">Провалено</div>
                </div>
                <div className="p-4 rounded-lg text-center bg-blue-100 text-blue-800">
                  <div className="text-2xl font-bold">{testResults.total || 0}</div>
                  <div className="text-sm">Всего тестов</div>
                </div>
                <div className="p-4 rounded-lg text-center bg-purple-100 text-purple-800">
                  <div className="text-2xl font-bold">{testResults.coverage || 0}%</div>
                  <div className="text-sm">Покрытие</div>
                </div>
              </div>
            )}

            {/* Детальная информация о тестах */}
            {testResults?.tests && (
              <div>
                <h4 className="font-medium mb-3">Детали тестов</h4>
                <div className="space-y-2 max-h-80 overflow-y-auto">
                  {testResults.tests.map((test, index) => (
                    <div
                      key={index}
                      className="flex items-center justify-between p-3 border rounded hover:bg-gray-50"
                    >
                      <div className="flex items-center space-x-3">
                        <span className={getStatusColor(test.status)}>
                          {getStatusIcon(test.status)}
                        </span>
                        <div>
                          <div className="font-medium">{test.name}</div>
                          <div className="text-sm text-gray-500">{test.file}</div>
                        </div>
                      </div>
                      <div className="flex items-center space-x-3">
                        <span className="text-sm text-gray-500">
                          {test.duration ? `${test.duration}ms` : 'N/A'}
                        </span>
                        <Button
                          size="small"
                          variant="secondary"
                          onClick={() => runSpecificTest(test.file)}
                          disabled={isRunning}
                        >
                          Запустить
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Логи выполнения */}
          <div className="bg-white rounded-lg border shadow-sm p-6">
            <div className="flex justify-between items-center mb-4">
              <h4 className="font-medium">Логи выполнения</h4>
              <Button onClick={clearLogs} size="small" variant="secondary">
                Очистить логи
              </Button>
            </div>
            <div className="bg-gray-900 text-green-400 p-4 rounded font-mono text-sm max-h-60 overflow-y-auto">
              {logs.length === 0 ? (
                <div className="text-gray-500">Логи появятся здесь после запуска тестов...</div>
              ) : (
                logs.map((log, index) => (
                  <div key={index} className="py-1">
                    {log}
                  </div>
                ))
              )}
            </div>
          </div>
        </>
      ) : (
        /* Вкладка истории тестов */
        <TestHistory
          project={project}
          onRunTestFromHistory={handleRunFromHistory}
        />
      )}

      {/* Информация о проекте */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <h4 className="font-medium text-blue-900 mb-2">Информация о проекте</h4>
        <div className="text-sm text-blue-800 space-y-1">
          <p><strong>Проект:</strong> {project.name}</p>
          <p><strong>Технологии:</strong> {project.latest_analysis?.result?.technologies?.join(', ') || 'Не определены'}</p>
          <p><strong>Тестовые фреймворки:</strong> {project.latest_analysis?.result?.test_analysis?.test_frameworks?.join(', ') || 'Не обнаружены'}</p>
          <p><strong>Тестовых файлов:</strong> {project.latest_analysis?.result?.test_analysis?.test_files_count || 0}</p>
        </div>
      </div>
    </div>
  );
};

export default TestRunner;