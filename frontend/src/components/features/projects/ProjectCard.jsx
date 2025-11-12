import React from 'react';

function getCoverageColor(pct) {
  if (pct >= 70) return 'bg-gradient-to-r from-green-500 to-green-600';
  if (pct >= 40) return 'bg-gradient-to-r from-yellow-500 to-yellow-600';
  if (pct >= 20) return 'bg-gradient-to-r from-orange-500 to-orange-600';
  return 'bg-gradient-to-r from-red-500 to-red-600';
}

function getSourceIcon(project) {
  return project.repo_url ? '🐙' : '📦';
}

function getProjectStatus(project) {
  // Если нет coverage и нет анализа - ожидание
  if (!project.coverage && !project.latest_analysis) {
    return {
      status: 'pending',
      text: '⏳ Ожидание анализа',
      color: 'text-yellow-600'
    };
  }

  // Если есть анализ с тестами
  if (project.latest_analysis?.result?.test_analysis?.has_tests) {
    const frameworks = project.latest_analysis.result.test_analysis.test_frameworks;
    return {
      status: 'has_tests',
      text: `✅ ${frameworks.length > 0 ? frameworks.join(', ') : 'Тесты есть'}`,
      color: 'text-green-600'
    };
  }

  // Если есть анализ но нет тестов
  if (project.latest_analysis && !project.latest_analysis.result?.test_analysis?.has_tests) {
    return {
      status: 'no_tests',
      text: '❌ Нет тестов',
      color: 'text-red-600'
    };
  }

  return {
    status: 'unknown',
    text: '❓ Анализ не завершен',
    color: 'text-gray-600'
  };
}

export default function ProjectCard({ project, onOpen, onDelete }) {
  const coverage = project.coverage || 0;
  const sourceIcon = getSourceIcon(project);
  const projectStatus = getProjectStatus(project);

  const handleDelete = async (e) => {
    e.stopPropagation();
    if (window.confirm(`Удалить проект "${project.name}"?`)) {
      try {
        await onDelete(project.id);
      } catch (error) {
        alert('Ошибка при удалении проекта: ' + error.message);
      }
    }
  };

  return (
    <div
      className="rounded-lg shadow-md overflow-hidden cursor-pointer w-72 hover:shadow-lg transition-shadow bg-white"
      onClick={() => onOpen(project)}
    >
      <div className={`p-4 text-white font-semibold relative ${getCoverageColor(coverage)}`}>
        <div className="flex justify-between items-start">
          <span className="truncate">{project.name}</span>
          <span className="text-lg ml-2">{sourceIcon}</span>
        </div>
        {project.description && (
          <p className="text-white/90 text-sm font-normal mt-1 truncate">
            {project.description}
          </p>
        )}

        <div className="absolute bottom-2 right-2 bg-black/20 px-2 py-1 rounded text-xs">
          {coverage}%
        </div>
      </div>

      <div className="p-3 space-y-2">
        <div className="flex items-center justify-between">
          <div className="text-sm text-gray-600">
            Покрытие: {coverage}%
          </div>
          {project.repo_url ? (
            <div className="text-xs text-blue-600 bg-blue-50 px-2 py-1 rounded">
              GitHub
            </div>
          ) : (
            <div className="text-xs text-gray-600 bg-gray-50 px-2 py-1 rounded">
              ZIP
            </div>
          )}
        </div>

        <div className={`text-xs font-medium ${projectStatus.color}`}>
          {projectStatus.text}
        </div>

        {project.latest_analysis?.result?.technologies && (
          <div className="flex flex-wrap gap-1">
            {project.latest_analysis.result.technologies.slice(0, 3).map(tech => (
              <span key={tech} className="text-xs bg-gray-100 text-gray-700 px-2 py-1 rounded">
                {tech}
              </span>
            ))}
            {project.latest_analysis.result.technologies.length > 3 && (
              <span className="text-xs text-gray-500">
                +{project.latest_analysis.result.technologies.length - 3}
              </span>
            )}
          </div>
        )}

        <div className="flex justify-end">
          <button
            onClick={handleDelete}
            className="text-gray-400 hover:text-red-500 transition-colors p-1"
            title="Удалить проект"
          >
            🗑️
          </button>
        </div>
      </div>
    </div>
  );
}