import os
import requests
import json

def create_github_repo():
    """
    Create a new GitHub repository for the YouTube transcript extractor project.
    
    This function:
    1. Connects to GitHub using your personal access token
    2. Creates a new public repository
    3. Sets up the initial repository settings
    4. Returns the repository URL for cloning
    
    Before using this function, make sure you have:
    1. A GitHub account
    2. A personal access token stored in your environment variables
    3. Git installed on your computer
    
    The repository will be created with:
    - Name: youtube-transcript-extractor
    - Description: A web application for YouTube transcripts
    - Public visibility
    - No initial files (you'll push them later)
    
    Returns:
        tuple: (success, result)
            - success (bool): True if repository was created, False if it failed
            - result (str): The repository URL if successful, error message if failed
    
    Example:
        >>> success, result = create_github_repo()
        >>> if success:
        ...     print(f"Repository created at: {result}")
        ... else:
        ...     print(f"Error: {result}")
    """
    headers = {
        'Authorization': f'token {os.environ["GITHUB_TOKEN"]}',
        'Accept': 'application/vnd.github.v3+json'
    }

    data = {
        'name': 'youtube-transcript-extractor',
        'description': 'A web application for extracting and managing YouTube video transcripts, supporting both individual videos and playlists.',
        'private': False,
        'auto_init': False
    }

    response = requests.post('https://api.github.com/user/repos', headers=headers, json=data)
    
    if response.status_code == 201:
        repo_info = response.json()
        return True, repo_info['clone_url']
    else:
        return False, f"Failed to create repository. Status code: {response.status_code}, Response: {response.text}"

if __name__ == "__main__":
    """
    Main execution block to create a GitHub repository and push initial commits.
    
    When the script is run directly, it calls the 'create_github_repo' function and handles the outcome. If the repository is created successfully, it adds the remote origin, sets the main branch, and pushes the initial commit. On failure, it prints the error message.
    """
    success, result = create_github_repo()
    if success:
        print(f"Repository created successfully!")
        print(f"Repository URL: {result}")
        
        # Add remote and push
        os.system(f'git remote add origin {result}')
        os.system('git branch -M main')
        os.system('git push -u origin main')
    else:
        print(f"Error: {result}")
