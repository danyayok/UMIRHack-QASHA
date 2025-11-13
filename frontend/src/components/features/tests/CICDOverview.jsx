// src/components/features/tests/CICDOverview.jsx
import React, { useState } from 'react';
import { Button } from '../../ui';

const CICDOverview = ({ project }) => {
  const [pipelines, setPipelines] = useState([
    {
      id: 1,
      name: 'GitHub Actions',
      status: 'active',
      lastRun: '2024-01-15T10:30:00Z',
      duration: '2m 15s',
      success: true
    },
    {
      id: 2,
      name: 'Docker Build',
      status: 'inactive',
      lastRun: null,
      duration: null,
      success: null
    }
  ]);

  const [integrations, setIntegrations] = useState([
    { name: 'GitHub', connected: true, type: 'repository' },
    { name: 'Slack', connected: true, type: 'notifications' },
    { name: 'Jira', connected: false, type: 'issues' },
    { name: 'Docker Hub', connected: false, type: 'registry' }
  ]);

  const togglePipeline = (pipelineId) => {
    setPipelines(prev => prev.map(pipeline =>
      pipeline.id === pipelineId
        ? { ...pipeline, status: pipeline.status === 'active' ? 'inactive' : 'active' }
        : pipeline
    ));
  };

  const toggleIntegration = (integrationName) => {
    setIntegrations(prev => prev.map(integration =>
      integration.name === integrationName
        ? { ...integration, connected: !integration.connected }
        : integration
    ));
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'active': return 'text-green-600 bg-green-100';
      case 'inactive': return 'text-gray-600 bg-gray-100';
      case 'failed': return 'text-red-600 bg-red-100';
      default: return 'text-yellow-600 bg-yellow-100';
    }
  };

  const getIntegrationIcon = (type) => {
    switch (type) {
      case 'repository': return '📁';
      case 'notifications': return '🔔';
      case 'issues': return '🎫';
      case 'registry': return '🐳';
      default: return '🔗';
    }
  };

  return (
    <div className="space-y-6">
      {/* CI/CD Pipelines */}
      <div className="bg-white rounded-lg border shadow-sm p-6">
        <h3 className="text-xl font-semibold mb-4">CI/CD Pipelines</h3>

        <div className="space-y-4">
          {pipelines.map(pipeline => (
            <div key={pipeline.id} className="flex items-center justify-between p-4 border rounded-lg">
              <div className="flex items-center space-x-4">
                <div className={`px-3 py-1 rounded-full text-sm font-medium ${getStatusColor(pipeline.status)}`}>
                  {pipeline.status === 'active' ? 'Активен' : 'Неактивен'}
                </div>
                <div>
                  <div className="font-medium">{pipeline.name}</div>
                  {pipeline.lastRun && (
                    <div className="text-sm text-gray-500">
                      Последний запуск: {new Date(pipeline.lastRun).toLocaleString()}
                    </div>
                  )}
                </div>
              </div>
              <div className="flex items-center space-x-4">
                {pipeline.lastRun && (
                  <>
                    <span className="text-sm text-gray-500">
                      Длительность: {pipeline.duration}
                    </span>
                    <span className={`text-lg ${pipeline.success ? 'text-green-500' : 'text-red-500'}`}>
                      {pipeline.success ? '✅' : '❌'}
                    </span>
                  </>
                )}
                <Button
                  variant={pipeline.status === 'active' ? 'danger' : 'primary'}
                  size="small"
                  onClick={() => togglePipeline(pipeline.id)}
                >
                  {pipeline.status === 'active' ? 'Отключить' : 'Активировать'}
                </Button>
              </div>
            </div>
          ))}
        </div>

        <div className="mt-6">
          <Button variant="primary">
            + Добавить новый pipeline
          </Button>
        </div>
      </div>

      {/* Интеграции */}
      <div className="bg-white rounded-lg border shadow-sm p-6">
        <h3 className="text-xl font-semibold mb-4">Интеграции</h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {integrations.map(integration => (
            <div key={integration.name} className="flex items-center justify-between p-4 border rounded-lg">
              <div className="flex items-center space-x-3">
                <span className="text-2xl">{getIntegrationIcon(integration.type)}</span>
                <div>
                  <div className="font-medium">{integration.name}</div>
                  <div className="text-sm text-gray-500 capitalize">{integration.type}</div>
                </div>
              </div>
              <Button
                variant={integration.connected ? 'secondary' : 'primary'}
                size="small"
                onClick={() => toggleIntegration(integration.name)}
              >
                {integration.connected ? 'Отключить' : 'Подключить'}
              </Button>
            </div>
          ))}
        </div>
      </div>

      {/* Настройки CI/CD */}
      <div className="bg-white rounded-lg border shadow-sm p-6">
        <h3 className="text-xl font-semibold mb-4">Настройки CI/CD</h3>

        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="font-medium">Автозапуск тестов при push</div>
              <div className="text-sm text-gray-500">Автоматически запускать тесты при обновлении кода</div>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input type="checkbox" className="sr-only peer" defaultChecked />
              <div className="w-11 h-6 bg-gray-200 peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
            </label>
          </div>

          <div className="flex items-center justify-between">
            <div>
              <div className="font-medium">Уведомления в Slack</div>
              <div className="text-sm text-gray-500">Отправлять уведомления о результатах тестов</div>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input type="checkbox" className="sr-only peer" defaultChecked />
              <div className="w-11 h-6 bg-gray-200 peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
            </label>
          </div>

          <div className="flex items-center justify-between">
            <div>
              <div className="font-medium">Создание issues при падении тестов</div>
              <div className="text-sm text-gray-500">Автоматически создавать задачи при провале тестов</div>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input type="checkbox" className="sr-only peer" />
              <div className="w-11 h-6 bg-gray-200 peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
            </label>
          </div>
        </div>
      </div>
    </div>
  );
};

export default CICDOverview;