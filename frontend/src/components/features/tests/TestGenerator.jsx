// src/components/features/tests/TestGenerator.jsx
import React, { useState, useEffect } from 'react';
import { Button } from '../../ui';
import TestSpecificationForm from './TestSpecificationForm';
import ProjectInfo from '../projects/ProjectInfo';
import CICDForm from './CICDForm';
import { projectsAPI, testsAPI } from '../../../services/api';

const TestGenerator = ({ project, testResults, onRunTests }) => {
  const [activeMode, setActiveMode] = useState('tests');
  const [config, setConfig] = useState({
    framework: 'auto',
    coverage_target: 80,
    generate_unit_tests: true,
    generate_integration_tests: true,
    generate_e2e_tests: false,
    include_comments: true,
    generate_documentation: false,
    documentation_format: 'txt',
    test_pattern: 'standard',
    test_directory: '',
    custom_test_path: false
  });

  const [generating, setGenerating] = useState(false);
  const [generatedTests, setGeneratedTests] = useState([]);
  const [hasHtmlFiles, setHasHtmlFiles] = useState(false);

  // Проверяем наличие HTML файлов в проекте
  useEffect(() => {
  const loadAnalysisData = async () => {
    try {
      const analysis = await projectsAPI.getLatestAnalysis(project.id);
      if (analysis?.result) {
        const result = analysis.result;

        // Проверяем технологии
        const hasHtmlTech = result.technologies?.some(tech =>
          tech.toLowerCase().includes('html')
        );

        // Проверяем структуру файлов (рекурсивно)
        const hasHtmlFiles = checkFileStructure(result.file_structure || {});

        // Проверяем фреймворки
        const hasWebFrameworks = result.frameworks?.some(fw =>
          ['react', 'vue', 'angular', 'django', 'flask', 'express']
            .includes(fw.toLowerCase())
        );

        setHasHtmlFiles(hasHtmlTech || hasHtmlFiles || hasWebFrameworks);
      }
    } catch (error) {
      console.error('Ошибка загрузки анализа:', error);
      setHasHtmlFiles(false);
    }
  };

  loadAnalysisData();
}, [project.id]);
const checkFileStructure = (structure) => {
  for (const key in structure) {
    if (key.toLowerCase().endsWith('.html') || key.toLowerCase().endsWith('.htm')) {
      return true;
    }
    if (typeof structure[key] === 'object') {
      if (checkFileStructure(structure[key])) return true;
    }
  }
  return false;
};

  const handleConfigChange = (key) => (e) => {
    const value = e.target.type === 'checkbox' ? e.target.checked : e.target.value;
    setConfig(prev => ({ ...prev, [key]: value }));
  };

  const getFrameworkOptions = () => {
    const tech = project.latest_analysis?.result?.technologies || [];

    const frameworks = {
      python: ['pytest', 'unittest', 'nose'],
      javascript: ['jest', 'mocha', 'jasmine', 'cypress', 'playwright'],
      java: ['junit', 'testng', 'selenium'],
      html: ['cypress', 'playwright', 'selenium']
    };

    let options = ['auto'];

    tech.forEach(technology => {
      if (frameworks[technology]) {
        options = [...options, ...frameworks[technology]];
      }
    });

    return [...new Set(options)];
  };

  const handleGenerateTests = async () => {
    setGenerating(true);

    try {
      const result = await testsAPI.generateTests(project.id, config);

      if (result.status === 'success') {
        setGeneratedTests(result.tests);
        alert(`✅ Сгенерировано ${result.generated_tests} тестов!`);
      }
    } catch (error) {
      console.error('Generation error:', error);
      alert('❌ Ошибка генерации тестов');
    } finally {
      setGenerating(false);
    }
  };

const getTestTypesDescription = () => {
  const types = [];
  if (config.generate_unit_tests) types.push('Unit');
  if (config.generate_integration_tests) types.push('Интеграционные');
  if (config.generate_e2e_tests && hasHtmlFiles) types.push('E2E');
  return types.length > 0 ? types.join(', ') : 'Не выбраны';
};

  const getEstimatedTime = () => {
    let time = 0;
    if (config.generate_unit_tests) time += 2;
    if (config.generate_integration_tests) time += 3;
    if (config.generate_e2e_tests) time += 5;
    if (config.generate_documentation) time += 1;

    return time > 0 ? `~${time} минут` : 'Менее 1 минуты';
  };

  // Быстрые пресеты
  const applyPreset = (preset) => {
    switch (preset) {
      case 'standard':
        setConfig({
          framework: 'auto',
          coverage_target: 70,
          generate_unit_tests: true,
          generate_integration_tests: true,
          generate_e2e_tests: hasHtmlFiles,
          include_comments: true,
          generate_documentation: false,
          documentation_format: 'txt',
          test_pattern: 'standard',
          test_directory: '',
          custom_test_path: false
        });
        break;
      case 'comprehensive':
        setConfig({
          framework: 'auto',
          coverage_target: 85,
          generate_unit_tests: true,
          generate_integration_tests: true,
          generate_e2e_tests: hasHtmlFiles,
          include_comments: true,
          generate_documentation: true,
          documentation_format: 'doc',
          test_pattern: 'comprehensive',
          test_directory: '',
          custom_test_path: false
        });
        break;
      case 'minimal':
        setConfig({
          framework: 'auto',
          coverage_target: 50,
          generate_unit_tests: true,
          generate_integration_tests: false,
          generate_e2e_tests: false,
          include_comments: false,
          generate_documentation: false,
          documentation_format: 'txt',
          test_pattern: 'minimal',
          test_directory: '',
          custom_test_path: false
        });
        break;
      default:
        break;
    }
  };

  return (
    <div className="space-y-6">
      {/* Переключатель режимов */}
      <div className="bg-white rounded-lg border shadow-sm p-6">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-xl font-semibold">Генератор</h3>
            <p className="text-gray-600 text-sm">
              Выберите что вы хотите сгенерировать для проекта
            </p>
          </div>

          {/* Переключатель */}
          <div className="flex bg-gray-100 rounded-lg p-1">
            <button
              onClick={() => setActiveMode('tests')}
              className={`px-6 py-2 rounded-md font-medium text-sm transition-all ${
                activeMode === 'tests'
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              🧪 Тесты
            </button>
            <button
              onClick={() => setActiveMode('cicd')}
              className={`px-6 py-2 rounded-md font-medium text-sm transition-all ${
                activeMode === 'cicd'
                  ? 'bg-green-600 text-white shadow-sm'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              🚀 CI/CD
            </button>
          </div>
        </div>
      </div>

      {/* Контент в зависимости от выбранного режима */}
      {activeMode === 'tests' ? (
        /* Режим генерации тестов */
        <div className="space-y-6">
          {/* Основная форма генерации тестов */}
          <div className="bg-white rounded-lg border shadow-sm p-6">
            <h3 className="text-xl font-semibold mb-6">🧪 Генератор тестов</h3>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
              {/* Левая колонка - Настройки генерации */}
              <div className="space-y-6">
                <h4 className="font-medium text-gray-900 border-b pb-2">Настройки генерации</h4>

                {/* Фреймворк тестирования */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Фреймворк тестирования
                  </label>
                  <select
                    value={config.framework}
                    onChange={handleConfigChange('framework')}
                    className="w-full p-2 border border-gray-300 rounded focus:ring-blue-500 focus:border-blue-500"
                  >
                    {getFrameworkOptions().map(framework => (
                      <option key={framework} value={framework}>
                        {framework === 'auto' ? 'Автоопределение' : framework}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Целевое покрытие */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Целевое покрытие ({config.coverage_target}%)
                  </label>
                  <input
                    type="range"
                    min="10"
                    max="95"
                    step="5"
                    value={config.coverage_target}
                    onChange={handleConfigChange('coverage_target')}
                    className="w-full"
                  />
                  <div className="flex justify-between text-xs text-gray-500 mt-1">
                    <span>10% (минимальное)</span>
                    <span>95% (максимальное)</span>
                  </div>
                </div>

                {/* Шаблон тестов */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Шаблон тестов
                  </label>
                  <select
                    value={config.test_pattern}
                    onChange={handleConfigChange('test_pattern')}
                    className="w-full p-2 border border-gray-300 rounded focus:ring-blue-500 focus:border-blue-500"
                  >
                    <option value="standard">Стандартный (баланс качества и скорости)</option>
                    <option value="comprehensive">Полный охват (максимальное покрытие)</option>
                    <option value="minimal">Минимальный (только критичные тесты)</option>
                    <option value="behavior">BDD стиль (поведенческие тесты)</option>
                  </select>
                </div>

                {/* Типы тестов */}
                <div className="space-y-3">
                  <h5 className="font-medium text-gray-700">Типы тестов</h5>

                  <label className="flex items-center space-x-3">
                    <input
                      type="checkbox"
                      checked={config.generate_unit_tests}
                      onChange={handleConfigChange('generate_unit_tests')}
                      className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    />
                    <span className="text-sm text-gray-700">
                      <div className="font-medium">Unit-тесты</div>
                      <div className="text-gray-500">Тестирование отдельных функций и методов</div>
                    </span>
                  </label>

                  <label className="flex items-center space-x-3">
                    <input
                      type="checkbox"
                      checked={config.generate_integration_tests}
                      onChange={handleConfigChange('generate_integration_tests')}
                      className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    />
                    <span className="text-sm text-gray-700">
                      <div className="font-medium">Интеграционные тесты</div>
                      <div className="text-gray-500">Тестирование взаимодействия компонентов</div>
                    </span>
                  </label>

                  {/* E2E тесты - с улучшенным отображением */}
                    <div className={`space-y-3 ${hasHtmlFiles ? 'opacity-100' : 'opacity-60'}`}>
                      <label className={`flex items-center space-x-3 ${!hasHtmlFiles && 'cursor-not-allowed'}`}>
                        <input
                          type="checkbox"
                          checked={config.generate_e2e_tests}
                          onChange={handleConfigChange('generate_e2e_tests')}
                          disabled={!hasHtmlFiles}
                          className="rounded border-gray-300 text-blue-600 focus:ring-blue-500 disabled:opacity-50"
                        />
                        <span className="text-sm text-gray-700">
                          <div className="font-medium flex items-center">
                            E2E тесты
                            {!hasHtmlFiles && (
                              <span className="ml-2 text-xs bg-gray-100 text-gray-600 px-2 py-1 rounded">
                                Недоступно
                              </span>
                            )}
                          </div>
                          <div className="text-gray-500">
                            End-to-end тестирование веб-интерфейсов
                            {!hasHtmlFiles && (
                              <span className="text-orange-600 text-xs block mt-1">
                                ⚠️ Для E2E тестов нужен веб-проект с HTML файлами
                              </span>
                            )}
                          </div>
                        </span>
                      </label>
                    </div>

                  <label className="flex items-center space-x-3">
                    <input
                      type="checkbox"
                      checked={config.include_comments}
                      onChange={handleConfigChange('include_comments')}
                      className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    />
                    <span className="text-sm text-gray-700">
                      <div className="font-medium">Добавлять комментарии</div>
                      <div className="text-gray-500">Пояснения к тестовым случаям</div>
                    </span>
                  </label>
                </div>

                {/* Документация */}
                <div className="space-y-3 border-t pt-4">
                  <label className="flex items-center space-x-3">
                    <input
                      type="checkbox"
                      checked={config.generate_documentation}
                      onChange={handleConfigChange('generate_documentation')}
                      className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    />
                    <span className="text-sm text-gray-700">
                      <div className="font-medium">Генерировать текстовую документацию</div>
                      <div className="text-gray-500">Создать документацию по тестам</div>
                    </span>
                  </label>

                  {config.generate_documentation && (
                    <div className="ml-6">
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Формат документации
                      </label>
                      <div className="grid grid-cols-2 gap-2">
                        {['txt', 'doc', 'excel'].map(format => (
                          <label key={format} className="flex items-center space-x-2">
                            <input
                              type="radio"
                              name="documentation_format"
                              value={format}
                              checked={config.documentation_format === format}
                              onChange={handleConfigChange('documentation_format')}
                              className="text-blue-600 focus:ring-blue-500"
                            />
                            <span className="text-sm text-gray-700 capitalize">
                              {format === 'txt' ? 'TXT' : format === 'doc' ? 'DOC' : 'Excel'}
                            </span>
                          </label>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                {/* Расположение тестов */}
                <div className="space-y-3 border-t pt-4">
                  <h5 className="font-medium text-gray-700">Расположение тестов</h5>

                  <label className="flex items-center space-x-3">
                    <input
                      type="checkbox"
                      checked={config.custom_test_path}
                      onChange={handleConfigChange('custom_test_path')}
                      className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    />
                    <span className="text-sm text-gray-700">
                      <div className="font-medium">Указать кастомный путь для тестов</div>
                      <div className="text-gray-500">Задать конкретную директорию в репозитории</div>
                    </span>
                  </label>

                  {config.custom_test_path && (
                    <div className="ml-6">
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Путь к директории с тестами
                      </label>
                      <input
                        type="text"
                        value={config.test_directory}
                        onChange={handleConfigChange('test_directory')}
                        placeholder="например: tests/ или src/test/"
                        className="w-full p-2 border border-gray-300 rounded focus:ring-blue-500 focus:border-blue-500 text-sm"
                      />
                      <p className="text-xs text-gray-500 mt-1">
                        Укажите относительный путь от корня репозитория
                      </p>
                    </div>
                  )}

                  {!config.custom_test_path && (
                    <div className="text-sm text-gray-600 bg-gray-50 p-2 rounded">
                      📁 Тесты будут размещены в стандартных директориях для {project.latest_analysis?.result?.technologies?.[0] || 'проекта'}
                    </div>
                  )}
                </div>
              </div>

              {/* Правая колонка - Предпросмотр и действия */}
              <div className="space-y-6">
                <h4 className="font-medium text-gray-900 border-b pb-2">Предпросмотр и действия</h4>

                {/* Карточка конфигурации */}
                <div className="bg-gradient-to-br from-blue-50 to-indigo-50 border border-blue-200 rounded-lg p-4">
                  <h4 className="font-medium text-blue-900 mb-3 flex items-center">
                    <span className="mr-2">⚙️</span>
                    Конфигурация генерации
                  </h4>
                  <div className="text-sm text-blue-800 space-y-2">
                    <div className="flex justify-between items-center">
                      <span>Фреймворк:</span>
                      <strong className="bg-white px-2 py-1 rounded border text-blue-700">
                        {config.framework === 'auto' ? 'Автоопределение' : config.framework}
                      </strong>
                    </div>
                    <div className="flex justify-between items-center">
                      <span>Покрытие:</span>
                      <strong className="bg-white px-2 py-1 rounded border text-blue-700">
                        {config.coverage_target}%
                      </strong>
                    </div>
                    <div className="flex justify-between items-start">
                      <span className="flex-shrink-0 mr-2">Типы тестов:</span>
                      <strong className="text-right bg-white px-2 py-1 rounded border text-blue-700 text-xs leading-tight">
                        {getTestTypesDescription()}
                      </strong>
                    </div>
                    <div className="flex justify-between items-center">
                      <span>Шаблон:</span>
                      <strong className="bg-white px-2 py-1 rounded border text-blue-700 capitalize">
                        {config.test_pattern}
                      </strong>
                    </div>
                    {config.generate_documentation && (
                      <div className="flex justify-between items-center">
                        <span>Документация:</span>
                        <strong className="bg-white px-2 py-1 rounded border text-blue-700 uppercase">
                          {config.documentation_format}
                        </strong>
                      </div>
                    )}
                    <div className="flex justify-between items-center border-t border-blue-200 pt-2 mt-2">
                      <span>Примерное время:</span>
                      <strong className="text-green-700">{getEstimatedTime()}</strong>
                    </div>
                  </div>
                </div>

                {/* Кнопки действий */}
                <div className="space-y-3">
                  <Button
                    onClick={handleGenerateTests}
                    loading={generating}
                    variant="primary"
                    size="large"
                    className="w-full"
                  >
                    🚀 Сгенерировать тесты
                  </Button>

                  <Button
                    onClick={onRunTests}
                    variant="secondary"
                    size="large"
                    className="w-full"
                  >
                    ▶️ Запустить существующие тесты
                  </Button>
                </div>

                {/* Список сгенерированных тестов */}
                {generatedTests.length > 0 && (
                  <div className="bg-white rounded border shadow p-4">
                    <h4 className="font-medium mb-3">Сгенерированные тесты</h4>
                    <div className="space-y-3 max-h-64 overflow-y-auto">
                      {generatedTests.map((test, index) => (
                        <div key={index} className="border rounded p-3">
                          <div className="flex justify-between items-start mb-2">
                            <div>
                              <div className="font-medium">{test.name}</div>
                              <div className="text-sm text-gray-500">{test.file} • {test.type}</div>
                            </div>
                            <span className="text-xs bg-blue-100 text-blue-800 px-2 py-1 rounded">
                              {test.framework}
                            </span>
                          </div>
                          <pre className="text-xs bg-gray-50 p-2 rounded overflow-x-auto">
                            {test.content}
                          </pre>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Информация о проекте */}
                <ProjectInfo project={project} />
              </div>
            </div>

            {/* Быстрый старт с улучшенными пресетами */}
            <div className="mt-8 border-t pt-6">
              <h4 className="font-medium text-gray-900 mb-4 flex items-center">
                <span className="mr-2">🚀</span>
                Быстрый старт
              </h4>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <button
                  onClick={() => applyPreset('standard')}
                  className="p-4 border-2 border-blue-200 rounded-lg hover:bg-blue-50 transition-all text-left group"
                >
                  <div className="font-medium text-blue-900 group-hover:text-blue-700">
                    🎯 Стандартный набор
                  </div>
                  <div className="text-sm text-blue-700 mt-1">
                    Базовые тесты + документация
                  </div>
                  <div className="text-xs text-blue-500 mt-2">
                    • Unit тесты ✓<br/>
                    • Интеграционные тесты ✓<br/>
                    • E2E тесты {hasHtmlFiles ? '✓' : '✗'}<br/>
                    • Документация ✗
                  </div>
                </button>

                <button
                  onClick={() => applyPreset('comprehensive')}
                  className="p-4 border-2 border-green-200 rounded-lg hover:bg-green-50 transition-all text-left group"
                >
                  <div className="font-medium text-green-900 group-hover:text-green-700">
                    🏆 Полный набор
                  </div>
                  <div className="text-sm text-green-700 mt-1">
                    Все типы тестов + DOC документация
                  </div>
                  <div className="text-xs text-green-500 mt-2">
                    • Unit тесты ✓<br/>
                    • Интеграционные тесты ✓<br/>
                    • E2E тесты {hasHtmlFiles ? '✓' : '✗'}<br/>
                    • Документация ✓
                  </div>
                </button>

                <button
                  onClick={() => applyPreset('minimal')}
                  className="p-4 border-2 border-orange-200 rounded-lg hover:bg-orange-50 transition-all text-left group"
                >
                  <div className="font-medium text-orange-900 group-hover:text-orange-700">
                    ⚡ Минимальный набор
                  </div>
                  <div className="text-sm text-orange-700 mt-1">
                    Только unit-тесты для быстрого старта
                  </div>
                  <div className="text-xs text-orange-500 mt-2">
                    • Unit тесты ✓<br/>
                    • Интеграционные тесты ✗<br/>
                    • E2E тесты ✗<br/>
                    • Документация ✗
                  </div>
                </button>
              </div>
            </div>
        </div>
          {/* Загрузка спецификации */}
          <div className="bg-gradient-to-r from-purple-50 to-blue-50 rounded-lg border border-purple-200 shadow-sm p-6">
            <TestSpecificationForm
              project={project}
              onSpecificationUpload={(specData) => {
                console.log('Спецификация для генерации тестов:', specData);
              }}
            />
          </div>
        </div>
      ) : (
        /* Режим генерации CI/CD */
        <CICDForm project={project} />
      )}
    </div>
  );
};

export default TestGenerator;