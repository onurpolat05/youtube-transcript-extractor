from flask import Flask, render_template, request, jsonify, make_response
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from youtube_transcript_api.formatters import TextFormatter
import re
import os
import json
import html
import logging
import xml.etree.ElementTree as ET
from io import StringIO
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import tempfile
import time
import random
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from functools import lru_cache
import backoff
from transcript_processor import batch_process_transcripts
from dotenv import load_dotenv

# .env dosyasını yükle
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'default-secret-key')
YOUTUBE_API_KEY = os.environ.get('YOUTUBE_API_KEY')
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')

# OpenAI API anahtarını kontrol et
if not OPENAI_API_KEY:
    logger.error("OpenAI API anahtarı bulunamadı!")
    raise ValueError("OpenAI API anahtarı tanımlanmamış")

# Constants
PLAYLIST_FETCH_TIMEOUT = 30  # seconds
MAX_PLAYLIST_ITEMS = 200
MAX_CONCURRENT_DOWNLOADS = 2
RATE_LIMIT_DELAY = 1  # seconds between requests
MAX_RETRIES = 5       # maximum number of retry attempts

# Rate limiting and progress tracking
download_locks = {}
download_progress = {}
progress_lock = Lock()
response_cache = {}
cache_lock = Lock()

def validate_youtube_url(url):
    """Validate YouTube URL format."""
    patterns = [
        r'^((?:https?:)?\/\/)?((?:www|m)\.)?youtube\.com\/watch\?v=[\w-]{11}',
        r'^((?:https?:)?\/\/)?((?:www|m)\.)?youtube\.com\/shorts\/[\w-]{11}',
        r'^((?:https?:)?\/\/)?((?:www|m)\.)?youtube\.com\/live\/[\w-]{11}',
        r'^((?:https?:)?\/\/)?((?:www|m)\.)?(youtube\.com|youtube-nocookie\.com)\/embed\/[\w-]{11}',
        r'^((?:https?:)?\/\/)?youtu\.be\/[\w-]{11}',
        r'^((?:https?:)?\/\/)?((?:www|m)\.)?youtube\.com\/playlist\?list=[\w-]+',
    ]
    url = url.split('&')[0]  # Remove query parameters after video ID/playlist ID
    return any(bool(re.match(pattern, url)) for pattern in patterns)

def extract_playlist_id(url):
    """Extract playlist ID from YouTube URL."""
    pattern = r'(?:youtube\.com\/playlist\?list=)([\w-]+)'
    match = re.search(pattern, url)
    return match.group(1) if match else None

@backoff.on_exception(
    backoff.expo,
    (HttpError,),
    max_tries=MAX_RETRIES,
    giveup=lambda e: isinstance(e, HttpError) and e.resp.status not in [429, 500, 503]
)
def fetch_playlist_videos(playlist_id):
    """Fetch video details from a YouTube playlist with rate limiting and retries."""
    if not YOUTUBE_API_KEY:
        logger.error("YouTube API key is missing")
        raise ValueError("YouTube API key is not configured")

    logger.info(f"Starting playlist fetch for playlist ID: {playlist_id}")
    youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
    start_time = time.time()
    videos = []
    next_page_token = None
    items_fetched = 0

    try:
        while True:
            if time.time() - start_time > PLAYLIST_FETCH_TIMEOUT:
                logger.error("Playlist fetch timeout")
                raise TimeoutError("Playlist fetch operation timed out")

            if items_fetched >= MAX_PLAYLIST_ITEMS:
                logger.warning(f"Reached maximum playlist items limit: {MAX_PLAYLIST_ITEMS}")
                break

            time.sleep(RATE_LIMIT_DELAY)
            
            logger.info(f"Fetching page of playlist items. Token: {next_page_token}")
            try:
                playlist_response = youtube.playlistItems().list(
                    part='snippet',
                    playlistId=playlist_id,
                    maxResults=50,
                    pageToken=next_page_token
                ).execute()

                if 'items' not in playlist_response:
                    raise ValueError("Invalid playlist data received from YouTube")

                for item in playlist_response['items']:
                    try:
                        snippet = item['snippet']
                        video_data = {
                            'title': snippet['title'],
                            'video_id': snippet['resourceId']['videoId'],
                            'thumbnail': snippet['thumbnails']['default']['url']
                        }
                        videos.append(video_data)
                        items_fetched += 1
                    except KeyError as e:
                        logger.warning(f"Skipping malformed playlist item: {str(e)}")
                        continue

                next_page_token = playlist_response.get('nextPageToken')
                if not next_page_token or items_fetched >= MAX_PLAYLIST_ITEMS:
                    break

            except HttpError as e:
                if e.resp.status in [403, 404]:
                    logger.error(f"Playlist not found or not accessible: {str(e)}")
                    raise ValueError("Playlist not found or not accessible")
                raise

        if not videos:
            logger.error("No valid videos found in playlist")
            raise ValueError("No valid videos found in playlist")

        logger.info(f"Successfully fetched {len(videos)} videos from playlist")
        return videos

    except Exception as e:
        logger.error(f"Error fetching playlist: {str(e)}")
        raise

@app.route('/')
def index():
    """Render the main page."""
    return render_template('index.html')

@app.route('/get_playlist', methods=['POST'])
def get_playlist():
    """Handle playlist fetching request."""
    try:
        if not request.is_json:
            return create_error_response("Request must be JSON", 415)
        
        data = request.get_json()
        if not isinstance(data, dict):
            return create_error_response("Invalid request format", 400)
        
        url = data.get('url')
        if not url:
            return create_error_response("No URL provided", 400)
        
        if not isinstance(url, str):
            return create_error_response("URL must be a string", 400)
        
        if not validate_youtube_url(url):
            return create_error_response("Invalid YouTube URL", 400)
        
        playlist_id = extract_playlist_id(url)
        if not playlist_id:
            return create_error_response("Invalid playlist URL", 400)
        
        logger.info(f"Fetching playlist for URL: {url}")
        try:
            videos = fetch_playlist_videos(playlist_id)
        except ValueError as e:
            return create_error_response(str(e), 400)
        except TimeoutError as e:
            return create_error_response(str(e), 408)
        except Exception as e:
            logger.error(f"Unexpected error in playlist fetch: {str(e)}")
            return create_error_response("An unexpected error occurred", 500)

        return jsonify({
            'status': 'success',
            'data': {
                'videos': videos
            }
        })
    
    except Exception as e:
        logger.error(f"Server error in get_playlist: {str(e)}")
        return create_error_response("An unexpected error occurred", 500)

@app.route('/download_transcript_batch', methods=['POST'])
def download_transcript_batch_route():
    """Handle batch transcript download requests with processing style selection."""
    try:
        logger.info("Starting batch transcript download request")
        if not request.is_json:
            return create_error_response("Request must be JSON", 415)

        data = request.get_json()
        video_ids = data.get('video_ids', [])
        style = data.get('style', 'default')

        logger.info(f"Starting transcript download for videos: {video_ids}")
        logger.info(f"Using processing style: {style}")

        if not video_ids:
            return create_error_response("No video IDs provided", 400)

        transcripts = []
        for video_id in video_ids:
            try:
                with progress_lock:
                    download_progress[video_id] = 0
                
                logger.info(f"Fetching video details from YouTube API for video: {video_id}")
                youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
                video_response = youtube.videos().list(
                    part='snippet',
                    id=video_id,
                    fields='items(snippet(title))'
                ).execute()
                
                video_title = video_response['items'][0]['snippet']['title']
                
                logger.info(f"Fetching transcript for video: {video_id}")
                transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
                formatter = TextFormatter()
                formatted_transcript = formatter.format_transcript(transcript_list)
                
                transcripts.append({
                    'video_id': video_id,
                    'title': video_title,
                    'transcript': formatted_transcript
                })
                
                with progress_lock:
                    download_progress[video_id] = 50  # 50% after transcript download
                    
            except YouTubeTranscriptApi.TranscriptsDisabled:
                logger.error(f"Transcripts are disabled for video {video_id}")
                with progress_lock:
                    download_progress[video_id] = -1
                continue
            except YouTubeTranscriptApi.NoTranscriptFound:
                logger.error(f"No transcript found for video {video_id}")
                with progress_lock:
                    download_progress[video_id] = -1
                continue
            except HttpError as e:
                logger.error(f"YouTube API error for video {video_id}: {str(e)}")
                with progress_lock:
                    download_progress[video_id] = -1
                continue
            except Exception as e:
                logger.error(f"Error processing video {video_id}: {str(e)}")
                with progress_lock:
                    download_progress[video_id] = -1
                continue

        if transcripts:
            logger.info(f"Starting OpenAI processing for {len(transcripts)} transcripts")
            processed_results = batch_process_transcripts(transcripts, style)
            
            for result in processed_results:
                video_id = result.get('video_id')
                if video_id and result.get('success', False):
                    with progress_lock:
                        download_progress[video_id] = 75  # 75% after OpenAI processing

            output = []
            for result in processed_results:
                if result.get('success', False):
                    output.extend([
                        f"Video Title: {result['title']}",
                        f"Video ID: {result['video_id']}",
                        f"Processing Style: {result['style']}",
                        "-" * 80,
                        "Summary:",
                        result['summary'],
                        "\nTags:",
                        ", ".join(result['tags']),
                        "\nKey Points:",
                        "\n".join([f"- {point}" for point in result['key_points']]),
                        "\nFormatted Text:",
                        result['formatted_text']
                    ])
                    
                    # Add style-specific sections
                    if result.get('research_implications'):
                        output.extend([
                            "\nResearch Implications:",
                            "\n".join([f"- {imp}" for imp in result['research_implications']])
                        ])
                    if result.get('code_snippets'):
                        output.extend([
                            "\nCode Snippets:",
                            "\n".join([f"```\n{snippet}\n```" for snippet in result['code_snippets']])
                        ])
                    if result.get('technical_concepts'):
                        output.extend([
                            "\nTechnical Concepts:",
                            "\n".join([f"- {concept}" for concept in result['technical_concepts']])
                        ])
                    if result.get('market_insights'):
                        output.extend([
                            "\nMarket Insights:",
                            "\n".join([f"- {insight}" for insight in result['market_insights']])
                        ])
                    if result.get('strategic_implications'):
                        output.extend([
                            "\nStrategic Implications:",
                            "\n".join([f"- {impl}" for impl in result['strategic_implications']])
                        ])

                    output.extend([
                        "=" * 80,
                        ""
                    ])

                    with progress_lock:
                        download_progress[result['video_id']] = 100
                else:
                    output.extend([
                        f"Error processing video {result.get('video_id', 'unknown')}: {result.get('error', 'Unknown error')}",
                        "=" * 80,
                        ""
                    ])

            if not output:
                logger.error("No output generated after processing")
                return create_error_response("Failed to generate output", 500)

            logger.info(f"Successfully processed {len(processed_results)} transcripts")
            response = make_response('\n'.join(output), 200)
            response.headers['Content-Type'] = 'text/plain'
            response.headers['Content-Disposition'] = 'attachment; filename="transcripts.txt"'
            return response
        else:
            return create_error_response("Failed to process any transcripts", 500)

    except Exception as e:
        logger.error(f"Server error in batch transcript download: {str(e)}")
        return create_error_response(f"Server error: {str(e)}", 500)

@app.route('/download_progress', methods=['POST'])
def get_download_progress():
    """Get the download progress for specified video IDs."""
    try:
        if not request.is_json:
            return create_error_response("Request must be JSON", 415)

        data = request.get_json()
        video_ids = data.get('video_ids', [])

        if not video_ids:
            return create_error_response("No video IDs provided", 400)

        with progress_lock:
            progress = {video_id: download_progress.get(video_id, 0) for video_id in video_ids}

        return jsonify({
            'status': 'success',
            'data': {
                'progress': progress
            }
        })

    except Exception as e:
        logger.error(f"Server error in progress check: {str(e)}")
        return create_error_response("An unexpected error occurred", 500)

def create_error_response(message, status_code=400):
    """Create a standardized error response."""
    logger.error(f"Creating error response: {message} (status: {status_code})")
    response = make_response(
        jsonify({
            'error': message,
            'status': 'error'
        }),
        status_code
    )
    response.headers['Content-Type'] = 'application/json'
    return response

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
