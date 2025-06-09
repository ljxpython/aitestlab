/**
 * SSE Hook
 * 提供便捷的SSE连接管理
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import { request, SSEConfig, SSEEvent } from '../utils/request';

export interface UseSSEOptions {
  url: string;
  data?: any;
  autoConnect?: boolean;
  reconnect?: boolean;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
  onMessage?: (event: SSEEvent) => void;
  onError?: (error: Event) => void;
  onOpen?: (event: Event) => void;
  onClose?: (event: Event) => void;
}

export interface UseSSEReturn {
  isConnected: boolean;
  isConnecting: boolean;
  error: string | null;
  connect: (data?: any) => void;
  disconnect: () => void;
  reconnect: () => void;
  connectionId: string;
}

export const useSSE = (options: UseSSEOptions): UseSSEReturn => {
  const {
    url,
    data,
    autoConnect = false,
    reconnect: enableReconnect = true,
    reconnectInterval = 3000,
    maxReconnectAttempts = 5,
    onMessage,
    onError,
    onOpen,
    onClose,
  } = options;

  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const connectionIdRef = useRef<string>(`sse_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  /**
   * 连接SSE
   */
  const connect = useCallback((connectData?: any) => {
    if (isConnecting || isConnected) {
      return;
    }

    setIsConnecting(true);
    setError(null);

    const config: SSEConfig = {
      url,
      data: connectData || data,
      onOpen: (event) => {
        console.log('SSE连接已建立');
        setIsConnected(true);
        setIsConnecting(false);
        setError(null);
        reconnectAttemptsRef.current = 0;
        onOpen?.(event);
      },
      onMessage: (event) => {
        console.log('收到SSE消息:', event);
        onMessage?.(event);
      },
      onError: (event) => {
        console.error('SSE连接错误:', event);
        setIsConnected(false);
        setIsConnecting(false);
        setError('连接错误');
        onError?.(event);

        // 自动重连
        if (enableReconnect && reconnectAttemptsRef.current < maxReconnectAttempts) {
          scheduleReconnect();
        }
      },
      onClose: (event) => {
        console.log('SSE连接已关闭');
        setIsConnected(false);
        setIsConnecting(false);
        onClose?.(event);
      },
    };

    try {
      request.createSSEConnection(connectionIdRef.current, config);
    } catch (err) {
      console.error('创建SSE连接失败:', err);
      setIsConnecting(false);
      setError('创建连接失败');
    }
  }, [url, data, isConnecting, isConnected, enableReconnect, maxReconnectAttempts, onMessage, onError, onOpen, onClose]);

  /**
   * 断开SSE连接
   */
  const disconnect = useCallback(() => {
    // 清除重连定时器
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    // 关闭连接
    request.closeSSEConnection(connectionIdRef.current);

    setIsConnected(false);
    setIsConnecting(false);
    setError(null);
    reconnectAttemptsRef.current = 0;
  }, []);

  /**
   * 重新连接
   */
  const reconnectConnection = useCallback(() => {
    disconnect();
    setTimeout(() => {
      connect();
    }, 100);
  }, [disconnect, connect]);

  /**
   * 安排重连
   */
  const scheduleReconnect = useCallback(() => {
    if (reconnectAttemptsRef.current >= maxReconnectAttempts) {
      console.log('达到最大重连次数，停止重连');
      setError('连接失败，已达到最大重连次数');
      return;
    }

    reconnectAttemptsRef.current += 1;
    console.log(`安排第 ${reconnectAttemptsRef.current} 次重连，${reconnectInterval}ms 后执行`);

    reconnectTimeoutRef.current = setTimeout(() => {
      if (!isConnected) {
        connect();
      }
    }, reconnectInterval);
  }, [maxReconnectAttempts, reconnectInterval, isConnected, connect]);

  // 自动连接
  useEffect(() => {
    if (autoConnect) {
      connect();
    }

    // 清理函数
    return () => {
      disconnect();
    };
  }, [autoConnect]); // 只在autoConnect变化时执行

  // 组件卸载时清理
  useEffect(() => {
    return () => {
      disconnect();
    };
  }, [disconnect]);

  return {
    isConnected,
    isConnecting,
    error,
    connect,
    disconnect,
    reconnect: reconnectConnection,
    connectionId: connectionIdRef.current,
  };
};

/**
 * 简化的SSE Hook，用于单次请求
 */
export const useSSERequest = (url: string) => {
  const [data, setData] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const {
    isConnected,
    isConnecting,
    connect,
    disconnect,
  } = useSSE({
    url,
    onMessage: (event) => {
      if (event.data) {
        setData(prev => [...prev, event.data]);
      }
    },
    onOpen: () => {
      setLoading(true);
      setError(null);
      setData([]);
    },
    onError: (error) => {
      setLoading(false);
      setError('连接错误');
    },
    onClose: () => {
      setLoading(false);
    },
  });

  const sendRequest = useCallback((requestData?: any) => {
    setData([]);
    setError(null);
    connect(requestData);
  }, [connect]);

  const stopRequest = useCallback(() => {
    disconnect();
    setLoading(false);
  }, [disconnect]);

  return {
    data,
    loading: loading || isConnecting,
    error,
    isConnected,
    sendRequest,
    stopRequest,
  };
};

export default useSSE;
