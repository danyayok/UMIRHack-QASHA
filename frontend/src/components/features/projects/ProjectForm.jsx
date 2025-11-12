import React, { useState } from 'react';
import { Modal } from '../../../components/ui';
import { Button } from '../../../components/ui';
import { projectsAPI } from '../../../services/api';

const ProjectForm = ({ isOpen, onClose, onProjectCreated }) => {
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const [formData, setFormData] = useState({
    // Шаг 1: Основная информация
    name: '',
    description: '',

    // Шаг 2: Источник
    source_type: 'github', // 'github' или 'zip'
    repo_url: '',
    branch: 'main',
    zip_file: null,

    // Шаг 3: Настройки
    auto_analyze: true,
  });

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.name.trim()) return;

    setLoading(true);
    setError('');

    try {
      const formDataToSend = new FormData();

      // Основные поля
      formDataToSend.append('name', formData.name);
      if (formData.description) {
        formDataToSend.append('description', formData.description);
      }

      // Поля источника
      formDataToSend.append('source_type', formData.source_type);
      formDataToSend.append('auto_analyze', formData.auto_analyze.toString());

      if (formData.source_type === 'github') {
        formDataToSend.append('repo_url', formData.repo_url);
        formDataToSend.append('branch', formData.branch);
      } else if (formData.source_type === 'zip' && formData.zip_file) {
        formDataToSend.append('zip_file', formData.zip_file);
      }

      const project = await projectsAPI.createProject(formDataToSend);
      onProjectCreated(project);
      resetForm();
      onClose();

    } catch (err) {
      setError(err.message || 'Произошла ошибка при создании проекта');
    } finally {
      setLoading(false);
    }
  };

  const resetForm = () => {
    setFormData({
      name: '',
      description: '',
      source_type: 'github',
      repo_url: '',
      branch: 'main',
      zip_file: null,
      auto_analyze: true,
    });
    setStep(1);
    setError('');
  };

  const handleChange = (field) => (e) => {
    const value = field === 'auto_analyze'
      ? e.target.checked
      : e.target.value;

    setFormData(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    setFormData(prev => ({
      ...prev,
      zip_file: file
    }));
  };

  const nextStep = () => {
    if (step === 1 && !formData.name.trim()) {
      setError('Введите название проекта');
      return;
    }
    if (step === 2) {
      if (formData.source_type === 'github' && !formData.repo_url.trim()) {
        setError('Введите URL GitHub репозитория');
        return;
      }
      if (formData.source_type === 'zip' && !formData.zip_file) {
        setError('Выберите ZIP файл');
        return;
      }
    }
    setError('');
    setStep(step + 1);
  };

  const prevStep = () => {
    setStep(step - 1);
    setError('');
  };

  const handleClose = () => {
    resetForm();
    onClose();
  };

  // Валидация GitHub URL
  const isValidGitHubUrl = (url) => {
    return url.includes('github.com') && url.startsWith('https://');
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title="Создать новый проект"
      size="lg"
    >
      <div className="mb-6">
        <div className="flex items-center justify-center space-x-4">
          {[1, 2, 3].map((stepNumber) => (
            <div key={stepNumber} className="flex items-center">
              <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
                stepNumber === step
                  ? 'bg-blue-600 text-white'
                  : stepNumber < step
                    ? 'bg-green-500 text-white'
                    : 'bg-gray-200 text-gray-600'
              }`}>
                {stepNumber}
              </div>
              {stepNumber < 3 && (
                <div className={`w-12 h-1 mx-2 ${
                  stepNumber < step ? 'bg-green-500' : 'bg-gray-200'
                }`} />
              )}
            </div>
          ))}
        </div>
        <div className="flex justify-between text-xs text-gray-500 mt-2 px-2">
          <span>Основное</span>
          <span>Источник</span>
          <span>Настройки</span>
        </div>
      </div>

      <form onSubmit={handleSubmit}>
        {/* Шаг 1: Основная информация */}
        {step === 1 && (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Название проекта *
              </label>
              <input
                type="text"
                required
                value={formData.name}
                onChange={handleChange('name')}
                className="w-full p-2 border border-gray-300 rounded focus:ring-blue-500 focus:border-blue-500"
                placeholder="Мой Awesome Проект"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Описание
              </label>
              <textarea
                value={formData.description}
                onChange={handleChange('description')}
                rows={3}
                className="w-full p-2 border border-gray-300 rounded focus:ring-blue-500 focus:border-blue-500"
                placeholder="Описание проекта..."
              />
            </div>
          </div>
        )}

        {/* Шаг 2: Выбор источника */}
        {step === 2 && (
          <div className="space-y-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-3">
                Выберите источник кода
              </label>

              <div className="grid grid-cols-2 gap-4">
                {/* GitHub вариант */}
                <label className={`relative flex cursor-pointer rounded-lg border p-4 focus:outline-none ${
                  formData.source_type === 'github'
                    ? 'border-blue-500 bg-blue-50'
                    : 'border-gray-300'
                }`}>
                  <input
                    type="radio"
                    name="source_type"
                    value="github"
                    checked={formData.source_type === 'github'}
                    onChange={handleChange('source_type')}
                    className="sr-only"
                  />
                  <div className="flex w-full items-center justify-between">
                    <div className="flex items-center">
                      <div className="text-sm">
                        <div className="font-medium text-gray-900">GitHub репозиторий</div>
                        <div className="text-gray-500">Анализ напрямую из GitHub</div>
                      </div>
                    </div>
                    <div className="text-2xl">🐙</div>
                  </div>
                </label>

                {/* ZIP вариант */}
                <label className={`relative flex cursor-pointer rounded-lg border p-4 focus:outline-none ${
                  formData.source_type === 'zip'
                    ? 'border-blue-500 bg-blue-50'
                    : 'border-gray-300'
                }`}>
                  <input
                    type="radio"
                    name="source_type"
                    value="zip"
                    checked={formData.source_type === 'zip'}
                    onChange={handleChange('source_type')}
                    className="sr-only"
                  />
                  <div className="flex w-full items-center justify-between">
                    <div className="flex items-center">
                      <div className="text-sm">
                        <div className="font-medium text-gray-900">ZIP архив</div>
                        <div className="text-gray-500">Загрузите архив с кодом</div>
                      </div>
                    </div>
                    <div className="text-2xl">📦</div>
                  </div>
                </label>
              </div>
            </div>

            {/* GitHub настройки */}
            {formData.source_type === 'github' && (
              <div className="space-y-4 border-t pt-4">
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
              </div>
            )}

            {/* ZIP настройки */}
            {formData.source_type === 'zip' && (
              <div className="space-y-4 border-t pt-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Выберите ZIP архив *
                  </label>
                  <input
                    type="file"
                    accept=".zip,.rar,.7z"
                    onChange={handleFileChange}
                    className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
                  />
                  {formData.zip_file && (
                    <p className="text-sm text-green-600 mt-1">
                      Выбран файл: {formData.zip_file.name}
                    </p>
                  )}
                </div>

                <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3">
                  <p className="text-sm text-yellow-800">
                    💡 Вы сможете добавить GitHub репозиторий позже в настройках проекта
                  </p>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Шаг 3: Настройки */}
        {step === 3 && (
          <div className="space-y-4">
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <h4 className="font-medium text-blue-900 mb-2">Сводка проекта</h4>
              <div className="text-sm text-blue-800 space-y-1">
                <p><strong>Название:</strong> {formData.name}</p>
                <p><strong>Источник:</strong> {formData.source_type === 'github' ? 'GitHub' : 'ZIP архив'}</p>
                {formData.source_type === 'github' && (
                  <p><strong>Репозиторий:</strong> {formData.repo_url}</p>
                )}
                {formData.source_type === 'zip' && (
                  <p><strong>Файл:</strong> {formData.zip_file?.name || 'Не выбран'}</p>
                )}
              </div>
            </div>

            <div className="flex items-center space-x-3 p-3 border rounded-lg">
              <input
                type="checkbox"
                id="auto_analyze"
                checked={formData.auto_analyze}
                onChange={handleChange('auto_analyze')}
                className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              />
              <label htmlFor="auto_analyze" className="text-sm text-gray-700">
                <div className="font-medium">Запустить автоматический анализ сразу после создания</div>
                <div className="text-gray-500">Система проанализирует код и сгенерирует тесты</div>
              </label>
            </div>

            {formData.auto_analyze && (
              <div className="bg-green-50 border border-green-200 rounded-lg p-3">
                <p className="text-sm text-green-800">
                  ✅ Анализ будет запущен автоматически. Вы сможете отслеживать прогресс на странице проекта.
                </p>
              </div>
            )}
          </div>
        )}

        {error && (
          <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mt-4">
            {error}
          </div>
        )}

        <div className="flex justify-between pt-6">
          <div>
            {step > 1 && (
              <Button
                type="button"
                variant="secondary"
                onClick={prevStep}
                disabled={loading}
              >
                Назад
              </Button>
            )}
          </div>

          <div className="flex gap-2">
            {step < 3 ? (
              <Button
                type="button"
                onClick={nextStep}
                disabled={loading}
              >
                Далее
              </Button>
            ) : (
              <Button
                type="submit"
                loading={loading}
                disabled={!formData.name.trim()}
              >
                Создать проект
              </Button>
            )}
          </div>
        </div>
      </form>
    </Modal>
  );
};

export default ProjectForm;