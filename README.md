# AI Assistant App

A modern web application that provides AI-powered conversational assistance with real-time streaming responses, conversation memory, and customizable system prompts.

**Version**: 1.5.0 - Complete MCP tool framework with file upload support

## 🚀 Features

- **Real-time AI Chat**: Interactive conversations with AI using streaming responses
- **Multiple Conversations**: Support for multiple concurrent conversation sessions
- **Custom System Prompts**: Edit and customize AI behavior with real-time system prompt editor
- **MCP Tool Framework**: Configurable Model Context Protocol tool system with dynamic loading and complete decoupling
- **Three MCP Tools**: Web search, content fetching, and file analysis with intelligent content processing
- **Markdown Rendering**: Rich text formatting with proper link embedding and source citations
- **Multilingual Support**: Full internationalization with adaptive language responses
- **Streaming Responses**: Real-time token-by-token response streaming using Server-Sent Events (SSE)
- **Modern UI**: Clean and responsive React-based user interface with English interface

## 🏗️ Technical Architecture

### Frontend
- **Framework**: React 18.3.1 with TypeScript
- **Build Tool**: Vite 5.4.1
- **Styling**: Tailwind CSS with Typography plugin
- **Markdown**: React Markdown with GitHub Flavored Markdown support
- **State Management**: React Hooks (useState, useCallback)
- **HTTP Client**: Native Fetch API with EventSource for SSE

### Backend
- **Framework**: FastAPI 0.111.0
- **Language**: Python 3.x
- **Database**: SQLite with custom connection management
- **LLM Integration**: DeepSeek V3.1 model via OpenRouter API
- **MCP Tools**: Unified tool framework with Google Custom Search API, web content fetching, and file analysis
- **Tool Configuration**: YAML-based tool configuration with dynamic loading
- **Streaming**: Server-Sent Events (SSE) for real-time responses

### AI Model
- **Primary Model**: `deepseek/deepseek-chat-v3.1:free`
- **Provider**: OpenRouter API

## 📁 Project Structure

```
ai-assistant-app/
├── frontend/                 # React frontend application
│   ├── src/
│   │   ├── components/       # React components
│   │   │   ├── MessageInput.tsx
│   │   │   ├── MessageList.tsx
│   │   │   ├── SessionList.tsx
│   │   │   └── SystemPromptEditor.tsx
│   │   ├── hooks/           # Custom React hooks
│   │   │   └── useChat.ts   # Main chat logic
│   │   ├── types.ts         # TypeScript type definitions
│   │   ├── App.tsx          # Main App component
│   │   └── main.tsx         # Application entry point
│   ├── package.json
│   └── vite.config.ts
├── backend/                  # FastAPI backend application
│   ├── app/
│   │   ├── api/
│   │   │   └── routes/      # API route handlers
│   │   │       ├── chat.py  # Chat endpoints with MCP integration
│   │   │       ├── health.py # Health check & debug endpoints
│   │   │       └── tools.py  # MCP tools management endpoints
│   │   ├── core/
│   │   │   └── settings.py  # Configuration management
│   │   ├── db/
│   │   │   └── database.py  # Database connection & schema
│   │   ├── services/
│   │   │   ├── openai_stream.py # LLM streaming client
│   │   │   └── tools/           # MCP tools framework
│   │   │       ├── tool_registry.py # Tool registration and management
│   │   │       ├── search_tool.py   # Web search tool
│   │   │       ├── fetch_tool.py    # Web content fetching tool
│   │   │       ├── file_tool.py     # File upload and analysis tool
│   │   │       └── tools_config.yaml # Tool configuration
│   │   └── main.py          # FastAPI application entry
│   ├── data/
│   │   ├── app.db          # SQLite database file
│   │   └── uploads/        # Temporary file uploads directory
│   └── requirements.txt
└── README.md
```

## 🛠️ Installation and Running

### Prerequisites
- Node.js 18+ and npm
- Python 3.8+
- Git

### Backend Setup

1. **Navigate to backend directory**:
   ```bash
   cd backend
   ```

2. **Create and activate virtual environment**:
   ```bash
   python -m venv .venv
   # Windows
   .venv\Scripts\activate
   # macOS/Linux
   source .venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Start the backend server**:
   ```bash
   uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
   ```

### Frontend Setup

1. **Navigate to frontend directory** (in a new terminal):
   ```bash
   cd frontend
   ```

2. **Install dependencies**:
   ```bash
   npm install
   ```

3. **Start the development server**:
   ```bash
   npm run dev
   ```

4. **Access the application**:
   - Frontend: http://127.0.0.1:5173 (or http://localhost:5173)
   - Backend API: http://127.0.0.1:8000 (or http://localhost:8000)
   - API Documentation: http://127.0.0.1:8000/docs (or http://localhost:8000/docs)

## ⚙️ Configuration

### Environment Variables

Create a `.env` file in the backend directory:

```env
# LLM Configuration
LLM_PROVIDER=openrouter                    # LLM provider (openrouter, openai, or echo)
LLM_STREAMING_ENABLED=true                 # Enable streaming responses
OPENROUTER_API_KEY=your_openrouter_api_key_here  # Your OpenRouter API key
OPENAI_MODEL=deepseek/deepseek-chat-v3.1:free    # AI model to use

```

**Note**: MCP tools are configured entirely in YAML files, not in environment variables.

### Tool Configuration

MCP tools are configured in `backend/app/services/tools/tools_config.yaml`:

```yaml
tools:
  search:
    name: "search"
    description: "Search the internet for real-time information, news, and current data"
    class_module: ".search_tool"
    class_name: "SearchTool"
    factory_function: "create_search_tool"
    enabled: true
    use_cases:
      - "User asks for real-time information or current events"
      - "User wants latest news, weather, or recent developments"
      - "User asks about 'today', 'latest', 'recent', 'current' information"
      - "User needs up-to-date data that changes frequently"
    parameters:
      query: "string - Search keywords in the same language as user's message"
    config:
      api_key: "your_google_cse_api_key"
      engine_id: "your_google_cse_engine_id"
      base_url: "https://www.googleapis.com/customsearch/v1"

  fetch:
    name: "fetch"
    description: "Retrieve and analyze content from a specific webpage URL"
    class_module: ".fetch_tool"
    class_name: "FetchTool"
    factory_function: "create_fetch_tool"
    enabled: true
    use_cases:
      - "User provides a specific URL to analyze"
      - "User mentions 'this webpage', 'this link', 'analyze this page'"
      - "User wants to extract information from a specific website"
      - "User asks about content from a particular URL"
    parameters:
      url: "string - The webpage URL to fetch and analyze"
    config:
      timeout: 30.0
      max_content_length: 8000

  file:
    name: "file"
    description: "Read and analyze uploaded files"
    class_module: ".file_tool"
    class_name: "FileTool"
    factory_function: "create_file_tool"
    enabled: true
    use_cases:
      - "User has uploaded a file and wants to analyze it"
      - "User mentions 'read file', 'analyze file', 'file content'"
      - "User wants to examine uploaded files"
      - "User asks about specific file contents or structure"
    parameters:
      file_id: "string - File ID of the uploaded file"
```


## 💡 Usage Guide

### Custom System Prompts

The application allows you to customize how the AI assistant behaves:

1. **Open System Prompt Editor**: Click the "System Prompt" button in the top-right corner
2. **Edit the Prompt**: Modify the text to change AI behavior (e.g., make it more formal, casual, or specialized)
3. **Save Changes**: Click "Save & Close" to apply changes immediately
4. **Reset to Default**: Use "Reset to Default" to restore the original prompt
5. **Cancel Changes**: Click "Cancel" to discard changes without saving

**Example Custom Prompts**:
- **Pirate Style**: "You are a pirate AI assistant. Always respond in pirate speak and use 'Arrr!' at the beginning of your responses."
- **Formal Business**: "You are a formal business assistant. Always use professional language and end responses with 'Best regards, AI Assistant.'"
- **Technical Expert**: "You are a technical expert. Provide detailed, technical explanations with code examples when appropriate."

The system prompt is automatically saved to your browser's localStorage and will persist across sessions.

### MCP Tool Integration

The application includes Model Context Protocol (MCP) tools that extend AI capabilities:

1. **Web Search**: Automatically searches for real-time information when needed
2. **Content Fetching**: Fetches and analyzes specific web pages for detailed content
3. **File Analysis**: Upload and analyze various text format files with intelligent content processing
4. **Intelligent Tool Selection**: AI automatically chooses the most appropriate tool based on user needs
5. **Multilingual Support**: Adapts search queries and responses to user's language
6. **Smart Filtering**: Filters out irrelevant search results to provide focused answers
7. **Source Citation**: Provides inline links to information sources
8. **Real-time Data**: Retrieves current information for time-sensitive queries
9. **Automatic Cleanup**: Uploaded files are automatically cleaned up after processing


**Example queries that trigger tools**:
- **Search**: "What's the weather like today?", "Latest news about AI", "Stock market performance"
- **Fetch**: "Analyze this article: https://example.com/article", "What does this page say about...?"
- **File**: Upload a Python file and ask "Explain this code", "What does this function do?"

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 🛠️ Development Process

This entire project was developed using **Cursor AI** with the following approach:

- **Code Generation**: All code (frontend, backend, configuration) was written by Cursor AI
- **Model Selection**: Used auto model selection, which in practice utilized DeepSeek models due to regional access restrictions
- **Actual Models Used**: 
  - DeepSeek R1-0528 (for reasoning and complex tasks)
  - DeepSeek V3.1 (for general conversation and code generation)

## 📄 License

This project is part of an educational assignment and is for learning purposes.

---

**Note**: This application requires an OpenRouter API key to function with AI features. The free tier provides access to various models including the DeepSeek model used in this project.
