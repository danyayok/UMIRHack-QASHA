// src/pages/ProjectTestsPage.jsx
import React, { useEffect, useState } from 'react';
import { useParams, Link, Routes, Route, useNavigate } from 'react-router-dom';
import { DashboardLayout } from '../components/layout';
import { projectsAPI, testsAPI } from '../services/api';
import TestGenerator from '../components/features/tests/TestGenerator';
import TestRunner from '../components/features/tests/TestRunner';
import CICDOverview from '../components/features/tests/CICDOverview';

const ProjectTestsPage = () => {
  const { id } = useParams();
  const [project, setProject] = useState(null);
  const [projects, setProjects] = useState([]);
  const [showGenerator, setShowGenerator] = useState(false);
  const [testResults, setTestResults] = useState(null);
  const [loading, setLoading] = useState(true);
  const nav = useNavigate();

  useEffect(() => {
    loadProjectData();
  }, [id]);

  const loadProjectData = async () => {
    try {
      const [projectData, allProjects] = await Promise.all([
        projectsAPI.getProject(id),
        projectsAPI.getProjects()
      ]);

      setProject(projectData);
      setProjects(allProjects || []);

      // Загружаем результаты тестов если есть
      const results = await testsAPI.getTestResults(id).catch(() => null);
      setTestResults(results);
    } catch (err) {
      console.error('Ошибка загрузки проекта:', err);
      nav('/dashboard');
    } finally {
      setLoading(false);
    }
  };

  const handleTestsGenerated = (result) => {
    loadProjectData();
    setShowGenerator(false);
  };

  const handleRunTests = async () => {
    try {
      const results = await testsAPI.runTests(id);
      setTestResults(results);
    } catch (err) {
      console.error('Ошибка запуска тестов:', err);
    }
  };

  if (!project) return <div className="p-6">Загрузка проекта...</div>;

  const headerProps = {
    title: `Тесты & CI/CD - ${project.name}`,
    actions: (
      <div className="flex items-center space-x-2">
        <Link
          to={`/projects/${id}/tests`}
          className="px-3 py-1 bg-blue-600 text-white rounded hover:bg-blue-700"
        >
          Генератор тестов
        </Link>
        <Link
          to={`/projects/${id}/tests/runner`}
          className="px-3 py-1 bg-slate-200 rounded hover:bg-slate-300"
        >
          Запуск тестов
        </Link>
        <Link
          to={`/projects/${id}/tests/cicd`}
          className="px-3 py-1 bg-slate-200 rounded hover:bg-slate-300"
        >
          CI/CD
        </Link>
        <button
          onClick={() => setShowGenerator(true)}
          className="px-3 py-1 bg-green-600 text-white rounded hover:bg-green-700"
        >
          🧪 Новые тесты
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
      <div className="p-6">
        <Routes>
          <Route path="" element={
            <TestGenerator
              project={project}
              testResults={testResults}
              onRunTests={handleRunTests}
            />
          } />
          <Route path="runner" element={
            <TestRunner
              project={project}
              testResults={testResults}
              onRunTests={handleRunTests}
            />
          } />
          <Route path="cicd" element={
            <CICDOverview project={project} />
          } />
        </Routes>

      </div>
    </DashboardLayout>
  );
};

export default ProjectTestsPage;