import React, { useState } from 'react';
import { SessionList } from './components/SessionList';
import { MessageList } from './components/MessageList';
import { MessageInput } from './components/MessageInput';
import { SystemPromptEditor } from './components/SystemPromptEditor';
import { useChat } from './hooks/useChat';

export function App() {
  const {
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
  } = useChat();

  const [showPromptEditor, setShowPromptEditor] = useState(false);

  return (
    <div className="h-screen flex bg-gray-50">
      <SessionList
        sessions={sessions}
        currentSessionId={currentSessionId}
        onSelectSession={selectSession}
        onNewSession={newSession}
      />
      
      <div className="flex-1 flex flex-col">
        <div className="bg-white border-b border-gray-200 px-6 py-4">
          <div className="flex justify-between items-center">
            <h1 className="text-xl font-semibold text-gray-800">AI Assistant</h1>
            <button
              onClick={() => setShowPromptEditor(true)}
              className="px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700"
            >
              System Prompt
            </button>
          </div>
          {error && (
            <div className="mt-2 p-2 bg-red-100 border border-red-300 text-red-700 rounded">
              {error}
            </div>
          )}
        </div>
        
        <MessageList messages={messages} isStreaming={isStreaming} />
        
        <MessageInput onSendMessage={sendMessage} disabled={isStreaming} />
      </div>
      
      {showPromptEditor && (
        <SystemPromptEditor
          systemPrompt={systemPrompt}
          onUpdate={updateSystemPrompt}
          onClose={() => setShowPromptEditor(false)}
        />
      )}
    </div>
  );
}


