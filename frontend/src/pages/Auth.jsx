import React, { useState } from 'react';
import { useAuth } from '../hooks/useAuth';
import { authAPI } from '../services/api';
import { Button } from '../components/ui';

export default function Auth() {
  const [mode, setMode] = useState('login');
  const [formData, setFormData] = useState({ email: '', password: '', full_name: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const { login } = useAuth();

  const handleSubmit = async (e) => {
      e.preventDefault();
      setLoading(true);
      setError('');

      try {
        if (mode === 'login') {
          const data = await authAPI.login(formData.email, formData.password);
          login(data.access_token, formData.email);
        } else {
          await authAPI.register(formData);
          setMode('login');
          setError('Регистрация успешна! Теперь войдите в систему.');
        }
      } catch (err) {
        setError(err.message || 'Произошла ошибка');
      } finally {
        setLoading(false);
      }
  };

  const handleChange = (field) => (e) => {
    setFormData(prev => ({ ...prev, [field]: e.target.value }));
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100">
      <div className="w-full max-w-md bg-white p-8 rounded-2xl shadow-lg">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">QA Autopilot</h1>
          <p className="text-gray-600">Автоматизация тестирования с ИИ</p>
        </div>

        <div className="flex border-b border-gray-200 mb-6">
          <button
            className={`flex-1 py-2 font-medium ${mode === 'login' ? 'text-blue-600 border-b-2 border-blue-600' : 'text-gray-500'}`}
            onClick={() => setMode('login')}
          >
            Вход
          </button>
          <button
            className={`flex-1 py-2 font-medium ${mode === 'register' ? 'text-blue-600 border-b-2 border-blue-600' : 'text-gray-500'}`}
            onClick={() => setMode('register')}
          >
            Регистрация
          </button>
        </div>

        {error && (
          <div className={`p-3 rounded mb-4 ${
            error.includes('успешна')
              ? 'bg-green-100 text-green-700 border border-green-200'
              : 'bg-red-100 text-red-700 border border-red-200'
          }`}>
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          {mode === 'register' && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Полное имя
              </label>
              <input
                type="text"
                value={formData.full_name}
                onChange={handleChange('full_name')}
                className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                placeholder="Иван Иванов"
              />
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Email
            </label>
            <input
              type="email"
              required
              value={formData.email}
              onChange={handleChange('email')}
              className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              placeholder="your@email.com"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Пароль
            </label>
            <input
              type="password"
              required
              value={formData.password}
              onChange={handleChange('password')}
              className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              placeholder="••••••••"
            />
          </div>

          <Button
            type="submit"
            loading={loading}
            className="w-full"
            size="large"
          >
            {mode === 'login' ? 'Войти' : 'Зарегистрироваться'}
          </Button>
        </form>
      </div>
    </div>
  );
}