/**
 * 测试用例相关API
 */

import { useState } from 'react';
import { request } from '../utils/request';
import { useSSE } from '../hooks/useSSE';
import {
  TestCaseRequest,
  TestCaseResponse,
  StreamResponse,
  BaseResponse,
  API_ENDPOINTS,
} from './types';

/**
 * 测试用例API服务
 */
export class TestCaseAPI {
  /**
   * 生成测试用例（普通请求）
   */
  static async generate(data: TestCaseRequest): Promise<BaseResponse<TestCaseResponse>> {
    return request.post<TestCaseResponse>(API_ENDPOINTS.TESTCASE.GENERATE, data);
  }

  /**
   * 生成测试用例（流式请求）
   */
  static async generateStream(data: TestCaseRequest): Promise<BaseResponse<TestCaseResponse>> {
    return request.post<TestCaseResponse>(API_ENDPOINTS.TESTCASE.GENERATE_STREAM, data);
  }

  /**
   * 提交用户反馈
   */
  static async submitFeedback(data: {
    conversation_id: string;
    feedback: string;
    round_number: number;
  }): Promise<BaseResponse<any>> {
    return request.post(API_ENDPOINTS.TESTCASE.FEEDBACK, data);
  }

  /**
   * 获取历史记录
   */
  static async getHistory(params: {
    page?: number;
    pageSize?: number;
    conversation_id?: string;
  }): Promise<BaseResponse<TestCaseResponse[]>> {
    return request.get(API_ENDPOINTS.TESTCASE.HISTORY, { params });
  }

  /**
   * 导出测试用例
   */
  static async export(data: {
    conversation_id: string;
    format: 'excel' | 'pdf' | 'word';
  }): Promise<BaseResponse<{ download_url: string }>> {
    return request.post(API_ENDPOINTS.TESTCASE.EXPORT, data);
  }
}

/**
 * SSE测试用例生成Hook
 */
export const useTestCaseSSE = () => {
  const {
    isConnected,
    isConnecting,
    error,
    connect,
    disconnect,
    connectionId,
  } = useSSE({
    url: API_ENDPOINTS.TESTCASE.GENERATE_SSE,
    reconnect: true,
    maxReconnectAttempts: 3,
  });

  /**
   * 开始生成测试用例
   */
  const startGeneration = (data: TestCaseRequest, onMessage?: (event: StreamResponse) => void) => {
    return new Promise<void>((resolve, reject) => {
      const messages: StreamResponse[] = [];
      let isComplete = false;

      // 准备SSE查询参数
      const sseParams = {
        conversation_id: data.conversation_id || '',
        text_content: data.text_content || '',
        round_number: data.round_number || 1,
        user_feedback: data.user_feedback || ''
      };

      const config = {
        url: API_ENDPOINTS.TESTCASE.GENERATE_SSE,
        data: sseParams, // 通过查询参数传递数据
        onMessage: (event: any) => {
          try {
            const message: StreamResponse = event.data;
            messages.push(message);

            console.log('收到测试用例生成消息:', message);
            onMessage?.(message);

            // 检查是否完成
            if (message.is_complete || message.is_final) {
              isComplete = true;
              disconnect();
              resolve();
            }
          } catch (error) {
            console.error('解析SSE消息失败:', error);
            reject(error);
          }
        },
        onError: (error: Event) => {
          console.error('SSE连接错误:', error);
          if (!isComplete) {
            reject(new Error('连接错误'));
          }
        },
        onClose: () => {
          if (!isComplete) {
            resolve(); // 正常关闭也视为完成
          }
        },
      };

      // 创建连接
      request.createSSEConnection(connectionId, config);
    });
  };

  /**
   * 停止生成
   */
  const stopGeneration = () => {
    disconnect();
  };

  return {
    isConnected,
    isConnecting,
    error,
    startGeneration,
    stopGeneration,
    connectionId,
  };
};

/**
 * 简化的测试用例生成Hook
 */
export const useTestCaseGeneration = () => {
  const [messages, setMessages] = useState<StreamResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { startGeneration, stopGeneration, isConnected } = useTestCaseSSE();

  /**
   * 生成测试用例
   */
  const generate = async (data: TestCaseRequest) => {
    setMessages([]);
    setLoading(true);
    setError(null);

    try {
      await startGeneration(data, (message) => {
        setMessages(prev => [...prev, message]);
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : '生成失败');
    } finally {
      setLoading(false);
    }
  };

  /**
   * 停止生成
   */
  const stop = () => {
    stopGeneration();
    setLoading(false);
  };

  /**
   * 清空消息
   */
  const clear = () => {
    setMessages([]);
    setError(null);
  };

  return {
    messages,
    loading,
    error,
    isConnected,
    generate,
    stop,
    clear,
  };
};

export default TestCaseAPI;
