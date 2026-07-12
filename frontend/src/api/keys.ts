import { apiClient } from './index';

export interface VpnKey {
  id: number;
  server_id: number;
  protocol: string;
  internal_ip: string | null;
  client_uuid: string | null;
  config_data: string;
  status: string;
  expires_at: string | null;
}

export const fetchMyKeys = async (): Promise<VpnKey[]> => {
  const response = await apiClient.get('/keys/my');
  return response.data;
};
