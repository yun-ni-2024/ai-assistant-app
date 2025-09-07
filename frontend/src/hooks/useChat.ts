import { useState, useCallback } from 'react';
import { Message, Session, CreateChatRequest, CreateChatResponse, StreamEvent } from '../types';

export function useChat() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [systemPrompt, setSystemPrompt] = useState<string>(() => {
    // Load from localStorage or use default
    const saved = localStorage.getItem('ai-assistant-system-prompt');
    return saved || "You are a helpful AI assistant. When responding to users:\n\n1. Always start your response as a complete, independent statement\n2. Be conversational and helpful, but maintain your AI identity\n3. You have access to the full conversation history and should maintain context\n4. Respond naturally and engage with the user's questions or requests\n5. If the user asks about something from previous messages, reference it appropriately\n6. Keep responses clear, informative, and well-structured";
  });

  const currentSession = sessions.find(s => s.id === currentSessionId);

  const createMessage = (role: 'user' | 'assistant', content: string): Message => ({
    id: Math.random().toString(36).substr(2, 9),
    role,
    content,
    timestamp: new Date().toISOString(),
  });

  const sendMessage = useCallback(async (userMessage: string) => {
    if (!userMessage.trim()) return;

    setError(null);
    setIsStreaming(true);

    // Add user message immediately
    const userMsg = createMessage('user', userMessage);
    setMessages(prev => [...prev, userMsg]);

    try {
      // Step 1: Create chat request
      // Check if user message requires search (don't override system prompt for search queries)
      const needsSearch = /最新|今天|现在|当前|实时|新闻|天气|股价|价格|时间/.test(userMessage);
      
      const createRequest: CreateChatRequest = {
        session_id: currentSessionId || undefined,
        user_message: userMessage,
        system_prompt: needsSearch ? undefined : systemPrompt, // Use default system prompt for search queries
      };
      
      console.log('🔍 Sending request with system prompt:', systemPrompt.substring(0, 100) + '...');

      const createResponse = await fetch('/api/chat/create', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(createRequest),
      });

      if (!createResponse.ok) {
        throw new Error(`HTTP ${createResponse.status}: ${createResponse.statusText}`);
      }

      const createData: CreateChatResponse = await createResponse.json();
      
      // Update current session ID if this is a new session
      if (!currentSessionId) {
        setCurrentSessionId(createData.session_id);
        
        // Create new session
        const newSession: Session = {
          id: createData.session_id,
          title: userMessage.slice(0, 40) || 'New Chat',
          createdAt: new Date().toISOString(),
          messages: [userMsg],
        };
        setSessions(prev => [newSession, ...prev]);
      } else {
        // Update existing session
        setSessions(prev => prev.map(s => 
          s.id === currentSessionId 
            ? { ...s, messages: [...s.messages, userMsg] }
            : s
        ));
      }

      // Step 2: Stream response
      const eventSource = new EventSource(`/api/chat/stream/${createData.stream_id}`);
      
      let assistantContent = '';
      const assistantMsg = createMessage('assistant', '');
      
      // Add assistant message placeholder immediately
      setMessages(prev => [...prev, assistantMsg]);
      
      eventSource.onmessage = (event) => {
        console.log('🔍 SSE raw event data:', event.data);
        try {
          const data: StreamEvent = JSON.parse(event.data);
          console.log('🔍 Parsed SSE data:', data);
          
          if (data.delta) {
            console.log('🔍 Processing delta:', data.delta);
            assistantContent += data.delta;
            console.log('🔍 Updated assistantContent:', assistantContent);
            setMessages(prev => {
              const updated = [...prev];
              const lastMsg = updated[updated.length - 1];
              if (lastMsg && lastMsg.role === 'assistant' && lastMsg.id === assistantMsg.id) {
                lastMsg.content = assistantContent;
                console.log('🔍 Updated last message content:', lastMsg.content);
              } else {
                console.log('🔍 Could not find matching assistant message to update');
              }
              return updated;
            });
          }
          
          if (data.done) {
            console.log('🔍 Stream done, final content:', assistantContent);
            eventSource.close();
            setIsStreaming(false);
            
            // Update session with final assistant message
            if (currentSessionId) {
              const finalAssistantMsg = { ...assistantMsg, content: assistantContent };
              console.log('🔍 Updating session with final assistant message:', finalAssistantMsg);
              setSessions(prev => {
                const updated = prev.map(s => 
                  s.id === currentSessionId 
                    ? { ...s, messages: [...s.messages, finalAssistantMsg] }
                    : s
                );
                console.log('🔍 Updated sessions:', updated.map(s => ({ id: s.id, title: s.title, messageCount: s.messages.length })));
                return updated;
              });
            }
          }
        } catch (err) {
          console.error('Error parsing SSE data:', err);
        }
      };

      eventSource.onerror = (err) => {
        console.error('SSE error:', err);
        eventSource.close();
        setIsStreaming(false);
        setError('Connection interrupted, please try again');
      };

    } catch (err) {
      console.error('Error sending message:', err);
      setIsStreaming(false);
      setError(err instanceof Error ? err.message : 'Failed to send message, please try again');
    }
  }, [currentSessionId, systemPrompt]);

  const selectSession = useCallback(async (sessionId: string) => {
    console.log('🔍 selectSession called with:', sessionId);
    console.log('🔍 Available sessions:', sessions.map(s => ({ id: s.id, title: s.title, messageCount: s.messages.length })));
    
    setCurrentSessionId(sessionId);
    setError(null);
    
    try {
      // Fetch latest messages from backend to ensure data consistency
      const response = await fetch(`/api/chat/sessions/${sessionId}/messages`);
      if (response.ok) {
        const messages = await response.json();
        console.log('🔍 Loaded messages from backend:', messages);
        setMessages(messages);
      } else {
        // Fallback to local session data if API fails
        const session = sessions.find(s => s.id === sessionId);
        console.log('🔍 Fallback to local session:', session);
        if (session) {
          console.log('🔍 Session messages:', session.messages);
          setMessages([...session.messages]);
        } else {
          console.log('🔍 No session found, clearing messages');
          setMessages([]);
        }
      }
    } catch (error) {
      console.error('🔍 Error loading messages:', error);
      // Fallback to local session data
      const session = sessions.find(s => s.id === sessionId);
      if (session) {
        setMessages([...session.messages]);
      } else {
        setMessages([]);
      }
    }
  }, [sessions]);

  const newSession = useCallback(() => {
    setCurrentSessionId(null);
    setMessages([]);
    setError(null);
  }, []);

  const updateSystemPrompt = useCallback((newPrompt: string) => {
    setSystemPrompt(newPrompt);
    localStorage.setItem('ai-assistant-system-prompt', newPrompt);
  }, []);

  return {
    sessions,
    currentSessionId,
    messages,
    isStreaming,
    error,
    systemPrompt,
    sendMessage,
    selectSession,
    newSession,
    updateSystemPrompt,
  };
}
