import axios from 'axios';

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use(
  config => {
    const token = localStorage.getItem('authToken');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  error => {
    return Promise.reject(error);
  }
);

api.interceptors.response.use(
  response => response,
  error => {
    if (error.response && error.response.status === 401) {
      localStorage.removeItem('authToken');
      console.error("Unauthorized access, redirecting to login.");
    }
    return Promise.reject(error);
  }
);
export default api;

export const getApiCallStatistics = () => {
  return api.get('/api_keys/statistics/calls');
};

export const getApiKeysPaginated = (params) => {
  return api.get('/api_keys/paginated', { params });
};

export const bulkAddApiKeys = (data) => {
  return api.post('/api_keys/add-list', data);
};

export const createApiKey = (data) => {
  return api.post('/api_keys/', data);
};

export const updateApiKey = (id, data) => {
  return api.put(`/api_keys/${id}`, data);
};

export const deleteApiKey = (id) => {
  return api.delete(`/api_keys/${id}`);
};

export const bulkDeleteApiKeys = (data) => {
  return api.delete('/api_keys/bulk-delete', { data });
};

export const bulkCheckApiKeys = (key_ids) => {
  return api.post('/api_keys/bulk-check', { key_ids });
};

export const checkApiKey = (key_id) => {
  return api.post(`/api_keys/check/${key_id}`);
};

export const getAllConfig = () => {
  return api.get('/config/');
};

export const bulkSaveConfig = (data) => {
  return api.post('/config/bulk-save', data);
};