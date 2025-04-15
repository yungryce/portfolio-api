import azure.functions as func
import datetime
import json
import logging
import os
import requests
from base64 import b64decode

# Import the AI assistant blueprint
from ai_assistant import fetch_and_process_repos, query_ai_assistant

# Configure logging
logger = logging.getLogger('portfolio.api')
logger.setLevel(logging.INFO)

app = func.FunctionApp()

@app.route(route="github/repos", auth_level=func.AuthLevel.ANONYMOUS)
def get_github_repos(req: func.HttpRequest) -> func.HttpResponse:
    logger.info('Processing request for GitHub repos listing')
    
    # Get token from environment (securely stored in Azure)
    github_token = os.getenv('GITHUB_TOKEN')
    username = 'yungryce'  # Your GitHub username
    
    if not github_token:
        logger.error('GitHub token not configured in environment variables')
        return func.HttpResponse(
            json.dumps({"error": "GitHub token not configured"}),
            status_code=500,
            mimetype="application/json"
        )
    
    # Log the request details
    logger.info(f"Fetching repositories for user: {username}")
        
    # Make authenticated request to GitHub API
    headers = {'Authorization': f'token {github_token}'}
    
    try:
        response = requests.get(
            f'https://api.github.com/users/{username}/repos?sort=updated&per_page=10',
            headers=headers
        )
        
        logger.info(f"GitHub API response status: {response.status_code}")
        
        if response.status_code != 200:
            logger.warning(f"GitHub API returned non-200 status: {response.status_code}")
            logger.debug(f"Response content: {response.text[:500]}...")
            
        # Return the GitHub API response directly
        return func.HttpResponse(
            response.text,
            status_code=response.status_code,
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
    
    # Make authenticated request to GitHub API
    headers = {'Authorization': f'token {github_token}'}
    logger.info(f"Making request to GitHub API for repository details: {username}/{repo}")
    
    try:
        response = requests.get(
            f'https://api.github.com/repos/{username}/{repo}',
            headers=headers
        )
        
        logger.info(f"GitHub API response status: {response.status_code}")
        
        if response.status_code != 200:
            logger.warning(f"GitHub API returned non-200 status: {response.status_code}")
            logger.debug(f"Response content: {response.text[:500]}...")
        
        return func.HttpResponse(
            response.text,
            status_code=response.status_code,
            mimetype="application/json"
        )
    except Exception as e:
        logger.error(f"Error fetching GitHub repository {username}/{repo}: {str(e)}", exc_info=True)
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
    
    # Make authenticated request to GitHub API for README
    headers = {
        'Authorization': f'token {github_token}',
        'Accept': 'application/vnd.github.v3.raw'
    }
    
    try:
        logger.info(f"Fetching README content for {username}/{repo}")
        response = requests.get(
            f'https://api.github.com/repos/{username}/{repo}/readme',
            headers=headers
        )
        
        logger.info(f"GitHub API README response status: {response.status_code}")
        
        # If successful, return the raw content
        if response.status_code == 200:
            logger.info(f"Successfully retrieved README for {username}/{repo} (length: {len(response.text)} chars)")
            return func.HttpResponse(
                response.text,
                status_code=200,
                mimetype="text/plain"
            )
        
        # Handle error cases
        logger.warning(f"Failed to fetch README for {username}/{repo}: status {response.status_code}")
        return func.HttpResponse(
            json.dumps({"error": "README not found"}),
            status_code=response.status_code,
            mimetype="application/json"
        )
    except Exception as e:
        logger.error(f"Error fetching README for {username}/{repo}: {str(e)}", exc_info=True)
        return func.HttpResponse(
            json.dumps({"error": f"Failed to fetch README: {str(e)}"}),
            status_code=500,
            mimetype="application/json"
        )

@app.route(route="portfolio/query", auth_level=func.AuthLevel.ANONYMOUS, methods=["POST"])
def portfolio_query(req: func.HttpRequest) -> func.HttpResponse:
    logger.info('Processing portfolio query with AI assistance')
    
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
        
        # Use the blueprint functions to fetch and process repositories
        logger.info(f"Fetching and processing repositories for {username}")
        start_time = datetime.datetime.now()
        filtered_repos = fetch_and_process_repos(username, github_token)
        fetch_time = datetime.datetime.now() - start_time
        logger.info(f"Fetched {len(filtered_repos)} repositories in {fetch_time.total_seconds():.2f} seconds")
        
        # Get AI response using the blueprint function
        logger.info("Querying AI assistant with portfolio data")
        start_time = datetime.datetime.now()
        ai_response = query_ai_assistant(query, filtered_repos)
        query_time = datetime.datetime.now() - start_time
        logger.info(f"AI generated response of {len(ai_response)} chars in {query_time.total_seconds():.2f} seconds")
        
        # Return the AI response
        result = {
            "response": ai_response,
            "repositories": filtered_repos  # Include repository data in response
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