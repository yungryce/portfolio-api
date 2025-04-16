import json
import logging
import os
import re
import requests
import time
from datetime import datetime, timedelta
from azure.storage.blob import BlobServiceClient, ContentSettings
from base64 import b64decode

# Configure logging
logger = logging.getLogger('portfolio.github_client')
logger.setLevel(logging.INFO)

class GitHubClient:
    """Centralized client for GitHub API with caching and error handling."""
    
    def __init__(self, token=None, username=None, use_cache=True):
        """Initialize the GitHub client with authentication."""
        self.token = token or os.getenv('GITHUB_TOKEN')
        self.username = username or 'yungryce'  # Default to your username
        self.headers = {'Authorization': f'token {self.token}'} if self.token else {}
        self.use_cache = use_cache
        self.cache_ttl = 3600  # Default cache TTL: 1 hour
        
        # Connect to Azure Blob Storage for caching
        connection_string = os.getenv('AzureWebJobsStorage')
        if connection_string and self.use_cache:
            try:
                self.blob_service_client = BlobServiceClient.from_connection_string(connection_string)
                self.container_name = 'github-cache'
                
                # Create container if it doesn't exist
                try:
                    self.blob_service_client.create_container(self.container_name)
                    logger.info(f"Created cache container: {self.container_name}")
                except Exception:
                    # Container likely already exists
                    logger.debug(f"Container {self.container_name} already exists")
                    
                logger.info("Azure Storage cache initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Azure Storage cache: {str(e)}")
                self.blob_service_client = None
        else:
            logger.warning("Azure Storage connection string not found, caching disabled")
            self.blob_service_client = None
    
    def _cache_key(self, endpoint):
        """Generate a cache key for a given endpoint."""
        return f"{endpoint.replace('/', '_')}"
    
    def _get_from_cache(self, endpoint):
        """Retrieve data from cache if available and not expired."""
        if not self.blob_service_client or not self.use_cache:
            return None
            
        cache_key = self._cache_key(endpoint)
        try:
            # Get the blob client
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name, 
                blob=cache_key
            )
            
            # Check if blob exists
            if blob_client.exists():
                # Download the blob
                data = blob_client.download_blob().readall()
                cache_data = json.loads(data)
                
                # Check expiration
                if 'expires_at' in cache_data:
                    expires_at = datetime.fromisoformat(cache_data['expires_at'])
                    if expires_at > datetime.now():
                        logger.info(f"Cache hit for {endpoint}")
                        return cache_data['data']
                    else:
                        logger.debug(f"Cache expired for {endpoint}")
                
                # Delete expired blob
                blob_client.delete_blob()
                
            return None
        except Exception as e:
            logger.warning(f"Error reading from cache: {str(e)}")
            return None
    
    def _save_to_cache(self, endpoint, data, ttl=None):
        """Save data to cache with expiration time."""
        if not self.blob_service_client or not self.use_cache:
            return False
            
        ttl = ttl or self.cache_ttl
        cache_key = self._cache_key(endpoint)
        
        try:
            # Prepare data with expiration
            cache_data = {
                'data': data,
                'expires_at': (datetime.now() + timedelta(seconds=ttl)).isoformat(),
                'cached_at': datetime.now().isoformat()
            }
            
            # Get the blob client
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name, 
                blob=cache_key
            )
            
            # Upload the data
            blob_client.upload_blob(
                json.dumps(cache_data),
                overwrite=True,
                content_settings=ContentSettings(content_type='application/json')
            )
            
            logger.info(f"Saved to cache: {endpoint}")
            return True
        except Exception as e:
            logger.warning(f"Error saving to cache: {str(e)}")
            return False
    
    def make_request(self, method, endpoint, headers=None, params=None, data=None, accept_raw=False, use_cache=None):
        """Make a request to GitHub API with caching and error handling."""
        use_cache = self.use_cache if use_cache is None else use_cache
        full_url = f"https://api.github.com/{endpoint.lstrip('/')}"
        
        # Merge default headers with custom headers
        request_headers = self.headers.copy()
        if headers:
            request_headers.update(headers)
            
        # Add Accept header for raw content if requested
        if accept_raw:
            request_headers['Accept'] = 'application/vnd.github.v3.raw'
        
        # Generate cache key only for GET requests
        cache_eligible = method.upper() == 'GET' and use_cache
        
        # Check cache first for GET requests
        if cache_eligible:
            cache_data = self._get_from_cache(endpoint)
            if cache_data is not None:
                return cache_data
        
        # Make the request with retries
        retries = 3
        backoff = 1
        last_exception = None
        
        for attempt in range(retries):
            try:
                logger.debug(f"Making {method} request to {full_url} (attempt {attempt+1}/{retries})")
                response = requests.request(
                    method=method,
                    url=full_url,
                    headers=request_headers,
                    params=params,
                    json=data,
                    timeout=10  # Add a reasonable timeout
                )
                
                # Handle rate limiting
                if response.status_code == 403 and 'X-RateLimit-Remaining' in response.headers:
                    remaining = int(response.headers.get('X-RateLimit-Remaining', 0))
                    if remaining == 0:
                        reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
                        wait_time = max(0, reset_time - time.time())
                        logger.warning(f"Rate limit exceeded, waiting {wait_time:.2f}s")
                        if wait_time > 0 and wait_time < 60:  # Only wait if reasonable
                            time.sleep(wait_time + 1)
                            continue
                
                # If successful and it's a GET request, cache the result
                if response.status_code == 200 and cache_eligible:
                    if accept_raw:
                        result = response.text
                    else:
                        try:
                            result = response.json()
                        except:
                            result = response.text
                    
                    # Cache the result
                    self._save_to_cache(endpoint, result)
                    return result
                
                # Return the response directly for success or failure
                if accept_raw:
                    return response.text if response.status_code == 200 else None
                else:
                    try:
                        return response.json()
                    except:
                        return response.text
                
            except requests.exceptions.ConnectionError as e:
                logger.warning(f"Connection error on attempt {attempt+1}: {str(e)}")
                last_exception = e
                if "Failed to resolve" in str(e) or "Name or service not known" in str(e):
                    logger.error(f"DNS resolution failure when connecting to GitHub API")
                time.sleep(backoff)
                backoff *= 2
                continue
                
            except Exception as e:
                logger.warning(f"Request error on attempt {attempt+1}: {str(e)}")
                last_exception = e
                time.sleep(backoff)
                backoff *= 2
                continue
        
        # If we get here, all retries failed
        logger.error(f"All {retries} attempts failed for {full_url}: {str(last_exception)}")
        raise Exception(f"GitHub API request failed after {retries} attempts: {str(last_exception)}")
    
    def get_user_repos(self, username=None, per_page=100):
        """Get repositories for a user with pagination handling."""
        username = username or self.username
        endpoint = f"users/{username}/repos"
        params = {'sort': 'updated', 'per_page': per_page}
        
        # Check if we have this cached
        cache_key = f"users_{username}_repos_full"
        cached_data = self._get_from_cache(cache_key)
        if cached_data is not None:
            logger.info(f"Using cached repository data for {username}")
            return cached_data
        
        # If not cached, fetch all pages
        all_repos = []
        page = 1
        
        while True:
            params['page'] = page
            logger.info(f"Fetching repositories page {page} for {username}")
            
            try:
                repos = self.make_request('GET', endpoint, params=params)
                
                if not repos or not isinstance(repos, list):
                    break
                    
                all_repos.extend(repos)
                logger.info(f"Fetched {len(repos)} repositories on page {page}")
                
                if len(repos) < per_page:
                    break
                    
                page += 1
                
            except Exception as e:
                logger.error(f"Error fetching repos for {username}, page {page}: {str(e)}")
                break
        
        # Cache the complete repository list
        if all_repos:
            self._save_to_cache(cache_key, all_repos, ttl=7200)  # Cache for 2 hours
            
        return all_repos
    
    def get_readme(self, username=None, repo=None):
        """Get README content for a repository."""
        username = username or self.username
        if not repo:
            raise ValueError("Repository name is required")
            
        endpoint = f"repos/{username}/{repo}/readme"
        return self.make_request('GET', endpoint, accept_raw=True)
    
    def extract_readme_sections(self, readme_content):
        """Extract meaningful sections from README content."""
        if not readme_content:
            return {}
            
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
            matches = re.search(pattern, readme_content, re.DOTALL)
            if matches:
                sections[key] = matches.group(1).strip()
        
        logger.debug(f"Found {len(sections)} README sections")
        return sections
        
    def get_repo_details(self, username=None, repo=None):
        """Get detailed information for a repository."""
        username = username or self.username
        if not repo:
            raise ValueError("Repository name is required")
            
        endpoint = f"repos/{username}/{repo}"
        return self.make_request('GET', endpoint)
        
    def get_repo_languages(self, username=None, repo=None):
        """Get languages used in a repository."""
        username = username or self.username
        if not repo:
            raise ValueError("Repository name is required")
            
        endpoint = f"repos/{username}/{repo}/languages"
        return self.make_request('GET', endpoint)
        
    def get_file_content(self, username=None, repo=None, path=None):
        """Get content of a specific file in a repository."""
        username = username or self.username
        if not repo:
            raise ValueError("Repository name is required")
        if not path:
            raise ValueError("File path is required")
            
        endpoint = f"repos/{username}/{repo}/contents/{path}"
        return self.make_request('GET', endpoint, accept_raw=True)
    
    def extract_repo_metadata(self, repo_name, username=None):
        """Extract structured metadata from special files in the repository."""
        username = username or self.username
        metadata = {}
        
        # Check for repo-context.json at root
        try:
            logger.debug(f"Checking for .repo-context.json in {username}/{repo_name}")
            context_data = self.get_file_content(username, repo_name, '.repo-context.json')
            if context_data:
                try:
                    context_json = json.loads(context_data)
                    metadata['context'] = context_json
                    logger.debug(f"Extracted .repo-context.json from {repo_name}")
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON in .repo-context.json for {repo_name}")
        except Exception as e:
            logger.debug(f"No .repo-context.json found for {repo_name}: {str(e)}")
        
        # Check for PROJECT-MANIFEST.md files in subdirectories
        try:
            manifest_content = self.get_file_content(username, repo_name, 'PROJECT-MANIFEST.md')
            if manifest_content:
                metadata['manifest'] = manifest_content
                logger.debug(f"Extracted PROJECT-MANIFEST.md from {repo_name}")
        except Exception as e:
            logger.debug(f"No PROJECT-MANIFEST.md found for {repo_name}: {str(e)}")
        
        # Check for SKILLS-INDEX.md
        try:
            skills_content = self.get_file_content(username, repo_name, 'SKILLS-INDEX.md')
            if skills_content:
                metadata['skills'] = skills_content
                logger.debug(f"Extracted SKILLS-INDEX.md from {repo_name}")
        except Exception as e:
            logger.debug(f"No SKILLS-INDEX.md found for {repo_name}: {str(e)}")
        
        if metadata:
            logger.info(f"Extracted metadata from {len(metadata)} special files for {repo_name}")
            
        return metadata
        
    def get_processed_repos(self, username=None):
        """Get processed repository data with all necessary details."""
        username = username or self.username
        
        # Check for cached processed repos
        cache_key = f"processed_repos_{username}"
        cached_data = self._get_from_cache(cache_key)
        if cached_data is not None:
            logger.info(f"Using cached processed repositories for {username}")
            return cached_data
        
        # Get all repositories
        all_repos = self.get_user_repos(username)
        
        # Process repositories to extract details
        processed_repos = []
        for repo in all_repos:
            try:
                repo_name = repo['name']
                logger.info(f"Processing repository: {repo_name}")
                
                # Get languages
                languages = self.get_repo_languages(username, repo_name)
                
                # Get README
                readme_content = self.get_readme(username, repo_name)
                
                # Extract readme sections
                readme_sections = self.extract_readme_sections(readme_content) if readme_content else {}
                
                # Extract metadata
                metadata = self.extract_repo_metadata(repo_name, username)
                
                repo_info = {
                    'name': repo_name,
                    'description': repo.get('description', ''),
                    'language': repo.get('language', ''),
                    'languages': list(languages.keys()) if languages else [],
                    'topics': repo.get('topics', []),
                    'stars': repo.get('stargazers_count', 0),
                    'updated_at': repo.get('updated_at', ''),
                    'url': repo.get('html_url', ''),
                    'is_fork': repo.get('fork', False),
                    'readme_excerpt': readme_content[:1000] if readme_content else "",
                    'readme_sections': readme_sections,
                    'metadata': metadata
                }
                
                processed_repos.append(repo_info)
                logger.info(f"Successfully processed repository: {repo_name}")
                
            except Exception as e:
                logger.error(f"Error processing repository {repo.get('name', 'unknown')}: {str(e)}")
                # Continue with next repository
        
        # Sort by updated_at date
        processed_repos.sort(key=lambda x: x.get('updated_at', ''), reverse=True)
        
        # Cache the processed repositories
        if processed_repos:
            self._save_to_cache(cache_key, processed_repos, ttl=7200)  # Cache for 2 hours
            
        return processed_repos
    
    def generate_enhanced_context(self, repos_data):
        """Generate rich context from structured repository data."""
        logger.info(f"Generating enhanced context from {len(repos_data)} repositories")
        context = []
        
        for repo in repos_data:
            repo_context = f"Repository: {repo['name']}\n"
            repo_context += f"Description: {repo['description']}\n"
            
            # Add languages
            if repo['languages']:
                repo_context += f"Languages: {', '.join(repo['languages'])}\n"
            
            # Add topics
            if repo.get('topics'):
                repo_context += f"Topics: {', '.join(repo['topics'])}\n"
            
            # Add readme sections
            if repo.get('readme_sections'):
                for section_name, section_content in repo['readme_sections'].items():
                    repo_context += f"\n{section_name.replace('_', ' ').title()}:\n{section_content[:500]}...\n"
            
            # Add metadata
            if repo.get('metadata'):
                repo_context += "\nMetadata:\n"
                if 'context' in repo['metadata']:
                    context_data = repo['metadata']['context']
                    if isinstance(context_data, dict):
                        for key, value in context_data.items():
                            repo_context += f"- {key}: {value}\n"
                
                if 'skills' in repo['metadata']:
                    skills_content = repo['metadata']['skills']
                    repo_context += f"\nSkills: {skills_content[:300]}...\n"
            
            context.append(repo_context)
        
        final_context = "\n\n".join(context)
        logger.info(f"Generated enhanced context ({len(final_context)} chars)")
        return final_context