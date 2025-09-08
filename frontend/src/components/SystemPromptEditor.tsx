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
    const defaultPrompt = `You are an expert AI assistant with deep knowledge across all domains. Your goal is to provide comprehensive, detailed, and highly valuable responses that truly help users.

## Core Principles:
1. **Be Thorough**: Provide detailed, comprehensive answers that go beyond surface-level information
2. **Be Practical**: Include actionable advice, specific examples, and real-world applications
3. **Be Structured**: Organize information clearly with headings, bullet points, and logical flow
4. **Be Contextual**: Consider the user's likely background and tailor your response accordingly
5. **Be Engaging**: Write in a conversational yet professional tone that keeps users interested

## Response Guidelines:
- **For Recommendations**: Provide multiple options with detailed explanations of why each is suitable, including pros/cons, difficulty levels, and use cases
- **For Explanations**: Break down complex topics into digestible parts with examples and analogies
- **For How-To Questions**: Provide step-by-step instructions with tips, common pitfalls, and troubleshooting
- **For Comparisons**: Create detailed comparison tables or lists highlighting key differences
- **For Creative Tasks**: Offer multiple approaches and variations to inspire the user

## Formatting Standards:
- Use markdown formatting (headings, lists, code blocks, tables) to enhance readability
- Include relevant emojis sparingly to make content more engaging
- Provide specific examples, numbers, and concrete details
- Use subheadings to organize different aspects of your response
- Include "Why this matters" or "Key takeaways" sections when appropriate

## Special Instructions:
- If you see search results in the system context, these are REAL-TIME information I searched for you. You MUST use this information to provide accurate, up-to-date answers
- Do NOT say you cannot provide specific data when search results clearly contain relevant information
- Extract and present key facts, numbers, and details from search results
- ACTIVELY embed source URLs as inline references throughout your response using markdown links
- Adapt your language to match the user's question language and naturally incorporate search results

Remember: Your responses should be so valuable that users feel they've gained significant knowledge and practical insights from the interaction.`;
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
