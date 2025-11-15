import React, { useState, useEffect } from 'react';
import { Button } from '../../ui';
import { testsAPI, generatedTestsAPI } from '../../../services/api';

const PushToRepository = ({ project, onPushComplete }) => {
  const [testBatches, setTestBatches] = useState([]);
  const [testCases, setTestCases] = useState([]);
  const [selectedBatch, setSelectedBatch] = useState(null);
  const [selectedTestCases, setSelectedTestCases] = useState(new Set());
  const [pushConfig, setPushConfig] = useState({
    commit_message: 'Add generated tests and test cases',
    include_test_cases: true,
    test_cases_format: 'markdown',
    create_documentation_folder: true
  });
  const [pushing, setPushing] = useState(false);
  const [pushStatus, setPushStatus] = useState('idle');
  const [error, setError] = useState(null);

  useEffect(() => {
    loadTestBatches();
    loadTestCases();
  }, [project.id]);

  const loadTestBatches = async () => {
    try {
      const batches = await generatedTestsAPI.getTestBatches(project.id);
      setTestBatches(batches || []);
    } catch (error) {
      console.error('Error loading test batches:', error);
    }
  };

  const loadTestCases = async () => {
    try {
      const cases = await testsAPI.getTestCases(project.id);
      setTestCases(cases || []);
    } catch (error) {
      console.error('Error loading test cases:', error);
    }
  };

  const handleBatchSelect = (batchId) => {
    setSelectedBatch(batchId);
  };

  const handleTestCaseSelect = (caseId) => {
    setSelectedTestCases(prev => {
      const newSelection = new Set(prev);
      if (newSelection.has(caseId)) {
        newSelection.delete(caseId);
      } else {
        newSelection.add(caseId);
      }
      return newSelection;
    });
  };

  const handleSelectAllTestCases = () => {
    if (selectedTestCases.size === testCases.length) {
      setSelectedTestCases(new Set());
    } else {
      setSelectedTestCases(new Set(testCases.map(tc => tc.id)));
    }
  };

  const handlePush = async () => {
    if (!selectedBatch && selectedTestCases.size === 0) {
      alert('Выберите тесты или тест-кейсы для пуша');
      return;
    }

    setPushing(true);
    setPushStatus('pushing');
    setError(null);

    try {
      const pushData = {
        test_batch_id: selectedBatch,
        test_case_ids: Array.from(selectedTestCases),
        include_test_cases: pushConfig.include_test_cases,
        commit_message: pushConfig.commit_message,
        test_cases_format: pushConfig.test_cases_format
      };

      const result = await testsAPI.pushTestsAndCases(project.id, pushData);

      if (result.status === 'success') {
        setPushStatus('success');
        alert('✅ Тесты и тест-кейсы успешно отправлены в репозиторий!');

        // Обновляем данные
        loadTestBatches();
        loadTestCases();

        onPushComplete?.(result);
      } else {
        setPushStatus('error');
        setError(result.error || 'Ошибка при пуше в репозиторий');
      }
    } catch (error) {
      setPushStatus('error');
      setError(error.message);
      console.error('Push failed:', error);
    } finally {
      setPushing(false);
    }
  };

  const getSelectedBatch = () => {
    return testBatches.find(batch => batch.id === selectedBatch);
  };

  const getSelectedTestCases = () => {
    return testCases.filter(tc => selectedTestCases.has(tc.id));
  };

  return (
    <div className="bg-white rounded-lg border shadow-sm p-6">
      <h3 className="text-xl font-semibold mb-6">🚀 Пуш в репозиторий</h3>

      <div className="space-y-6">
        {/* Выбор тестов */}
        <div>
          <h4 className="font-medium text-gray-900 mb-4">Выберите тесты для пуша</h4>

          {/* Выбор пачки тестов */}
          <div className="mb-6">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Пачка тестов
            </label>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {testBatches.map(batch => (
                <div
                  key={batch.id}
                  className={`p-4 border rounded-lg cursor-pointer transition-all ${
                    selectedBatch === batch.id
                      ? 'border-blue-500 bg-blue-50'
                      : 'border-gray-200 hover:border-gray-300'
                  }`}
                  onClick={() => handleBatchSelect(batch.id)}
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-medium">{batch.name}</span>
                    <span className={`px-2 py-1 text-xs rounded-full ${
                      batch.status === 'pushed'
                        ? 'bg-green-100 text-green-800'
                        : 'bg-gray-100 text-gray-800'
                    }`}>
                      {batch.status === 'pushed' ? '✅ Отправлено' : '📦 Готово'}
                    </span>
                  </div>
                  <div className="text-sm text-gray-600">
                    {batch.total_tests} тестов • {batch.framework}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Выбор тест-кейсов */}
          <div>
            <div className="flex items-center justify-between mb-4">
              <label className="block text-sm font-medium text-gray-700">
                Тест-кейсы
              </label>
              <Button
                onClick={handleSelectAllTestCases}
                variant="secondary"
                size="small"
              >
                {selectedTestCases.size === testCases.length ? 'Снять выделение' : 'Выделить все'}
              </Button>
            </div>

            <div className="max-h-60 overflow-y-auto border rounded-lg">
              {testCases.map(testCase => (
                <div
                  key={testCase.id}
                  className={`p-3 border-b last:border-b-0 flex items-center space-x-3 cursor-pointer ${
                    selectedTestCases.has(testCase.id)
                      ? 'bg-blue-50'
                      : 'hover:bg-gray-50'
                  }`}
                  onClick={() => handleTestCaseSelect(testCase.id)}
                >
                  <input
                    type="checkbox"
                    checked={selectedTestCases.has(testCase.id)}
                    onChange={() => {}}
                    className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                  />
                  <div className="flex-1">
                    <div className="flex items-center justify-between">
                      <span className="font-medium">{testCase.test_case_id}</span>
                      <span className={`px-2 py-1 text-xs rounded ${
                        testCase.priority === 'high' ? 'bg-red-100 text-red-800' :
                        testCase.priority === 'medium' ? 'bg-yellow-100 text-yellow-800' :
                        'bg-green-100 text-green-800'
                      }`}>
                        {testCase.priority}
                      </span>
                    </div>
                    <div className="text-sm text-gray-600">{testCase.name}</div>
                    <div className="text-xs text-gray-500">
                      {testCase.test_type} • {testCase.status}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Настройки пуша */}
        <div>
          <h4 className="font-medium text-gray-900 mb-4">Настройки пуша</h4>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Сообщение коммита
              </label>
              <input
                type="text"
                value={pushConfig.commit_message}
                onChange={(e) => setPushConfig(prev => ({
                  ...prev,
                  commit_message: e.target.value
                }))}
                className="w-full p-2 border border-gray-300 rounded focus:ring-blue-500 focus:border-blue-500"
                placeholder="Add generated tests and test cases"
              />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Формат тест-кейсов
                </label>
                <select
                  value={pushConfig.test_cases_format}
                  onChange={(e) => setPushConfig(prev => ({
                    ...prev,
                    test_cases_format: e.target.value
                  }))}
                  className="w-full p-2 border border-gray-300 rounded focus:ring-blue-500 focus:border-blue-500"
                >
                  <option value="markdown">Markdown (.md)</option>
                  <option value="html">HTML</option>
                  <option value="txt">Text (.txt)</option>
                </select>
              </div>

              <div className="flex items-center space-x-3">
                <input
                  type="checkbox"
                  checked={pushConfig.include_test_cases}
                  onChange={(e) => setPushConfig(prev => ({
                    ...prev,
                    include_test_cases: e.target.checked
                  }))}
                  className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                <span className="text-sm text-gray-700">
                  Включать тест-кейсы
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Статистика */}
        {(selectedBatch || selectedTestCases.size > 0) && (
          <div className="bg-gray-50 rounded-lg p-4">
            <h5 className="font-medium text-gray-900 mb-3">Сводка пуша</h5>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div>
                <span className="text-gray-600">Пачка тестов:</span>
                <div className="font-medium">
                  {selectedBatch ? getSelectedBatch()?.name : 'Не выбрана'}
                </div>
              </div>
              <div>
                <span className="text-gray-600">Тесты:</span>
                <div className="font-medium">
                  {selectedBatch ? getSelectedBatch()?.total_tests : 0}
                </div>
              </div>
              <div>
                <span className="text-gray-600">Тест-кейсы:</span>
                <div className="font-medium">
                  {selectedTestCases.size}
                </div>
              </div>
              <div>
                <span className="text-gray-600">Формат:</span>
                <div className="font-medium">
                  {pushConfig.test_cases_format}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Кнопка пуша и статус */}
        <div className="flex items-center justify-between pt-4 border-t">
          <div className="flex-1">
            {pushStatus === 'success' && (
              <div className="text-green-600 font-medium">
                ✅ Успешно отправлено в репозиторий
              </div>
            )}
            {pushStatus === 'error' && (
              <div className="text-red-600">
                ❌ Ошибка: {error}
              </div>
            )}
          </div>

          <Button
            onClick={handlePush}
            loading={pushing}
            disabled={pushing || (!selectedBatch && selectedTestCases.size === 0)}
            variant="primary"
            size="large"
          >
            {pushing ? '🔄 Отправка...' : '🚀 Отправить в репозиторий'}
          </Button>
        </div>
      </div>
    </div>
  );
};

export default PushToRepository;