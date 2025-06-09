/**
 * 聊天相关API
 */

import { useState } from 'react';
import { request } from '../utils/request';
import { useSSE } from '../hooks/useSSE';
import {
  ChatRequest,
  ChatResponse,
  ChatMessage,
  BaseResponse,
  API_ENDPOINTS,
} from './types';

/**
 * 聊天API服务
 */
export class ChatAPI {
  /**
   * 发送聊天消息（普通请求）
   */
  static async sendMessage(data: ChatRequest): Promise<BaseResponse<ChatResponse>> {
    return request.post<ChatResponse>(API_ENDPOINTS.CHAT.SEND, data);
  }

  /**
   * 发送聊天消息（流式请求）
   */
  static async sendMessageStream(data: ChatRequest): Promise<BaseResponse<ChatResponse>> {
    return request.post<ChatResponse>(API_ENDPOINTS.CHAT.STREAM, data);
  }

  /**
   * 获取聊天历史
   */
  static async getHistory(params: {
    conversation_id?: string;
    page?: number;
    pageSize?: number;
  }): Promise<BaseResponse<ChatMessage[]>> {
    return request.get(API_ENDPOINTS.CHAT.HISTORY, { params });
  }

  /**
   * 获取对话列表
   */
  static async getConversations(params: {
    page?: number;
    pageSize?: number;
  }): Promise<BaseResponse<any[]>> {
    return request.get(API_ENDPOINTS.CHAT.CONVERSATIONS, { params });
  }

  /**
   * 删除对话
   */
  static async deleteConversation(conversationId: string): Promise<BaseResponse<any>> {
    const url = API_ENDPOINTS.CHAT.DELETE_CONVERSATION.replace('{id}', conversationId);
    return request.delete(url);
  }
}

/**
 * SSE聊天Hook
 */
export const useChatSSE = () => {
  const {
    isConnected,
    isConnecting,
    error,
    connect,
    disconnect,
    connectionId,
  } = useSSE({
    url: API_ENDPOINTS.CHAT.STREAM,
    reconnect: true,
    maxReconnectAttempts: 3,
  });

  /**
   * 发送消息
   */
  const sendMessage = (data: ChatRequest, onMessage?: (message: ChatMessage) => void) => {
    return new Promise<ChatMessage>((resolve, reject) => {
      let finalMessage: ChatMessage | null = null;

      const config = {
        url: API_ENDPOINTS.CHAT.STREAM,
        data,
        onMessage: (event: any) => {
          try {
            const message: ChatMessage = event.data;
            console.log('收到聊天消息:', message);
            onMessage?.(message);
            finalMessage = message;
          } catch (error) {
            console.error('解析聊天消息失败:', error);
            reject(error);
          }
        },
        onError: (error: Event) => {
          console.error('聊天SSE连接错误:', error);
          reject(new Error('连接错误'));
        },
        onClose: () => {
          if (finalMessage) {
            resolve(finalMessage);
          } else {
            reject(new Error('未收到消息'));
          }
        },
      };

      // 创建连接
      request.createSSEConnection(connectionId, config);
    });
  };

  /**
   * 停止发送
   */
  const stopSending = () => {
    disconnect();
  };

  return {
    isConnected,
    isConnecting,
    error,
    sendMessage,
    stopSending,
    connectionId,
  };
};

/**
 * 聊天管理Hook
 */
export const useChat = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);

  const { sendMessage, stopSending, isConnected } = useChatSSE();

  /**
   * 发送消息
   */
  const send = async (content: string, files?: any[]) => {
    if (!content.trim()) return;

    // 添加用户消息
    const userMessage: ChatMessage = {
      id: `user_${Date.now()}`,
      content,
      role: 'user',
      timestamp: new Date().toISOString(),
      conversation_id: conversationId || '',
    };

    setMessages(prev => [...prev, userMessage]);
    setLoading(true);
    setError(null);

    try {
      const request: ChatRequest = {
        message: content,
        conversation_id: conversationId || undefined,
        files,
      };

      let assistantMessage = '';
      const assistantMessageId = `assistant_${Date.now()}`;

      await sendMessage(request, (message) => {
        assistantMessage += message.content;

        // 更新助手消息
        setMessages(prev => {
          const newMessages = [...prev];
          const existingIndex = newMessages.findIndex(m => m.id === assistantMessageId);

          const updatedMessage: ChatMessage = {
            id: assistantMessageId,
            content: assistantMessage,
            role: 'assistant',
            timestamp: message.timestamp,
            conversation_id: message.conversation_id,
          };

          if (existingIndex >= 0) {
            newMessages[existingIndex] = updatedMessage;
          } else {
            newMessages.push(updatedMessage);
          }

          return newMessages;
        });

        // 更新对话ID
        if (message.conversation_id && !conversationId) {
          setConversationId(message.conversation_id);
        }
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : '发送失败');
    } finally {
      setLoading(false);
    }
  };

  /**
   * 停止发送
   */
  const stop = () => {
    stopSending();
    setLoading(false);
  };

  /**
   * 清空聊天
   */
  const clear = () => {
    setMessages([]);
    setConversationId(null);
    setError(null);
  };

  /**
   * 加载历史消息
   */
  const loadHistory = async (convId?: string) => {
    try {
      const response = await ChatAPI.getHistory({
        conversation_id: convId || conversationId || undefined,
      });

      if (response.code === 0) {
        setMessages(response.data);
        if (convId) {
          setConversationId(convId);
        }
      }
    } catch (err) {
      setError('加载历史失败');
    }
  };

  return {
    messages,
    loading,
    error,
    conversationId,
    isConnected,
    send,
    stop,
    clear,
    loadHistory,
  };
};

export default ChatAPI;
