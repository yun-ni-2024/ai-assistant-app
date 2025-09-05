export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
}

export interface Session {
  id: string;
  title: string;
  createdAt: string;
  messages: Message[];
}

export interface CreateChatRequest {
  session_id?: string;
  user_message: string;
}

export interface CreateChatResponse {
  stream_id: string;
  session_id: string;
}

export interface StreamEvent {
  delta: string;
  done: boolean;
}
