import React, { useEffect, useState } from 'react';
import { useParams, Link, Routes, Route, useNavigate } from 'react-router-dom';
import { DashboardLayout } from '../components/layout';
import { projectsAPI } from '../services/api';

function AnalysisHistory({ analyses, onRefresh }) {
  const formatResult = (result) => {
    if (!result) return 'Нет данных';

    console.log('📋 Analysis History Raw Data:', result);

    // Новый формат (реальный анализ)
    if (result.file_structure_summary && result.test_analysis) {
      const {
        technologies = [],
        file_structure_summary = {},
        test_analysis = {},
        coverage_estimate = 0
      } = result;

      return `
Технологии: ${technologies.join(', ') || 'не обнаружены'}
Файлов проанализировано: ${file_structure_summary.total_files || 0}
Файлов кода: ${file_structure_summary.code_files || 0}
Тестовых файлов: ${file_structure_summary.test_files || 0}
Тесты найдены: ${test_analysis.has_tests ? '✅ Да' : '❌ Нет'}
Фреймворки тестирования: ${test_analysis.test_frameworks?.join(', ') || 'не обнаружены'}
Покрытие: ${coverage_estimate}%
      `.trim();
    }

    // Старый формат
    if (result.technologies && Array.isArray(result.technologies)) {
      return `
Технологии: ${result.technologies.join(', ')}
Файлов проанализировано: ${result.metrics?.total_files || 0}
Сгенерировано тестов: ${result.generated_tests?.total_generated || 0}
Фреймворки тестирования: ${result.test_frameworks?.join(', ') || 'не обнаружены'}
      `.trim();
    }

    // Любой другой формат
    if (typeof result === 'string') {
      return result;
    }

    return JSON.stringify(result, null, 2);
  };

  return (
    <div className="mt-6">
      <div className="flex justify-between items-center mb-2">
        <h4 className="font-medium">История анализов</h4>
        <button
          onClick={onRefresh}
          className="px-2 py-1 text-sm bg-blue-100 text-blue-700 rounded hover:bg-blue-200"
        >
          Обновить
        </button>
      </div>
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
                <pre className="text-sm text-slate-700 bg-slate-50 p-2 rounded mt-2 whitespace-pre-wrap max-h-40 overflow-y-auto">
                  {formatResult(analysis.result)}
                </pre>
              )}
              {analysis.error_message && (
                <div className="text-sm text-red-600 bg-red-50 p-2 rounded mt-2">
                  Ошибка: {analysis.error_message}
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function ProgressBar({ progress, status }) {
  return (
    <div className="w-full bg-gray-200 rounded-full h-4 mb-2">
      <div
        className="bg-blue-600 h-4 rounded-full transition-all duration-500 ease-out"
        style={{ width: `${progress}%` }}
      ></div>
      <div className="flex justify-between text-xs text-gray-600 mt-1">
        <span>{status}</span>
        <span>{progress}%</span>
      </div>
    </div>
  );
}

function Overview({ project, analyses, onRefresh, onAnalyze }) {
  const latestAnalysis = analyses[0];
  const isAnalyzing = analyses.some(a =>
    a.status === 'pending' || a.status === 'running' || a.status === 'analyzing' || a.status === 'generating'
  );

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

    const formatAnalysisResult = (result) => {
      if (!result) return 'Нет данных анализа';

      // Проверяем, что это реальные данные анализа (а не ошибка или старый формат)
      if (result.technologies || result.file_structure_summary) {
        const {
          technologies = [],
          frameworks = [],
          file_structure_summary = {},
          test_analysis = {},
          dependencies = {},
          coverage_estimate = 0,
          project_structure = {}
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
📊 РЕАЛЬНЫЕ РЕЗУЛЬТАТЫ АНАЛИЗА

🏗️ Обнаруженные технологии:
${technologies.length > 0 ? technologies.map(tech => `• ${tech}`).join('\n') : '• Не обнаружено'}

📁 Статистика проекта:
• Всего файлов: ${total_files}
• Файлов кода: ${code_files}
• Тестовых файлов: ${test_files}
• Всего строк кода: ${total_lines}
• Размер проекта: ${total_size_kb} KB

🧪 Анализ тестов:
• Тесты найдены: ${has_tests ? '✅ Да' : '❌ Нет'}
• Тестовых файлов: ${test_files_count}
• Фреймворки тестирования: ${test_frameworks.length > 0 ? test_frameworks.join(', ') : 'Не обнаружены'}
• Тестовые директории: ${test_directories.length > 0 ? test_directories.join(', ') : 'Не обнаружены'}

📈 Покрытие тестами:
• Оценка покрытия: ${coverage_estimate}%

🏛️ Фреймворки:
${frameworks.length > 0 ? frameworks.map(fw => `• ${fw}`).join('\n') : '• Не обнаружено'}

📦 Зависимости:
${Object.keys(dependencies).length > 0 ?
      Object.entries(dependencies).map(([tech, deps]) =>
        `• ${tech}: ${Array.isArray(deps) ? deps.slice(0, 5).join(', ') : JSON.stringify(deps)}`
      ).join('\n') :
      '• Не обнаружены'
    }
        `.trim();
      }

      // Если данные в старом формате или строка
      if (typeof result === 'string') {
        return result;
      }

      return JSON.stringify(result, null, 2);
    };

  return (
    <div className="p-4 bg-white rounded shadow space-y-4">
      <div className="flex justify-between items-center">
        <h3 className="text-xl font-semibold">Обзор проекта</h3>
        <button
          onClick={onAnalyze}
          disabled={isAnalyzing}
          className={`px-4 py-2 rounded font-medium ${
            isAnalyzing
              ? 'bg-gray-400 text-white cursor-not-allowed'
              : 'bg-blue-600 text-white hover:bg-blue-700'
          }`}
        >
          {isAnalyzing ? 'Анализ выполняется...' : 'Запустить анализ'}
        </button>
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
              <ProgressBar
                progress={getProgress(latestAnalysis)}
                status={latestAnalysis.status}
              />
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

      <AnalysisHistory analyses={analyses} onRefresh={onRefresh} />
    </div>
  );
}

function TestsTab({ analyses }) {
  const latestAnalysis = analyses[0];

    const getTestMetrics = (analysis) => {
      if (!analysis?.result) return null;

      const result = analysis.result;

      // Используем реальные данные из анализа
      return {
        coverage: result.coverage_estimate || 0,
        totalTests: result.test_analysis?.test_files_count || 0,
        testFiles: result.test_analysis?.test_files_count || 0,
        technologies: result.technologies || [],
        frameworks: result.test_analysis?.test_frameworks || [],
        totalFiles: result.file_structure_summary?.total_files || 0,
        codeFiles: result.file_structure_summary?.code_files || 0,
        hasTests: result.test_analysis?.has_tests || false,
        totalLines: result.file_structure_summary?.total_lines || 0
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
}

function PipelineTab() {
  return (
    <div className="p-4 bg-white rounded shadow space-y-4">
      <h3 className="text-xl font-semibold">Pipeline и интеграции</h3>

      <div className="space-y-3">
        <div className="p-4 border rounded bg-slate-50">
          <h4 className="font-medium text-slate-800 mb-2">CI/CD Pipeline</h4>
          <div className="flex items-center space-x-2 mb-2">
            <div className="w-3 h-3 bg-red-500 rounded-full"></div>
            <span className="text-sm font-medium">GitHub Actions</span>
            <span className="text-sm text-slate-500">— last run: failed (2 tests)</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div className="bg-red-500 h-2 rounded-full" style={{ width: '65%' }}></div>
          </div>
        </div>

        <div className="p-4 border rounded bg-slate-50">
          <h4 className="font-medium text-slate-800 mb-2">Интеграции</h4>
          <div className="space-y-2">
            <div className="flex items-center space-x-2">
              <div className="w-2 h-2 bg-green-500 rounded-full"></div>
              <span className="text-sm">Telegram notifications enabled</span>
            </div>
            <div className="flex items-center space-x-2">
              <div className="w-2 h-2 bg-green-500 rounded-full"></div>
              <span className="text-sm">Slack integration active</span>
            </div>
            <div className="flex items-center space-x-2">
              <div className="w-2 h-2 bg-yellow-500 rounded-full"></div>
              <span className="text-sm">Jira integration pending</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function ProjectPage() {
  const { id } = useParams();
  const [project, setProject] = useState(null);
  const [analyses, setAnalyses] = useState([]);
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const nav = useNavigate();

  useEffect(() => {
    loadProjectData();

    // Обновляем данные каждые 3 секунды если есть незавершенные анализы
    const interval = setInterval(() => {
      const hasRunning = analyses.some(a =>
        a.status === 'pending' || a.status === 'running' || a.status === 'analyzing' || a.status === 'generating'
      );
      if (hasRunning) {
        loadAnalyses();
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [id]);

  async function loadProjectData() {
    try {
      const [projectData, allProjects] = await Promise.all([
        projectsAPI.getProject(id),
        projectsAPI.getProjects()
      ]);

      setProject(projectData);
      setProjects(allProjects || []);
      await loadAnalyses();
    } catch (err) {
      console.error('Ошибка загрузки данных проекта:', err);
      alert('Ошибка получения данных проекта');
      nav('/dashboard');
    } finally {
      setLoading(false);
    }
  }

    async function loadAnalyses() {
      try {
        const analysesData = await projectsAPI.getProjectAnalyses(id);
        console.log('📊 ANALYSES DATA:', analysesData); // ДЛЯ ОТЛАДКИ
        setAnalyses(analysesData || []);
      } catch (err) {
        console.error('Ошибка загрузки анализов:', err);
      }
    }

  async function handleAnalyze() {
    try {
      await projectsAPI.analyzeProject(id);
      // Обновляем анализы после запуска
      setTimeout(loadAnalyses, 1000);
    } catch (err) {
      console.error('Ошибка запуска анализа:', err);
      alert('Ошибка запуска анализа: ' + err.message);
    }
  }

  if (!project) return <div className="p-6">Загрузка проекта...</div>;

  const headerProps = {
    title: project.name,
    actions: (
      <div className="flex items-center space-x-2">
        <Link to={`/projects/${id}`} className="px-3 py-1 bg-slate-200 rounded hover:bg-slate-300">Overview</Link>
        <Link to={`/projects/${id}/tests`} className="px-3 py-1 bg-slate-200 rounded hover:bg-slate-300">Tests</Link>
        <Link to={`/projects/${id}/pipeline`} className="px-3 py-1 bg-slate-200 rounded hover:bg-slate-300">Pipeline</Link>
      </div>
    )
  };

  const sidebarProps = {
    projects,
    currentProjectId: project.id
  };

  return (
    <DashboardLayout headerProps={headerProps} sidebarProps={sidebarProps}>
      <Routes>
        <Route path="" element={
          <Overview
            project={project}
            analyses={analyses}
            onRefresh={loadAnalyses}
            onAnalyze={handleAnalyze}
          />
        } />
        <Route path="tests" element={<TestsTab analyses={analyses} />} />
        <Route path="pipeline" element={<PipelineTab />} />
      </Routes>
    </DashboardLayout>
  );
}