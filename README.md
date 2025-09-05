# AI Assistant App

A modern web application that provides AI-powered conversational assistance with real-time streaming responses and conversation memory.

## 🚀 Features

- **Real-time AI Chat**: Interactive conversations with AI using streaming responses
- **Conversation Memory**: AI maintains context across multiple messages in a session
- **Session Management**: Create, switch between, and manage multiple conversation sessions
- **Streaming Responses**: Real-time token-by-token response streaming using Server-Sent Events (SSE)
- **Modern UI**: Clean and responsive React-based user interface
- **Database Persistence**: SQLite database for storing conversations and messages

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
│   │   │   └── SessionList.tsx
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
│   │   │       ├── chat.py  # Chat endpoints
│   │   │       └── health.py # Health check & debug endpoints
│   │   ├── core/
│   │   │   └── settings.py  # Configuration management
│   │   ├── db/
│   │   │   └── database.py  # Database connection & schema
│   │   ├── services/
│   │   │   └── openai_stream.py # LLM streaming client
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
- [x] Error handling and fallback mechanisms
- [x] Debug endpoints for development

### 🚧 In Progress
- [ ] System prompt customization
- [ ] MCP (Model Context Protocol) tool integration
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
- `POST /api/chat/create` - Create a new chat session
- `GET /api/chat/stream/{stream_id}` - Stream AI responses
- `GET /api/chat/sessions/{session_id}/messages` - Get session messages

### Utility Endpoints
- `GET /healthz` - Health check
- `GET /config` - Configuration status
- `GET /debug/sessions` - Debug: View all sessions and messages

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
