// src/pages/ProjectAnalysisPage.jsx
import React, { useEffect, useState } from 'react';
import { useParams, Link, Routes, Route, useNavigate } from 'react-router-dom';
import { DashboardLayout } from '../components/layout';
import { projectsAPI } from '../services/api';
import AnalysisOverview from '../components/features/analysis/AnalysisOverview';
import AnalysisDetails from '../components/features/analysis/AnalysisDetails';

const ProjectAnalysisPage = () => {
  const { id } = useParams();
  const [project, setProject] = useState(null);
  const [analyses, setAnalyses] = useState([]);
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const nav = useNavigate();

  useEffect(() => {
    loadProjectData();

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
      setAnalyses(analysesData || []);
    } catch (err) {
      console.error('Ошибка загрузки анализов:', err);
    }
  }

  async function handleAnalyze() {
    try {
      await projectsAPI.analyzeProject(id);
      setTimeout(loadAnalyses, 1000);
    } catch (err) {
      console.error('Ошибка запуска анализа:', err);
      alert('Ошибка запуска анализа: ' + err.message);
    }
  }

  if (!project) return <div className="p-6">Загрузка проекта...</div>;

  const headerProps = {
    title: `Анализ - ${project.name}`,
    actions: (
      <div className="flex items-center space-x-2">
        <Link
          to={`/projects/${id}/analysis`}
          className="px-3 py-1 bg-blue-600 text-white rounded hover:bg-blue-700"
        >
          Обзор
        </Link>
        <Link
          to={`/projects/${id}/analysis/details`}
          className="px-3 py-1 bg-slate-200 rounded hover:bg-slate-300"
        >
          Детали
        </Link>
        <button
          onClick={handleAnalyze}
          className="px-3 py-1 bg-green-600 text-white rounded hover:bg-green-700"
        >
          🔄 Обновить анализ
        </button>
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
          <AnalysisOverview
            project={project}
            analyses={analyses}
            onRefresh={loadAnalyses}
            onAnalyze={handleAnalyze}
          />
        } />
        <Route path="details" element={
          <AnalysisDetails analyses={analyses} />
        } />
      </Routes>
    </DashboardLayout>
  );
};

export default ProjectAnalysisPage;