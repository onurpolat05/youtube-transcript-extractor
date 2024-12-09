import os
from openai import OpenAI
import json
import time
import logging
from functools import wraps
import backoff
import re
import httpx
from prompt_templates import get_template
from dotenv import load_dotenv
from datetime import datetime
from typing import Dict  # Add this line

# .env dosyasını yükle
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Create a file handler
file_handler = logging.FileHandler('app.log')
file_handler.setLevel(logging.DEBUG)

# Create a logging format
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)

# Add the file handler to the logger
logger.addHandler(file_handler)

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
                logger.debug(f"Rate limiting: sleeping for {sleep_time} seconds")
                time.sleep(sleep_time)
            
            result = func(*args, **kwargs)
            last_call[func.__name__] = time.time()
            return result
        return wrapper
    return decorator

def validate_response(input_text, response):
    """
    Validate the OpenAI API response for proper text formatting.
    """
    logger.debug("Validating response")
    if not response.get('formatted_text'):
        logger.error("Response missing formatted text")
        raise ValueError("Response missing formatted text")
    
    if response['formatted_text'] == input_text:
        logger.error("Formatted text unchanged from input")
        raise ValueError("Formatted text unchanged from input")
        
    # Check for metadata in formatted text
    metadata_patterns = [
        r'^(?:Title|Video Title):[^\n]+\n',
        r'^(?:Video )?ID:[^\n]+\n',
        r'^Channel:[^\n]+\n',
        r'^Published:[^\n]+\n',
        r'^Transcript:\n'
    ]
    
    formatted_text = response['formatted_text']
    for pattern in metadata_patterns:
        if re.search(pattern, formatted_text, re.MULTILINE):
            logger.debug("Cleaning metadata from formatted text")
            response['formatted_text'] = clean_metadata_from_text(formatted_text)
            break
        
    # Additional validation - ensure required fields exist
    required_fields = ['summary', 'tags', 'key_points']
    missing_fields = [field for field in required_fields if not response.get(field)]
    if missing_fields:
        logger.error(f"Response missing required fields: {', '.join(missing_fields)}")
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
    logger.debug("Cleaning and transforming response")
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
            # Try to parse cleaned JSON
            return json.loads(cleaned_text)
        except json.JSONDecodeError:
            # If still failing, extract content using regex
            logger.warning("Falling back to regex extraction for response parsing")
            extracted = {
                'formatted_text': extract_field(response_text, 'formatted_text') or '',
                'summary': extract_field(response_text, 'summary') or '',
                'tags': extract_field(response_text, 'tags', is_list=True) or [],
                'key_points': extract_field(response_text, 'key_points', is_list=True) or []
            }
            
            # Validate extracted content
            if not any(extracted.values()):
                logger.error("Failed to extract any content from response")
                raise ValueError("Failed to parse response and extract content")
                
            # Clean up empty or malformed entries
            if isinstance(extracted['key_points'], list):
                extracted['key_points'] = [point.strip() for point in extracted['key_points'] if point.strip() and point.strip() != ',']
            if isinstance(extracted['tags'], list):
                extracted['tags'] = [tag.strip() for tag in extracted['tags'] if tag.strip() and tag.strip() != ',']
                
            return extracted

def extract_field(text, field_name, is_list=False):
    """
    Extract field values from text using regex patterns.
    """
    logger.debug(f"Extracting field: {field_name}")
    if is_list:
        pattern = r'["\']?' + re.escape(field_name) + r'["\']?\s*:\s*\[(.*?)\]'
        match = re.search(pattern, text, re.DOTALL)
        if match:
            items = re.findall(r'["\']([^"\']+)["\']', match.group(1))
            return items
        return []
    else:
        # For formatted_text, try to extract everything after the field name until the next field
        if field_name == 'formatted_text':
            pattern = r'["\']?' + re.escape(field_name) + r'["\']?\s*:\s*["\']([^"]*(?:"(?:[^"]*"[^"]*)*)?)["\']'
            match = re.search(pattern, text, re.DOTALL)
            if match:
                extracted_text = match.group(1)
                # Clean metadata from the extracted text
                return clean_metadata_from_text(extracted_text)
        
        # For other fields, use the standard pattern
        pattern = r'["\']?' + re.escape(field_name) + r'["\']?\s*:\s*["\']([^"\']+)["\']'
        match = re.search(pattern, text)
        if match:
            return match.group(1)
            
        # If no match, try multiline pattern
        pattern = r'["\']?' + re.escape(field_name) + r'["\']?\s*:\s*["\']([^"\']+(?:[^"\']+)*)["\']'
        match = re.search(pattern, text, re.DOTALL)
        return match.group(1) if match else ""

def identify_sections(text: str) -> Dict[str, str]:
    """
    Split the response into main sections for targeted cleaning.
    """
    logger.debug("Identifying sections in text")
    sections = {
        'summary': '',
        'tags': '',
        'key_points': '',
        'formatted_text': ''
    }
    
    try:
        # Extract each section using regex
        summary_match = re.search(r'1\.\s*Summary:(.+?)(?=2\.\s*(?:Relevant\s*)?[Tt]ags:)', text, re.DOTALL)
        tags_match = re.search(r'2\.\s*(?:Relevant\s*)?[Tt]ags:(.+?)(?=3\.\s*Key\s*[Pp]oints:)', text, re.DOTALL)
        key_points_match = re.search(r'3\.\s*Key\s*[Pp]oints:(.+?)(?=4\.\s*Formatted\s*[Tt]ranscript:)', text, re.DOTALL)
        formatted_text_match = re.search(r'4\.\s*Formatted\s*[Tt]ranscript:(.+?)$', text, re.DOTALL)
        
        if summary_match:
            sections['summary'] = summary_match.group(1).strip()
            logger.debug(f"Found summary section: {len(sections['summary'])} chars")
        
        if tags_match:
            sections['tags'] = tags_match.group(1).strip()
            logger.debug(f"Found tags section: {len(sections['tags'])} chars")
        
        if key_points_match:
            sections['key_points'] = key_points_match.group(1).strip()
            logger.debug(f"Found key points section: {len(sections['key_points'])} chars")
        
        if formatted_text_match:
            sections['formatted_text'] = formatted_text_match.group(1).strip()
            logger.debug(f"Found formatted text section: {len(sections['formatted_text'])} chars")
        
        # Log if any section is missing
        missing_sections = [k for k, v in sections.items() if not v]
        if missing_sections:
            logger.warning(f"Missing sections: {', '.join(missing_sections)}")
            
    except Exception as e:
        logger.error(f"Error splitting sections: {str(e)}")
    
    return sections

def clean_transcript_content(text: str) -> str:
    """
    Clean only the transcript portion, preserving actual content.
    """
    logger.debug("Cleaning transcript content")
    if not text:
        return text
    
    # Remove transcript metadata but preserve content
    patterns = [
        (r'Transcriber:.*?\n', 'transcriber info'),
        (r'Reviewer:.*?\n', 'reviewer info'),
        (r'\[(?:Music|Applause)\](?:\s*\n)?', 'sound effects'),
        (r'^\s*\[[\d:]+\]\s*', 'timestamps', re.MULTILINE),  # Remove timestamps at start of lines
    ]
    
    cleaned = text
    for pattern_tuple in patterns:
        pattern = pattern_tuple[0]
        pattern_name = pattern_tuple[1]
        flags = pattern_tuple[2] if len(pattern_tuple) > 2 else 0
        
        before_length = len(cleaned)
        cleaned = re.sub(pattern, '', cleaned, flags=flags)
        after_length = len(cleaned)
        if before_length != after_length:
            logger.debug(f"Removed {pattern_name} metadata: {before_length - after_length} characters")
    
    # Clean up whitespace while preserving paragraph structure
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    cleaned = re.sub(r'^\s+', '', cleaned, flags=re.MULTILINE)  # Remove leading whitespace
    cleaned = re.sub(r'\s+$', '', cleaned, flags=re.MULTILINE)  # Remove trailing whitespace
    cleaned = cleaned.strip()
    
    return cleaned

def clean_metadata_from_text(text: str) -> str:
    """
    Clean metadata using a structured approach with detailed logging.
    """
    logger.debug("Cleaning metadata from text")
    if not text:
        logger.debug("Empty text received")
        return text
    
    # Split into sections
    sections = identify_sections(text)
    logger.debug("Sections identified and split")
    
    # Clean formatted text section specifically
    if sections['formatted_text']:
        logger.debug("Processing formatted text section")
        sections['formatted_text'] = clean_transcript_content(sections['formatted_text'])
    
    # Reconstruct the text with proper formatting
    cleaned_text = []
    
    # Add each section with proper formatting
    cleaned_text.append("1. Summary:")
    cleaned_text.append(sections['summary'])
    cleaned_text.append("\n2. Tags:")
    cleaned_text.append(sections['tags'])
    cleaned_text.append("\n3. Key Points:")
    cleaned_text.append(sections['key_points'])
    cleaned_text.append("\n4. Formatted Transcript:")
    cleaned_text.append(sections['formatted_text'])
    
    final_text = "\n".join(cleaned_text)
    logger.debug(f"Final cleaned text length: {len(final_text)}")
    return final_text.strip()

@rate_limit_decorator()
@backoff.on_exception(
    backoff.expo,
    (Exception,),
    max_tries=MAX_RETRIES,
    giveup=lambda e: isinstance(e, KeyError)
)
def process_transcript(transcript_text, video_title=None, video_id=None, publish_date=None, style="default"):
    logger.info(f"Processing transcript for video {video_id}")
    try:
        if not transcript_text or not transcript_text.strip():
            raise ValueError("Invalid transcript text provided")

        template = get_template(style)
        
        # Create a context string that includes video metadata
        context = ""
        if video_title:
            context += f"Video Title: {video_title}\n"
        if publish_date:
            context += f"Published: {publish_date}\n"
        if video_id:
            context += f"Video ID: {video_id}\n"
        if context:
            context += "\nTranscript:\n"
        
        # Combine context with transcript
        full_text = context + transcript_text
        
        model_name = os.getenv('OPENAI_MODEL', 'gpt-4o-mini-2024-07-18')
        logger.info(f"Using OpenAI model: {model_name}")
        
        response = client.chat.completions.create(
            model=model_name,
            messages=[
               {
                    "role": "system",
                    "content": template["system_prompt"]
                },
                  {"role": "user", "content": transcript_text}
            ]
        )
        
        response_text = response.choices[0].message.content
        processed_response = clean_and_transform_response(response_text)
        
        # Validate the response
        validate_response(transcript_text, processed_response)
        
        # Add metadata to the response after processing
        if video_title:
            processed_response['title'] = video_title
        if video_id:
            processed_response['video_id'] = video_id
        if publish_date:
            processed_response['publishedAt'] = publish_date
        if style:
            processed_response['style'] = style
        
        logger.info(f"Successfully processed transcript for video {video_id}")
        return processed_response
    except Exception as e:
        logger.error(f"Failed to process transcript for video {video_id}: {e}")
        return {
            'video_id': video_id,
            'error': str(e),
            'success': False,
            'error_type': 'processing_error'
        }

def batch_process_transcripts(transcripts, style="default"):
    """Process multiple transcripts in batch."""
    logger.info("Starting batch processing of transcripts")
    results = []
    try:
        # Input validation
        for transcript in transcripts:
            if not isinstance(transcript, dict):
                logger.error(f"Invalid transcript format for {transcript}")
                results.append({
                    'video_id': transcript.get('video_id', 'unknown'),
                    'error': 'Invalid transcript format',
                    'success': False,
                    'error_type': 'validation_error'
                })
                continue
            
            if 'transcript' not in transcript or 'video_id' not in transcript:
                logger.error(f"Missing required fields for video {transcript.get('video_id', 'unknown')}")
                results.append({
                    'video_id': transcript.get('video_id', 'unknown'),
                    'error': 'Missing required fields',
                    'success': False,
                    'error_type': 'validation_error'
                })
                continue

        # Sort transcripts by date (newest first), handling None values and invalid dates
        def get_date(transcript):
            """Get datetime object from transcript publishedAt field."""
            try:
                if not transcript.get('publishedAt'):
                    return datetime.min
                date_str = transcript['publishedAt'].replace('Z', '+00:00')
                return datetime.fromisoformat(date_str)
            except (ValueError, TypeError, AttributeError):
                return datetime.min

        sorted_transcripts = sorted(
            transcripts,
            key=get_date,
            reverse=True
        )

        # Process each transcript with rate limiting and retries
        for transcript in sorted_transcripts:
            try:
                processed = process_transcript(
                    transcript['transcript'],
                    video_title=transcript.get('title'),
                    video_id=transcript['video_id'],
                    publish_date=transcript.get('publishedAt'),
                    style=style
                )
                
                results.append({
                    'video_id': transcript['video_id'],
                    'title': transcript.get('title', 'Unknown Title'),
                    'channel_name': transcript.get('channel_name', 'Unknown Channel'),
                    'publishedAt': transcript.get('publishedAt'),  # Pass raw date
                    'formatted_text': processed.get('formatted_text', ''),
                    'summary': processed.get('summary', ''),
                    'tags': processed.get('tags', []),
                    'key_points': processed.get('key_points', []),
                    'full_transcript': transcript['transcript'],
                    'style': style,
                    'research_implications': processed.get('research_implications', []),
                    'code_snippets': processed.get('code_snippets', []),
                    'technical_concepts': processed.get('technical_concepts', []),
                    'market_insights': processed.get('market_insights', []),
                    'strategic_implications': processed.get('strategic_implications', []),
                    'success': True
                })
            except Exception as e:
                error_info = handle_api_error(e, transcript.get('video_id', 'unknown'))
                logger.error(f"Error processing transcript for video {transcript.get('video_id', 'unknown')}: {error_info}")
                results.append({
                    'video_id': transcript.get('video_id', 'unknown'),
                    'error': str(e),
                    'success': False,
                    'error_type': 'processing_error'
                })
                continue

        logger.info("Batch processing completed")
        return results

    except Exception as e:
        logger.error(f"Error in batch processing: {str(e)}")
        raise

def handle_api_error(error, video_id):
    try:
        # Implement error handling logic here
        error_type = "unknown_error"
        message = str(error)
        
        if isinstance(error, httpx.HTTPStatusError):
            if error.response.status_code == 401:
                error_type = "authentication_error"
                message = "Invalid API key"
            elif error.response.status_code == 403:
                error_type = "permission_error"
                message = "Access forbidden"
            elif error.response.status_code == 404:
                error_type = "not_found_error"
                message = "Resource not found"
            elif error.response.status_code == 429:
                error_type = "rate_limit_error"
                message = "Rate limit exceeded"
            elif error.response.status_code >= 500:
                error_type = "server_error"
                message = "Server error"
        
        logger.error(f"API error for video {video_id}: {message}")
        return {
            'error_type': error_type,
            'message': message,
            'video_id': video_id
        }
    except Exception as e:
        logger.error(f"Failed to handle API error for video {video_id}: {e}")
        return {
            'error_type': 'error_handling_failure',
            'message': str(e),
            'video_id': video_id
        }
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
    # Implement progress update logic here

def format_transcript_output(processed_data):
    """
    Format the processed transcript data into a readable text format.
    """
    output = []
    
    # Add video information
    output.append(f"Title: {processed_data.get('title', 'Unknown Title')}")
    output.append(f"Video ID: {processed_data.get('video_id', 'Unknown ID')}")
    output.append(f"Channel: {processed_data.get('channel_name', 'Unknown Channel')}")
    output.append(f"Published: {format_date(processed_data.get('publishedAt', 'Not available'))}")
    output.append(f"Watch on YouTube: https://www.youtube.com/watch?v={processed_data.get('video_id', '')}\n")
    
    # Add summary section
    output.append("Summary:")
    output.append(processed_data.get('summary', ''))
    output.append("\n")
    
    # Add key points
    output.append("Key Points:")
    for point in processed_data.get('key_points', []):
        output.append(f"- {point}")
    output.append("\n")
    
    # Add tags
    output.append("Tags:")
    for tag in processed_data.get('tags', []):
        output.append(f"- {tag}")
    output.append("\n")
    
    # Add style-specific sections
    if 'research_implications' in processed_data:
        output.append("Research Implications:")
        for implication in processed_data['research_implications']:
            output.append(f"- {implication}")
        output.append("\n")
    
    if 'code_snippets' in processed_data:
        output.append("Code Snippets:")
        for snippet in processed_data['code_snippets']:
            output.append(f"- {snippet}")
        output.append("\n")
    
    if 'technical_concepts' in processed_data:
        output.append("Technical Concepts:")
        for concept in processed_data['technical_concepts']:
            output.append(f"- {concept}")
        output.append("\n")
    
    if 'market_insights' in processed_data:
        output.append("Market Insights:")
        for insight in processed_data['market_insights']:
            output.append(f"- {insight}")
        output.append("\n")
    
    if 'strategic_implications' in processed_data:
        output.append("Strategic Implications:")
        for implication in processed_data['strategic_implications']:
            output.append(f"- {implication}")
        output.append("\n")
    
    # Add full formatted transcript
    output.append("Full Transcript:")
    output.append(processed_data.get('formatted_text', ''))
    
    return "\n".join(output)

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
    # Implement input validation logic here

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
    # Implement caching logic here

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

def format_date(date_str):
    """Format a date string consistently throughout the application."""
    if not date_str or date_str == 'Not available':
        return 'Not available'
    try:
        # Handle ISO format dates with Z or +00:00
        date_str = date_str.replace('Z', '+00:00')
        dt = datetime.fromisoformat(date_str)
        return dt.strftime('%Y-%m-%d %H:%M:%S UTC')
    except (ValueError, TypeError, AttributeError):
        return 'Not available'


