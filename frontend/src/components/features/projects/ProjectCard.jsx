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
  // Если есть последний анализ, смотрим его статус
  if (project.latest_analysis && project.latest_analysis.status) {
    const analysis = project.latest_analysis;

    switch (analysis.status) {
      case 'completed':
        return {
          status: 'analyzed',
          text: '✅ Анализ завершен',
          color: 'text-green-600',
          hasCoverage: true
        };
      case 'failed':
        return {
          status: 'failed',
          text: `❌ Ошибка анализа`,
          color: 'text-red-600',
          hasCoverage: false
        };
      case 'pending':
      case 'cloning':
      case 'extracting':
      case 'analyzing':
      case 'generating':
        const statusText = {
          pending: 'Ожидание запуска',
          cloning: 'Клонирование репозитория',
          extracting: 'Извлечение файлов',
          analyzing: 'Анализ кода',
          generating: 'Генерация тестов'
        };
        return {
          status: 'in_progress',
          text: `🔄 ${statusText[analysis.status] || analysis.status}`,
          color: 'text-blue-600',
          hasCoverage: false
        };
      default:
        return {
          status: 'unknown',
          text: `❓ Статус: ${analysis.status}`,
          color: 'text-gray-600',
          hasCoverage: false
        };
    }
  }

  // Если нет анализа или статуса - проверяем coverage
  if (project.coverage !== undefined && project.coverage !== null) {
    return {
      status: 'analyzed',
      text: '✅ Анализ завершен',
      color: 'text-green-600',
      hasCoverage: true
    };
  }

  // Если нет анализа вообще
  return {
    status: 'no_analysis',
    text: '⏳ Ожидание анализа',
    color: 'text-yellow-600',
    hasCoverage: false
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
      className="rounded-lg shadow-md overflow-hidden cursor-pointer w-72 hover:shadow-lg transition-shadow bg-white flex flex-col h-full"
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

        {/* Показываем coverage если анализ завершен или если есть значение coverage */}
        {projectStatus.hasCoverage && (
          <div className="absolute bottom-2 right-2 bg-black/20 px-2 py-1 rounded text-xs">
            {coverage}%
          </div>
        )}
      </div>

      <div className="p-3 flex-grow space-y-2">
        <div className="flex items-center justify-between">
          <div className={`text-xs font-medium ${projectStatus.color} truncate max-w-[180px]`}>
            {projectStatus.text}
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

        {/* Показываем coverage в основном контенте только если анализ завершен */}
        {projectStatus.hasCoverage && (
          <div className="text-sm text-gray-600">
            Покрытие тестами: {coverage}%
          </div>
        )}

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
      </div>

      <div className="p-2 border-t border-gray-100 flex justify-end">
        <button
          onClick={handleDelete}
          className="text-gray-400 hover:text-red-500 transition-colors p-1"
          title="Удалить проект"
        >
          🗑️
        </button>
      </div>
    </div>
  );
}