# API Project Manifest

## 🎯 Purpose
The API module provides secure backend services for the portfolio website, including GitHub data retrieval and AI-powered portfolio assistant functionality.

## 📂 Structure
- **function_app.py** - Main Azure Functions application with HTTP routes
- **ai_assistant.py** - AI processing module for portfolio queries
- **requirements.txt** - Python dependencies
- **host.json** - Azure Functions configuration

## 🧩 Key Components

### HTTP Endpoints
- **/github/repos** - Retrieves GitHub repositories
- **/github/repos/{username}/{repo}** - Gets specific repository details
- **/github/repos/{username}/{repo}/readme** - Returns README content
- **/portfolio/query** - Processes AI queries about the portfolio

### Core Modules
- **AI Assistant**: Processes natural language queries using repository data
- **Repository Processor**: Extracts and structures GitHub repository information
- **Metadata Extractor**: Parses special files for enhanced repository context

## 🔄 Workflows

### Repository Data Workflow
1. Frontend requests repository data through HTTP endpoint
2. Function authenticates with GitHub using secure token
3. GitHub API data is retrieved, processed, and returned
4. Special files are extracted for enhanced metadata

### AI Query Workflow
1. Frontend submits query via POST to /portfolio/query
2. All repositories are fetched and processed for context
3. Rich context is generated for the LLM
4. Query is sent to Groq API with appropriate prompts
5. Response is processed and returned to frontend

## 💪 Technical Highlights
- Serverless architecture using Azure Functions
- Comprehensive structured logging
- Secure API token management
- Enhanced repository metadata extraction
- AI context generation and processing

## 📚 Dependencies
- Azure Functions Python SDK
- OpenAI API client for Groq integration
- Requests library for HTTP communication
- Regular expressions for content parsing