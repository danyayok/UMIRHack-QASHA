import React, { useState } from 'react';
import { Modal } from '../../../components/ui';
import { Button } from '../../../components/ui';
import { projectsAPI } from '../../../services/api';

const GitHubRepoForm = ({ project, onClose, onRepoUpdated }) => {
  const [formData, setFormData] = useState({
    repo_url: project.repo_url || '',
    branch: project.branch || 'main',
    start_analysis: true
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.repo_url.trim()) return;

    setLoading(true);
    setError('');

    try {
      const result = await projectsAPI.updateProjectRepo(
        project.id,
        formData.repo_url,
        formData.branch
      );

      onRepoUpdated(result);

    } catch (err) {
      setError(err.message || 'Произошла ошибка при обновлении репозитория');
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (field) => (e) => {
    const value = field === 'start_analysis' ? e.target.checked : e.target.value;
    setFormData(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const isValidGitHubUrl = (url) => {
    return url.includes('github.com') && url.startsWith('https://');
  };

  return (
    <Modal
      isOpen={true}
      onClose={onClose}
      title={project.repo_url ? "Изменить GitHub репозиторий" : "Добавить GitHub репозиторий"}
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            URL GitHub репозитория *
          </label>
          <input
            type="url"
            required
            value={formData.repo_url}
            onChange={handleChange('repo_url')}
            className="w-full p-2 border border-gray-300 rounded focus:ring-blue-500 focus:border-blue-500"
            placeholder="https://github.com/username/repository"
          />
          {formData.repo_url && !isValidGitHubUrl(formData.repo_url) && (
            <p className="text-sm text-red-600 mt-1">
              Введите корректный GitHub URL
            </p>
          )}
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Ветка
          </label>
          <input
            type="text"
            value={formData.branch}
            onChange={handleChange('branch')}
            className="w-full p-2 border border-gray-300 rounded focus:ring-blue-500 focus:border-blue-500"
            placeholder="main"
          />
        </div>

        <div className="flex items-center space-x-3 p-3 border rounded-lg">
          <input
            type="checkbox"
            id="start_analysis"
            checked={formData.start_analysis}
            onChange={handleChange('start_analysis')}
            className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
          />
          <label htmlFor="start_analysis" className="text-sm text-gray-700">
            <div className="font-medium">Запустить анализ сразу после обновления</div>
            <div className="text-gray-500">Система проанализирует новый репозиторий</div>
          </label>
        </div>

        {error && (
          <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
            {error}
          </div>
        )}

        <div className="flex justify-end gap-2 pt-4">
          <Button
            type="button"
            variant="secondary"
            onClick={onClose}
            disabled={loading}
          >
            Отмена
          </Button>
          <Button
            type="submit"
            loading={loading}
            disabled={!formData.repo_url.trim() || !isValidGitHubUrl(formData.repo_url)}
          >
            {project.repo_url ? 'Обновить' : 'Добавить'}
          </Button>
        </div>
      </form>
    </Modal>
  );
};

export default GitHubRepoForm;