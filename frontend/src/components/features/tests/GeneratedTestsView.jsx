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
  const [selectedTest, setSelectedTest] = useState(null); // Для просмотра конкретного теста

  useEffect(() => {
    loadTestBatches();
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

  const loadBatchTests = async (batchId) => {
    try {
      setError(null);
      const batchData = await generatedTestsAPI.getTestBatch(project.id, batchId);
      console.log('🧪 Real batch tests:', batchData);

      if (batchData) {
        setSelectedBatch(batchData);
        // Код тестов уже содержится в batchData.tests[].content
        setBatchTests(batchData.tests || []);
        setViewMode('tests');
      }
    } catch (error) {
      console.error('Ошибка загрузки тестов пачки:', error);
      setError('Не удалось загрузить тесты пачки');
    }
  };

  // Просмотр конкретного теста - данные уже загружены!
  const viewTestCode = (testId) => {
    setSelectedTest(testId);
  };

  // Закрыть просмотр кода теста
  const closeTestCode = () => {
    setSelectedTest(null);
  };

  // Получить код теста из уже загруженных данных
  const getTestCode = (testId) => {
    const test = batchTests.find(t => t.id === testId);
    return test?.content || test?.code || '// Код теста не доступен';
  };

  // Получить объект теста по ID
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

  const handleSelectAllTests = () => {
    if (selectedTests.size === batchTests.length) {
      setSelectedTests(new Set());
    } else {
      setSelectedTests(new Set(batchTests.map(test => test.id)));
    }
  };

  const handlePushBatchToRepo = async (batchId) => {
    try {
      setPushLoading(true);
      setError(null);
      const result = await generatedTestsAPI.pushBatchToRepository(project.id, batchId);
      console.log('📤 Push result:', result);

      alert(`✅ ${result.message || 'Пачка тестов успешно отправлена в репозиторий!'}`);

      setTestBatches(prev => prev.map(batch =>
        batch.id === batchId ? { ...batch, status: 'pushed' } : batch
      ));
    } catch (error) {
      console.error('Ошибка отправки тестов:', error);
      setError('Ошибка отправки тестов: ' + error.message);
      alert('❌ Ошибка отправки тестов: ' + error.message);
    } finally {
      setPushLoading(false);
    }
  };

  const handlePushSelectedTests = async () => {
    if (selectedTests.size === 0) {
      alert('Выберите тесты для отправки в репозиторий');
      return;
    }

    try {
      setPushLoading(true);
      setError(null);
      const testIdsArray = Array.from(selectedTests);
      const result = await generatedTestsAPI.pushBatchToRepository(
        project.id,
        selectedBatch.id,
        testIdsArray
      );

      console.log('📤 Push selected result:', result);
      alert(`✅ ${result.message || `${selectedTests.size} тестов успешно отправлены в репозиторий!`}`);
      setSelectedTests(new Set());
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
              // Кнопки для режима просмотра кода теста
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
              // Кнопки для режима просмотра тестов
              <>
                <Button
                  onClick={handleSelectAllTests}
                  variant="secondary"
                  size="medium"
                >
                  {selectedTests.size === batchTests.length ? 'Снять выделение' : 'Выделить все'}
                </Button>
                <Button
                  onClick={handlePushSelectedTests}
                  loading={pushLoading}
                  disabled={selectedTests.size === 0}
                  variant="primary"
                  size="medium"
                >
                  📤 Отправить выбранные ({selectedTests.size})
                </Button>
                <Button
                  onClick={handleBackToBatches}
                  variant="secondary"
                  size="medium"
                >
                  ← Назад к пачкам
                </Button>
              </>
            ) : null}

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
                      className="p-6 hover:bg-gray-50 transition-colors cursor-pointer"
                      onClick={() => loadBatchTests(batch.id)}
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
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
              </div>
            </div>

            <div className="bg-white rounded-lg border shadow-sm p-4">
              <h3 className="font-semibold mb-3">🎯 Эффективность AI</h3>
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span>GigaChat:</span>
                  <span className="font-medium">
                    {testBatches.filter(b => b.ai_provider === 'giga').length} пачек
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span>g4f:</span>
                  <span className="font-medium">
                    {testBatches.filter(b => b.ai_provider === 'g4f').length} пачек
                  </span>
                </div>
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
                      onView={viewTestCode} // Передаем функцию просмотра
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
                  onClick={handlePushBatchToRepo}
                  variant="primary"
                  size="small"
                  className="w-full justify-center"
                >
                  📤 Отправить всю пачку
                </Button>
              </div>
            </div>

<div className="bg-white rounded-lg border shadow-sm p-4">
  <h3 className="font-semibold mb-3">📋 Документация E2E тестов</h3>
  <div className="space-y-3">
    <div className="text-sm text-gray-600 mb-3">
      Документация по end-to-end тестированию будет сгенерирована автоматически
    </div>

    <div className="grid grid-cols-1 gap-2">
      <Button
        onClick={() => alert('Функция в разработке')}
        variant="secondary"
        size="small"
        className="w-full justify-center"
      >
        📄 Просмотреть TXT документацию
      </Button>

      <Button
        onClick={() => alert('Функция в разработке')}
        variant="secondary"
        size="small"
        className="w-full justify-center"
      >
        📝 Просмотреть DOC документацию
      </Button>

      <Button
        onClick={() => alert('Функция в разработке')}
        variant="secondary"
        size="small"
        className="w-full justify-center"
      >
        📊 Просмотреть Excel отчет
      </Button>
    </div>

    <div className="border-t pt-3 mt-3">
      <div className="flex justify-between items-center text-xs text-gray-500">
        <span>Статус:</span>
        <span className="bg-yellow-100 text-yellow-800 px-2 py-1 rounded">В разработке</span>
      </div>
    </div>
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
// Обновленный компонент TestCard с кнопкой просмотра кода
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