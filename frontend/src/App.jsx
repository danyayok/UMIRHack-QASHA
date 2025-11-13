// src/App.jsx
import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Landing from './pages/Landing';
import Auth from './pages/Auth';
import Dashboard from './pages/Dashboard';
import ProjectAnalysisPage from './pages/ProjectAnalysisPage';
import ProjectTestsPage from './pages/ProjectTestsPage';
import { useAuth } from './hooks/useAuth';
import './index.css';

function App() {
  const { user, loading } = useAuth();

  if (loading) {
    return <div>Loading...</div>;
  }

  return (
    <Router>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/auth" element={<Auth />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/projects/:id/analysis/*" element={<ProjectAnalysisPage />} />
        <Route path="/projects/:id/tests/*" element={<ProjectTestsPage />} />
        <Route path="/projects/:id" element={<Navigate to="analysis" replace />} />
      </Routes>
    </Router>
  );
}

export default App;