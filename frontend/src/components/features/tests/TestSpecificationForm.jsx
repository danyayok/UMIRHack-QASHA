// src/components/features/tests/TestSpecificationForm.jsx
import React, { useState } from 'react';
import { Button } from '../../ui';

const TestSpecificationForm = ({ project, onSpecificationUpload }) => {
  const [uploadedFile, setUploadedFile] = useState(null);
  const [parsingConfig, setParsingConfig] = useState({
    document_type: 'excel',
    sheet_name: '',
    test_cases_column: 'A',
    expected_results_column: 'B',
    parse_comments: true,
    generate_from_spec: true,
    // Новые поля для генерации тест-кейсов
    generate_test_cases: true,
    test_case_format: 'excel',
    include_ui_interactions: true,
    test_case_template: 'standard'
  });
  const [previewData, setPreviewData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [sampleTestCases, setSampleTestCases] = useState([]);

  const handleFileUpload = (event) => {
    const file = event.target.files[0];
    if (!file) return;

    // Проверяем тип файла
    const allowedTypes = [
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      'application/vnd.ms-excel',
      'application/msword',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      'text/plain'
    ];

    if (!allowedTypes.includes(file.type)) {
      alert('Пожалуйста, загрузите файл в формате Excel (.xlsx, .xls), Word (.doc, .docx) или TXT');
      return;
    }

    setUploadedFile(file);

    // Определяем тип документа по расширению
    const fileExtension = file.name.split('.').pop().toLowerCase();
    let docType = 'excel';
    if (fileExtension === 'doc' || fileExtension === 'docx') docType = 'word';
    if (fileExtension === 'txt') docType = 'txt';

    setParsingConfig(prev => ({
      ...prev,
      document_type: docType
    }));

    // Имитируем предпросмотр данных
    simulatePreview(file, docType);
  };

  const simulatePreview = (file, docType) => {
    setLoading(true);

    // Имитация парсинга файла
    setTimeout(() => {
      const mockPreview = {
        fileName: file.name,
        fileType: docType,
        fileSize: (file.size / 1024).toFixed(2) + ' KB',
        detectedColumns: docType === 'excel' ? ['A', 'B', 'C', 'D'] : ['Заголовок', 'Содержание'],
        sampleData: docType === 'excel' ? [
          ['TC001', 'Логин с валидными данными', 'Успешный вход', 'Высокий'],
          ['TC002', 'Логин с невалидным паролем', 'Ошибка аутентификации', 'Высокий'],
          ['TC003', 'Восстановление пароля', 'Письмо отправлено', 'Средний']
        ] : [
          ['Тест-кейс 1: Авторизация пользователя', 'Проверить вход с корректными учетными данными'],
          ['Тест-кейс 2: Валидация формы', 'Проверить обязательные поля формы регистрации']
        ],
        estimatedTestCases: docType === 'excel' ? 15 : 8
      };

      // Генерируем примеры тест-кейсов на основе загруженного файла
      generateSampleTestCases(docType);

      setPreviewData(mockPreview);
      setLoading(false);
    }, 1500);
  };

  const generateSampleTestCases = (docType) => {
    // Примеры тест-кейсов которые будут сгенерированы нейросетью
    const samples = [
      {
        id: 'TC001',
        title: 'Авторизация пользователя',
        description: 'Проверка входа в систему с корректными учетными данными',
        steps: [
          'Открыть страницу логина',
          'Ввести валидный email в поле "Email"',
          'Ввести валидный пароль в поле "Пароль"',
          'Нажать кнопку "Войти"'
        ],
        expectedResults: [
          'Происходит перенаправление на главную страницу',
          'Отображается приветственное сообщение',
          'В хедере отображается имя пользователя'
        ],
        testData: {
          email: 'test@example.com',
          password: 'Password123'
        },
        priority: 'Высокий',
        type: 'Функциональный'
      },
      {
        id: 'TC002',
        title: 'Валидация формы регистрации',
        description: 'Проверка обязательных полей и валидации ввода',
        steps: [
          'Открыть страницу регистрации',
          'Оставить все поля пустыми',
          'Нажать кнопку "Зарегистрироваться"',
          'Проверить сообщения об ошибках'
        ],
        expectedResults: [
          'Отображаются сообщения об ошибках для обязательных полей',
          'Кнопка "Зарегистрироваться" неактивна до исправления ошибок',
          'Подсвечиваются поля с ошибками красным цветом'
        ],
        testData: {},
        priority: 'Высокий',
        type: 'Валидация'
      }
    ];

    setSampleTestCases(samples);
  };

  const handleConfigChange = (key) => (e) => {
    const value = e.target.type === 'checkbox' ? e.target.checked : e.target.value;
    setParsingConfig(prev => ({ ...prev, [key]: value }));
  };

  const handleGenerateFromSpec = () => {
    if (!uploadedFile) {
      alert('Пожалуйста, загрузите файл со спецификацией тестов');
      return;
    }

    const specificationData = {
      file: uploadedFile,
      config: parsingConfig,
      project_id: project.id,
      preview: previewData,
      sample_test_cases: sampleTestCases,
      // Инструкция для нейросети
      generation_instructions: {
        generate_test_cases: parsingConfig.generate_test_cases,
        test_case_format: parsingConfig.test_case_format,
        include_ui_interactions: parsingConfig.include_ui_interactions,
        template: parsingConfig.test_case_template
      }
    };

    console.log('Данные для генерации тестов и тест-кейсов:', specificationData);
    onSpecificationUpload?.(specificationData);

    alert(`Спецификация загружена! Будет сгенерировано ~${previewData?.estimatedTestCases} тестовых случаев.`);
  };

  const getDocumentTypeName = (type) => {
    const names = {
      'excel': 'Excel таблица',
      'word': 'Word документ',
      'txt': 'Текстовый файл'
    };
    return names[type] || type;
  };

  const downloadTestCaseTemplate = (format) => {
    let templateContent = '';
    let fileName = '';
    let mimeType = '';

    switch (format) {
      case 'excel':
        // Простой CSV как пример
        templateContent = 'ID Тест-кейса,Название,Описание,Шаги,Ожидаемый результат,Приоритет\nTC001,Пример тест-кейса,Описание тестового сценария,"Шаг 1: ...|Шаг 2: ...",Ожидаемый результат,Высокий';
        fileName = 'template_test_cases.csv';
        mimeType = 'text/csv';
        break;
      case 'doc':
        templateContent = 'Шаблон тест-кейса\n\nНазвание: [Название тест-кейса]\nОписание: [Описание]\nШаги:\n1. [Шаг 1]\n2. [Шаг 2]\nОжидаемый результат: [Результат]\nПриоритет: [Высокий/Средний/Низкий]';
        fileName = 'template_test_cases.txt';
        mimeType = 'text/plain';
        break;
      case 'txt':
        templateContent = 'TC001 - Авторизация пользователя\nОписание: Проверка входа в систему\nШаги:\n- Открыть страницу логина\n- Ввести email\n- Ввести пароль\n- Нажать "Войти"\nОжидаемый результат: Успешный вход в систему';
        fileName = 'template_test_cases.txt';
        mimeType = 'text/plain';
        break;
    }

    const blob = new Blob([templateContent], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = fileName;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="bg-white rounded-lg border shadow-sm p-6">
      <h3 className="text-xl font-semibold mb-6">📋 Генерация тестов и тест-кейсов из спецификации</h3>

      <div className="space-y-6">
        {/* Загрузка файла */}
        <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center">
          <input
            type="file"
            id="specification-file"
            accept=".xlsx,.xls,.doc,.docx,.txt"
            onChange={handleFileUpload}
            className="hidden"
          />
          <label htmlFor="specification-file" className="cursor-pointer">
            <div className="text-4xl mb-3">📄</div>
            <div className="font-medium text-gray-700 mb-2">
              {uploadedFile ? uploadedFile.name : 'Загрузите файл с примерами тест-кейсов'}
            </div>
            <div className="text-sm text-gray-500 mb-4">
              Поддерживаемые форматы: Excel (.xlsx, .xls), Word (.doc, .docx), TXT
            </div>
            <Button variant="secondary">
              {uploadedFile ? 'Заменить файл' : 'Выбрать файл'}
            </Button>
          </label>
        </div>

        {/* Настройки парсинга и генерации */}
        {uploadedFile && (
          <div className="space-y-4">
            <h4 className="font-medium text-gray-900 border-b pb-2">Настройки генерации</h4>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Базовые настройки */}
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Тип документа
                  </label>
                  <div className="p-2 bg-gray-100 rounded text-sm">
                    {getDocumentTypeName(parsingConfig.document_type)}
                  </div>
                </div>

                {parsingConfig.document_type === 'excel' && (
                  <>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Название листа
                      </label>
                      <input
                        type="text"
                        value={parsingConfig.sheet_name}
                        onChange={handleConfigChange('sheet_name')}
                        placeholder="Sheet1"
                        className="w-full p-2 border border-gray-300 rounded focus:ring-blue-500 focus:border-blue-500"
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Колонка с тест-кейсами
                      </label>
                      <input
                        type="text"
                        value={parsingConfig.test_cases_column}
                        onChange={handleConfigChange('test_cases_column')}
                        placeholder="A"
                        className="w-full p-2 border border-gray-300 rounded focus:ring-blue-500 focus:border-blue-500"
                      />
                    </div>
                  </>
                )}
              </div>

              {/* Настройки генерации тест-кейсов */}
              <div className="space-y-4">
                <label className="flex items-center space-x-3">
                  <input
                    type="checkbox"
                    checked={parsingConfig.generate_test_cases}
                    onChange={handleConfigChange('generate_test_cases')}
                    className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                  />
                  <span className="text-sm text-gray-700">
                    <div className="font-medium">Генерировать тест-кейсы</div>
                    <div className="text-gray-500">Создать документацию для ручного тестирования</div>
                  </span>
                </label>

                {parsingConfig.generate_test_cases && (
                  <>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Формат тест-кейсов
                      </label>
                      <select
                        value={parsingConfig.test_case_format}
                        onChange={handleConfigChange('test_case_format')}
                        className="w-full p-2 border border-gray-300 rounded focus:ring-blue-500 focus:border-blue-500"
                      >
                        <option value="excel">Excel таблица</option>
                        <option value="doc">Word документ</option>
                        <option value="txt">Текстовый файл</option>
                      </select>
                    </div>

                    <label className="flex items-center space-x-3">
                      <input
                        type="checkbox"
                        checked={parsingConfig.include_ui_interactions}
                        onChange={handleConfigChange('include_ui_interactions')}
                        className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                      />
                      <span className="text-sm text-gray-700">
                        Включать UI взаимодействия
                      </span>
                    </label>
                  </>
                )}
              </div>
            </div>

            {/* Предпросмотр сгенерированных тест-кейсов */}
            {sampleTestCases.length > 0 && (
              <div className="border-t pt-4">
                <h5 className="font-medium text-gray-700 mb-3">
                  Пример тест-кейсов которые будут сгенерированы:
                </h5>
                <div className="space-y-3">
                  {sampleTestCases.map((testCase, index) => (
                    <div key={index} className="bg-gray-50 rounded-lg p-4 border">
                      <div className="flex justify-between items-start mb-2">
                        <div>
                          <strong className="text-blue-700">{testCase.id}</strong>
                          <span className="ml-2 font-medium">{testCase.title}</span>
                        </div>
                        <span className={`px-2 py-1 text-xs rounded ${
                          testCase.priority === 'Высокий' ? 'bg-red-100 text-red-800' :
                          testCase.priority === 'Средний' ? 'bg-yellow-100 text-yellow-800' :
                          'bg-green-100 text-green-800'
                        }`}>
                          {testCase.priority}
                        </span>
                      </div>
                      <p className="text-sm text-gray-600 mb-3">{testCase.description}</p>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                        <div>
                          <strong>Шаги:</strong>
                          <ul className="list-disc list-inside mt-1 space-y-1">
                            {testCase.steps.map((step, stepIndex) => (
                              <li key={stepIndex} className="text-gray-700">{step}</li>
                            ))}
                          </ul>
                        </div>
                        <div>
                          <strong>Ожидаемые результаты:</strong>
                          <ul className="list-disc list-inside mt-1 space-y-1">
                            {testCase.expectedResults.map((result, resultIndex) => (
                              <li key={resultIndex} className="text-green-700">{result}</li>
                            ))}
                          </ul>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Кнопки действий */}
            <div className="flex justify-between items-center pt-4">
              <div className="space-x-2">
                <Button
                  onClick={() => downloadTestCaseTemplate('excel')}
                  variant="secondary"
                  size="small"
                >
                  📊 Скачать шаблон Excel
                </Button>
                <Button
                  onClick={() => downloadTestCaseTemplate('doc')}
                  variant="secondary"
                  size="small"
                >
                  📝 Скачать шаблон Word
                </Button>
              </div>

              <Button
                onClick={handleGenerateFromSpec}
                loading={loading}
                variant="primary"
                size="large"
              >
                🚀 Сгенерировать тесты и тест-кейсы
              </Button>
            </div>
          </div>
        )}

        {/* Инструкция */}
        {!uploadedFile && (
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <h5 className="font-medium text-blue-900 mb-2">Как подготовить спецификацию тест-кейсов?</h5>
            <div className="text-sm text-blue-800 space-y-2">
              <p><strong>Для E2E тестов укажите:</strong></p>
              <ul className="list-disc list-inside ml-4">
                <li>Последовательность действий пользователя</li>
                <li>Элементы интерфейса для взаимодействия</li>
                <li>Ожидаемые результаты после каждого действия</li>
                <li>Тестовые данные (логины, пароли, и т.д.)</li>
              </ul>
              <p className="mt-2">Нейросеть сгенерирует код автотестов и документацию тест-кейсов!</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default TestSpecificationForm;