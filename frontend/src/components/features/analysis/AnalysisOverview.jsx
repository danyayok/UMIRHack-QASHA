// src/components/features/analysis/AnalysisOverview.jsx
import React from 'react';

const AnalysisOverview = ({ project, analyses, onRefresh, onAnalyze }) => {
  const latestAnalysis = analyses[0];

  const formatAnalysisResult = (result) => {
    if (!result) return 'Нет данных анализа';

    // Новый формат (реальный анализ)
    if (result.file_structure_summary && result.test_analysis) {
      const {
        technologies = [],
        frameworks = [],
        file_structure_summary = {},
        test_analysis = {},
        coverage_estimate = 0,
        dependencies = {}
      } = result;

      const {
        total_files = 0,
        code_files = 0,
        test_files = 0,
        total_lines = 0,
        total_size_kb = 0
      } = file_structure_summary;

      const {
        has_tests = false,
        test_frameworks = [],
        test_files_count = 0,
        test_directories = []
      } = test_analysis;

      return `
🎯 РЕАЛЬНЫЙ АНАЛИЗ КОДА

🏗️ Технологии: ${technologies.join(', ') || 'не обнаружены'}
📊 Статистика проекта:
   • Всего файлов: ${total_files}
   • Файлов кода: ${code_files}
   • Тестовых файлов: ${test_files}
   • Строк кода: ${total_lines}
   • Размер: ${total_size_kb} KB

🧪 Анализ тестов:
   • Тесты найдены: ${has_tests ? '✅ Да' : '❌ Нет'}
   • Тестовых файлов: ${test_files_count}
   • Фреймворки: ${test_frameworks.join(', ') || 'не обнаружены'}
   • Тестовые директории: ${test_directories.join(', ') || 'не обнаружены'}

📈 Покрытие тестами: ${coverage_estimate}%

🏛️ Фреймворки: ${frameworks.join(', ') || 'не обнаружены'}

📦 Зависимости: ${Object.keys(dependencies).length > 0 ?
  Object.keys(dependencies).join(', ') :
  'не обнаружены'}
      `.trim();
    }

    // Старый формат
    if (result.technologies && Array.isArray(result.technologies)) {
      return `
📋 АНАЛИЗ ПРОЕКТА

🏗️ Технологии: ${result.technologies.join(', ')}
📁 Файлов: ${result.metrics?.total_files || 0}
🧪 Сгенерировано тестов: ${result.generated_tests?.total_generated || 0}
⚡ Фреймворки: ${result.test_frameworks?.join(', ') || 'не обнаружены'}
      `.trim();
    }

    return JSON.stringify(result, null, 2);
  };

  const getProgress = (analysis) => {
    const progressMap = {
      "pending": 0,
      "cloning": 25,
      "extracting": 25,
      "analyzing": 50,
      "generating": 75,
      "completed": 100,
      "failed": 0
    };
    return progressMap[analysis?.status] || 0;
  };

  const isAnalyzing = analyses.some(a =>
    a.status === 'pending' || a.status === 'running' || a.status === 'analyzing' || a.status === 'generating'
  );

  return (
    <div className="p-4 bg-white rounded shadow space-y-6">
      <div className="flex justify-between items-center">
        <h3 className="text-xl font-semibold">Обзор анализа</h3>
        <div className="flex gap-3">
          <button
            onClick={onRefresh}
            className="px-4 py-2 bg-gray-600 text-white rounded hover:bg-gray-700"
          >
            🔄 Обновить
          </button>
          <button
            onClick={onAnalyze}
            disabled={isAnalyzing}
            className={`px-4 py-2 rounded font-medium ${
              isAnalyzing
                ? 'bg-gray-400 text-white cursor-not-allowed'
                : 'bg-blue-600 text-white hover:bg-blue-700'
            }`}
          >
            {isAnalyzing ? 'Анализ выполняется...' : '🔄 Запустить анализ'}
          </button>
        </div>
      </div>

      <p className="text-slate-600">{project.description || 'Нет описания'}</p>

      {project.repo_url && (
        <div className="p-3 bg-blue-50 rounded">
          <h4 className="font-medium text-blue-800">GitHub репозиторий</h4>
          <a
            href={project.repo_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-600 hover:underline break-all"
          >
            {project.repo_url}
          </a>
          <div className="text-sm text-blue-700 mt-1">
            Ветка: {project.branch || 'main'}
          </div>
        </div>
      )}

      <div>
        <h4 className="font-medium mb-3">Текущий статус анализа</h4>
        {latestAnalysis ? (
          <div className="mt-2 p-4 border rounded bg-slate-50">
            <div className="flex justify-between items-center mb-3">
              <span className="font-medium">Статус:
                <span className={`ml-2 ${
                  latestAnalysis.status === 'completed' ? 'text-green-600' :
                  latestAnalysis.status === 'failed' ? 'text-red-600' :
                  'text-blue-600'
                }`}>
                  {latestAnalysis.status}
                </span>
              </span>
              <span className="text-sm text-slate-500">
                {new Date(latestAnalysis.created_at).toLocaleString()}
              </span>
            </div>

            {isAnalyzing && (
              <div className="w-full bg-gray-200 rounded-full h-4 mb-2">
                <div
                  className="bg-blue-600 h-4 rounded-full transition-all duration-500 ease-out"
                  style={{ width: `${getProgress(latestAnalysis)}%` }}
                ></div>
                <div className="flex justify-between text-xs text-gray-600 mt-1">
                  <span>{latestAnalysis.status}</span>
                  <span>{getProgress(latestAnalysis)}%</span>
                </div>
              </div>
            )}

            {latestAnalysis.result && (
              <pre className="text-sm text-slate-700 mt-3 whitespace-pre-wrap max-h-60 overflow-y-auto bg-white p-3 rounded border">
                {formatAnalysisResult(latestAnalysis.result)}
              </pre>
            )}
            {latestAnalysis.error_message && (
              <div className="text-sm text-red-600 mt-2 p-2 bg-red-50 rounded">
                <strong>Ошибка:</strong> {latestAnalysis.error_message}
              </div>
            )}
          </div>
        ) : (
          <p className="text-slate-500">Анализы не проводились</p>
        )}
      </div>

      {/* История анализов */}
      <div className="mt-6">
        <h4 className="font-medium mb-3">История анализов</h4>
        <div className="space-y-2">
          {analyses.length === 0 ? (
            <p className="text-slate-500 text-sm">Анализы не проводились</p>
          ) : (
            analyses.map(analysis => (
              <div key={analysis.id} className="p-3 border rounded bg-white">
                <div className="flex justify-between items-center">
                  <div>
                    <span className="font-medium">Анализ #{analysis.id}</span>
                    <span className={`ml-2 px-2 py-1 text-xs rounded ${
                      analysis.status === 'completed' ? 'bg-green-100 text-green-800' :
                      analysis.status === 'running' ? 'bg-blue-100 text-blue-800' :
                      analysis.status === 'failed' ? 'bg-red-100 text-red-800' :
                      'bg-gray-100 text-gray-800'
                    }`}>
                      {analysis.status}
                    </span>
                  </div>
                  <div className="text-sm text-slate-500">
                    {new Date(analysis.created_at).toLocaleString()}
                  </div>
                </div>
                {analysis.result && (
                  <div className="text-sm text-slate-700 bg-slate-50 p-2 rounded mt-2 max-h-20 overflow-y-auto">
                    {analysis.result.technologies?.join(', ') || 'Нет данных'}
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};

export default AnalysisOverview;