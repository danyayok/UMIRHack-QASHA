// src/components/features/tests/GeneratedTestsView.jsx
import React, { useState, useEffect } from 'react';
import { Button } from '../../ui';
import { testsAPI, generatedTestsAPI } from '../../../services/api';

const GeneratedTestsView = ({ project, onRunTests }) => {
  const [testBatches, setTestBatches] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedBatch, setSelectedBatch] = useState(null);
  const [batchTests, setBatchTests] = useState([]);
  const [selectedTests, setSelectedTests] = useState(new Set());
  const [pushLoading, setPushLoading] = useState(false);
  const [viewMode, setViewMode] = useState('batches');
  const [error, setError] = useState(null);
  const [selectedTest, setSelectedTest] = useState(null);
  const [testCases, setTestCases] = useState([]);
  const [selectedTestCases, setSelectedTestCases] = useState(new Set());
  const [showPushModal, setShowPushModal] = useState(false);
  const [pushConfig, setPushConfig] = useState({
    commit_message: 'Add generated tests and test cases',
    include_test_cases: true,
    test_cases_format: 'markdown'
  });

  useEffect(() => {
    loadTestBatches();
    loadTestCases();
  }, [project.id]);

  const loadTestBatches = async () => {
    try {
      setLoading(true);
      setError(null);
      const batches = await generatedTestsAPI.getTestBatches(project.id);
      console.log('📦 Real test batches:', batches);
      setTestBatches(batches || []);
    } catch (error) {
      console.error('Ошибка загрузки пачек тестов:', error);
      setError('Не удалось загрузить пачки тестов');
      setTestBatches([]);
    } finally {
      setLoading(false);
    }
  };

  const loadTestCases = async () => {
    try {
      const cases = await generatedTestsAPI.getTestCases(project.id, {
        status: 'draft' // Загружаем только неотправленные тест-кейсы
      });
      setTestCases(cases || []);
    } catch (error) {
      console.error('Ошибка загрузки тест-кейсов:', error);
    }
  };

  const loadBatchTests = async (batchId) => {
    try {
      setError(null);
      const batchData = await generatedTestsAPI.getTestBatch(project.id, batchId);
      console.log('🧪 Real batch tests:', batchData);

      if (batchData) {
        setSelectedBatch(batchData);
        setBatchTests(batchData.tests || []);
        setViewMode('tests');
      }
    } catch (error) {
      console.error('Ошибка загрузки тестов пачки:', error);
      setError('Не удалось загрузить тесты пачки');
    }
  };

  // Просмотр конкретного теста
  const viewTestCode = (testId) => {
    setSelectedTest(testId);
  };

  const closeTestCode = () => {
    setSelectedTest(null);
  };

  const getTestCode = (testId) => {
    const test = batchTests.find(t => t.id === testId);
    return test?.content || test?.code || '// Код теста не доступен';
  };

  const getTest = (testId) => {
    return batchTests.find(t => t.id === testId);
  };

  const handleTestSelect = (testId) => {
    setSelectedTests(prev => {
      const newSelection = new Set(prev);
      if (newSelection.has(testId)) {
        newSelection.delete(testId);
      } else {
        newSelection.add(testId);
      }
      return newSelection;
    });
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

  const handleSelectAllTests = () => {
    if (selectedTests.size === batchTests.length) {
      setSelectedTests(new Set());
    } else {
      setSelectedTests(new Set(batchTests.map(test => test.id)));
    }
  };

  const handleSelectAllTestCases = () => {
    if (selectedTestCases.size === testCases.length) {
      setSelectedTestCases(new Set());
    } else {
      setSelectedTestCases(new Set(testCases.map(tc => tc.id)));
    }
  };

  const handlePushToRepository = async () => {
    if (!selectedBatch && selectedTestCases.size === 0) {
      alert('Выберите тесты или тест-кейсы для отправки в репозиторий');
      return;
    }

    try {
      setPushLoading(true);
      setError(null);

      const pushData = {
        test_batch_id: selectedBatch?.id,
        test_case_ids: Array.from(selectedTestCases),
        include_test_cases: pushConfig.include_test_cases,
        commit_message: pushConfig.commit_message,
        test_cases_format: pushConfig.test_cases_format
      };

      const result = await generatedTestsAPI.pushTestsAndCases(project.id, pushData);

      console.log('📤 Push result:', result);

      if (result.status === 'success') {
        alert(`✅ ${result.message || 'Тесты и тест-кейсы успешно отправлены в репозиторий!'}`);

        // Обновляем данные
        loadTestBatches();
        loadTestCases();

        // Сбрасываем выбор
        setSelectedTests(new Set());
        setSelectedTestCases(new Set());
        setShowPushModal(false);

        // Обновляем статус пачки в UI
        if (selectedBatch) {
          setTestBatches(prev => prev.map(batch =>
            batch.id === selectedBatch.id ? { ...batch, status: 'pushed' } : batch
          ));
        }
      } else {
        throw new Error(result.error || 'Ошибка при отправке');
      }
    } catch (error) {
      console.error('Ошибка отправки тестов:', error);
      setError('Ошибка отправки тестов: ' + error.message);
      alert('❌ Ошибка отправки тестов: ' + error.message);
    } finally {
      setPushLoading(false);
    }
  };

  const handlePushBatchToRepo = async (batchId) => {
    try {
      setPushLoading(true);
      setError(null);

      const pushData = {
        test_batch_id: batchId,
        test_case_ids: [],
        include_test_cases: false,
        commit_message: 'Add generated tests',
        test_cases_format: 'markdown'
      };

      const result = await generatedTestsAPI.pushTestsAndCases(project.id, pushData);

      if (result.status === 'success') {
        alert(`✅ ${result.message || 'Пачка тестов успешно отправлена в репозиторий!'}`);

        setTestBatches(prev => prev.map(batch =>
          batch.id === batchId ? { ...batch, status: 'pushed' } : batch
        ));
      } else {
        throw new Error(result.error || 'Ошибка при отправке');
      }
    } catch (error) {
      console.error('Ошибка отправки тестов:', error);
      setError('Ошибка отправки тестов: ' + error.message);
      alert('❌ Ошибка отправки тестов: ' + error.message);
    } finally {
      setPushLoading(false);
    }
  };

  const handleBackToBatches = () => {
    setSelectedBatch(null);
    setBatchTests([]);
    setSelectedTests(new Set());
    setSelectedTest(null);
    setViewMode('batches');
    setError(null);
  };

  const getStatusColor = (status) => {
    const colors = {
      completed: 'bg-green-100 text-green-800',
      pending: 'bg-yellow-100 text-yellow-800',
      failed: 'bg-red-100 text-red-800',
      pushed: 'bg-blue-100 text-blue-800'
    };
    return colors[status] || 'bg-gray-100 text-gray-800';
  };

  const getStatusIcon = (status) => {
    const icons = {
      completed: '✅',
      pending: '⏳',
      failed: '❌',
      pushed: '📤'
    };
    return icons[status] || '📁';
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="text-lg">Загрузка сгенерированных тестов...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Модальное окно пуша */}
      {showPushModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto">
            <h3 className="text-xl font-semibold mb-4">🚀 Отправка в репозиторий</h3>

            <div className="space-y-4">
              {/* Выбор тест-кейсов */}
              <div>
                <h4 className="font-medium mb-3">Тест-кейсы для отправки ({selectedTestCases.size})</h4>
                <div className="max-h-40 overflow-y-auto border rounded-lg">
                  {testCases.map(testCase => (
                    <div
                      key={testCase.id}
                      className={`p-3 border-b last:border-b-0 flex items-center space-x-3 cursor-pointer ${
                        selectedTestCases.has(testCase.id) ? 'bg-blue-50' : 'hover:bg-gray-50'
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
                        <div className="font-medium">{testCase.test_case_id}</div>
                        <div className="text-sm text-gray-600">{testCase.name}</div>
                      </div>
                    </div>
                  ))}
                </div>
                <div className="flex justify-between items-center mt-2">
                  <span className="text-sm text-gray-600">
                    Выбрано: {selectedTestCases.size} тест-кейсов
                  </span>
                  <Button
                    onClick={handleSelectAllTestCases}
                    variant="secondary"
                    size="small"
                  >
                    {selectedTestCases.size === testCases.length ? 'Снять выделение' : 'Выделить все'}
                  </Button>
                </div>
              </div>

              {/* Настройки пуша */}
              <div>
                <h4 className="font-medium mb-3">Настройки отправки</h4>
                <div className="space-y-3">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
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
                    />
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
                      Включать тест-кейсы в документацию
                    </span>
                  </div>
                </div>
              </div>

              {/* Сводка */}
              <div className="bg-gray-50 rounded-lg p-4">
                <h5 className="font-medium mb-2">Сводка отправки</h5>
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div>
                    <span className="text-gray-600">Тесты:</span>
                    <span className="font-medium ml-2">
                      {selectedBatch ? `${selectedBatch.total_tests} из пачки` : 'Не выбраны'}
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-600">Тест-кейсы:</span>
                    <span className="font-medium ml-2">{selectedTestCases.size}</span>
                  </div>
                  <div>
                    <span className="text-gray-600">Формат:</span>
                    <span className="font-medium ml-2">{pushConfig.test_cases_format}</span>
                  </div>
                  <div>
                    <span className="text-gray-600">Репозиторий:</span>
                    <span className="font-medium ml-2">{project.repo_url}</span>
                  </div>
                </div>
              </div>
            </div>

            <div className="flex justify-end space-x-3 mt-6">
              <Button
                onClick={() => setShowPushModal(false)}
                variant="secondary"
                disabled={pushLoading}
              >
                Отмена
              </Button>
              <Button
                onClick={handlePushToRepository}
                loading={pushLoading}
                variant="primary"
              >
                📤 Отправить в репозиторий
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Заголовок и действия */}
      <div className="bg-white rounded-lg border shadow-sm p-6">
        <div className="flex justify-between items-center">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">
              {viewMode === 'batches' ? '📦 Пачки тестов' :
               selectedTest ? `📝 Просмотр теста` : `🧪 Тесты: ${selectedBatch?.name}`}
            </h2>
            <p className="text-gray-600 mt-1">
              {viewMode === 'batches'
                ? 'Группировка тестов по генерациям'
                : selectedTest
                ? 'Просмотр кода выбранного теста'
                : `Просмотр тестов из пачки "${selectedBatch?.name}"`}
            </p>
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-3">
              <p className="text-red-800 text-sm">{error}</p>
            </div>
          )}

          <div className="flex items-center space-x-3">
            {selectedTest ? (
              <>
                <Button
                  onClick={closeTestCode}
                  variant="secondary"
                  size="medium"
                >
                  ← Назад к тестам
                </Button>
                <Button
                  onClick={() => {
                    const code = getTestCode(selectedTest);
                    navigator.clipboard.writeText(code);
                    alert('Код теста скопирован в буфер обмена!');
                  }}
                  variant="primary"
                  size="medium"
                >
                  📋 Копировать код
                </Button>
              </>
            ) : viewMode === 'tests' ? (
              <>
                <Button
                  onClick={handleSelectAllTests}
                  variant="secondary"
                  size="medium"
                >
                  {selectedTests.size === batchTests.length ? 'Снять выделение' : 'Выделить все'}
                </Button>
                <Button
                  onClick={() => setShowPushModal(true)}
                  variant="primary"
                  size="medium"
                >
                  📤 Отправить в репозиторий
                </Button>
                <Button
                  onClick={handleBackToBatches}
                  variant="secondary"
                  size="medium"
                >
                  ← Назад к пачкам
                </Button>
              </>
            ) : (
              <Button
                onClick={() => setShowPushModal(true)}
                variant="primary"
                size="medium"
              >
                📤 Отправить в репозиторий
              </Button>
            )}

            {!selectedTest && (
              <Button
                onClick={onRunTests}
                variant="secondary"
                size="medium"
              >
                ▶️ Запустить тесты
              </Button>
            )}
          </div>
        </div>
      </div>

      {/* Основной контент */}
      {viewMode === 'batches' ? (
        /* Режим просмотра пачек */
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Список пачек */}
          <div className="lg:col-span-2 space-y-4">
            <div className="bg-white rounded-lg border shadow-sm">
              <div className="p-4 border-b">
                <div className="flex justify-between items-center">
                  <h3 className="font-semibold">История генераций ({testBatches.length})</h3>
                  <Button
                    onClick={loadTestBatches}
                    variant="secondary"
                    size="small"
                  >
                    🔄 Обновить
                  </Button>
                </div>
              </div>

              {testBatches.length === 0 ? (
                <div className="p-8 text-center text-gray-500">
                  <div className="text-lg mb-2">📭 Нет сгенерированных тестов</div>
                  <div className="text-sm">
                    Сгенерируйте тесты через вкладку "Генератор тестов"
                  </div>
                </div>
              ) : (
                <div className="divide-y">
                  {testBatches.map(batch => (
                    <div
                      key={batch.id}
                      className="p-6 hover:bg-gray-50 transition-colors"
                    >
                      <div className="flex items-start justify-between">
                        <div
                          className="flex-1 cursor-pointer"
                          onClick={() => loadBatchTests(batch.id)}
                        >
                          <div className="flex items-center space-x-3 mb-2">
                            <span className={`px-2 py-1 text-xs rounded-full ${getStatusColor(batch.status)}`}>
                              {getStatusIcon(batch.status)} {batch.status}
                            </span>
                            <span className="text-sm text-gray-500">
                              {new Date(batch.created_at).toLocaleDateString()}
                            </span>
                          </div>

                          <h4 className="font-semibold text-lg mb-2">{batch.name}</h4>
                          <p className="text-gray-600 mb-3">{batch.description}</p>

                          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                            <div>
                              <span className="text-gray-500">Тестов:</span>
                              <span className="font-medium ml-2">{batch.total_tests}</span>
                            </div>
                            <div>
                              <span className="text-gray-500">Покрытие +:</span>
                              <span className="font-medium text-green-600 ml-2">
                                +{batch.coverage_improvement}%
                              </span>
                            </div>
                            <div>
                              <span className="text-gray-500">Фреймворк:</span>
                              <span className="font-medium ml-2">{batch.framework}</span>
                            </div>
                            <div>
                              <span className="text-gray-500">AI:</span>
                              <span className="font-medium ml-2">{batch.ai_provider}</span>
                            </div>
                          </div>
                        </div>

                        <div className="flex flex-col space-y-2 ml-4">
                          <Button
                            onClick={(e) => {
                              e.stopPropagation();
                              loadBatchTests(batch.id);
                            }}
                            variant="secondary"
                            size="small"
                          >
                            👁️ Просмотр
                          </Button>
                          <Button
                            onClick={(e) => {
                              e.stopPropagation();
                              handlePushBatchToRepo(batch.id);
                            }}
                            loading={pushLoading}
                            disabled={batch.status === 'pushed'}
                            variant="primary"
                            size="small"
                          >
                            {batch.status === 'pushed' ? '✅ Отправлено' : '📤 В репозиторий'}
                          </Button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Статистика */}
          <div className="space-y-6">
            <div className="bg-white rounded-lg border shadow-sm p-4">
              <h3 className="font-semibold mb-3">📊 Общая статистика</h3>
              <div className="space-y-3">
                <div className="flex justify-between items-center">
                  <span className="text-sm text-gray-600">Всего пачек:</span>
                  <span className="font-medium">{testBatches.length}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-sm text-gray-600">Всего тестов:</span>
                  <span className="font-medium">
                    {testBatches.reduce((sum, batch) => sum + batch.total_tests, 0)}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-sm text-gray-600">Успешных генераций:</span>
                  <span className="font-medium text-green-600">
                    {testBatches.filter(b => b.status === 'completed').length}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-sm text-gray-600">Отправлено в репо:</span>
                  <span className="font-medium text-blue-600">
                    {testBatches.filter(b => b.status === 'pushed').length}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-sm text-gray-600">Тест-кейсов:</span>
                  <span className="font-medium text-purple-600">
                    {testCases.length}
                  </span>
                </div>
              </div>
            </div>

            <div className="bg-white rounded-lg border shadow-sm p-4">
              <h3 className="font-semibold mb-3">🎯 Быстрые действия</h3>
              <div className="space-y-2">
                <Button
                  onClick={() => setShowPushModal(true)}
                  variant="primary"
                  size="small"
                  className="w-full justify-center"
                >
                  📤 Отправить в репозиторий
                </Button>
                <Button
                  onClick={loadTestBatches}
                  variant="secondary"
                  size="small"
                  className="w-full justify-center"
                >
                  🔄 Обновить данные
                </Button>
              </div>
            </div>
          </div>
        </div>
      ) : selectedTest ? (
        /* Режим просмотра кода теста */
        <div className="bg-white rounded-lg border shadow-sm">
          <div className="p-4 border-b">
            <div className="flex justify-between items-center">
              <h3 className="font-semibold">
                Код теста: {getTest(selectedTest)?.name || 'Неизвестный тест'}
              </h3>
              <div className="flex items-center space-x-2">
                <span className={`px-2 py-1 text-xs rounded-full ${getTestTypeColor(getTest(selectedTest)?.test_type)}`}>
                  {getTest(selectedTest)?.test_type}
                </span>
                <span className="text-sm text-gray-500">
                  {getTest(selectedTest)?.file_path}
                </span>
              </div>
            </div>
          </div>

          <div className="p-4">
            <div className="bg-gray-900 text-gray-100 rounded-lg p-4 overflow-x-auto">
              <pre className="whitespace-pre-wrap text-sm font-mono">
                {getTestCode(selectedTest)}
              </pre>
            </div>

            <div className="mt-4 flex justify-between items-center">
              <div className="text-sm text-gray-600">
                Длина кода: {getTestCode(selectedTest).length} символов •
                Фреймворк: {getTest(selectedTest)?.framework} •
                Тип: {getTest(selectedTest)?.test_type}
              </div>
              <div className="flex space-x-2">
                <Button
                  onClick={() => {
                    const code = getTestCode(selectedTest);
                    navigator.clipboard.writeText(code);
                    alert('Код теста скопирован в буфер обмена!');
                  }}
                  variant="primary"
                  size="small"
                >
                  📋 Копировать код
                </Button>
                <Button
                  onClick={closeTestCode}
                  variant="secondary"
                  size="small"
                >
                  ← Назад к списку
                </Button>
              </div>
            </div>
          </div>
        </div>
      ) : (
        /* Режим просмотра списка тестов */
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Список тестов */}
          <div className="lg:col-span-2 space-y-4">
            <div className="bg-white rounded-lg border shadow-sm">
              <div className="p-4 border-b">
                <div className="flex justify-between items-center">
                  <h3 className="font-semibold">
                    Тесты пачки ({batchTests.length})
                  </h3>
                  <div className="flex items-center space-x-2">
                    <span className={`px-2 py-1 text-xs rounded-full ${getStatusColor(selectedBatch.status)}`}>
                      {getStatusIcon(selectedBatch.status)} {selectedBatch.status}
                    </span>
                  </div>
                </div>
              </div>

              {batchTests.length === 0 ? (
                <div className="p-8 text-center text-gray-500">
                  <div className="text-lg mb-2">📭 Нет тестов в этой пачке</div>
                </div>
              ) : (
                <div className="divide-y">
                  {batchTests.map(test => (
                    <TestCard
                      key={test.id}
                      test={test}
                      isSelected={selectedTests.has(test.id)}
                      onSelect={handleTestSelect}
                      onView={viewTestCode}
                    />
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Информация о пачке */}
          <div className="space-y-6">
            <div className="bg-white rounded-lg border shadow-sm p-4">
              <h3 className="font-semibold mb-3">📋 Информация о пачке</h3>
              <div className="space-y-3">
                <div>
                  <strong>Название:</strong>
                  <p className="text-sm text-gray-600 mt-1">{selectedBatch.name}</p>
                </div>
                <div>
                  <strong>Описание:</strong>
                  <p className="text-sm text-gray-600 mt-1">{selectedBatch.description}</p>
                </div>
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div>
                    <span className="text-gray-500">Тестов:</span>
                    <span className="font-medium ml-2">{selectedBatch.total_tests}</span>
                  </div>
                  <div>
                    <span className="text-gray-500">Покрытие:</span>
                    <span className="font-medium text-green-600 ml-2">
                      +{selectedBatch.coverage_improvement}%
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-500">Фреймворк:</span>
                    <span className="font-medium ml-2">{selectedBatch.framework}</span>
                  </div>
                  <div>
                    <span className="text-gray-500">AI:</span>
                    <span className="font-medium ml-2">{selectedBatch.ai_provider}</span>
                  </div>
                </div>
              </div>
            </div>

            <div className="bg-white rounded-lg border shadow-sm p-4">
              <h3 className="font-semibold mb-3">⚡ Быстрые действия</h3>
              <div className="space-y-2">
                <Button
                  onClick={() => setSelectedTests(new Set(batchTests.filter(t => t.priority === 'high').map(t => t.id)))}
                  variant="secondary"
                  size="small"
                  className="w-full justify-center"
                >
                  Выбрать высокоприоритетные
                </Button>
                <Button
                  onClick={() => setSelectedTests(new Set(batchTests.filter(t => t.test_type === 'unit').map(t => t.id)))}
                  variant="secondary"
                  size="small"
                  className="w-full justify-center"
                >
                  Выбрать unit тесты
                </Button>
                <Button
                  onClick={() => setShowPushModal(true)}
                  variant="primary"
                  size="small"
                  className="w-full justify-center"
                >
                  📤 Отправить в репозиторий
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

const getTestTypeColor = (type) => {
  const colors = {
    unit: 'bg-blue-100 text-blue-800',
    integration: 'bg-green-100 text-green-800',
    e2e: 'bg-purple-100 text-purple-800',
    api: 'bg-orange-100 text-orange-800'
  };
  return colors[type] || 'bg-gray-100 text-gray-800';
};

// Компонент TestCard
const TestCard = ({ test, isSelected, onSelect, onView }) => {
  const getTestTypeColor = (type) => {
    const colors = {
      unit: 'bg-blue-100 text-blue-800',
      integration: 'bg-green-100 text-green-800',
      e2e: 'bg-purple-100 text-purple-800',
      api: 'bg-orange-100 text-orange-800'
    };
    return colors[type] || 'bg-gray-100 text-gray-800';
  };

  const getPriorityColor = (priority) => {
    const colors = {
      high: 'bg-red-100 text-red-800',
      medium: 'bg-yellow-100 text-yellow-800',
      low: 'bg-green-100 text-green-800'
    };
    return colors[priority] || 'bg-gray-100 text-gray-800';
  };

  return (
    <div className="p-4 hover:bg-gray-50 transition-colors">
      <div className="flex items-start space-x-3">
        <input
          type="checkbox"
          checked={isSelected}
          onChange={() => onSelect(test.id)}
          className="mt-1 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
        />
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center space-x-2">
              <h4 className="font-medium text-gray-900 truncate">
                {test.name}
              </h4>
              <span className={`px-2 py-1 text-xs rounded-full ${getTestTypeColor(test.test_type)}`}>
                {test.test_type}
              </span>
              <span className={`px-2 py-1 text-xs rounded-full ${getPriorityColor(test.priority)}`}>
                {test.priority}
              </span>
            </div>
            <span className="text-sm text-gray-500">
              {test.coverage_estimate}% coverage
            </span>
          </div>

          <div className="text-sm text-gray-600 mb-2">
            <div>📁 {test.file_path}</div>
            <div>🎯 Целевой файл: {test.target_file}</div>
            <div>⚙️ Фреймворк: {test.framework} • AI: {test.ai_provider}</div>
          </div>

          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-500">
              Создан: {new Date(test.created_at).toLocaleDateString()}
            </span>
            <div className="flex space-x-2">
              <Button
                onClick={() => onView(test.id)}
                variant="primary"
                size="small"
              >
                👁️ Просмотр кода
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default GeneratedTestsView;