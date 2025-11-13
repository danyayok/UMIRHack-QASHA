// src/components/features/analysis/AnalysisDetails.jsx
import React from 'react';

const AnalysisDetails = ({ analyses }) => {
  const latestAnalysis = analyses[0];

  const getTestMetrics = (analysis) => {
    if (!analysis?.result) return null;

    // Получаем данные из РЕАЛЬНОГО анализа
    const result = analysis.result;

    return {
      coverage: result.coverage_estimate || 0,
      totalTests: result.test_analysis?.test_files_count || 0,
      testFiles: result.test_analysis?.test_files_count || 0,
      technologies: result.technologies || [],
      frameworks: result.test_analysis?.test_frameworks || [],
      // Дополнительные метрики из реального анализа
      totalFiles: result.file_structure_summary?.total_files || 0,
      codeFiles: result.file_structure_summary?.code_files || 0,
      hasTests: result.test_analysis?.has_tests || false
    };
  };

  const metrics = getTestMetrics(latestAnalysis);

  // Если нет данных, показываем сообщение
  if (!latestAnalysis || !latestAnalysis.result) {
    return (
      <div className="p-4 bg-white rounded shadow space-y-6">
        <h3 className="text-xl font-semibold">Эффективность тестов</h3>
        <div className="text-center py-12 bg-slate-50 rounded border">
          <div className="text-slate-500 text-lg mb-4">
            Запустите анализ для получения данных о тестах
          </div>
          <div className="text-sm text-slate-400">
            После анализа здесь появятся метрики покрытия и статистика тестов
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="p-4 bg-white rounded shadow space-y-6">
      <h3 className="text-xl font-semibold">Эффективность тестов</h3>

      <div className="space-y-6">
        {/* Статус анализа */}
        <div className="bg-slate-50 p-4 rounded border">
          <h4 className="font-medium mb-2">Статус анализа</h4>
          <div className="flex items-center space-x-4">
            <span className={`px-3 py-1 rounded-full text-sm font-medium ${
              latestAnalysis.status === 'completed' ? 'bg-green-100 text-green-800' :
              latestAnalysis.status === 'running' ? 'bg-blue-100 text-blue-800' :
              'bg-gray-100 text-gray-800'
            }`}>
              {latestAnalysis.status}
            </span>
            <span className="text-sm text-slate-500">
              {new Date(latestAnalysis.created_at).toLocaleString()}
            </span>
          </div>
        </div>

        {/* Прогресс бар и метрики */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="space-y-4">
            <h4 className="font-medium">Прогресс тестирования</h4>

            {/* Прогресс покрытия */}
            <div>
              <div className="flex justify-between mb-1">
                <span className="text-sm font-medium">Покрытие кода</span>
                <span className="text-sm font-bold text-blue-600">{metrics.coverage}%</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-3">
                <div
                  className="bg-green-600 h-3 rounded-full transition-all duration-1000 ease-out"
                  style={{ width: `${metrics.coverage}%` }}
                ></div>
              </div>
              <div className="flex justify-between text-xs text-gray-500 mt-1">
                <span>0%</span>
                <span>100%</span>
              </div>
            </div>

            {/* Прогресс тестовых файлов */}
            <div>
              <div className="flex justify-between mb-1">
                <span className="text-sm font-medium">Тестовые файлы</span>
                <span className="text-sm font-bold text-blue-600">
                  {metrics.testFiles} / {metrics.totalFiles}
                </span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-3">
                <div
                  className="bg-blue-600 h-3 rounded-full transition-all duration-1000 ease-out"
                  style={{ width: `${Math.min(100, (metrics.testFiles / metrics.totalFiles) * 100)}%` }}
                ></div>
              </div>
              <div className="flex justify-between text-xs text-gray-500 mt-1">
                <span>0</span>
                <span>{metrics.totalFiles}</span>
              </div>
            </div>
          </div>

          {/* Статистика */}
          <div className="grid grid-cols-2 gap-4">
            <div className="p-4 bg-green-50 rounded-lg text-center border border-green-200">
              <div className="text-2xl font-bold text-green-700">{metrics.coverage}%</div>
              <div className="text-sm text-green-600 font-medium">Coverage</div>
            </div>
            <div className="p-4 bg-blue-50 rounded-lg text-center border border-blue-200">
              <div className="text-2xl font-bold text-blue-700">{metrics.testFiles}</div>
              <div className="text-sm text-blue-600 font-medium">Test Files</div>
            </div>
            <div className="p-4 bg-purple-50 rounded-lg text-center border border-purple-200">
              <div className="text-2xl font-bold text-purple-700">{metrics.totalFiles}</div>
              <div className="text-sm text-purple-600 font-medium">Total Files</div>
            </div>
            <div className="p-4 bg-orange-50 rounded-lg text-center border border-orange-200">
              <div className="text-2xl font-bold text-orange-700">{metrics.technologies.length}</div>
              <div className="text-sm text-orange-600 font-medium">Technologies</div>
            </div>
          </div>
        </div>

        {/* Детали анализа */}
        <div className="bg-slate-50 p-4 rounded border">
          <h4 className="font-medium mb-3">Детали анализа</h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
            <div>
              <h5 className="font-medium text-slate-700 mb-2">Технологии</h5>
              <div className="flex flex-wrap gap-1">
                {metrics.technologies.map((tech, index) => (
                  <span key={index} className="px-2 py-1 bg-white rounded border text-slate-600">
                    {tech}
                  </span>
                ))}
                {metrics.technologies.length === 0 && (
                  <span className="text-slate-400">Не обнаружено</span>
                )}
              </div>
            </div>
            <div>
              <h5 className="font-medium text-slate-700 mb-2">Фреймворки тестирования</h5>
              <div className="flex flex-wrap gap-1">
                {metrics.frameworks.map((fw, index) => (
                  <span key={index} className="px-2 py-1 bg-white rounded border text-slate-600">
                    {fw}
                  </span>
                ))}
                {metrics.frameworks.length === 0 && (
                  <span className="text-slate-400">Не обнаружено</span>
                )}
              </div>
            </div>
          </div>

          {/* Дополнительная информация */}
          <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div className="text-center p-2 bg-white rounded border">
              <div className="font-medium text-slate-700">{metrics.codeFiles}</div>
              <div className="text-slate-500">Файлов кода</div>
            </div>
            <div className="text-center p-2 bg-white rounded border">
              <div className="font-medium text-slate-700">{metrics.hasTests ? 'Да' : 'Нет'}</div>
              <div className="text-slate-500">Тесты найдены</div>
            </div>
            <div className="text-center p-2 bg-white rounded border">
              <div className="font-medium text-slate-700">{metrics.frameworks.length}</div>
              <div className="text-slate-500">Фреймворков</div>
            </div>
            <div className="text-center p-2 bg-white rounded border">
              <div className="font-medium text-slate-700">
                {latestAnalysis.result.file_structure_summary?.total_lines || 0}
              </div>
              <div className="text-slate-500">Строк кода</div>
            </div>
          </div>
        </div>

        {/* Полные результаты */}
        <div className="bg-white p-4 rounded border">
          <h4 className="font-medium mb-3">Полные результаты анализа</h4>
          <pre className="text-sm text-slate-700 whitespace-pre-wrap bg-slate-50 p-3 rounded border max-h-80 overflow-y-auto">
            {JSON.stringify(latestAnalysis.result, null, 2)}
          </pre>
        </div>
      </div>
    </div>
  );
};

export default AnalysisDetails;