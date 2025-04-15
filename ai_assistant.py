import json
import logging
import os
import re
import requests
import time
from openai import OpenAI

# Configure logging
logger = logging.getLogger('portfolio.ai_assistant')
logger.setLevel(logging.INFO)

def extract_repo_metadata(repo_name, username, github_token):
    """Extract structured metadata from special files in the repository."""
    metadata = {}
    
    # Check for repo-context.json at root
    try:
        logger.debug(f"Checking for .repo-context.json in {username}/{repo_name}")
        context_response = requests.get(
            f"https://api.github.com/repos/{username}/{repo_name}/contents/.repo-context.json",
            headers={"Authorization": f"token {github_token}", "Accept": "application/vnd.github.v3.raw"}
        )
        if context_response.status_code == 200:
            logger.info(f"Found .repo-context.json in {username}/{repo_name}")
            metadata['repo_context'] = json.loads(context_response.text)
        else:
            logger.debug(f"No .repo-context.json found in {username}/{repo_name} (status: {context_response.status_code})")
    except Exception as e:
        logger.debug(f"Error checking for .repo-context.json: {str(e)}")
    
    # Check for PROJECT-MANIFEST.md files in subdirectories
    try:
        logger.debug(f"Checking for PROJECT-MANIFEST.md files in {username}/{repo_name}")
        contents_response = requests.get(
            f"https://api.github.com/repos/{username}/{repo_name}/contents",
            headers={"Authorization": f"token {github_token}"}
        )
        if contents_response.status_code == 200:
            contents = contents_response.json()
            project_manifests = {}
            
            # Find directories that might contain PROJECT-MANIFEST.md
            dirs = [item['name'] for item in contents if item['type'] == 'dir']
            logger.debug(f"Found {len(dirs)} directories to check for manifests")
            
            for dir_name in dirs:
                manifest_response = requests.get(
                    f"https://api.github.com/repos/{username}/{repo_name}/contents/{dir_name}/PROJECT-MANIFEST.md",
                    headers={"Authorization": f"token {github_token}", "Accept": "application/vnd.github.v3.raw"}
                )
                if manifest_response.status_code == 200:
                    logger.info(f"Found PROJECT-MANIFEST.md in {username}/{repo_name}/{dir_name}")
                    project_manifests[dir_name] = manifest_response.text
            
            if project_manifests:
                logger.info(f"Found {len(project_manifests)} project manifests in {username}/{repo_name}")
                metadata['project_manifests'] = project_manifests
    except Exception as e:
        logger.debug(f"Error checking for project manifests: {str(e)}")
    
    # Check for SKILLS-INDEX.md
    try:
        logger.debug(f"Checking for SKILLS-INDEX.md in {username}/{repo_name}")
        skills_response = requests.get(
            f"https://api.github.com/repos/{username}/{repo_name}/contents/SKILLS-INDEX.md",
            headers={"Authorization": f"token {github_token}", "Accept": "application/vnd.github.v3.raw"}
        )
        if skills_response.status_code == 200:
            logger.info(f"Found SKILLS-INDEX.md in {username}/{repo_name}")
            metadata['skills_index'] = skills_response.text
    except Exception as e:
        logger.debug(f"Error checking for SKILLS-INDEX.md: {str(e)}")
    if metadata:
        logger.info(f"Completed metadata extraction for {username}/{repo_name}. Found {len(metadata)} metadata items")
    return metadata


def extract_readme_sections(readme_content):
    """Extract meaningful sections from README content."""
    logger.debug("Extracting sections from README content")
    sections = {}
    
    # Common pattern headers
    section_patterns = [
        (r"## Technology Signature\s+(.*?)(?=##|\Z)", "tech_stack"),
        (r"## Demonstrated Competencies\s+(.*?)(?=##|\Z)", "skills"),
        (r"## System Architecture\s+(.*?)(?=##|\Z)", "architecture"),
        (r"## Project Structure\s+(.*?)(?=##|\Z)", "structure"),
        (r"## Deployment Workflow\s+(.*?)(?=##|\Z)", "workflow")
    ]
    
    for pattern, key in section_patterns:
        match = re.search(pattern, readme_content, re.DOTALL)
        if match:
            sections[key] = match.group(1).strip()
            logger.debug(f"Extracted README section: {key} ({len(sections[key])} chars)")
    
    logger.debug(f"Found {len(sections)} README sections")
    return sections


def generate_enhanced_context(filtered_repos):
    """Generate rich context from structured repository data."""
    logger.info(f"Generating enhanced context from {len(filtered_repos)} repositories")
    context = []
    
    for repo in filtered_repos:
        logger.debug(f"Building context for repository: {repo['name']}")
        repo_context = f"# {repo['name']}\n"
        
        # Add basic repository info
        repo_context += f"## Overview\n{repo.get('description', 'No description provided.')}\n\n"
        
        # Add technology information (from metadata or fallback to API data)
        if 'repo_context' in repo.get('metadata', {}):
            tech_stack = repo['metadata']['repo_context'].get('tech_stack', {})
            if tech_stack:
                logger.debug(f"Adding tech stack from metadata for {repo['name']}")
                repo_context += "## Technologies\n"
                if 'primary' in tech_stack:
                    repo_context += "### Primary: " + ", ".join(tech_stack['primary']) + "\n"
                if 'secondary' in tech_stack:
                    repo_context += "### Secondary: " + ", ".join(tech_stack['secondary']) + "\n"
                if 'key_libraries' in tech_stack:
                    repo_context += "### Key Libraries: " + ", ".join(tech_stack['key_libraries']) + "\n"
        else:
            # Fallback to API data
            logger.debug(f"Using API data for tech stack in {repo['name']}")
            repo_context += f"## Technologies\nMain Language: {repo.get('language', 'Not specified')}\n"
            repo_context += f"All Languages: {', '.join(repo.get('languages', []))}\n"
        
        # Add skills information
        if 'repo_context' in repo.get('metadata', {}):
            skill_manifest = repo['metadata']['repo_context'].get('skill_manifest', {})
            if skill_manifest:
                logger.debug(f"Adding skills from metadata for {repo['name']}")
                repo_context += "## Skills Demonstrated\n"
                if 'technical' in skill_manifest:
                    repo_context += "### Technical: " + ", ".join(skill_manifest['technical']) + "\n"
                if 'domain' in skill_manifest:
                    repo_context += "### Domain: " + ", ".join(skill_manifest['domain']) + "\n"
        
        # Add README sections if available
        if 'readme_sections' in repo:
            logger.debug(f"Adding README sections for {repo['name']}")
            if 'architecture' in repo['readme_sections']:
                repo_context += f"## Architecture\n{repo['readme_sections']['architecture']}\n\n"
            if 'workflow' in repo['readme_sections']:
                repo_context += f"## Workflow\n{repo['readme_sections']['workflow']}\n\n"
        
        # Add project manifests if available
        if 'metadata' in repo and 'project_manifests' in repo['metadata']:
            logger.debug(f"Adding project manifests for {repo['name']}")
            repo_context += "## Project Components\n"
            for dir_name, manifest in repo['metadata']['project_manifests'].items():
                repo_context += f"### {dir_name}\n{manifest[:300]}...\n\n"
        
        context.append(repo_context)
        logger.debug(f"Finished context for {repo['name']} ({len(repo_context)} chars)")
    
    final_context = "\n\n".join(context)
    logger.info(f"Generated enhanced context ({len(final_context)} chars)")
    return final_context


def fetch_and_process_repos(username, github_token):
    """Fetch repositories and process them to extract relevant information."""
    logger.info(f"Fetching and processing repositories for user: {username}")
    headers = {'Authorization': f'token {github_token}'}
    all_repos = []
    page = 1
    per_page = 100  # GitHub API maximum
    
    # Fetch all repositories using pagination
    while True:
        logger.debug(f"Fetching repositories page {page}")
        repos_response = requests.get(
            f'https://api.github.com/users/{username}/repos?sort=updated&per_page={per_page}&page={page}',
            headers=headers
        )
        
        if repos_response.status_code != 200:
            logger.warning(f"GitHub API returned non-200 status for repos: {repos_response.status_code}")
            break
            
        page_repos = repos_response.json()
        if not page_repos:
            logger.debug(f"No more repositories found on page {page}")
            break
            
        all_repos.extend(page_repos)
        logger.debug(f"Added {len(page_repos)} repositories from page {page}")
        page += 1
    
    logger.info(f"Fetched {len(all_repos)} repositories for {username}")
    
    # Filter repositories and extract enhanced information
    filtered_repos = []
    for i, repo in enumerate(all_repos):
        # Include all repositories (both original and forked)
        # Get repository owner to check if it's owned by the user even if forked
        repo_owner = repo.get('owner', {}).get('login') 
        
        # Check if fork status needs to be logged
        if repo.get('fork', False):
            if repo_owner == username:
                logger.info(f"Including forked repository {repo['name']} as it's owned by {username}")
            else:
                logger.debug(f"Skipping third-party forked repository: {repo['name']}")
                continue
                
        logger.debug(f"Processing repository {i+1}/{len(all_repos)}: {repo['name']}")
        
        # Fetch additional details about the repo (languages, etc.)
        repo_detail_response = requests.get(
            repo['url'],
            headers=headers
        )
        
        if repo_detail_response.status_code == 200:
            repo_details = repo_detail_response.json()
            
            # Get languages used in the repo
            logger.debug(f"Fetching languages for {repo['name']}")
            languages_response = requests.get(
                repo['languages_url'],
                headers=headers
            )
            languages = languages_response.json() if languages_response.status_code == 200 else {}
            
            # Get README content if available
            readme_content = ""
            try:
                logger.debug(f"Fetching README for {repo['name']}")
                readme_response = requests.get(
                    f"https://api.github.com/repos/{username}/{repo['name']}/readme",
                    headers={"Authorization": f"token {github_token}", "Accept": "application/vnd.github.v3.raw"}
                )
                if readme_response.status_code == 200:
                    readme_content = readme_response.text
                    logger.debug(f"README found for {repo['name']} ({len(readme_content)} chars)")
                    readme_sections = extract_readme_sections(readme_content)
                else:
                    logger.debug(f"No README found for {repo['name']}")
                    readme_sections = {}
            except Exception as e:
                logger.warning(f"Error fetching README for {repo['name']}: {str(e)}")
                readme_sections = {}
            
            # Extract metadata from special files
            metadata = extract_repo_metadata(repo['name'], username, github_token)
            
            # Add fork status to the metadata for reference
            if repo.get('fork', False):
                if 'repo_context' not in metadata:
                    metadata['repo_context'] = {}
                if not isinstance(metadata['repo_context'], dict):
                    metadata['repo_context'] = {}
                metadata['repo_context']['fork_status'] = {
                    'is_fork': True,
                    'parent_full_name': repo.get('parent', {}).get('full_name', 'unknown'),
                    'fork_note': 'This is a fork owned by the portfolio author'
                }
            
            repo_info = {
                'name': repo['name'],
                'description': repo.get('description', ''),
                'language': repo.get('language', ''),
                'languages': list(languages.keys()),
                'topics': repo_details.get('topics', []),
                'stars': repo['stargazers_count'],
                'updated_at': repo['updated_at'],
                'url': repo['html_url'],
                'is_fork': repo.get('fork', False),  # Add fork status explicitly
                'readme_excerpt': readme_content[:1000] if readme_content else "",
                'readme_sections': readme_sections,
                'metadata': metadata
            }
            filtered_repos.append(repo_info)
            logger.info(f"Added repository to filtered list: {repo['name']}")
        else:
            logger.warning(f"Failed to fetch details for {repo['name']}: {repo_detail_response.status_code}")
    
    # Sort repositories by updated_at date (most recent first)
    filtered_repos.sort(key=lambda x: x.get('updated_at', ''), reverse=True)
    logger.info(f"Processed {len(filtered_repos)} repositories for {username}")
    
    return filtered_repos


def query_ai_assistant(query, repos_data):
    """Query the AI assistant with repository data and user query."""
    logger.info("Starting AI assistant query")
    
    # Add tracing for request sequence
    request_id = f"req-{int(time.time())}"
    logger.info(f"Request ID: {request_id} - Processing query: {query[:100]}...")
    
    # Generate enhanced context for the LLM
    context_start = time.time()
    context = generate_enhanced_context(repos_data)
    context_time = time.time() - context_start
    logger.info(f"Request ID: {request_id} - Generated context in {context_time:.2f}s ({len(context)} chars)")
    
    # Get the Groq API key from environment variables
    groq_api_key = os.getenv("GROQ_API_KEY")
    
    if not groq_api_key:
        logger.error(f"Request ID: {request_id} - Groq API key not configured")
        raise Exception("AI service (Groq) not configured")
    
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
        logger.debug(f"Request ID: {request_id} - Sending request to Groq API")
        api_start = time.time()
        
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": query}
            ],
            temperature=0.2,
            max_tokens=1000  # Increased to accommodate more detailed responses
        )
        
        api_time = time.time() - api_start
        logger.info(f"Request ID: {request_id} - Groq API responded in {api_time:.2f}s")
        
        # Extract response text
        ai_response = response.choices[0].message.content.strip()
        logger.info(f"Request ID: {request_id} - Generated response ({len(ai_response)} chars)")
        
        return ai_response
    except Exception as e:
        logger.error(f"Request ID: {request_id} - Error calling Groq API: {str(e)}", exc_info=True)
        raise