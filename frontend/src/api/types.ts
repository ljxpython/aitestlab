/**
 * API接口类型定义
 * 前后端统一规范
 */

// 基础响应接口
export interface BaseResponse<T = any> {
  code: number;
  message: string;
  data: T;
  timestamp?: string;
}

// 分页响应接口
export interface PageResponse<T = any> extends BaseResponse<T[]> {
  pagination: {
    page: number;
    pageSize: number;
    total: number;
    totalPages: number;
  };
}

// 文件上传接口
export interface FileUpload {
  filename: string;
  content: string; // base64编码
  content_type: string;
  size: number;
}

// 智能体类型枚举
export enum AgentType {
  REQUIREMENT_AGENT = 'requirement_agent',
  TESTCASE_AGENT = 'testcase_agent',
  USER_PROXY = 'user_proxy',
  SYSTEM = 'system',
}

// 智能体消息接口
export interface AgentMessage {
  id: string;
  content: string;
  agentType: AgentType;
  agentName: string;
  timestamp: string;
  roundNumber: number;
  isComplete?: boolean;
}

// 测试用例请求接口
export interface TestCaseRequest {
  conversation_id?: string;
  text_content?: string;
  files?: FileUpload[];
  round_number: number;
  user_feedback?: string;
}

// 测试用例响应接口
export interface TestCaseResponse {
  conversation_id: string;
  content: string;
  agent_type: AgentType;
  agent_name: string;
  round_number: number;
  is_complete: boolean;
  timestamp: string;
}

// SSE流式响应接口
export interface StreamResponse {
  source: string;
  content: string;
  agent_type: string;
  agent_name: string;
  conversation_id: string;
  round_number: number;
  is_complete: boolean;
  is_final: boolean;
  timestamp: string;
}

// 聊天消息接口
export interface ChatMessage {
  id: string;
  content: string;
  role: 'user' | 'assistant' | 'system';
  timestamp: string;
  conversation_id: string;
}

// 聊天请求接口
export interface ChatRequest {
  message: string;
  conversation_id?: string;
  files?: FileUpload[];
  model?: string;
  temperature?: number;
  max_tokens?: number;
}

// 聊天响应接口
export interface ChatResponse {
  message: ChatMessage;
  conversation_id: string;
  usage?: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
}

// 用户接口
export interface User {
  id: string;
  username: string;
  email: string;
  avatar?: string;
  created_at: string;
  updated_at: string;
}

// 登录请求接口
export interface LoginRequest {
  username: string;
  password: string;
}

// 登录响应接口
export interface LoginResponse {
  user: User;
  token: string;
  expires_in: number;
}

// 注册请求接口
export interface RegisterRequest {
  username: string;
  email: string;
  password: string;
  confirm_password: string;
}

// 错误响应接口
export interface ErrorResponse {
  code: number;
  message: string;
  details?: any;
  timestamp: string;
}

// 从配置文件导入常量
export { API_ENDPOINTS, HTTP_STATUS, BUSINESS_CODE } from '../config/api';
