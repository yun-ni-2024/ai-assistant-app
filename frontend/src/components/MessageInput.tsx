import React, { useState, KeyboardEvent, useRef } from 'react';

interface MessageInputProps {
  onSendMessage: (message: string, file?: File) => void;
  disabled: boolean;
}

export function MessageInput({ onSendMessage, disabled }: MessageInputProps) {
  const [message, setMessage] = useState('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      setSelectedFile(file);
    }
  };

  const uploadFile = async (file: File): Promise<string | null> => {
    try {
      setUploading(true);
      const formData = new FormData();
      formData.append('file', file);
      
      const response = await fetch('/api/chat/upload', {
        method: 'POST',
        body: formData,
      });
      
      if (!response.ok) {
        throw new Error('Upload failed');
      }
      
      const result = await response.json();
      return result.file_id;
    } catch (error) {
      console.error('File upload error:', error);
      return null;
    } finally {
      setUploading(false);
    }
  };

  const handleSubmit = async () => {
    if ((message.trim() || selectedFile) && !disabled && !uploading) {
      if (selectedFile) {
        // Upload file first
        const fileId = await uploadFile(selectedFile);
        if (fileId) {
          // Add file ID to message (hidden from user)
          const fileMessage = message.trim() + `\n[File ID: ${fileId}]`;
          onSendMessage(fileMessage);
        } else {
          alert('File upload failed, please try again');
          return;
        }
      } else {
        onSendMessage(message.trim());
      }
      
      setMessage('');
      setSelectedFile(null);
      // Reset file input
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const handleKeyPress = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleFileButtonClick = () => {
    fileInputRef.current?.click();
  };

  return (
    <div className="border-t bg-white p-4">
      <div className="flex flex-col space-y-2">
        {/* File selection row */}
        <div className="flex items-center space-x-2">
          <input
            ref={fileInputRef}
            type="file"
            accept=".txt,.md,.py,.js,.json,.csv,.html,.css,.yaml,.yml,.xml"
            onChange={handleFileSelect}
            className="hidden"
          />
          <button
            onClick={handleFileButtonClick}
            disabled={disabled}
            className="px-3 py-1 text-sm bg-gray-100 text-gray-700 rounded hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            📁 Select File
          </button>
          {selectedFile && (
            <span className="text-sm text-gray-600 truncate max-w-xs">
              {selectedFile.name}
            </span>
          )}
        </div>
        
        {/* Message input row */}
        <div className="flex space-x-2">
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Type a message or select a file... (Enter to send, Shift+Enter for new line)"
            disabled={disabled}
            className="flex-1 resize-none border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100 disabled:cursor-not-allowed"
            rows={1}
            style={{ minHeight: '40px', maxHeight: '120px' }}
          />
          <button
            onClick={handleSubmit}
            disabled={(!message.trim() && !selectedFile) || disabled || uploading}
            className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
          >
            {uploading ? 'Uploading...' : 'Send'}
          </button>
        </div>
      </div>
    </div>
  );
}
