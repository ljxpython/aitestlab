/**
 * API配置文件
 * 统一管理API相关配置
 */

import { getEnvironment, getApiBaseUrl, isDevelopment } from '../utils/env';

// API配置接口
export interface ApiConfig {
  baseURL: string;
  timeout: number;
  retryAttempts: number;
  retryDelay: number;
}

// 获取动态API基础URL
const apiBaseUrl = getApiBaseUrl();

// 默认配置
const defaultConfig: ApiConfig = {
  baseURL: apiBaseUrl,
  timeout: 30000,
  retryAttempts: 3,
  retryDelay: 1000,
};

// 开发环境配置
const developmentConfig: ApiConfig = {
  ...defaultConfig,
  timeout: 60000,
};

// 生产环境配置
const productionConfig: ApiConfig = {
  ...defaultConfig,
  timeout: 30000,
};

// 测试环境配置
const testConfig: ApiConfig = {
  ...defaultConfig,
  timeout: 10000,
};

/**
 * 获取API配置
 */
export function getApiConfig(): ApiConfig {
  const env = getEnvironment();

  switch (env) {
    case 'development':
      return developmentConfig;
    case 'production':
      return productionConfig;
    case 'test':
      return testConfig;
    default:
      return defaultConfig;
  }
}

/**
 * 设置自定义API配置
 */
export function setApiConfig(config: Partial<ApiConfig>): void {
  Object.assign(getApiConfig(), config);
}

/**
 * API端点配置
 */
export const API_ENDPOINTS = {
  // 认证相关
  AUTH: {
    LOGIN: '/auth/login',
    REGISTER: '/auth/register',
    LOGOUT: '/auth/logout',
    REFRESH: '/auth/refresh',
    PROFILE: '/auth/profile',
  },

  // 聊天相关
  CHAT: {
    SEND: '/chat/send',
    STREAM: '/chat/stream',
    HISTORY: '/chat/history',
    CONVERSATIONS: '/chat/conversations',
    DELETE_CONVERSATION: '/chat/conversations/{id}',
  },

  // 测试用例相关
  TESTCASE: {
    GENERATE: '/testcase/generate',
    GENERATE_STREAM: '/testcase/generate/stream',
    GENERATE_SSE: '/testcase/generate/sse',
    FEEDBACK: '/testcase/feedback',
    HISTORY: '/testcase/history',
    EXPORT: '/testcase/export',
  },

  // 文件相关
  FILE: {
    UPLOAD: '/file/upload',
    DOWNLOAD: '/file/download/{id}',
    DELETE: '/file/delete/{id}',
  },
} as const;

/**
 * HTTP状态码
 */
export const HTTP_STATUS = {
  OK: 200,
  CREATED: 201,
  NO_CONTENT: 204,
  BAD_REQUEST: 400,
  UNAUTHORIZED: 401,
  FORBIDDEN: 403,
  NOT_FOUND: 404,
  INTERNAL_SERVER_ERROR: 500,
} as const;

/**
 * 业务状态码
 */
export const BUSINESS_CODE = {
  SUCCESS: 0,
  INVALID_PARAMS: 1001,
  UNAUTHORIZED: 1002,
  FORBIDDEN: 1003,
  NOT_FOUND: 1004,
  INTERNAL_ERROR: 1005,
  RATE_LIMIT: 1006,
} as const;

// 导出当前配置
export const apiConfig = getApiConfig();

// 打印当前配置（仅在开发环境）
if (isDevelopment()) {
  console.log('API配置:', apiConfig);
}
