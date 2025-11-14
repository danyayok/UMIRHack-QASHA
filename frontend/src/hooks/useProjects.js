// hooks/useProjects.js
import { useState, useEffect } from 'react';
import { projectsAPI } from '../services/api';

export function useProjects() {
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchProjects = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await projectsAPI.getProjects(); // Исправлено: projectsAPI вместо apiService
      setProjects(data);
    } catch (err) {
      setError(err.message);
      console.error('Failed to fetch projects:', err);
    } finally {
      setLoading(false);
    }
  };

  const createProject = async (projectData) => {
    try {
      const formData = new FormData();
      Object.keys(projectData).forEach(key => {
        if (key !== 'zip_file') {
          formData.append(key, projectData[key]);
        }
      });
      if (projectData.source_type === 'zip' && projectData.zip_file) {
        formData.append('zip_file', projectData.zip_file);
      }
      const newProject = await projectsAPI.createProject(formData); // Исправлено: projectsAPI вместо apiService
      await fetchProjects(); // Исправлено: fetchProjects вместо loadProjects
      return newProject;
    } catch (error) {
      console.error('Failed to create project:', error);
      throw error;
    }
  };

  const deleteProject = async (projectId) => {
    try {
      await projectsAPI.deleteProject(projectId);
      setProjects(prev => prev.filter(p => p.id !== projectId));
    } catch (err) {
      setError(err.message);
      throw err;
    }
  };

  useEffect(() => {
    fetchProjects(); // Исправлено: fetchProjects вместо loadProjects
  }, []);

  return {
    projects,
    loading,
    error,
    createProject,
    deleteProject,
    refetch: fetchProjects // Исправлено: fetchProjects вместо loadProjects
  };
}