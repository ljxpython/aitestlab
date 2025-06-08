/**
 * 测试用例生成API服务
 */

export interface FileUpload {
  filename: string;
  content_type: string;
  size: number;
  content: string; // base64编码的文件内容
}

export interface TestCaseRequest {
  conversation_id?: string;
  files?: FileUpload[];
  text_content?: string;
  user_feedback?: string;
  round_number: number;
}

export interface AgentMessage {
  id: string;
  content: string;
  agent_type: 'requirement_agent' | 'testcase_agent' | 'user_proxy';
  agent_name: string;
  timestamp: string;
  conversation_id: string;
  round_number: number;
}

export interface TestCaseResponse {
  conversation_id: string;
  agent_messages: AgentMessage[];
  is_complete: boolean;
  round_number: number;
  max_rounds: number;
}

export interface TestCaseStreamChunk {
  content: string;
  agent_type: 'requirement_agent' | 'testcase_agent' | 'user_proxy';
  agent_name: string;
  conversation_id: string;
  round_number: number;
  is_complete: boolean;
  timestamp?: string;
}

const API_BASE_URL = '/api/testcase';

/**
 * 上传文件
 */
export const uploadFiles = async (
  files: File[],
  textContent?: string,
  conversationId?: string
): Promise<{
  conversation_id: string;
  files: Array<{
    filename: string;
    content_type: string;
    size: number;
  }>;
  text_content?: string;
  message: string;
}> => {
  const formData = new FormData();

  files.forEach(file => {
    formData.append('files', file);
  });

  if (textContent) {
    formData.append('text_content', textContent);
  }

  if (conversationId) {
    formData.append('conversation_id', conversationId);
  }

  const response = await fetch(`${API_BASE_URL}/upload`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    throw new Error(`上传失败: ${response.status}`);
  }

  return response.json();
};

/**
 * 流式生成测试用例
 */
export const generateTestCaseStream = async (
  request: TestCaseRequest,
  onChunk: (chunk: TestCaseStreamChunk) => void,
  onError?: (error: Error) => void,
  onComplete?: () => void
): Promise<void> => {
  try {
    const response = await fetch(`${API_BASE_URL}/generate/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      throw new Error(`请求失败: ${response.status}`);
    }

    const reader = response.body?.getReader();
    if (!reader) {
      throw new Error('无法获取响应流');
    }

    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6));
            onChunk(data);

            if (data.is_complete) {
              onComplete?.();
              return;
            }
          } catch (e) {
            console.error('解析SSE数据失败:', e);
          }
        }
      }
    }
  } catch (error) {
    onError?.(error as Error);
  }
};

/**
 * 普通生成测试用例
 */
export const generateTestCase = async (request: TestCaseRequest): Promise<TestCaseResponse> => {
  const response = await fetch(`${API_BASE_URL}/generate`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error(`生成失败: ${response.status}`);
  }

  return response.json();
};

/**
 * 提交用户反馈
 */
export const submitFeedback = async (
  conversationId: string,
  feedback: string,
  roundNumber: number
): Promise<{
  message: string;
  conversation_id: string;
  next_round: number;
  max_rounds_reached: boolean;
}> => {
  const response = await fetch(`${API_BASE_URL}/feedback`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      conversation_id: conversationId,
      feedback,
      round_number: roundNumber,
    }),
  });

  if (!response.ok) {
    throw new Error(`提交反馈失败: ${response.status}`);
  }

  return response.json();
};

/**
 * 获取对话历史
 */
export const getConversation = async (conversationId: string): Promise<{
  conversation_id: string;
  messages: Array<{
    content: string;
    agent_type: string;
    agent_name: string;
    conversation_id: string;
    timestamp: string;
  }>;
  last_testcases: string;
}> => {
  const response = await fetch(`${API_BASE_URL}/conversation/${conversationId}`);

  if (!response.ok) {
    throw new Error(`获取对话失败: ${response.status}`);
  }

  return response.json();
};

/**
 * 删除对话
 */
export const deleteConversation = async (conversationId: string): Promise<{
  message: string;
  conversation_id: string;
}> => {
  const response = await fetch(`${API_BASE_URL}/conversation/${conversationId}`, {
    method: 'DELETE',
  });

  if (!response.ok) {
    throw new Error(`删除对话失败: ${response.status}`);
  }

  return response.json();
};

/**
 * 获取统计信息
 */
export const getTestCaseStats = async (): Promise<{
  active_conversations: number;
  max_rounds: number;
  service_status: string;
}> => {
  const response = await fetch(`${API_BASE_URL}/stats`);

  if (!response.ok) {
    throw new Error(`获取统计信息失败: ${response.status}`);
  }

  return response.json();
};

/**
 * 文件转换为base64
 */
export const fileToBase64 = (file: File): Promise<string> => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.readAsDataURL(file);
    reader.onload = () => {
      const result = reader.result as string;
      // 移除data:xxx;base64,前缀
      const base64 = result.split(',')[1];
      resolve(base64);
    };
    reader.onerror = error => reject(error);
  });
};

/**
 * 批量转换文件为FileUpload格式
 */
export const convertFilesToUploads = async (files: File[]): Promise<FileUpload[]> => {
  const uploads: FileUpload[] = [];

  for (const file of files) {
    try {
      const base64Content = await fileToBase64(file);
      uploads.push({
        filename: file.name,
        content_type: file.type || 'application/octet-stream',
        size: file.size,
        content: base64Content,
      });
    } catch (error) {
      console.error(`转换文件 ${file.name} 失败:`, error);
    }
  }

  return uploads;
};
