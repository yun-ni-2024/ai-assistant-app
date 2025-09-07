import React, { useState, useEffect } from 'react';

interface SystemPromptEditorProps {
  systemPrompt: string;
  onUpdate: (prompt: string) => void;
  onClose: () => void;
}

export function SystemPromptEditor({ systemPrompt, onUpdate, onClose }: SystemPromptEditorProps) {
  const [prompt, setPrompt] = useState(systemPrompt);

  useEffect(() => {
    setPrompt(systemPrompt);
  }, [systemPrompt]);

  const handleSave = () => {
    onUpdate(prompt);
    onClose(); // Save and close
  };

  const handleCancel = () => {
    setPrompt(systemPrompt); // Restore to original value
    onClose(); // Cancel and close
  };

  const handleClose = () => {
    onClose(); // Close without saving
  };

  const handleReset = () => {
    const defaultPrompt = "You are a helpful AI assistant. When responding to users:\n\n1. Always start your response as a complete, independent statement\n2. Be conversational and helpful, but maintain your AI identity\n3. You have access to the full conversation history and should maintain context\n4. Respond naturally and engage with the user's questions or requests\n5. If the user asks about something from previous messages, reference it appropriately\n6. Keep responses clear, informative, and well-structured";
    setPrompt(defaultPrompt);
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 w-full max-w-4xl max-h-[80vh] flex flex-col">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-semibold">System Prompt Editor</h2>
          <button
            onClick={handleClose}
            className="text-gray-500 hover:text-gray-700 text-2xl"
            title="Close without saving"
          >
            ×
          </button>
        </div>
        
        <div className="flex-1 flex flex-col">
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Customize how the AI assistant behaves:
            </label>
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              className="w-full h-64 p-3 border border-gray-300 rounded-md font-mono text-sm resize-none"
              placeholder="Enter your custom system prompt here..."
            />
          </div>
          
          <div className="flex justify-between items-center">
            <div className="flex space-x-2">
              <button
                onClick={handleReset}
                className="px-4 py-2 text-sm bg-gray-200 text-gray-700 rounded hover:bg-gray-300"
              >
                Reset to Default
              </button>
            </div>
            
            <div className="flex space-x-2">
              <button
                onClick={handleCancel}
                className="px-4 py-2 text-sm bg-gray-200 text-gray-700 rounded hover:bg-gray-300"
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                className="px-4 py-2 text-sm bg-blue-600 text-white rounded hover:bg-blue-700"
              >
                Save & Close
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
