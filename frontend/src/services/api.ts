import axios from 'axios';
import { ChatRequest, ChatResponse } from '@/types/chat';

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
});

// 请求拦截器
api.interceptors.request.use(
  (config) => {
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// 响应拦截器
api.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    console.error('API Error:', error);
    return Promise.reject(error);
  }
);

export const chatApi = {
  // 普通聊天
  chat: async (request: ChatRequest): Promise<ChatResponse> => {
    const response = await api.post('/chat/', request);
    return response.data;
  },

  // 流式聊天
  chatStream: (request: ChatRequest): EventSource => {
    const url = new URL('/api/chat/stream', window.location.origin);

    const eventSource = new EventSource(url.toString());

    // 发送请求数据
    fetch('/api/chat/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });

    return eventSource;
  },

  // 清除对话
  clearConversation: async (conversationId: string) => {
    const response = await api.delete(`/chat/conversation/${conversationId}`);
    return response.data;
  },
};

export default api;
