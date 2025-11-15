import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { DashboardLayout } from '../components/layout';
import ProjectCard from '../components/features/projects/ProjectCard';
import ProjectForm from '../components/features/projects/ProjectForm';
import { useProjects } from '../hooks/useProjects';
import { Button } from '../components/ui';
import { projectsAPI } from '../services/api';

export default function Dashboard() {
  const { projects, loading, error, createProject, deleteProject, refetch } = useProjects();
  const navigate = useNavigate();
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newProject, setNewProject] = useState(null);
  const [projectsWithAnalysis, setProjectsWithAnalysis] = useState([]);

  // Загружаем анализы для каждого проекта
  useEffect(() => {
    const loadAnalyses = async () => {
      if (projects.length === 0) {
        setProjectsWithAnalysis([]);
        return;
      }

      try {
        const projectsWithAnalyses = await Promise.all(
          projects.map(async (project) => {
            try {
              const latestAnalysis = await projectsAPI.getLatestAnalysis(project.id);
              return {
                ...project,
                latest_analysis: latestAnalysis,
                // coverage берем из проекта, так как он уже приходит с бэкенда
                coverage: project.coverage || 0
              };
            } catch (error) {
              console.error(`Error loading analysis for project ${project.id}:`, error);
              return {
                ...project,
                latest_analysis: null,
                coverage: project.coverage || 0
              };
            }
          })
        );
        setProjectsWithAnalysis(projectsWithAnalyses);
      } catch (error) {
        console.error('Error loading analyses:', error);
        setProjectsWithAnalysis(projects); // fallback - используем проекты без анализов
      }
    };

    loadAnalyses();
  }, [projects]);

  const handleProjectCreated = (project) => {
    setNewProject(project);
    // Обновляем список проектов через некоторое время
    setTimeout(() => {
      refetch();
    }, 2000);
  };

  const openProject = (project) => {
    navigate(`/projects/${project.id}`);
  };

  const headerProps = {
    title: "Мои проекты",
    actions: (
      <Button onClick={() => setShowCreateModal(true)}>
        + Новый проект
      </Button>
    )
  };

  const sidebarProps = {
    projects: projectsWithAnalysis,
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
                <h3 className="text-blue-800 font-medium">✅ Проект создан!</h3>
                <p className="text-blue-700 text-sm">
                  Проект "{newProject.name}" успешно создан.
                </p>
                <p className="text-blue-600 text-xs mt-1">
                  Перейдите к проекту чтобы отслеживать прогресс анализа
                </p>
              </div>
              <div className="flex space-x-2">
                <Button
                  onClick={() => setNewProject(null)}
                  variant="secondary"
                  size="small"
                >
                  Закрыть
                </Button>
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
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <div className="text-lg text-gray-500">Загрузка проектов...</div>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {projectsWithAnalysis.map(project => (
              <ProjectCard
                key={project.id}
                project={project}
                onOpen={openProject}
                onDelete={deleteProject}
              />
            ))}
          </div>
        )}

        {!loading && projectsWithAnalysis.length === 0 && (
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