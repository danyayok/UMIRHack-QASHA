const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

class ApiError extends Error {
  constructor(message, status, details = null) {
    super(message);
    this.status = status;
    this.details = details;
    this.name = 'ApiError';
  }
}

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
      let errorDetails = null;
      try {
        errorDetails = await response.json();
      } catch {
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

  updateProjectRepo: (projectId, repoUrl, branch = null) => {
    const params = new URLSearchParams();
    params.append('repo_url', repoUrl);
    if (branch) {
      params.append('branch', branch);
    }

    return fetchWithAuth(`/projects/${projectId}/update-repo?${params.toString()}`, {
      method: 'PUT',
    });
  },

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


// test api
export const testsAPI = {
  generateTests: (projectId, config) =>
    fetchWithAuth(`/projects/${projectId}/generate-tests`, {
      method: 'POST',
      body: JSON.stringify(config),
    }),

  getTestTemplates: () =>
    fetchWithAuth('/tests/templates'),

  runTests: (projectId) =>
    fetchWithAuth(`/projects/${projectId}/run-tests`, {
      method: 'POST',
    }),

  getTestResults: (projectId) =>
    fetchWithAuth(`/projects/${projectId}/test-results`),
     runTests: (projectId) =>
    fetchWithAuth(`/projects/${projectId}/run-tests`, {
      method: 'POST',
    }),

  runSpecificTest: (projectId, testFile) =>
    fetchWithAuth(`/projects/${projectId}/run-tests/${encodeURIComponent(testFile)}`, {
      method: 'POST',
    }),

  getTestResults: (projectId) =>
    fetchWithAuth(`/projects/${projectId}/test-results`),

  generateTests: (projectId, config) =>
    fetchWithAuth(`/projects/${projectId}/generate-tests`, {
      method: 'POST',
      body: JSON.stringify(config),
    }),
  getTestHistory: (projectId) =>
    fetchWithAuth(`/projects/${projectId}/test-results`),

  getTestRunDetails: (runId) =>
    fetchWithAuth(`/tests/runs/${runId}`),

  rerunTests: (projectId, config = {}) =>
    fetchWithAuth(`/projects/${projectId}/run-tests`, {
      method: 'POST',
      body: JSON.stringify(config),
    }),
};

// generated testsссмисм
export const generatedTestsAPI = {
  // Пачки тестов
  getTestBatches: (projectId) =>
    fetchWithAuth(`/projects/${projectId}/test-batches`),

  getTestBatch: (projectId, batchId) =>
    fetchWithAuth(`/projects/${projectId}/test-batches/${batchId}`),

  getTestsFromBatch: (projectId, batchId) =>
    fetchWithAuth(`/projects/${projectId}/test-batches/${batchId}/tests`),

  pushBatchToRepository: (projectId, batchId, testIds = []) =>
    fetchWithAuth(`/projects/${projectId}/test-batches/${batchId}/push`, {
      method: 'POST',
      body: JSON.stringify({ test_ids: testIds }),
    }),

  deleteTestBatch: (projectId, batchId) =>
    fetchWithAuth(`/projects/${projectId}/test-batches/${batchId}`, {
      method: 'DELETE',
    }),

  downloadTestBatch: (projectId, batchId, format = 'zip') =>
    fetchWithAuth(`/projects/${projectId}/test-batches/${batchId}/download?format=${format}`),

  // Поиск тестов
  searchTests: (projectId, query, testType = null, framework = null) => {
    const params = new URLSearchParams({ query });
    if (testType) params.append('test_type', testType);
    if (framework) params.append('framework', framework);

    return fetchWithAuth(`/projects/${projectId}/test-batches/search?${params.toString()}`);
  },

  // Статистика по типам тестов
  getTestsByType: (projectId) =>
    fetchWithAuth(`/projects/${projectId}/tests/by-type`),

  // Массовое удаление тестов
  deleteBatchTests: (projectId, batchId, testIds) =>
    fetchWithAuth(`/projects/${projectId}/test-batches/${batchId}/tests`, {
      method: 'DELETE',
      body: JSON.stringify(testIds),
    }),
  // Статус отправки
  getPushStatus: (projectId, batchId) =>
    fetchWithAuth(`/projects/${projectId}/test-batches/${batchId}/push-status`),

};
// Health check
export const healthAPI = {
  check: () => fetch(`${BASE_URL}/health`).then(r => r.json())
};