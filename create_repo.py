import os
import requests
import json

def create_github_repo():
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
