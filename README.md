# Portfolio API

Azure Functions-based backend API for the portfolio website, providing GitHub integration and AI-powered portfolio assistance.

## 🚀 Technology Stack

- **Platform**: Azure Functions (Python)
- **AI Integration**: Groq API with Llama 3.1 model
- **External APIs**: GitHub API for repository data
- **Logging**: Comprehensive structured logging

## 📋 Features

- **GitHub Data Proxy**: Securely access GitHub data without exposing tokens
- **AI Assistant**: Process natural language queries about portfolio projects
- **Repository Analysis**: Extract and structure repository metadata
- **Content Extraction**: Parse and organize README content

## 🏗️ Project Structure

- `function_app.py` - Main Azure Functions application with API routes
- `ai_assistant.py` - AI processing module for portfolio queries
- `requirements.txt` - Python dependencies
- `host.json` - Azure Functions host configuration

## 🛠️ Key Components

### HTTP Endpoints

- **GET /github/repos** - Get list of GitHub repositories
- **GET /github/repos/{username}/{repo}** - Get specific repository details
- **GET /github/repos/{username}/{repo}/readme** - Get README content for a repository
- **POST /portfolio/query** - Process natural language queries about the portfolio

### AI Assistant Module

- **Repository Processing**: Fetches and processes GitHub repositories
- **Metadata Extraction**: Parses special files like `.repo-context.json` and `PROJECT-MANIFEST.md`
- **Enhanced Context Generation**: Creates rich context for the AI model
- **Query Processing**: Sends data to Groq API and processes responses

## 🔄 Data Flow

1. Frontend requests data through HTTP endpoints
2. Functions authenticate with GitHub using secure token
3. Repository data is processed and enhanced with metadata
4. AI queries are processed through Groq API
5. Responses are formatted and returned to frontend

## 🔒 Security

- GitHub token stored securely in environment variables
- Groq API key managed through Azure configuration
- No tokens exposed to frontend

## 📊 Logging

Comprehensive logging implemented for:
- API request/response tracking
- Performance metrics
- Error handling
- AI query processing