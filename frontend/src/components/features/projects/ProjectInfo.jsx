// src/components/features/projects/ProjectInfo.jsx
import React, { useState, useEffect } from 'react';
import { projectsAPI } from '../../../services/api';

const ProjectInfo = ({ project }) => {
  const [latestAnalysis, setLatestAnalysis] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadLatestAnalysis();
  }, [project.id]);

  const loadLatestAnalysis = async () => {
    try {
      const analysis = await projectsAPI.getLatestAnalysis(project.id);
      setLatestAnalysis(analysis);
    } catch (error) {
      console.error('Ошибка загрузки анализа:', error);
    } finally {
      setLoading(false);
    }
  };

  const analysisResult = latestAnalysis?.result;

  if (loading) {
    return (
      <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
        <h4 className="font-medium text-gray-900 mb-3">Информация о проекте</h4>
        <div className="text-center py-4 text-gray-500">
          Загрузка данных...
        </div>
      </div>
    );
  }

  if (!analysisResult) {
    return (
      <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
        <h4 className="font-medium text-gray-900 mb-3">Информация о проекте</h4>
        <div className="text-center py-4 text-gray-500">
          {latestAnalysis ? (
            <div>
              <p>Анализ выполняется...</p>
              <p className="text-sm">Статус: {latestAnalysis.status}</p>
              {latestAnalysis.error_message && (
                <p className="text-sm text-red-600">Ошибка: {latestAnalysis.error_message}</p>
              )}
            </div>
          ) : (
            <div>
              <p>Запустите анализ проекта для получения информации</p>
              <button
                onClick={loadLatestAnalysis}
                className="mt-2 px-3 py-1 bg-blue-600 text-white rounded text-sm hover:bg-blue-700"
              >
                Обновить
              </button>
            </div>
          )}
        </div>
      </div>
    );
  }

  // Безопасное извлечение данных
  const getTechnologies = () => {
    return analysisResult.technologies?.join(', ') || 'Технологии не обнаружены';
  };

  const getFrameworks = () => {
    return analysisResult.frameworks?.join(', ') || 'Фреймворки не обнаружены';
  };

  const getCoverage = () => {
    return analysisResult.coverage_estimate || project.coverage || 0;
  };

  const getFileStats = () => {
    if (analysisResult.file_structure_summary) {
      return analysisResult.file_structure_summary;
    }
    if (analysisResult.metrics) {
      return analysisResult.metrics;
    }
    return { total_files: 0, code_files: 0, test_files: 0, total_lines: 0 };
  };

  const getTestAnalysis = () => {
    if (analysisResult.test_analysis) {
      return analysisResult.test_analysis;
    }
    return { has_tests: false, test_frameworks: [], test_files_count: 0 };
  };

  const fileStats = getFileStats();
  const testAnalysis = getTestAnalysis();

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4">
      <div className="flex justify-between items-center mb-3">
        <h4 className="font-medium text-gray-900">📊 Информация о проекте</h4>
        <button
          onClick={loadLatestAnalysis}
          className="text-xs bg-gray-100 hover:bg-gray-200 px-2 py-1 rounded"
        >
          🔄
        </button>
      </div>

      <div className="space-y-4">
        {/* Основная информация о проекте */}
        <div className="flex justify-between items-start">
          <div>
            <div className="font-medium text-gray-900">{project.name}</div>
            {project.description && (
              <div className="text-sm text-gray-600 mt-1">{project.description}</div>
            )}
          </div>
          {project.repo_url && (
            <span className="text-xs bg-blue-100 text-blue-800 px-2 py-1 rounded">
              GitHub
            </span>
          )}
        </div>

        {/* Детали анализа */}
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="font-medium text-gray-700">Технологии:</span>
              <div className="text-gray-900 mt-1">{getTechnologies()}</div>
            </div>
            <div>
              <span className="font-medium text-gray-700">Фреймворки:</span>
              <div className="text-gray-900 mt-1">{getFrameworks()}</div>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="font-medium text-gray-700">Покрытие тестами:</span>
              <div className="text-gray-900 mt-1">{getCoverage()}%</div>
            </div>
            <div>
              <span className="font-medium text-gray-700">Статус тестов:</span>
              <div className="text-gray-900 mt-1">
                {testAnalysis.has_tests ? '✅ Обнаружены' : '❌ Не обнаружены'}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="font-medium text-gray-700">Файлов кода:</span>
              <div className="text-gray-900 mt-1">{fileStats.code_files || 0}</div>
            </div>
            <div>
              <span className="font-medium text-gray-700">Тестовых файлов:</span>
              <div className="text-gray-900 mt-1">{testAnalysis.test_files_count || 0}</div>
            </div>
          </div>

          {testAnalysis.test_frameworks && testAnalysis.test_frameworks.length > 0 && (
            <div className="text-sm">
              <span className="font-medium text-gray-700">Фреймворки тестирования:</span>
              <div className="text-gray-900 mt-1 flex flex-wrap gap-1">
                {testAnalysis.test_frameworks.map((framework, index) => (
                  <span key={index} className="bg-gray-100 px-2 py-1 rounded text-xs">
                    {framework}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Быстрая статистика */}
        <div className="grid grid-cols-4 gap-2 text-xs">
          <div className="text-center p-2 bg-green-50 rounded border border-green-200">
            <div className="font-bold text-green-700 text-sm">{getCoverage()}%</div>
            <div className="text-green-600">Покрытие</div>
          </div>
          <div className="text-center p-2 bg-blue-50 rounded border border-blue-200">
            <div className="font-bold text-blue-700 text-sm">{fileStats.code_files || 0}</div>
            <div className="text-blue-600">Файлов кода</div>
          </div>
          <div className="text-center p-2 bg-purple-50 rounded border border-purple-200">
            <div className="font-bold text-purple-700 text-sm">{testAnalysis.test_files_count || 0}</div>
            <div className="text-purple-600">Тестов</div>
          </div>
          <div className="text-center p-2 bg-orange-50 rounded border border-orange-200">
            <div className="font-bold text-orange-700 text-sm">{analysisResult.technologies?.length || 0}</div>
            <div className="text-orange-600">Технологий</div>
          </div>
        </div>

        {/* Статус анализа */}
        {latestAnalysis && (
          <div className="text-xs text-gray-500 border-t pt-2">
            <div className="flex justify-between">
              <span>Статус анализа:</span>
              <span className={`font-medium ${
                latestAnalysis.status === 'completed' ? 'text-green-600' :
                latestAnalysis.status === 'failed' ? 'text-red-600' :
                'text-blue-600'
              }`}>
                {latestAnalysis.status}
              </span>
            </div>
            <div className="flex justify-between mt-1">
              <span>Время анализа:</span>
              <span>{new Date(latestAnalysis.created_at).toLocaleString()}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default ProjectInfo;