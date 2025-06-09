/**
 * 统一请求模块
 * 支持普通HTTP请求和SSE流式请求
 */

import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios';
import { getApiConfig } from '../config/api';

// 请求配置接口
export interface RequestConfig extends AxiosRequestConfig {
  showLoading?: boolean;
  showError?: boolean;
  timeout?: number;
}

// 响应数据接口
export interface ApiResponse<T = any> {
  code: number;
  message: string;
  data: T;
  timestamp?: string;
}

// SSE事件接口
export interface SSEEvent<T = any> {
  type: string;
  data: T;
  id?: string;
  retry?: number;
}

// SSE配置接口
export interface SSEConfig {
  url: string;
  data?: any;
  headers?: Record<string, string>;
  withCredentials?: boolean;
  onMessage?: (event: SSEEvent) => void;
  onError?: (error: Event) => void;
  onOpen?: (event: Event) => void;
  onClose?: (event: Event) => void;
  reconnect?: boolean;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
}

// 请求类
class RequestManager {
  private axiosInstance: AxiosInstance;
  private activeSSEConnections: Map<string, EventSource> = new Map();

  constructor() {
    this.axiosInstance = this.createAxiosInstance();
    this.setupInterceptors();
  }

  /**
   * 创建axios实例
   */
  private createAxiosInstance(): AxiosInstance {
    const config = getApiConfig();

    const instance = axios.create({
      baseURL: config.baseURL,
      timeout: config.timeout,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    return instance;
  }

  /**
   * 设置请求拦截器
   */
  private setupInterceptors(): void {
    // 请求拦截器
    this.axiosInstance.interceptors.request.use(
      (config) => {
        // 添加认证token
        const token = localStorage.getItem('token');
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }

        // 添加请求ID用于追踪
        config.headers['X-Request-ID'] = this.generateRequestId();

        console.log('发送请求:', {
          url: config.url,
          method: config.method,
          data: config.data,
          headers: config.headers,
        });

        return config;
      },
      (error) => {
        console.error('请求拦截器错误:', error);
        return Promise.reject(error);
      }
    );

    // 响应拦截器
    this.axiosInstance.interceptors.response.use(
      (response: AxiosResponse<ApiResponse>) => {
        console.log('收到响应:', {
          url: response.config.url,
          status: response.status,
          data: response.data,
        });

        // 统一处理响应格式
        if (response.data && typeof response.data === 'object') {
          return response;
        }

        // 包装非标准响应
        return {
          ...response,
          data: {
            code: 200,
            message: 'success',
            data: response.data,
          },
        };
      },
      (error) => {
        console.error('响应拦截器错误:', error);

        // 统一错误处理
        const errorResponse = {
          code: error.response?.status || 500,
          message: error.response?.data?.message || error.message || '请求失败',
          data: null,
        };

        return Promise.reject(errorResponse);
      }
    );
  }

  /**
   * 生成请求ID
   */
  private generateRequestId(): string {
    return `req_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  /**
   * GET请求
   */
  async get<T = any>(url: string, config?: RequestConfig): Promise<ApiResponse<T>> {
    const response = await this.axiosInstance.get<ApiResponse<T>>(url, config);
    return response.data;
  }

  /**
   * POST请求
   */
  async post<T = any>(url: string, data?: any, config?: RequestConfig): Promise<ApiResponse<T>> {
    const response = await this.axiosInstance.post<ApiResponse<T>>(url, data, config);
    return response.data;
  }

  /**
   * PUT请求
   */
  async put<T = any>(url: string, data?: any, config?: RequestConfig): Promise<ApiResponse<T>> {
    const response = await this.axiosInstance.put<ApiResponse<T>>(url, data, config);
    return response.data;
  }

  /**
   * DELETE请求
   */
  async delete<T = any>(url: string, config?: RequestConfig): Promise<ApiResponse<T>> {
    const response = await this.axiosInstance.delete<ApiResponse<T>>(url, config);
    return response.data;
  }

  /**
   * 文件上传
   */
  async upload<T = any>(url: string, file: File, config?: RequestConfig): Promise<ApiResponse<T>> {
    const formData = new FormData();
    formData.append('file', file);

    const uploadConfig: RequestConfig = {
      ...config,
      headers: {
        'Content-Type': 'multipart/form-data',
        ...config?.headers,
      },
    };

    const response = await this.axiosInstance.post<ApiResponse<T>>(url, formData, uploadConfig);
    return response.data;
  }

  /**
   * SSE流式请求
   */
  createSSEConnection(connectionId: string, config: SSEConfig): EventSource {
    // 关闭已存在的连接
    this.closeSSEConnection(connectionId);

    // 构建URL - 对于SSE，数据通过查询参数传递
    const url = this.buildSSEUrl(config.url, config.data);

    // 创建EventSource
    const eventSource = new EventSource(url, {
      withCredentials: config.withCredentials || false,
    });

    // 设置事件监听器
    this.setupSSEEventListeners(eventSource, config);

    // 存储连接
    this.activeSSEConnections.set(connectionId, eventSource);

    console.log('创建SSE连接:', { connectionId, url });

    return eventSource;
  }

  /**
   * 创建POST+SSE连接（先POST数据，然后建立SSE连接）
   */
  async createPostSSEConnection(connectionId: string, config: SSEConfig & { postData?: any }): Promise<EventSource> {
    // 关闭已存在的连接
    this.closeSSEConnection(connectionId);

    try {
      // 如果有POST数据，先发送POST请求
      if (config.postData) {
        const postResponse = await this.post(config.url.replace('/sse', ''), config.postData);
        console.log('POST请求成功:', postResponse);

        // 使用POST响应中的数据来建立SSE连接
        if (postResponse.data?.conversation_id) {
          config.data = {
            ...config.data,
            conversation_id: postResponse.data.conversation_id
          };
        }
      }

      // 建立SSE连接
      return this.createSSEConnection(connectionId, config);
    } catch (error) {
      console.error('POST+SSE连接失败:', error);
      throw error;
    }
  }

  /**
   * 构建SSE URL
   */
  private buildSSEUrl(baseUrl: string, data?: any): string {
    // 安全地获取baseURL
    const axiosBaseURL = this.axiosInstance.defaults.baseURL || '';
    const fullUrl = baseUrl.startsWith('http') ? baseUrl : `${axiosBaseURL}${baseUrl}`;

    if (!data) {
      return fullUrl;
    }

    // 将数据转换为查询参数
    const params = new URLSearchParams();
    Object.keys(data).forEach(key => {
      const value = data[key];
      if (value !== null && value !== undefined) {
        params.append(key, typeof value === 'object' ? JSON.stringify(value) : String(value));
      }
    });

    return `${fullUrl}?${params.toString()}`;
  }

  /**
   * 设置SSE事件监听器
   */
  private setupSSEEventListeners(eventSource: EventSource, config: SSEConfig): void {
    // 连接打开
    eventSource.onopen = (event) => {
      console.log('SSE连接已打开:', event);
      config.onOpen?.(event);
    };

    // 接收消息
    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        const sseEvent: SSEEvent = {
          type: 'message',
          data,
          id: event.lastEventId,
        };

        console.log('收到SSE消息:', sseEvent);
        config.onMessage?.(sseEvent);
      } catch (error) {
        console.error('解析SSE消息失败:', error, event.data);
      }
    };

    // 连接错误
    eventSource.onerror = (event) => {
      console.error('SSE连接错误:', event);
      config.onError?.(event);
    };

    // 自定义事件类型
    ['error', 'complete', 'progress'].forEach(eventType => {
      eventSource.addEventListener(eventType, (event: any) => {
        try {
          // 检查是否有数据
          if (!event.data) {
            console.log(`收到SSE ${eventType}事件（无数据）`);
            return;
          }

          const data = JSON.parse(event.data);
          const sseEvent: SSEEvent = {
            type: eventType,
            data,
            id: event.lastEventId,
          };

          console.log(`收到SSE ${eventType}事件:`, sseEvent);
          config.onMessage?.(sseEvent);
        } catch (error) {
          console.error(`解析SSE ${eventType}事件失败:`, error, 'event.data:', event.data);

          // 对于错误事件，即使解析失败也要通知
          if (eventType === 'error') {
            const sseEvent: SSEEvent = {
              type: eventType,
              data: { error: 'Parse failed', raw: event.data },
              id: event.lastEventId,
            };
            config.onMessage?.(sseEvent);
          }
        }
      });
    });
  }

  /**
   * 关闭SSE连接
   */
  closeSSEConnection(connectionId: string): void {
    const eventSource = this.activeSSEConnections.get(connectionId);
    if (eventSource) {
      eventSource.close();
      this.activeSSEConnections.delete(connectionId);
      console.log('关闭SSE连接:', connectionId);
    }
  }

  /**
   * 关闭所有SSE连接
   */
  closeAllSSEConnections(): void {
    this.activeSSEConnections.forEach((eventSource, connectionId) => {
      eventSource.close();
      console.log('关闭SSE连接:', connectionId);
    });
    this.activeSSEConnections.clear();
  }

  /**
   * 获取活跃的SSE连接数量
   */
  getActiveSSEConnectionsCount(): number {
    return this.activeSSEConnections.size;
  }
}

// 创建全局请求实例
export const request = new RequestManager();

// 导出类型
export type { RequestConfig, ApiResponse, SSEEvent, SSEConfig };
