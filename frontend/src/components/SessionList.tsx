import React from 'react';
import { Session } from '../types';

interface SessionListProps {
  sessions: Session[];
  currentSessionId: string | null;
  onSelectSession: (sessionId: string) => void;
  onNewSession: () => void;
}

export function SessionList({ 
  sessions, 
  currentSessionId, 
  onSelectSession, 
  onNewSession 
}: SessionListProps) {
  return (
    <div className="w-64 bg-gray-100 border-r border-gray-200 flex flex-col">
      <div className="p-4 border-b border-gray-200">
        <button
          onClick={onNewSession}
          className="w-full px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors"
        >
          新建对话
        </button>
      </div>
      
      <div className="flex-1 overflow-y-auto">
        {sessions.length === 0 ? (
          <div className="p-4 text-center text-gray-500">
            <p>暂无对话</p>
          </div>
        ) : (
          <div className="p-2 space-y-1">
            {sessions.map((session) => (
              <button
                key={session.id}
                onClick={() => onSelectSession(session.id)}
                className={`w-full text-left p-3 rounded-lg transition-colors ${
                  currentSessionId === session.id
                    ? 'bg-blue-100 text-blue-800'
                    : 'hover:bg-gray-200 text-gray-700'
                }`}
              >
                <div className="font-medium truncate">{session.title}</div>
                <div className="text-sm text-gray-500">
                  {new Date(session.createdAt).toLocaleDateString()}
                </div>
                <div className="text-xs text-gray-400">
                  {session.messages.length} 条消息
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
