// src/components/layout/Sidebar.jsx
import React from 'react';
import { Link, useLocation } from 'react-router-dom';

const Sidebar = ({ projects = [], onCreateProject }) => {
  const location = useLocation();

  const isActive = (path) => {
    return location.pathname === path || location.pathname.startsWith(path);
  };

  const isProjectSubsection = (projectId, subsection) => {
    return location.pathname === `/projects/${projectId}/${subsection}` ||
           location.pathname.startsWith(`/projects/${projectId}/${subsection}`);
  };

  const navItems = [
    { path: '/dashboard', label: 'Главная', icon: '🏠' },
  ];

  // Группируем проекты по открытому состоянию
  const [openProjects, setOpenProjects] = React.useState({});

  const toggleProject = (projectId) => {
    setOpenProjects(prev => ({
      ...prev,
      [projectId]: !prev[projectId]
    }));
  };

  return (
    <div className="h-full bg-white border-r border-gray-200 flex flex-col w-64">
      <div className="p-4 border-b border-gray-200">
        <Link to="/dashboard" className="flex items-center space-x-2">
          <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
            <span className="text-white font-bold text-sm">QA</span>
          </div>
          <span className="text-xl font-bold text-gray-900">QA Autopilot</span>
        </Link>
      </div>

      <div className="flex-1 overflow-y-auto">
        <nav className="p-4 space-y-1">
          {navItems.map(item => (
            <Link
              key={item.path}
              to={item.path}
              className={`flex items-center px-3 py-2 text-sm font-medium rounded-lg transition-colors ${
                isActive(item.path)
                  ? 'bg-blue-50 text-blue-700 border border-blue-200'
                  : 'text-gray-700 hover:bg-gray-50 hover:text-gray-900'
              }`}
            >
              <span className="mr-3 text-lg">{item.icon}</span>
              {item.label}
            </Link>
          ))}

          <div className="pt-6">
            <div className="px-3 mb-2">
              <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
                Проекты
              </h3>
            </div>

            <div className="space-y-1">
              {projects.map(project => (
                <div key={project.id} className="space-y-1">
                  {/* Основная кнопка проекта */}
                  <button
                    onClick={() => toggleProject(project.id)}
                    className={`flex items-center justify-between w-full px-3 py-2 text-sm rounded-lg transition-colors ${
                      isActive(`/projects/${project.id}`)
                        ? 'bg-blue-50 text-blue-700 border border-blue-200'
                        : 'text-gray-700 hover:bg-gray-50'
                    }`}
                  >
                    <div className="flex items-center">
                      <span className="w-2 h-2 bg-green-400 rounded-full mr-3"></span>
                      <span className="truncate">{project.name}</span>
                    </div>
                    <span className={`transform transition-transform ${
                      openProjects[project.id] ? 'rotate-90' : ''
                    }`}>
                      ▶
                    </span>
                  </button>

                  {/* Подразделы проекта */}
                  {openProjects[project.id] && (
                    <div className="ml-6 space-y-1">
                      <Link
                        to={`/projects/${project.id}/analysis`}
                        className={`flex items-center px-3 py-2 text-sm rounded-lg transition-colors ${
                          isProjectSubsection(project.id, 'analysis')
                            ? 'bg-blue-50 text-blue-700 border border-blue-200'
                            : 'text-gray-600 hover:bg-gray-50'
                        }`}
                      >
                        <span className="mr-2">📊</span>
                        Анализ
                      </Link>
                      <Link
                        to={`/projects/${project.id}/tests`}
                        className={`flex items-center px-3 py-2 text-sm rounded-lg transition-colors ${
                          isProjectSubsection(project.id, 'tests')
                            ? 'bg-blue-50 text-blue-700 border border-blue-200'
                            : 'text-gray-600 hover:bg-gray-50'
                        }`}
                      >
                        <span className="mr-2">🧪</span>
                        Генерация тестов & CI/CD
                      </Link>
                    </div>
                  )}
                </div>
              ))}

              {projects.length === 0 && (
                <div className="px-3 py-2 text-sm text-gray-500 italic">
                  Нет проектов
                </div>
              )}
            </div>
          </div>
        </nav>
      </div>

      <div className="p-4 border-t border-gray-200">
        <button
          onClick={onCreateProject}
          className="w-full flex items-center justify-center px-4 py-2 border border-transparent text-sm font-medium rounded-lg text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-colors"
        >
          <span className="mr-2">+</span>
          Новый проект
        </button>
      </div>
    </div>
  );
};

export default Sidebar;