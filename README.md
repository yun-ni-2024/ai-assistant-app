# AI Assistant App

A modern web application that provides AI-powered conversational assistance with real-time streaming responses, conversation memory, and customizable system prompts.

**Version**: 1.2.0 - Added MCP tool integration with web search

## 🚀 Features

- **Real-time AI Chat**: Interactive conversations with AI using streaming responses
- **Conversation Memory**: AI maintains context across multiple messages in a session
- **Session Management**: Create, switch between, and manage multiple conversation sessions
- **Custom System Prompts**: Edit and customize AI behavior with real-time system prompt editor
- **MCP Tool Integration**: Web search capabilities with real-time information retrieval
- **Multilingual Support**: Full internationalization with adaptive language responses
- **Streaming Responses**: Real-time token-by-token response streaming using Server-Sent Events (SSE)
- **Modern UI**: Clean and responsive React-based user interface with English interface
- **Database Persistence**: SQLite database for storing conversations and messages
- **Persistent Settings**: System prompt preferences saved in browser localStorage

## 🏗️ Technical Architecture

### Frontend
- **Framework**: React 18.3.1 with TypeScript
- **Build Tool**: Vite 5.4.1
- **State Management**: React Hooks (useState, useCallback)
- **HTTP Client**: Native Fetch API with EventSource for SSE

### Backend
- **Framework**: FastAPI 0.111.0
- **Language**: Python 3.x
- **Database**: SQLite with custom connection management
- **LLM Integration**: OpenAI-compatible API (OpenRouter)
- **MCP Tools**: Google Custom Search API for web search
- **Streaming**: Server-Sent Events (SSE) for real-time responses

### AI Model
- **Primary Model**: `deepseek/deepseek-chat-v3.1:free`
- **Provider**: OpenRouter API
- **Features**: Streaming responses, conversation context awareness

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
│   │   │   ├── settings.py  # Configuration management
│   │   │   └── mcp_config.py # MCP tools configuration
│   │   ├── db/
│   │   │   └── database.py  # Database connection & schema
│   │   ├── services/
│   │   │   ├── openai_stream.py # LLM streaming client
│   │   │   └── mcp_client.py    # MCP tools client
│   │   └── main.py          # FastAPI application entry
│   ├── data/
│   │   └── app.db          # SQLite database file
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
   python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
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
   - Frontend: http://127.0.0.1:5173
   - Backend API: http://127.0.0.1:8000
   - API Documentation: http://127.0.0.1:8000/docs

## ⚙️ Configuration

### Environment Variables

Create a `.env` file in the backend directory:

```env
# LLM Configuration
LLM_PROVIDER=openrouter
LLM_STREAMING_ENABLED=true
OPENROUTER_API_KEY=your_openrouter_api_key_here
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENAI_MODEL=deepseek/deepseek-chat-v3.1:free

# Optional: Site information for OpenRouter
OPENROUTER_SITE_URL=http://localhost:5173
OPENROUTER_SITE_TITLE=AI Assistant App

# MCP Tools Configuration
MCP_SEARCH_ENABLED=true
MCP_SEARCH_URL=http://localhost:3001
GOOGLE_CSE_API_KEY=your_google_cse_api_key_here
GOOGLE_CSE_ENGINE_ID=your_google_cse_engine_id_here

# Database
DATABASE_URL=sqlite:///./data/app.db
```

### API Configuration

The application supports multiple LLM providers:
- **OpenRouter** (recommended): Free tier available with `deepseek/deepseek-chat-v3.1:free`
- **OpenAI**: Requires OpenAI API key
- **Fallback**: Local echo mode when no API keys are configured

## 📊 Development Status

### ✅ Completed Features
- [x] Project initialization and structure
- [x] Backend API with FastAPI
- [x] Frontend React application with TypeScript
- [x] SQLite database with sessions and messages tables
- [x] Two-step SSE streaming implementation
- [x] Real-time AI chat with streaming responses
- [x] Conversation memory and context awareness
- [x] Session management (create, switch, persist)
- [x] Message persistence and retrieval
- [x] Custom system prompt editor with real-time updates
- [x] Persistent system prompt settings (localStorage)
- [x] English user interface
- [x] Error handling and fallback mechanisms
- [x] Debug endpoints for development
- [x] MCP (Model Context Protocol) tool integration
- [x] Web search capabilities with Google Custom Search API
- [x] Multilingual support with adaptive responses
- [x] Real-time information retrieval and citation

### 🚧 In Progress
- [ ] Enhanced UI/UX improvements

### 📋 Planned Features
- [ ] User authentication system
- [ ] Conversation export/import
- [ ] Multiple AI model support
- [ ] Advanced conversation management
- [ ] Real-time collaboration features

### 🐛 Known Issues
- None currently identified

## 🔧 API Endpoints

### Chat Endpoints
- `POST /api/chat/create` - Create a new chat session (supports custom system_prompt)
- `GET /api/chat/stream/{stream_id}` - Stream AI responses with MCP tool integration
- `GET /api/chat/sessions/{session_id}/messages` - Get session messages

### MCP Tools Endpoints
- `GET /api/tools/` - List all available MCP tools
- `GET /api/tools/enabled` - List enabled MCP tools
- `POST /api/tools/execute` - Execute an MCP tool
- `GET /api/tools/{tool_name}/info` - Get specific tool information
- `GET /api/tools/health` - MCP tools health check

### Utility Endpoints
- `GET /healthz` - Health check
- `GET /config` - Configuration status
- `GET /debug/sessions` - Debug: View all sessions and messages

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
2. **Multilingual Support**: Adapts search queries and responses to user's language
3. **Source Citation**: Provides inline links to information sources
4. **Real-time Data**: Retrieves current information for time-sensitive queries

**How it works**:
- The AI automatically determines when web search is needed
- Search results are integrated into responses with proper citations
- Links are embedded inline for easy access to sources
- Supports multiple languages with appropriate formatting

**Example queries that trigger search**:
- "What's the weather like today?"
- "Latest news about AI"
- "Stock market performance on [date]"
- "Current events in [location]"

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is part of an educational assignment and is for learning purposes.

---

**Note**: This application requires an OpenRouter API key to function with AI features. The free tier provides access to various models including the DeepSeek model used in this project.
