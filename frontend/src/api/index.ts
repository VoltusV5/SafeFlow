import axios from 'axios';

// Базовый URL API (при локальной разработке Vite проксирует запросы)
const API_URL = import.meta.env.VITE_API_URL || '/api/v1';

export const apiClient = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Интерцептор для добавления токена авторизации
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Интерцептор для обработки ошибок
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Здесь позже добавим логику перевыпуска токена или редиректа на авторизацию
      console.error('Unauthorized. Token might be expired.');
    }
    return Promise.reject(error);
  }
);
