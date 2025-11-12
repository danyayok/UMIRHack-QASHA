import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { DashboardLayout } from '../components/layout';
import ProjectCard from '../components/features/projects/ProjectCard';
import ProjectForm from '../components/features/projects/ProjectForm';
import { useProjects } from '../hooks/useProjects';
import { Button } from '../components/ui';

export default function Dashboard() {
  const { projects, loading, error, createProject, deleteProject, refetch } = useProjects();
  const navigate = useNavigate();
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newProject, setNewProject] = useState(null);
  const [pollingCount, setPollingCount] = useState(0);

  // Автоматическое обновление каждые 5 секунд если есть проекты в анализе
  useEffect(() => {
    const hasPendingAnalysis = projects.some(project =>
      !project.coverage || project.coverage === 0
    );

    if (hasPendingAnalysis) {
      const interval = setInterval(() => {
        refetch();
        setPollingCount(prev => prev + 1);
      }, 5000);

      return () => clearInterval(interval);
    }
  }, [projects, refetch]);

  const handleProjectCreated = (project) => {
    setNewProject(project);
    // Начинаем опрос для нового проекта
    setTimeout(refetch, 2000);
  };

  const openProject = (project) => {
    navigate(`/projects/${project.id}`);
  };

  const headerProps = {
    title: "Мои проекты",
    actions: (
      <div className="flex items-center space-x-4">
        {pollingCount > 0 && (
          <div className="text-sm text-gray-500">
            Автообновление... ({pollingCount})
          </div>
        )}
        <Button onClick={() => setShowCreateModal(true)}>
          + Новый проект
        </Button>
      </div>
    )
  };

  const sidebarProps = {
    projects,
    onCreateProject: () => setShowCreateModal(true)
  };

  return (
    <DashboardLayout headerProps={headerProps} sidebarProps={sidebarProps}>
      <div className="p-6">
        {error && (
          <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
            Ошибка: {error}
          </div>
        )}

        {newProject && (
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-blue-800 font-medium">🔄 Проект создан!</h3>
                <p className="text-blue-700 text-sm">
                  Проект "{newProject.name}" создан. Запущен анализ репозитория...
                </p>
                <p className="text-blue-600 text-xs mt-1">
                  Данные появятся через 10-30 секунд
                </p>
              </div>
              <Button
                onClick={() => {
                  openProject(newProject);
                  setNewProject(null);
                }}
                variant="primary"
                size="small"
              >
                Перейти к проекту
              </Button>
            </div>
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <div className="text-lg text-gray-500">Загрузка проектов...</div>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {projects.map(project => (
              <ProjectCard
                key={project.id}
                project={project}
                onOpen={openProject}
                onDelete={deleteProject}
              />
            ))}
          </div>
        )}

        {!loading && projects.length === 0 && (
          <div className="text-center py-12">
            <div className="text-gray-500 text-lg mb-4">
              У вас пока нет проектов
            </div>
            <Button onClick={() => setShowCreateModal(true)}>
              Создать первый проект
            </Button>
          </div>
        )}

        <ProjectForm
          isOpen={showCreateModal}
          onClose={() => setShowCreateModal(false)}
          onProjectCreated={handleProjectCreated}
        />
      </div>
    </DashboardLayout>
  );
}