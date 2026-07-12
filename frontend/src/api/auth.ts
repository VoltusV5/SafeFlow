import { apiClient } from './index';

export const authTelegram = async (initData: string) => {
  const response = await apiClient.post('/auth/telegram', { initData });
  return response.data;
};
