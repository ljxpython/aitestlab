import { message } from 'antd';

const API_BASE_URL = '/api/auth';

// 用户信息接口
export interface User {
  id: number;
  username: string;
  email?: string;
  full_name?: string;
  avatar_url?: string;
  is_active: boolean;
  is_superuser: boolean;
  created_at?: string;
  updated_at?: string;
  last_login?: string;
}

// 登录响应接口
export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: User;
}

// 用户更新接口
export interface UserUpdate {
  email?: string;
  full_name?: string;
  avatar_url?: string;
}

// 获取认证头
const getAuthHeaders = () => {
  const token = localStorage.getItem('token');
  return {
    'Content-Type': 'application/json',
    ...(token && { 'Authorization': `Bearer ${token}` }),
  };
};

// 处理API响应
const handleResponse = async (response: Response) => {
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const errorMessage = errorData.detail || `HTTP ${response.status}: ${response.statusText}`;
    throw new Error(errorMessage);
  }
  return response.json();
};

// 用户登录
export const login = async (username: string, password: string): Promise<LoginResponse> => {
  try {
    const response = await fetch(`${API_BASE_URL}/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ username, password }),
    });

    return await handleResponse(response);
  } catch (error: any) {
    throw new Error(error.message || '登录失败');
  }
};

// 用户注册
export const register = async (userData: {
  username: string;
  password: string;
  email?: string;
  full_name?: string;
}): Promise<User> => {
  try {
    const response = await fetch(`${API_BASE_URL}/register`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(userData),
    });

    return await handleResponse(response);
  } catch (error: any) {
    throw new Error(error.message || '注册失败');
  }
};

// 获取当前用户信息
export const getCurrentUser = async (): Promise<User> => {
  try {
    const response = await fetch(`${API_BASE_URL}/me`, {
      method: 'GET',
      headers: getAuthHeaders(),
    });

    return await handleResponse(response);
  } catch (error: any) {
    throw new Error(error.message || '获取用户信息失败');
  }
};

// 更新用户信息
export const updateUser = async (userData: UserUpdate): Promise<User> => {
  try {
    const response = await fetch(`${API_BASE_URL}/me`, {
      method: 'PUT',
      headers: getAuthHeaders(),
      body: JSON.stringify(userData),
    });

    return await handleResponse(response);
  } catch (error: any) {
    throw new Error(error.message || '更新用户信息失败');
  }
};

// 修改密码
export const changePassword = async (oldPassword: string, newPassword: string): Promise<void> => {
  try {
    const response = await fetch(`${API_BASE_URL}/change-password`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({
        old_password: oldPassword,
        new_password: newPassword,
      }),
    });

    await handleResponse(response);
  } catch (error: any) {
    throw new Error(error.message || '修改密码失败');
  }
};

// 用户登出
export const logout = async (): Promise<void> => {
  try {
    const response = await fetch(`${API_BASE_URL}/logout`, {
      method: 'POST',
      headers: getAuthHeaders(),
    });

    await handleResponse(response);
  } catch (error: any) {
    // 即使服务器返回错误，也要清除本地存储
    console.warn('登出请求失败:', error.message);
  } finally {
    // 清除本地存储
    localStorage.removeItem('token');
    localStorage.removeItem('user');
  }
};

// 检查是否已登录
export const isAuthenticated = (): boolean => {
  const token = localStorage.getItem('token');
  return !!token;
};

// 获取本地存储的用户信息
export const getLocalUser = (): User | null => {
  try {
    const userStr = localStorage.getItem('user');
    return userStr ? JSON.parse(userStr) : null;
  } catch {
    return null;
  }
};

// 清除认证信息
export const clearAuth = (): void => {
  localStorage.removeItem('token');
  localStorage.removeItem('user');
};
