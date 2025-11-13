// src/components/features/tests/CICDForm.jsx
import React, { useState, useEffect } from 'react';
import { Button } from '../../ui';

const CICDForm = ({ project }) => {
  const [config, setConfig] = useState({
    provider: 'github-actions',
    branch: 'main',
    custom_branch: '',
    trigger_on_push: true,
    trigger_on_pr: true,
    run_tests: true,
    run_linting: true,
    run_security_scan: false,
    deploy_to: 'none',
    notifications: true,
    use_existing_config: false,
    existing_config_path: '.github/workflows/ci.yml'
  });

  const [hasExistingConfig, setHasExistingConfig] = useState(false);
  const [existingConfigs, setExistingConfigs] = useState([]);

  // Проверяем наличие существующих CI/CD конфигов
  useEffect(() => {
    const checkExistingConfigs = () => {
      const analysis = project.latest_analysis?.result;
      if (!analysis) return;

      const fileStructure = analysis.file_structure || {};
      const configFiles = Object.keys(fileStructure).filter(file =>
        file.includes('ci.yml') ||
        file.includes('.github/workflows') ||
        file.includes('.gitlab-ci.yml') ||
        file.includes('Jenkinsfile') ||
        file.includes('azure-pipelines.yml')
      );

      setHasExistingConfig(configFiles.length > 0);
      setExistingConfigs(configFiles);

      // Если есть конфиги, предлагаем первый по умолчанию
      if (configFiles.length > 0) {
        setConfig(prev => ({
          ...prev,
          existing_config_path: configFiles[0]
        }));
      }
    };

    checkExistingConfigs();
  }, [project]);

  const handleConfigChange = (key) => (e) => {
    const value = e.target.type === 'checkbox' ? e.target.checked : e.target.value;
    setConfig(prev => ({ ...prev, [key]: value }));
  };

  const generateCICD = () => {
    const finalConfig = {
      ...config,
      // Используем кастомную ветку если указана, иначе выбранную
      target_branch: config.custom_branch || config.branch,
      project_id: project.id,
      project_name: project.name,
      repo_url: project.repo_url
    };

    console.log('Генерация CI/CD конфигурации:', finalConfig);
    alert(`CI/CD конфигурация сгенерирована для ветки ${finalConfig.target_branch}!`);
  };

  const getExistingConfigOptions = () => {
    if (existingConfigs.length === 0) {
      return [<option key="none" value="">Не обнаружено конфигов</option>];
    }

    return existingConfigs.map(configPath => (
      <option key={configPath} value={configPath}>
        {configPath}
      </option>
    ));
  };

  return (
    <div className="bg-white rounded-lg border shadow-sm p-6">
      <h3 className="text-xl font-semibold mb-6">🚀 Генератор CI/CD конфигурации</h3>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <div className="space-y-6">
          <h4 className="font-medium text-gray-900">Настройки CI/CD</h4>

          {/* Провайдер CI/CD */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Провайдер CI/CD
            </label>
            <select
              value={config.provider}
              onChange={handleConfigChange('provider')}
              className="w-full p-2 border border-gray-300 rounded focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="github-actions">GitHub Actions</option>
              <option value="gitlab-ci">GitLab CI</option>
              <option value="jenkins">Jenkins</option>
              <option value="azure-pipelines">Azure Pipelines</option>
              <option value="custom">Кастомный</option>
            </select>
          </div>

          {/* Ветка для пуша */}
          <div className="space-y-3">
            <h5 className="font-medium text-gray-700">Ветка для запуска пайплайна</h5>

            <div className="grid grid-cols-2 gap-2">
              {['main', 'develop', 'master', 'release'].map(branch => (
                <label key={branch} className="flex items-center space-x-2">
                  <input
                    type="radio"
                    name="branch"
                    value={branch}
                    checked={config.branch === branch && !config.custom_branch}
                    onChange={handleConfigChange('branch')}
                    className="text-blue-600 focus:ring-blue-500"
                  />
                  <span className="text-sm text-gray-700">{branch}</span>
                </label>
              ))}
            </div>

            {/* Кастомная ветка */}
            <div className="flex items-center space-x-3">
              <input
                type="radio"
                name="branch"
                checked={!!config.custom_branch}
                onChange={() => setConfig(prev => ({ ...prev, custom_branch: prev.custom_branch || 'feature/' }))}
                className="text-blue-600 focus:ring-blue-500"
              />
              <input
                type="text"
                value={config.custom_branch}
                onChange={handleConfigChange('custom_branch')}
                placeholder="Введите название ветки"
                className="flex-1 p-2 border border-gray-300 rounded focus:ring-blue-500 focus:border-blue-500 text-sm"
              />
            </div>
          </div>

          {/* Использование существующего конфига */}
          {hasExistingConfig && (
            <div className="space-y-3 border-t pt-4">
              <label className="flex items-center space-x-3">
                <input
                  type="checkbox"
                  checked={config.use_existing_config}
                  onChange={handleConfigChange('use_existing_config')}
                  className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                <span className="text-sm text-gray-700">
                  <div className="font-medium">Использовать существующий CI/CD конфиг</div>
                  <div className="text-gray-500">Обновить найденный конфигурационный файл</div>
                </span>
              </label>

              {config.use_existing_config && (
                <div className="ml-6 space-y-2">
                  <label className="block text-sm font-medium text-gray-700">
                    Выберите конфигурационный файл
                  </label>
                  <select
                    value={config.existing_config_path}
                    onChange={handleConfigChange('existing_config_path')}
                    className="w-full p-2 border border-gray-300 rounded focus:ring-blue-500 focus:border-blue-500 text-sm"
                  >
                    {getExistingConfigOptions()}
                  </select>
                  <p className="text-xs text-gray-500">
                    Обнаружено {existingConfigs.length} конфигурационных файлов
                  </p>
                </div>
              )}
            </div>
          )}

          {/* Триггеры */}
          <div className="space-y-3">
            <h5 className="font-medium text-gray-700">Триггеры</h5>

            <label className="flex items-center space-x-3">
              <input
                type="checkbox"
                checked={config.trigger_on_push}
                onChange={handleConfigChange('trigger_on_push')}
                className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              />
              <span className="text-sm text-gray-700">
                Запускать при push в {config.custom_branch || config.branch} ветку
              </span>
            </label>

            <label className="flex items-center space-x-3">
              <input
                type="checkbox"
                checked={config.trigger_on_pr}
                onChange={handleConfigChange('trigger_on_pr')}
                className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              />
              <span className="text-sm text-gray-700">
                Запускать при создании Pull Request
              </span>
            </label>
          </div>

          {/* Этапы пайплайна */}
          <div className="space-y-3">
            <h5 className="font-medium text-gray-700">Этапы пайплайна</h5>

            <label className="flex items-center space-x-3">
              <input
                type="checkbox"
                checked={config.run_tests}
                onChange={handleConfigChange('run_tests')}
                className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              />
              <span className="text-sm text-gray-700">
                Запускать тесты
              </span>
            </label>

            <label className="flex items-center space-x-3">
              <input
                type="checkbox"
                checked={config.run_linting}
                onChange={handleConfigChange('run_linting')}
                className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              />
              <span className="text-sm text-gray-700">
                Проверка кода (linting)
              </span>
            </label>

            <label className="flex items-center space-x-3">
              <input
                type="checkbox"
                checked={config.run_security_scan}
                onChange={handleConfigChange('run_security_scan')}
                className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              />
              <span className="text-sm text-gray-700">
                Сканирование безопасности
              </span>
            </label>
          </div>

          {/* Уведомления */}
          <div className="space-y-3">
            <h5 className="font-medium text-gray-700">Уведомления</h5>

            <label className="flex items-center space-x-3">
              <input
                type="checkbox"
                checked={config.notifications}
                onChange={handleConfigChange('notifications')}
                className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              />
              <span className="text-sm text-gray-700">
                Отправлять уведомления о статусе сборки
              </span>
            </label>
          </div>
        </div>

        <div className="space-y-6">
          <h4 className="font-medium text-gray-900 border-b pb-2">Предпросмотр конфигурации</h4>

          {/* Карточка конфигурации */}
          <div className="bg-green-50 border border-green-200 rounded-lg p-4">
            <h4 className="font-medium text-green-900 mb-3">Конфигурация CI/CD</h4>
            <div className="text-sm text-green-800 space-y-2">
              <div className="flex justify-between">
                <span>Провайдер:</span>
                <strong>{config.provider}</strong>
              </div>
              <div className="flex justify-between">
                <span>Ветка:</span>
                <strong>{config.custom_branch || config.branch}</strong>
              </div>
              <div className="flex justify-between">
                <span>Триггеры:</span>
                <strong>
                  {[
                    config.trigger_on_push && 'push',
                    config.trigger_on_pr && 'PR'
                  ].filter(Boolean).join(', ')}
                </strong>
              </div>
              <div className="flex justify-between">
                <span>Этапы:</span>
                <strong>
                  {[
                    config.run_tests && 'тесты',
                    config.run_linting && 'linting',
                    config.run_security_scan && 'security'
                  ].filter(Boolean).join(', ')}
                </strong>
              </div>
              {config.use_existing_config && (
                <div className="flex justify-between">
                  <span>Базовый конфиг:</span>
                  <strong className="truncate max-w-xs">{config.existing_config_path}</strong>
                </div>
              )}
              <div className="flex justify-between border-t border-green-200 pt-2 mt-2">
                <span>Режим:</span>
                <strong>{config.use_existing_config ? 'Обновление' : 'Создание нового'}</strong>
              </div>
            </div>
          </div>

          {/* Кнопка генерации */}
          <Button
            onClick={generateCICD}
            variant="primary"
            size="large"
            className="w-full"
          >
            🚀 Сгенерировать CI/CD конфигурацию
          </Button>

          {/* Информация о проекте */}
          <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
            <h4 className="font-medium text-gray-900 mb-2">Проект</h4>
            <div className="text-sm text-gray-700 space-y-1">
              <p><strong>Название:</strong> {project.name}</p>
              <p><strong>Репозиторий:</strong> {project.repo_url || 'Не указан'}</p>
              <p><strong>Обнаружено CI/CD конфигов:</strong> {existingConfigs.length}</p>
              {hasExistingConfig && (
                <div className="mt-2">
                  <p className="font-medium text-sm">Найденные конфиги:</p>
                  <div className="text-xs text-gray-600 max-h-20 overflow-y-auto">
                    {existingConfigs.map(config => (
                      <div key={config}>• {config}</div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Подсказки */}
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
            <h5 className="font-medium text-blue-900 text-sm mb-1">💡 Подсказки</h5>
            <ul className="text-xs text-blue-800 space-y-1">
              <li>• Выберите ветку для которой будет работать CI/CD</li>
              <li>• Используйте существующий конфиг для обновления</li>
              <li>• Настройте триггеры под ваш workflow</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};

export default CICDForm;