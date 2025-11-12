const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

class ApiError extends Error {
  constructor(message, status, details = null) {
    super(message);
    this.status = status;
    this.details = details;
    this.name = 'ApiError';
  }
}

// Улучшенный fetch с лучшей обработкой ошибок
async function fetchWithAuth(url, options = {}) {
  const token = localStorage.getItem('token');

  const config = {
    headers: {
      'Content-Type': 'application/json',
      ...(token && { Authorization: `Bearer ${token}` }),
      ...options.headers,
    },
    ...options,
  };

  // Для FormData убираем Content-Type
  if (options.body instanceof FormData) {
    delete config.headers['Content-Type'];
  }

  try {
    const response = await fetch(`${BASE_URL}${url}`, config);

    if (!response.ok) {
      // Пытаемся получить детали ошибки
      let errorDetails = null;
      try {
        errorDetails = await response.json();
      } catch {
        // Если не JSON, используем текст
        errorDetails = await response.text();
      }

      if (response.status === 401) {
        localStorage.removeItem('token');
        window.location.href = '/auth';
        throw new ApiError('Authentication required', 401, errorDetails);
      }

      const errorMessage = errorDetails?.detail || errorDetails?.message || `HTTP error! status: ${response.status}`;
      throw new ApiError(errorMessage, response.status, errorDetails);
    }

    // Для пустых ответов
    if (response.status === 204) {
      return null;
    }

    return response.json();
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    // Сетевые ошибки
    throw new ApiError(`Network error: ${error.message}`, 0, { originalError: error.message });
  }
}

// Auth API
export const authAPI = {
  login: async (email, password) => {
    const formData = new URLSearchParams();
    formData.append('username', email);
    formData.append('password', password);

    const response = await fetch(`${BASE_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: formData.toString(),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new ApiError(errorData.detail || 'Login failed', response.status, errorData);
    }

    return response.json();
  },

  register: async (userData) => {
    return fetchWithAuth('/auth/register', {
      method: 'POST',
      body: JSON.stringify(userData),
    });
  },
};

// Projects API
export const projectsAPI = {
  getProjects: () => fetchWithAuth('/projects'),

  getProject: (id) => fetchWithAuth(`/projects/${id}`),

  createProject: async (formData) => {
    const token = localStorage.getItem('token');
    const response = await fetch(`${BASE_URL}/projects`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
      },
      body: formData,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new ApiError(errorData.detail || 'Create project failed', response.status, errorData);
    }

    return response.json();
  },

  updateProjectRepo: (projectId, repoUrl, branch = 'main') =>
    fetchWithAuth(`/projects/${projectId}/update-repo?repo_url=${encodeURIComponent(repoUrl)}&branch=${branch}`, {
      method: 'PUT',
    }),

  analyzeProject: (projectId) =>
    fetchWithAuth(`/projects/${projectId}/analyze`, {
      method: 'POST',
    }),

  getLatestAnalysis: (projectId) =>
    fetchWithAuth(`/projects/${projectId}/analysis/latest`).catch(() => null),

  getAnalysisStatus: (analysisId) =>
    fetchWithAuth(`/projects/analysis/${analysisId}/status`),

  getProjectAnalyses: (projectId) =>
    fetchWithAuth(`/projects/${projectId}/analyses`),
  deleteProject: (projectId) =>
    fetchWithAuth(`/projects/${projectId}`, {
      method: 'DELETE',
    }),
};

// Health check
export const healthAPI = {
  check: () => fetch(`${BASE_URL}/health`).then(r => r.json())
};