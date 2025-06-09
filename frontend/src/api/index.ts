/**
 * API统一入口
 */

// 导出请求工具
export { request } from '../utils/request';
export type { RequestConfig, ApiResponse, SSEEvent, SSEConfig } from '../utils/request';

// 导出Hook
export { default as useSSE, useSSERequest } from '../hooks/useSSE';
export type { UseSSEOptions, UseSSEReturn } from '../hooks/useSSE';

// 导出类型定义
export * from './types';

// 导出API服务
export { default as TestCaseAPI, useTestCaseSSE, useTestCaseGeneration } from './testcase';
export { default as ChatAPI, useChatSSE, useChat } from './chat';

// 导出常量
export { API_ENDPOINTS, HTTP_STATUS, BUSINESS_CODE } from './types';
