import json
import logging
import os
import azure.functions as func
from datetime import datetime

# Import the GitHub client
from github_client import GitHubClient

# Import AI assistant functions
from ai_assistant import query_ai_assistant

# Configure logging
logger = logging.getLogger('portfolio.api')
logger.setLevel(logging.INFO)

app = func.FunctionApp()

@app.route(route="github/repos", auth_level=func.AuthLevel.ANONYMOUS)
def get_github_repos(req: func.HttpRequest) -> func.HttpResponse:
    logger.info('Processing request for GitHub repos listing')
    
    # Get token from environment
    github_token = os.getenv('GITHUB_TOKEN')
    username = 'yungryce'  # Your GitHub username
    
    if not github_token:
        logger.error('GitHub token not configured in environment variables')
        return func.HttpResponse(
            json.dumps({"error": "GitHub token not configured"}),
            status_code=500,
            mimetype="application/json"
        )
    
    # Create GitHub client
    gh_client = GitHubClient(token=github_token, username=username)
    
    try:
        # Get the repositories
        all_repos = gh_client.get_user_repos(username)
        top_repos = all_repos[:10]  # Take only the first 10
        
        return func.HttpResponse(
            json.dumps(top_repos),
            status_code=200,
            mimetype="application/json"
        )
    except Exception as e:
        logger.error(f"Error fetching GitHub repositories: {str(e)}", exc_info=True)
        return func.HttpResponse(
            json.dumps({"error": f"Failed to fetch GitHub repositories: {str(e)}"}),
            status_code=500,
            mimetype="application/json"
        )

@app.route(route="github/repos/{username}/{repo}", auth_level=func.AuthLevel.ANONYMOUS)
def get_github_repo(req: func.HttpRequest) -> func.HttpResponse:
    # Get parameters from route
    username = req.route_params.get('username')
    repo = req.route_params.get('repo')
    
    logger.info(f"Processing request for specific GitHub repo: {username}/{repo}")
    
    # Get token from environment
    github_token = os.getenv('GITHUB_TOKEN')
    
    if not github_token:
        logger.error('GitHub token not configured in environment variables')
        return func.HttpResponse(
            json.dumps({"error": "GitHub token not configured"}),
            status_code=500,
            mimetype="application/json"
        )
    
    # Create GitHub client
    gh_client = GitHubClient(token=github_token, username=username)
    
    try:
        # Get repository details
        repo_details = gh_client.get_repo_details(username, repo)
        
        if not repo_details:
            logger.warning(f"Repository not found: {username}/{repo}")
            return func.HttpResponse(
                json.dumps({"error": "Repository not found"}),
                status_code=404,
                mimetype="application/json"
            )
        
        return func.HttpResponse(
            json.dumps(repo_details),
            status_code=200,
            mimetype="application/json"
        )
    except Exception as e:
        logger.error(f"Error fetching repository details: {str(e)}", exc_info=True)
        return func.HttpResponse(
            json.dumps({"error": f"Failed to fetch repository details: {str(e)}"}),
            status_code=500,
            mimetype="application/json"
        )

@app.route(route="github/repos/{username}/{repo}/readme", auth_level=func.AuthLevel.ANONYMOUS)
def get_github_readme(req: func.HttpRequest) -> func.HttpResponse:
    # Get parameters from route
    username = req.route_params.get('username')
    repo = req.route_params.get('repo')
    
    logger.info(f"Processing request for GitHub repo README: {username}/{repo}")
    
    # Get token from environment
    github_token = os.getenv('GITHUB_TOKEN')
    
    if not github_token:
        logger.error('GitHub token not configured in environment variables')
        return func.HttpResponse(
            json.dumps({"error": "GitHub token not configured"}),
            status_code=500,
            mimetype="application/json"
        )
    
    # Create GitHub client
    gh_client = GitHubClient(token=github_token, username=username)
    
    try:
        # Get README content
        readme_content = gh_client.get_readme(username, repo)
        
        if not readme_content:
            logger.warning(f"README not found for repository: {username}/{repo}")
            return func.HttpResponse(
                json.dumps({"error": "README not found for this repository"}),
                status_code=404,
                mimetype="application/json"
            )
        
        return func.HttpResponse(
            readme_content,
            status_code=200,
            mimetype="text/markdown"
        )
    except Exception as e:
        logger.error(f"Error fetching README: {str(e)}", exc_info=True)
        return func.HttpResponse(
            json.dumps({"error": f"Failed to fetch README: {str(e)}"}),
            status_code=500,
            mimetype="application/json"
        )

@app.route(route="portfolio/query", auth_level=func.AuthLevel.ANONYMOUS, methods=["POST", "OPTIONS"])
def portfolio_query(req: func.HttpRequest) -> func.HttpResponse:
    logger.info('Processing portfolio query with AI assistance')
    
    # Handle CORS preflight requests
    if req.method == "OPTIONS":
        return func.HttpResponse(
            status_code=200,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, Authorization"
            }
        )
    
    try:
        # Parse request body
        req_body = req.get_json()
        query = req_body.get('query')
        
        if not query:
            logger.warning('Portfolio query request missing query parameter')
            return func.HttpResponse(
                json.dumps({"error": "Missing query parameter"}),
                status_code=400,
                mimetype="application/json"
            )
        
        logger.info(f"Portfolio query received: {query[:100]}...")
        
        # Get GitHub token from environment
        github_token = os.getenv('GITHUB_TOKEN')
        username = 'yungryce'  # Your GitHub username
        
        if not github_token:
            logger.error('GitHub token not configured in environment variables')
            return func.HttpResponse(
                json.dumps({"error": "GitHub token not configured"}),
                status_code=500,
                mimetype="application/json"
            )
        
        # Create GitHub client
        gh_client = GitHubClient(token=github_token, username=username)
        
        # Try to get processed repos with graceful fallback
        try:
            logger.info("Retrieving processed repositories")
            filtered_repos = gh_client.get_processed_repos(username)
            logger.info(f"Successfully retrieved {len(filtered_repos)} repositories")
        except Exception as e:
            logger.error(f"Repository retrieval failed: {str(e)}", exc_info=True)
            if "Failed to resolve" in str(e) or "DNS resolution failure" in str(e):
                # Network error - check if we have any cached repos
                cache_key = f"processed_repos_{username}"
                cached_repos = gh_client._get_from_cache(cache_key)
                
                if cached_repos:
                    logger.info(f"Using {len(cached_repos)} cached repositories despite network error")
                    filtered_repos = cached_repos
                else:
                    return func.HttpResponse(
                        json.dumps({
                            "error": "Network connectivity issue accessing GitHub API",
                            "message": "The server is having trouble connecting to GitHub. Please try again later."
                        }),
                        status_code=503,  # Service Unavailable
                        mimetype="application/json"
                    )
            else:
                # Other error
                return func.HttpResponse(
                    json.dumps({"error": f"Failed to retrieve repository data: {str(e)}"}),
                    status_code=500,
                    mimetype="application/json"
                )
        
        # Get AI response using the blueprint function
        try:
            logger.info("Querying AI assistant with repository data")
            ai_response = query_ai_assistant(query, filtered_repos)
            logger.info(f"AI assistant generated a response of {len(ai_response)} chars")
        except Exception as e:
            logger.error(f"AI query failed: {str(e)}", exc_info=True)
            return func.HttpResponse(
                json.dumps({"error": f"AI processing error: {str(e)}"}),
                status_code=500,
                mimetype="application/json"
            )
        
        # Return the AI response
        result = {
            "response": ai_response
        }
        
        logger.info("Portfolio query processed successfully")
        return func.HttpResponse(
            json.dumps(result),
            status_code=200,
            mimetype="application/json"
        )
            
    except Exception as e:
        logger.error(f"Error processing portfolio query: {str(e)}", exc_info=True)
        return func.HttpResponse(
            json.dumps({"error": f"Internal server error: {str(e)}"}),
            status_code=500,
            mimetype="application/json"
        )

# Add a health check endpoint
@app.route(route="health", auth_level=func.AuthLevel.ANONYMOUS)
def health_check(req: func.HttpRequest) -> func.HttpResponse:
    """Simple endpoint to check API health"""
    logger.info('Processing API health check')
    
    # Perform basic GitHub connectivity test
    github_token = os.getenv('GITHUB_TOKEN')
    if github_token:
        try:
            # Create GitHub client with short cache TTL
            gh_client = GitHubClient(token=github_token, username='yungryce')
            gh_client.cache_ttl = 60  # 1 minute cache
            
            # Test GitHub API connectivity
            rate_limit = gh_client.make_request('GET', 'rate_limit')
            github_status = "connected" if rate_limit else "error"
        except Exception as e:
            logger.error(f"GitHub connectivity test failed: {str(e)}")
            github_status = f"error: {str(e)}"
    else:
        github_status = "unconfigured"
    
    # Check GROQ API key
    groq_api_key = os.getenv('GROQ_API_KEY')
    groq_status = "configured" if groq_api_key else "unconfigured"
    
    # Check Azure Storage
    azure_storage = os.getenv('AzureWebJobsStorage')
    storage_status = "configured" if azure_storage else "unconfigured"
    
    return func.HttpResponse(
        json.dumps({
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "environment": {
                "github_api": github_status,
                "groq_api": groq_status,
                "azure_storage": storage_status
            }
        }),
        status_code=200,
        mimetype="application/json"
    )