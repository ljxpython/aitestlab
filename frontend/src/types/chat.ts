export interface ChatMessage {
  id: string;
  content: string;
  role: 'user' | 'assistant' | 'system';
  timestamp: Date;
  isStreaming?: boolean;
}

export interface ChatRequest {
  message: string;
  conversation_id?: string;
  system_message?: string;
}

export interface ChatResponse {
  message: string;
  conversation_id: string;
  timestamp: string;
}

export interface StreamChunk {
  content: string;
  is_complete: boolean;
  conversation_id?: string;
}
