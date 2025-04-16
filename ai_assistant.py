import logging
import os
import time
from openai import OpenAI

# Configure logging
logger = logging.getLogger('portfolio.ai_assistant')
logger.setLevel(logging.INFO)

# Keep the empty functions for backward compatibility, but make them redirect
def extract_repo_metadata(repo_name, username, github_token):
    """
    Redirect to GitHubClient's extract_repo_metadata
    This function is kept for backward compatibility
    """
    from github_client import GitHubClient
    client = GitHubClient(token=github_token, username=username)
    return client.extract_repo_metadata(repo_name, username)

def extract_readme_sections(readme_content):
    """
    Redirect to GitHubClient's extract_readme_sections
    This function is kept for backward compatibility
    """
    from github_client import GitHubClient
    client = GitHubClient()
    return client.extract_readme_sections(readme_content)

def generate_enhanced_context(filtered_repos):
    """
    Redirect to GitHubClient's generate_enhanced_context
    This function is kept for backward compatibility
    """
    from github_client import GitHubClient
    client = GitHubClient()
    return client.generate_enhanced_context(filtered_repos)

def fetch_and_process_repos(username, github_token):
    """Fetch repositories and process them using the centralized GitHub client."""
    logger.info(f"Fetching and processing repositories for user: {username}")
    
    # Import the GitHub client here to avoid circular imports
    from github_client import GitHubClient
    
    # Create client instance
    client = GitHubClient(token=github_token, username=username)
    
    try:
        # Get processed repositories with all details
        filtered_repos = client.get_processed_repos(username)
        logger.info(f"Retrieved {len(filtered_repos)} processed repositories for {username}")
        return filtered_repos
    except Exception as e:
        logger.error(f"Error fetching processed repositories: {str(e)}", exc_info=True)
        raise

def query_ai_assistant(query, repos_data):
    """Query the AI assistant with repository data and user query."""
    logger.info("Starting AI assistant query")
    
    # Add tracing for request sequence
    request_id = f"req-{int(time.time())}"
    logger.info(f"Request ID: {request_id} - Processing query: {query[:100]}...")
    
    # Generate enhanced context for the LLM
    from github_client import GitHubClient
    client = GitHubClient()
    
    context_start = time.time()
    context = client.generate_enhanced_context(repos_data)
    context_time = time.time() - context_start
    logger.info(f"Request ID: {request_id} - Generated context in {context_time:.2f}s ({len(context)} chars)")
    
    # Get the Groq API key from environment variables
    groq_api_key = os.getenv("GROQ_API_KEY")
    
    if not groq_api_key:
        logger.error("GROQ_API_KEY not configured in environment")
        raise ValueError("GROQ_API_KEY environment variable is not set")
    
    # Initialize Groq client
    client = OpenAI(
        api_key=groq_api_key,
        base_url="https://api.groq.com/openai/v1"
    )
    
    # Create system message with enhanced repository context
    system_message = f"""You are an AI assistant that helps users understand Chigbu Joshua's portfolio projects.
Use the following structured information about the GitHub repositories to answer questions.

{context}

When answering:
1. Focus on the structured metadata, technology signatures, and demonstrated competencies
2. Reference specific projects and their architecture patterns when relevant
3. Highlight relationships between components in monorepo structures
4. Organize your response with clear sections and bullet points
5. Emphasize technical skills shown in the projects

Respond specifically and accurately about the projects listed above.
If asked about a specific technology, framework, or architecture pattern, check the metadata first before the general repository information.
"""
    
    logger.info(f"Request ID: {request_id} - Created system prompt ({len(system_message)} chars)")
    
    # Call Groq API with Llama model
    try:
        api_start = time.time()
        response = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": query}
            ],
            max_tokens=1024,
            temperature=0.3
        )
        api_time = time.time() - api_start
        
        # Extract the response text
        if response.choices and len(response.choices) > 0:
            answer = response.choices[0].message.content
            logger.info(f"Request ID: {request_id} - Received AI response in {api_time:.2f}s ({len(answer)} chars)")
            return answer
        else:
            logger.error(f"Request ID: {request_id} - Empty response from AI API")
            return "I'm sorry, I couldn't generate a response based on the portfolio information."
            
    except Exception as e:
        logger.error(f"Request ID: {request_id} - Error calling AI API: {str(e)}")
        raise