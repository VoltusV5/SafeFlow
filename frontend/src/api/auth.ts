import { apiClient } from './index';

export const authTelegram = async (initData: string) => {
  const response = await apiClient.post('/auth/telegram', { initData });
  return response.data;
};

export const registerInit = async (email: string, password: string) => {
  const response = await apiClient.post('/auth/register-init', { email, password });
  return response.data;
};

export const registerConfirm = async (email: string, code: string) => {
  const response = await apiClient.post('/auth/register-confirm', { email, code });
  return response.data;
};

export const loginBasic = async (email: string, password: string) => {
  const response = await apiClient.post('/auth/login', { email, password });
  return response.data;
};

export const loginCodeInit = async (email: string) => {
  const response = await apiClient.post('/auth/login-code-init', { email });
  return response.data;
};

export const loginCodeConfirm = async (email: string, code: string) => {
  const response = await apiClient.post('/auth/login-code-confirm', { email, code });
  return response.data;
};
