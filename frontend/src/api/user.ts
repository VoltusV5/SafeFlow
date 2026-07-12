import { apiClient } from './index';

export interface SubscriptionInfo {
  plan: string;
  expires_at: string | null;
  is_active: boolean;
}

export interface User {
  id: number;
  telegram_id: number | null;
  username: string | null;
  email: string | null;
  balance: number;
  is_banned: boolean;
  created_at: string;
}

export interface UserMeResponse {
  user: User;
  active_subscription: SubscriptionInfo | null;
}

export const fetchUserProfile = async (): Promise<UserMeResponse> => {
  const response = await apiClient.get('/users/me');
  return response.data;
};
