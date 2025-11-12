import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import Landing from './pages/Landing';
import Auth from './pages/Auth';
import Dashboard from './pages/Dashboard';
import ProjectPage from './pages/ProjectPage';

function requireAuth() {
  return !!localStorage.getItem('token');
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/auth" element={<Auth />} />
      <Route path="/dashboard" element={requireAuth() ? <Dashboard /> : <Navigate to="/auth" />} />
      <Route path="/projects/:id/*" element={requireAuth() ? <ProjectPage /> : <Navigate to="/auth" />} />
      <Route path="*" element={<Navigate to="/" />} />
    </Routes>
  );
}