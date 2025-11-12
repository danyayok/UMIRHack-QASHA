import React from 'react';
import { useNavigate } from 'react-router-dom';

export default function Landing() {
  const nav = useNavigate();
  return (
    <div className="min-h-screen flex items-center justify-center gradient-bg">
      <div className="text-center text-white">
        <h1 className="text-5xl font-bold mb-6">QA Autopilot</h1>
        <p className="mb-8 text-xl opacity-90">Автоматизация тестирования с ИИ</p>
        <button
          onClick={() => nav('/auth')}
          className="px-8 py-4 bg-white text-blue-600 rounded-lg shadow-lg hover:bg-gray-100 transition text-lg font-semibold"
        >
          НАЧАТЬ
        </button>
      </div>
    </div>
  );
}