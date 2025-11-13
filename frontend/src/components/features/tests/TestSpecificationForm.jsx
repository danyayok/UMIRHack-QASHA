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
    generate_from_spec: true
  });
  const [previewData, setPreviewData] = useState(null);
  const [loading, setLoading] = useState(false);

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

      setPreviewData(mockPreview);
      setLoading(false);
    }, 1500);
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
      preview: previewData
    };

    console.log('Данные для генерации тестов из спецификации:', specificationData);
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

  return (
    <div className="bg-white rounded-lg border shadow-sm p-6">
      <h3 className="text-xl font-semibold mb-6">📋 Генерация тестов из спецификации</h3>

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
              {uploadedFile ? uploadedFile.name : 'Загрузите файл со спецификацией тестов'}
            </div>
            <div className="text-sm text-gray-500 mb-4">
              Поддерживаемые форматы: Excel (.xlsx, .xls), Word (.doc, .docx), TXT
            </div>
            <Button variant="secondary">
              {uploadedFile ? 'Заменить файл' : 'Выбрать файл'}
            </Button>
          </label>
        </div>

        {/* Настройки парсинга */}
        {uploadedFile && (
          <div className="space-y-4">
            <h4 className="font-medium text-gray-900 border-b pb-2">Настройки парсинга</h4>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
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
                      Название листа (опционально)
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

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Колонка с ожидаемыми результатами
                    </label>
                    <input
                      type="text"
                      value={parsingConfig.expected_results_column}
                      onChange={handleConfigChange('expected_results_column')}
                      placeholder="B"
                      className="w-full p-2 border border-gray-300 rounded focus:ring-blue-500 focus:border-blue-500"
                    />
                  </div>
                </>
              )}

              <div className="md:col-span-2 space-y-3">
                <label className="flex items-center space-x-3">
                  <input
                    type="checkbox"
                    checked={parsingConfig.parse_comments}
                    onChange={handleConfigChange('parse_comments')}
                    className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                  />
                  <span className="text-sm text-gray-700">
                    <div className="font-medium">Извлекать комментарии и примечания</div>
                    <div className="text-gray-500">Использовать дополнительные заметки из документа</div>
                  </span>
                </label>

                <label className="flex items-center space-x-3">
                  <input
                    type="checkbox"
                    checked={parsingConfig.generate_from_spec}
                    onChange={handleConfigChange('generate_from_spec')}
                    className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                  />
                  <span className="text-sm text-gray-700">
                    <div className="font-medium">Генерировать тесты на основе спецификации</div>
                    <div className="text-gray-500">Создать автоматические тесты по описанию из документа</div>
                  </span>
                </label>
              </div>
            </div>

            {/* Предпросмотр данных */}
            {previewData && !loading && (
              <div className="border-t pt-4">
                <h5 className="font-medium text-gray-700 mb-3">Предпросмотр данных</h5>
                <div className="bg-gray-50 rounded-lg p-4">
                  <div className="grid grid-cols-2 gap-4 mb-4 text-sm">
                    <div>
                      <span className="font-medium">Файл:</span> {previewData.fileName}
                    </div>
                    <div>
                      <span className="font-medium">Размер:</span> {previewData.fileSize}
                    </div>
                    <div>
                      <span className="font-medium">Обнаружено колонок:</span> {previewData.detectedColumns.length}
                    </div>
                    <div>
                      <span className="font-medium">Примерное количество тестов:</span> {previewData.estimatedTestCases}
                    </div>
                  </div>

                  <div className="text-sm">
                    <div className="font-medium mb-2">Пример данных:</div>
                    <div className="bg-white border rounded p-3 max-h-32 overflow-y-auto">
                      {previewData.sampleData.map((row, index) => (
                        <div key={index} className="flex space-x-2 text-xs font-mono">
                          {row.map((cell, cellIndex) => (
                            <span key={cellIndex} className="flex-1 truncate">
                              {cell}
                            </span>
                          ))}
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {loading && (
              <div className="text-center py-4">
                <div className="text-gray-500">Анализ документа...</div>
              </div>
            )}

            {/* Кнопка генерации */}
            <div className="flex justify-end pt-4">
              <Button
                onClick={handleGenerateFromSpec}
                loading={loading}
                variant="primary"
                size="large"
              >
                🚀 Сгенерировать тесты из спецификации
              </Button>
            </div>
          </div>
        )}

        {/* Инструкция */}
        {!uploadedFile && (
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <h5 className="font-medium text-blue-900 mb-2">Как подготовить спецификацию?</h5>
            <div className="text-sm text-blue-800 space-y-2">
              <p><strong>Для Excel:</strong> Создайте таблицу с колонками: ID теста, Описание, Ожидаемый результат, Приоритет</p>
              <p><strong>Для Word:</strong> Используйте структурированный список тест-кейсов с четкими описаниями</p>
              <p><strong>Для TXT:</strong> Каждый тест-кейс на новой строке, разделите описание и ожидаемый результат табуляцией</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default TestSpecificationForm;