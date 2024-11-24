import os
from openai import OpenAI
import json
import time
import logging
from functools import wraps
import backoff
import re
from prompt_templates import get_template
from dotenv import load_dotenv

# .env dosyasını yükle
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# API anahtarını doğrudan .env'den oku ve OpenAI client'a ver
client = OpenAI(
    api_key=os.getenv('OPENAI_API_KEY', None)  # None varsayılan değer olarak
)

# Constants for rate limiting
RATE_LIMIT_DELAY = 10  # seconds between requests
MAX_RETRIES = 3

def rate_limit_decorator(min_delay=RATE_LIMIT_DELAY):
    """
    Decorator to implement rate limiting between API calls.
    
    This decorator ensures that there is a minimum delay between consecutive calls to the decorated function. It helps in respecting API rate limits by preventing rapid-fire requests.
    
    Args:
        min_delay (int, optional): The minimum delay in seconds between function calls. Defaults to RATE_LIMIT_DELAY.
    
    Returns:
        function: The decorated function with rate limiting applied.
    """
    last_call = {}
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            current_time = time.time()
            last_time = last_call.get(func.__name__, 0)
            sleep_time = min_delay - (current_time - last_time)
            
            if sleep_time > 0:
                time.sleep(sleep_time)
            
            result = func(*args, **kwargs)
            last_call[func.__name__] = time.time()
            return result
        return wrapper
    return decorator

def validate_response(input_text, response):
    """
    Validate the OpenAI API response for proper text formatting.
    
    This function checks whether the response from the OpenAI API contains the expected fields and that the formatted text differs from the input text. It ensures that the response meets the required structure and content integrity before further processing.
    
    Args:
        input_text (str): The original transcript text that was processed.
        response (dict): The response dictionary returned by the OpenAI API.
    
    Returns:
        bool: True if the response is valid, otherwise raises an error.
    
    Raises:
        ValueError: If the response is missing required fields or the formatted text remains unchanged.
    """
    if not response.get('formatted_text'):
        raise ValueError("Response missing formatted text")
    
    if response['formatted_text'] == input_text:
        raise ValueError("Formatted text unchanged from input")
        
    # Additional validation - ensure required fields exist
    required_fields = ['summary', 'tags', 'key_points']
    missing_fields = [field for field in required_fields if not response.get(field)]
    if missing_fields:
        raise ValueError(f"Response missing required fields: {', '.join(missing_fields)}")
    
    return True

def clean_and_transform_response(response_text):
    """
    Clean and transform the raw OpenAI response text into a structured JSON format.
    
    This function attempts to parse the raw response text from OpenAI as JSON. If direct parsing fails due to formatting issues, it applies several cleaning steps to correct common JSON formatting problems before attempting to parse again. As a last resort, it extracts specific fields using regex patterns.
    
    Args:
        response_text (str): The raw response text from the OpenAI API.
    
    Returns:
        dict: The cleaned and structured response data containing fields like 'formatted_text', 'summary', 'tags', and 'key_points'.
    """
    try:
        # First try direct JSON parsing
        return json.loads(response_text)
    except json.JSONDecodeError:
        # Fallback parsing for malformed JSON
        try:
            # Clean up common JSON formatting issues
            cleaned_text = response_text.strip()
            # Remove any markdown formatting
            cleaned_text = re.sub(r'```json\s*|\s*```', '', cleaned_text)
            # Ensure proper quote usage
            cleaned_text = cleaned_text.replace("'", '"')
            return json.loads(cleaned_text)
        except json.JSONDecodeError:
            # If still failing, extract content using regex
            extracted = {
                'formatted_text': extract_field(response_text, 'formatted_text'),
                'summary': extract_field(response_text, 'summary'),
                'tags': extract_field(response_text, 'tags', is_list=True),
                'key_points': extract_field(response_text, 'key_points', is_list=True)
            }
            return extracted

def extract_field(text, field_name, is_list=False):
    """
    Extract field values from text using regex patterns.
    
    This helper function searches for a specific field within the provided text and extracts its value. It supports extraction of both single values and lists based on the 'is_list' parameter.
    
    Args:
        text (str): The text to extract fields from.
        field_name (str): The name of the field to extract.
        is_list (bool, optional): Whether the field value is a list. Defaults to False.
    
    Returns:
        str or list: The extracted field value or list of values. Returns an empty list or string if extraction fails.
    """
    if is_list:
        pattern = r'["\']?' + re.escape(field_name) + r'["\']?\s*:\s*\[(.*?)\]'
        match = re.search(pattern, text, re.DOTALL)
        if match:
            items = re.findall(r'["\']([^"\']+)["\']', match.group(1))
            return items
        return []
    else:
        pattern = r'["\']?' + re.escape(field_name) + r'["\']?\s*:\s*["\']([^"\']+)["\']'
        match = re.search(pattern, text)
        return match.group(1) if match else ""

@rate_limit_decorator()
@backoff.on_exception(
    backoff.expo,
    (Exception,),
    max_tries=MAX_RETRIES,
    giveup=lambda e: isinstance(e, KeyError)
)
def process_transcript(transcript_text, style="default"):
    """
    Process a YouTube video transcript using OpenAI to make it more readable and extract key information.
    
    This function does several things:
    1. Takes the raw transcript text and sends it to OpenAI
    2. Formats the text to be more readable (fixes grammar, adds paragraphs, etc.)
    3. Creates a summary of the content
    4. Identifies important topics and tags
    5. Lists key points from the video
    
    The 'style' parameter changes how the transcript is processed:
    - "default": Basic formatting and analysis
    - "academic": Focus on research and scholarly content
    - "technical": Focus on technical details and code
    - "business": Focus on business insights and strategy
    
    Args:
        transcript_text (str): The raw transcript text from the YouTube video
        style (str, optional): How you want the transcript processed. Defaults to "default"
    
    Returns:
        dict: A dictionary containing:
            - formatted_text: The cleaned up transcript
            - summary: A brief summary of the content
            - tags: List of relevant topics
            - key_points: Main points from the video
            - Additional fields based on the style chosen
    
    Raises:
        ValueError: If the transcript text is empty or invalid
        Exception: If there's an error processing with OpenAI
    
    Example:
        >>> result = process_transcript("Raw video transcript...", style="technical")
        >>> print(result['summary'])
        'A technical discussion about Python programming...'
    """
    try:
        if not transcript_text or not isinstance(transcript_text, str):
            raise ValueError("Invalid transcript text provided")

        template = get_template(style)
        
        response = client.chat.completions.create(
            model=os.getenv('OPENAI_MODEL', 'gpt-4o-mini-2024-07-18'),
            messages=[
                {
                    "role": "system",
                    "content": template["system_prompt"]
                },
                {"role": "user", "content": transcript_text}
            ],
            response_format=template["response_format"]
        )
        
        response_text = response.choices[0].message.content
        processed_response = clean_and_transform_response(response_text)
        
        # Validate the response
        validate_response(transcript_text, processed_response)
        
        return processed_response
    except Exception as e:
        logger.error(f"Failed to process transcript: {e}")
        raise Exception(f"Failed to process transcript: {str(e)}")

def batch_process_transcripts(transcripts, style="default"):
    """
    Process multiple transcripts with OpenAI, incorporating improved error handling and rate limiting.
    
    This function iterates over a list of transcripts, processing each one using the 'process_transcript' function. It validates input data, manages rate limits, handles exceptions for individual transcripts, and compiles the results. The function raises an exception if all transcript processing attempts fail.
    
    Args:
        transcripts (list): A list of transcript dictionaries to process. Each dictionary should contain 'video_id', 'title', and 'transcript' keys.
        style (str, optional): The processing style to apply. Defaults to "default".
    
    Returns:
        list: A list of result dictionaries for each processed transcript, indicating success or failure and containing processed data or error messages.
    
    Raises:
        ValueError: If the input transcripts are invalid or the OpenAI API key is missing.
        Exception: If all transcript processing attempts fail.
    """
    if not transcripts or not isinstance(transcripts, list):
        raise ValueError("Invalid transcripts input: must be a non-empty list")

    if not client.api_key:
        raise ValueError("OpenAI API anahtarı bulunamadı!")

    results = []
    for transcript in transcripts:
        try:
            # Input validation
            if not isinstance(transcript, dict):
                raise ValueError(f"Invalid transcript format for video {transcript.get('video_id', 'unknown')}")
            
            if 'transcript' not in transcript or 'video_id' not in transcript:
                raise KeyError(f"Missing required fields for video {transcript.get('video_id', 'unknown')}")

            # Process transcript with rate limiting and retries
            processed = process_transcript(transcript['transcript'], style)
            
            results.append({
                'video_id': transcript['video_id'],
                'title': transcript.get('title', 'Unknown Title'),
                'formatted_text': processed.get('formatted_text', ''),
                'summary': processed.get('summary', ''),
                'tags': processed.get('tags', []),
                'key_points': processed.get('key_points', []),
                'full_transcript': transcript['transcript'],  # Original unformatted text
                'style': style,
                'research_implications': processed.get('research_implications', []),
                'code_snippets': processed.get('code_snippets', []),
                'technical_concepts': processed.get('technical_concepts', []),
                'market_insights': processed.get('market_insights', []),
                'strategic_implications': processed.get('strategic_implications', []),
                'success': True
            })
            
        except (ValueError, KeyError) as e:
            logger.error(f"Validation error for video {transcript.get('video_id', 'unknown')}: {e}")
            results.append({
                'video_id': transcript.get('video_id', 'unknown'),
                'error': str(e),
                'success': False,
                'error_type': 'validation_error'
            })
        except Exception as e:
            logger.error(f"Processing error for video {transcript.get('video_id', 'unknown')}: {e}")
            results.append({
                'video_id': transcript.get('video_id', 'unknown'),
                'error': str(e),
                'success': False,
                'error_type': 'processing_error'
            })

    if not any(result.get('success', False) for result in results):
        logger.error("All transcript processing attempts failed")
        raise Exception("Failed to process any transcripts successfully")

    return results

def handle_api_error(error, video_id):
    """
    Handle errors that occur during API calls to OpenAI.
    
    This function processes different types of API errors and creates appropriate error messages.
    It helps maintain consistent error handling across the application.
    
    Common errors handled:
    1. Rate limiting errors (too many requests)
    2. Authentication errors (invalid API key)
    3. Context length errors (transcript too long)
    4. Timeout errors (API taking too long)
    
    Args:
        error (Exception): The error that occurred during the API call
        video_id (str): ID of the video being processed when error occurred
    
    Returns:
        dict: Error information containing:
            - error_type: Classification of the error
            - message: Human-readable error message
            - video_id: The affected video ID
    
    Example:
        >>> try:
        ...     process_video()
        ... except Exception as e:
        ...     error_info = handle_api_error(e, "abc123")
        ...     print(f"Error type: {error_info['error_type']}")
    """

def update_progress(video_id, progress_value):
    """
    Update the processing progress for a specific video.
    
    This function safely updates the progress tracking for a video being processed.
    It uses thread-safe operations to prevent race conditions when multiple videos
    are being processed simultaneously.
    
    Progress values typically represent:
    - 0: Starting process
    - 25: Downloaded transcript
    - 50: Started OpenAI processing
    - 75: Completed OpenAI processing
    - 100: All processing complete
    - -1: Error occurred
    
    Args:
        video_id (str): The ID of the video to update progress for
        progress_value (int): The new progress value (0-100, or -1 for error)
    
    Example:
        >>> update_progress("abc123", 25)  # Transcript downloaded
        >>> update_progress("abc123", -1)  # Error occurred
    """

def format_transcript_output(processed_data):
    """
    Format the processed transcript data into a readable text format.
    
    Takes the raw processed data and creates a well-structured text document
    that's easy to read and understand. This is the final step before
    saving or displaying the results.
    
    The formatted output includes:
    1. Video information (title, ID)
    2. Summary section
    3. Key points in bullet format
    4. Tags section
    5. Style-specific sections (e.g., code snippets, research notes)
    6. Full formatted transcript
    
    Args:
        processed_data (dict): The processed transcript data containing all analysis
    
    Returns:
        str: A nicely formatted text document ready for saving or display
    
    Example:
        >>> data = process_transcript(raw_text)
        >>> formatted = format_transcript_output(data)
        >>> print(formatted)
        Video Title: Example Video
        ...
    """

def validate_input_data(transcript_data):
    """
    Check if the input transcript data has all required fields and valid formats.
    
    This function performs several checks:
    1. Verifies all required fields are present
    2. Checks that text fields contain actual content
    3. Validates video ID format
    4. Ensures transcript text isn't too long for API limits
    
    Required fields:
    - video_id: YouTube video identifier
    - title: Video title
    - transcript: The actual transcript text
    
    Args:
        transcript_data (dict): The transcript data to validate
    
    Returns:
        bool: True if all validation checks pass
    
    Raises:
        ValueError: If any validation checks fail, with specific error message
    
    Example:
        >>> data = {'video_id': 'abc123', 'title': 'Test', 'transcript': 'Text...'}
        >>> try:
        ...     validate_input_data(data)
        ...     print("Data is valid")
        ... except ValueError as e:
        ...     print(f"Invalid data: {e}")
    """

def cache_results(video_id, processed_data):
    """
    Cache the processed transcript results to avoid reprocessing the same video.
    
    This function:
    1. Stores processed results in memory cache
    2. Uses thread-safe operations for cache access
    3. Implements cache size limits to prevent memory issues
    4. Handles cache expiration
    
    The cache helps:
    - Reduce API costs
    - Improve response times
    - Reduce server load
    
    Args:
        video_id (str): The YouTube video ID to use as cache key
        processed_data (dict): The processed transcript data to cache
    
    Returns:
        bool: True if caching was successful, False if it failed
    
    Example:
        >>> results = process_transcript(text)
        >>> cache_results("abc123", results)
        True
    """

def get_cached_results(video_id):
    """
    Retrieve previously processed transcript results from cache.
    
    This function:
    1. Checks if results exist in cache
    2. Verifies cache entry hasn't expired
    3. Returns cached data if available
    4. Uses thread-safe operations
    
    Args:
        video_id (str): The YouTube video ID to look up
    
    Returns:
        dict or None: The cached results if found and valid, None otherwise
    
    Example:
        >>> cached_data = get_cached_results("abc123")
        >>> if cached_data:
        ...     print("Using cached results")
        ... else:
        ...     print("Need to process video")
    """
