import React from 'react';
import { useAuth } from '../../hooks/useAuth';

const Header = ({ title, actions }) => {
  const { user, logout } = useAuth();

  // Извлекаем имя из email
  const getUserName = () => {
    if (!user?.email) return 'User';

    const emailPart = user.email.split('@')[0];

    if (emailPart.includes('.')) {
      return emailPart.split('.')[0];
    }

    return emailPart;
  };

  const userName = getUserName();

  return (
    <header className="bg-white border-b border-gray-200 px-6 py-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <h1 className="text-2xl font-bold text-gray-900">{title}</h1>
          {actions && (
            <div className="flex items-center space-x-2">
              {actions}
            </div>
          )}
        </div>

        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 bg-blue-600 rounded-full flex items-center justify-center">
              <span className="text-white text-sm font-medium">
                {userName.charAt(0).toUpperCase()}
              </span>
            </div>
            <div className="hidden md:block">
              <div className="text-sm font-medium text-gray-900">
                {userName}
              </div>
              <div className="text-xs text-gray-500">
                {user?.email}
              </div>
            </div>
            <button
              onClick={logout}
              className="text-sm text-gray-500 hover:text-gray-700 transition-colors"
            >
              Выйти
            </button>
          </div>
        </div>
      </div>
    </header>
  );
};

export default Header;